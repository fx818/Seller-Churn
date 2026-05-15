"""Phase 3 — Retention Action Engine.

For every Red and Amber seller, runs:
- whatsapp_message       (all Red + Amber)
- pre_call_brief         (Red only)
- script_generation      (all Red + Amber)
- gifted_lead            (all Red + Amber)
- winback_priority       (all sellers, but materialised for Red + Amber here)

Writes per-seller action plan JSON files and a summary file.
"""
import os
import json
import sys
from datetime import datetime, timezone

from ..skills.registry import registry


def run_phase3(
    run_dir: str,
    sellers: list,
    action_tiers: dict,
    phase2_results: dict = None,
    peer_benchmarks: dict = None,
    model=None,
) -> dict:
    """Generate retention action plans for Red and Amber sellers.

    Args:
        run_dir: Path like 'runs/run_20260515_120000/'
        sellers: List of seller dicts
        action_tiers: Output dict from run_phase2 (contains 'tiers' sub-dict)
        phase2_results: Raw skill outputs per GLID from phase2 '_phase2_results'
        peer_benchmarks: Optional pre-computed peer benchmark data keyed by glid
        model: Unused placeholder (kept for orchestrator compatibility)

    Returns:
        Summary dict (also written to disk)
    """
    phase2_results = phase2_results or action_tiers.get("_phase2_results", {})
    peer_benchmarks = peer_benchmarks or {}
    tiers_map = action_tiers.get("tiers", action_tiers)  # tolerate bare tiers dict

    action_dir = os.path.join(run_dir, "action_plans")
    os.makedirs(action_dir, exist_ok=True)

    sellers_by_glid = {str(s.get("glid", "")): s for s in sellers}

    processed = 0
    red_plans = 0
    amber_plans = 0
    errors = []

    for glid, tier_info in tiers_map.items():
        final_tier = tier_info.get("final_tier", "Green")
        if final_tier not in ("Red", "Amber"):
            continue

        seller = sellers_by_glid.get(str(glid), {})
        p2 = phase2_results.get(str(glid), {})
        pb = peer_benchmarks.get(str(glid), {})

        try:
            churn_score = tier_info.get("churn_score") or p2.get("final_score", 50)
            rca_category = tier_info.get("rca_category", p2.get("shap_rca", {}).get("rca_category", "UNKNOWN"))
            company = seller.get("company", tier_info.get("company", ""))
            city = seller.get("city", tier_info.get("city", ""))

            base_inputs = {
                "glid": glid,
                "company": company,
                "seller_name": company.split()[0] if company else "Seller",
                "city": city,
                "ctype": seller.get("ctype", ""),
                "enterprise": seller.get("enterprise", ""),
                "rag": seller.get("rag", ""),
                "churn_score": churn_score,
                "risk": final_tier,
                "final_tier": final_tier,
                "rca_category": rca_category,
                "rca_explanation_en": p2.get("shap_rca", {}).get("rca_explanation_en", ""),
                "enq_30d": seller.get("enq_30d", 0),
                "replied_30d": seller.get("replied_30d", 0),
                "active_days_30d": seller.get("active_days_30d", 0),
                "cqs": seller.get("cqs", 0),
                "paid_history": seller.get("paid_history", False),
                "account_age_days": int(seller.get("account_age_days", seller.get("account_age", 0))),
                "mcats": seller.get("mcats", []),
                "hotleads_count": seller.get("hotleads_count", 0),
                "bl_velocity_pct": seller.get("bl_velocity_pct", 0.0),
                "pns_success_pct": seller.get("pns_success_pct", 0.0),
                **pb,
            }

            # WhatsApp message (all Red + Amber)
            wa_result = registry.run("whatsapp_message", base_inputs)

            # Pre-call brief (Red and Amber)
            pcb_result = None
            if final_tier in ("Red", "Amber"):
                pcb_result = registry.run("pre_call_brief", base_inputs)

            # Script generation
            sg_result = registry.run("script_generation", base_inputs)

            # Gifted lead
            gl_result = registry.run("gifted_lead", base_inputs)

            # Winback priority
            wb_result = registry.run("winback_priority", base_inputs)

            action_plan = {
                "glid": glid,
                "company": company,
                "city": city,
                "final_tier": final_tier,
                "churn_score": churn_score,
                "rca_category": rca_category,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "actions": {
                    "whatsapp_message": wa_result.data if wa_result.success else {"error": wa_result.error},
                    "pre_call_brief": (pcb_result.data if pcb_result and pcb_result.success
                                       else ({"error": pcb_result.error} if pcb_result else None)),
                    "script_generation": sg_result.data if sg_result.success else {"error": sg_result.error},
                    "gifted_lead": gl_result.data if gl_result.success else {"error": gl_result.error},
                    "winback_priority": wb_result.data if wb_result.success else {"error": wb_result.error},
                },
            }

            plan_path = os.path.join(action_dir, f"{glid}_action.json")
            with open(plan_path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(action_plan, ensure_ascii=False, default=str, indent=2))

            processed += 1
            if final_tier == "Red":
                red_plans += 1
            else:
                amber_plans += 1

        except Exception as exc:
            msg = f"[phase3] ERROR for glid={glid}: {exc}"
            print(msg, file=sys.stderr)
            errors.append({"glid": glid, "error": str(exc)})

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_action_plans": processed,
        "red_plans": red_plans,
        "amber_plans": amber_plans,
        "errors": errors,
    }

    summary_path = os.path.join(action_dir, "retention_summary.json")
    with open(summary_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, ensure_ascii=False, default=str, indent=2))

    print(f"[phase3] Written {summary_path}  (plans={processed}, red={red_plans}, amber={amber_plans})")
    return summary


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    _sample_sellers = [
        {
            "glid": "9999001", "company": "Demo Textiles", "city": "Surat",
            "ctype": "FREELIST", "rag": "Red",
            "account_age": 30, "account_age_days": 30,
            "paid_history": False, "mcats": ["Textiles"], "cqs": 20,
            "enq_30d": 0, "replied_30d": 0, "active_days_30d": 0,
            "bl_velocity_pct": 0.0, "pns_success_pct": 0.0,
            "hotleads_count": 0, "event_count": 0, "monthly_enq": 0,
        },
    ]
    _action_tiers = {
        "tiers": {
            "9999001": {
                "glid": "9999001", "company": "Demo Textiles", "city": "Surat",
                "churn_score": 72, "final_tier": "Red",
                "model": "early_life", "rca_category": "NO_LEADS",
                "llm_risk_level": None, "llm_confidence": None,
            }
        }
    }
    _run_dir = os.path.join(os.path.dirname(__file__), "..", "..", "runs", "sample_run")
    out = run_phase3(_run_dir, _sample_sellers, _action_tiers)
    print(json.dumps(out, indent=2, default=str))
