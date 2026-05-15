# action_plan_aggregator.py
# Combines all per-seller phase outputs into a master_action_plan.json.

import json
import os
import glob
from datetime import datetime

# ---------------------------------------------------------------------------
# ARR estimation constants
# ---------------------------------------------------------------------------
_RED_SELLER_AVG_ARR = 15_000        # Rs per year
_SAVEABLE_FRACTION  = 0.60          # 60 % of Red ARR is recoverable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: str, default=None):
    """Load JSON file; return default (dict/list/etc.) if missing or corrupt."""
    if default is None:
        default = {}
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _priority_for_tier(tier: str) -> int:
    return {"Red": 1, "Amber": 2, "Green": 3}.get(tier, 4)


def _action_type_for_tier(tier: str) -> str:
    return {"Red": "HUMAN_CALL", "Amber": "WHATSAPP", "Green": "WHATSAPP"}.get(tier, "MONITOR")


def _urgency_for_tier(tier: str) -> str:
    return {"Red": "SAME_DAY", "Amber": "48H", "Green": "WEEKLY"}.get(tier, "WEEKLY")


# ---------------------------------------------------------------------------
# Main aggregation
# ---------------------------------------------------------------------------

def aggregate(run_dir: str, run_id: str = None) -> dict:
    """
    Aggregate all phase outputs into a master action plan.

    Parameters
    ----------
    run_dir : absolute path to the run directory (e.g. runs/run_20260515_120000)
    run_id  : optional run identifier; inferred from run_dir basename if None

    Returns
    -------
    dict — master_action_plan (also written to {run_dir}/action_plans/master_action_plan.json)
    """
    if run_id is None:
        run_id = os.path.basename(run_dir.rstrip("/\\"))

    generated_at = datetime.utcnow().isoformat() + "Z"

    # ------------------------------------------------------------------ #
    # 1. Load source files                                                 #
    # ------------------------------------------------------------------ #
    analysis_dir      = os.path.join(run_dir, "analysis")
    action_plans_dir  = os.path.join(run_dir, "action_plans")

    action_tiers        = _load_json(os.path.join(analysis_dir, "action_tiers.json"), {})
    onboarding          = _load_json(os.path.join(analysis_dir, "onboarding_assessments.json"), {})
    retention_summary   = _load_json(os.path.join(action_plans_dir, "retention_summary.json"), {})
    bl_upgrade_flags    = _load_json(os.path.join(action_plans_dir, "bl_upgrade_flags.json"), {})
    renewal_boost_flags = _load_json(os.path.join(action_plans_dir, "renewal_boost_flags.json"), {})
    delivery_cascade    = _load_json(os.path.join(action_plans_dir, "delivery_cascade.json"), {})

    # Per-seller action files: {glid}_action.json
    per_seller_actions: dict = {}
    pattern = os.path.join(action_plans_dir, "*_action.json")
    for fp in glob.glob(pattern):
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            glid = str(data.get("glid", os.path.basename(fp).replace("_action.json", "")))
            per_seller_actions[glid] = data
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # 2. Build seller index from action_tiers (primary source of truth)   #
    # ------------------------------------------------------------------ #
    # action_tiers can be:
    #   { "sellers": [ {glid, company, city, tier, churn_score, rca, ...} ] }
    #   or a plain list
    #   or a dict keyed by glid
    sellers_raw: list = []
    if isinstance(action_tiers, dict):
        sellers_raw = action_tiers.get("sellers", []) or action_tiers.get("tiers", [])
        if isinstance(sellers_raw, dict):
            # tiers stored as {glid: {...}} mapping — convert to list of values
            sellers_raw = list(sellers_raw.values())
        if not sellers_raw and action_tiers:
            # Fallback: treat top-level dict values as seller records
            sellers_raw = [v for v in action_tiers.values() if isinstance(v, dict)]
    elif isinstance(action_tiers, list):
        sellers_raw = action_tiers

    # Normalise to list of dicts; ensure glid is a string key
    sellers: dict = {}   # glid -> record
    for rec in sellers_raw:
        if not isinstance(rec, dict):
            continue
        glid = str(rec.get("glid", ""))
        if glid:
            sellers[glid] = rec

    # ------------------------------------------------------------------ #
    # 3. Enrich each seller with cross-phase data                         #
    # ------------------------------------------------------------------ #
    bl_map:      dict = {}
    renewal_map: dict = {}
    gifted_map:  dict = {}
    winback_map: dict = {}

    # bl_upgrade_flags: list or {glid: bool/dict}
    if isinstance(bl_upgrade_flags, list):
        for item in bl_upgrade_flags:
            if isinstance(item, dict):
                bl_map[str(item.get("glid", ""))] = item
    elif isinstance(bl_upgrade_flags, dict):
        for g, v in bl_upgrade_flags.items():
            bl_map[str(g)] = v if isinstance(v, dict) else {"flagged": bool(v)}

    # renewal_boost_flags: list or {glid: bool/dict}
    if isinstance(renewal_boost_flags, list):
        for item in renewal_boost_flags:
            if isinstance(item, dict):
                renewal_map[str(item.get("glid", ""))] = item
    elif isinstance(renewal_boost_flags, dict):
        for g, v in renewal_boost_flags.items():
            renewal_map[str(g)] = v if isinstance(v, dict) else {"flagged": bool(v)}

    # retention_summary may carry gifted_lead and winback fields
    if isinstance(retention_summary, dict):
        for g, v in retention_summary.items():
            if isinstance(v, dict):
                if v.get("gifted_lead_available"):
                    gifted_map[str(g)] = True
                if v.get("winback_eligible"):
                    winback_map[str(g)] = True
        # Also handle flat list form
        for item in retention_summary.get("sellers", []):
            if isinstance(item, dict):
                g = str(item.get("glid", ""))
                if item.get("gifted_lead_available"):
                    gifted_map[g] = True
                if item.get("winback_eligible"):
                    winback_map[g] = True

    # ------------------------------------------------------------------ #
    # 4. Counters                                                          #
    # ------------------------------------------------------------------ #
    count_red   = 0
    count_amber = 0
    count_green = 0
    count_llm_scored      = 0
    count_llm_upgraded    = 0
    count_human_calls     = 0
    count_whatsapp        = 0
    count_bl_upgrades     = 0
    count_gifted          = 0
    count_winback         = 0
    count_new_seller_red  = 0
    rca_breakdown: dict   = {}

    action_queue = []

    for glid, rec in sellers.items():
        tier   = str(rec.get("final_tier") or rec.get("tier") or "Green")
        churn  = int(rec.get("churn_score", 0))
        rca    = str(rec.get("rca_category") or rec.get("rca") or "UNKNOWN")
        company = str(rec.get("company", glid))
        city    = str(rec.get("city", ""))
        llm_risk = str(rec.get("llm_risk_level") or rec.get("llm_risk") or "")
        is_llm_scored   = bool(rec.get("llm_scored") or llm_risk)
        is_llm_upgraded = bool(rec.get("llm_upgraded_to_red"))

        # Tier counts
        if tier == "Red":
            count_red += 1
            count_human_calls += 1
        elif tier == "Amber":
            count_amber += 1
            count_whatsapp += 1
        else:
            count_green += 1
            count_whatsapp += 1

        if is_llm_scored:
            count_llm_scored += 1
        if is_llm_upgraded:
            count_llm_upgraded += 1

        # New-seller Red
        ob = onboarding.get(glid, {})
        if isinstance(ob, dict) and ob.get("is_new_seller") and tier == "Red":
            count_new_seller_red += 1

        # BL upgrades
        if glid in bl_map:
            bl_val = bl_map[glid]
            if isinstance(bl_val, dict) and bl_val.get("flagged", True):
                count_bl_upgrades += 1
            elif isinstance(bl_val, bool) and bl_val:
                count_bl_upgrades += 1

        # Gifted / winback
        if glid in gifted_map:
            count_gifted += 1
        if glid in winback_map:
            count_winback += 1

        # RCA breakdown
        rca_breakdown[rca] = rca_breakdown.get(rca, 0) + 1

        # Action queue entry
        action_queue.append({
            "priority": _priority_for_tier(tier),
            "glid": glid,
            "company": company,
            "city": city,
            "churn_score": churn,
            "final_tier": tier,
            "llm_risk_level": llm_risk,
            "rca": rca,
            "action_type": _action_type_for_tier(tier),
            "urgency": _urgency_for_tier(tier),
            "gifted_lead_available": glid in gifted_map,
            "winback_eligible": glid in winback_map,
            "bl_upgrade_flagged": glid in bl_map,
        })

    # Sort action queue: Red first, then by churn_score desc
    action_queue.sort(key=lambda x: (x["priority"], -x["churn_score"]))

    # ------------------------------------------------------------------ #
    # 5. ARR estimation                                                    #
    # ------------------------------------------------------------------ #
    total_sellers      = len(sellers)
    arr_at_risk        = count_red * _RED_SELLER_AVG_ARR
    arr_saveable       = int(arr_at_risk * _SAVEABLE_FRACTION)
    coverage_pct       = round(count_llm_scored / total_sellers, 4) if total_sellers else 0.0

    # ------------------------------------------------------------------ #
    # 6. Assemble master plan                                              #
    # ------------------------------------------------------------------ #
    master_plan = {
        "run_id": run_id,
        "generated_at": generated_at,
        "summary": {
            "total_sellers": total_sellers,
            "red": count_red,
            "amber": count_amber,
            "green": count_green,
            "llm_scored": count_llm_scored,
            "llm_upgraded_to_red": count_llm_upgraded,
            "human_calls_queued": count_human_calls,
            "whatsapp_queued": count_whatsapp,
            "gifted_leads_allocated": count_gifted,
            "winback_eligible": count_winback,
            "bl_upgrades_flagged": count_bl_upgrades,
            "new_seller_red": count_new_seller_red,
            "estimated_arr_at_risk": arr_at_risk,
            "estimated_arr_saveable": arr_saveable,
            "coverage_pct": coverage_pct,
        },
        "action_queue": action_queue,
        "rca_breakdown": rca_breakdown,
    }

    # ------------------------------------------------------------------ #
    # 7. Write output                                                      #
    # ------------------------------------------------------------------ #
    os.makedirs(action_plans_dir, exist_ok=True)
    out_path = os.path.join(action_plans_dir, "master_action_plan.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(master_plan, fh, ensure_ascii=False, default=str, indent=2)

    return master_plan
