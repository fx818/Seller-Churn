"""Phase 4 — BL Upgrade Flag Engine.

Runs bl_upgrade skill for every seller.
For eligible sellers also runs gifted_lead to pair an upgrade offer with a
complimentary lead.
"""
import os
import json
import sys
from datetime import datetime, timezone

from ..skills.registry import registry


def run_phase4(run_dir: str, sellers: list, phase2_results: dict = None) -> dict:
    """Flag sellers eligible for BL upgrade and generate upgrade messages.

    Args:
        run_dir: Path like 'runs/run_20260515_120000/'
        sellers: List of seller dicts
        phase2_results: Raw skill outputs per GLID from phase2 '_phase2_results'

    Returns:
        BL upgrade flags dict (also written to disk)
    """
    phase2_results = phase2_results or {}

    action_dir = os.path.join(run_dir, "action_plans")
    os.makedirs(action_dir, exist_ok=True)

    flags = {}
    total_eligible = 0
    mode_a_count = 0
    mode_b_count = 0

    for seller in sellers:
        glid = str(seller.get("glid", ""))
        try:
            p2 = phase2_results.get(glid, {})
            churn_score = (
                p2.get("final_score")
                or p2.get("churn_scoring", {}).get("churn_score")
                or p2.get("churn_scoring", {}).get("score")
                or 50
            )
            rca_category = (
                p2.get("shap_rca", {}).get("rca_category")
                or p2.get("rca_category", "UNKNOWN")
            )
            final_tier = p2.get("final_tier", "Green")

            bl_inputs = {
                "glid": glid,
                "company": seller.get("company", ""),
                "city": seller.get("city", ""),
                "ctype": seller.get("ctype", ""),
                "rag": seller.get("rag", ""),
                "account_age_days": int(seller.get("account_age_days", seller.get("account_age", 0))),
                "paid_history": seller.get("paid_history", False),
                "enq_30d": seller.get("enq_30d", 0),
                "replied_30d": seller.get("replied_30d", 0),
                "active_days_30d": seller.get("active_days_30d", 0),
                "cqs": seller.get("cqs", 0),
                "bl_velocity_pct": seller.get("bl_velocity_pct", 0.0),
                "pns_success_pct": seller.get("pns_success_pct", 0.0),
                "hotleads_count": seller.get("hotleads_count", 0),
                "churn_score": churn_score,
                "rca_category": rca_category,
                "final_tier": final_tier,
                "mcats": seller.get("mcats", []),
            }

            bl_result = registry.run("bl_upgrade", bl_inputs)
            bl_data = bl_result.data if bl_result.success else {}

            eligible = bool(bl_data.get("eligible", False))
            mode = bl_data.get("mode", "")

            gifted_lead_data = None
            if eligible:
                total_eligible += 1
                if "A" in str(mode).upper():
                    mode_a_count += 1
                elif "B" in str(mode).upper():
                    mode_b_count += 1

                gl_result = registry.run("gifted_lead", {
                    **bl_inputs,
                    "upgrade_mode": mode,
                })
                gifted_lead_data = gl_result.data if gl_result.success else {"error": gl_result.error}

            flags[glid] = {
                "glid": glid,
                "company": seller.get("company", ""),
                "city": seller.get("city", ""),
                "eligible": eligible,
                "mode": mode,
                "upgrade_message_hi": bl_data.get("upgrade_message_hi", ""),
                "upgrade_message_en": bl_data.get("upgrade_message_en", bl_data.get("message", "")),
                "gifted_lead": gifted_lead_data,
                "bl_skill_data": bl_data,
            }

        except Exception as exc:
            print(f"[phase4] ERROR for glid={glid}: {exc}", file=sys.stderr)
            flags[glid] = {
                "glid": glid,
                "company": seller.get("company", ""),
                "eligible": False,
                "error": str(exc),
            }

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_eligible": total_eligible,
        "mode_a_count": mode_a_count,
        "mode_b_count": mode_b_count,
        "flags": flags,
    }

    out_path = os.path.join(action_dir, "bl_upgrade_flags.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(result, ensure_ascii=False, default=str, indent=2))

    print(f"[phase4] Written {out_path}  (total={len(sellers)}, eligible={total_eligible}, modeA={mode_a_count}, modeB={mode_b_count})")
    return result


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    _sample_sellers = [
        {
            "glid": "9999002", "company": "Old Machinery Co", "city": "Pune",
            "ctype": "CATALOG", "rag": "Amber",
            "account_age": 200, "account_age_days": 200,
            "paid_history": True, "mcats": ["Industrial Machinery"], "cqs": 55,
            "enq_30d": 3, "replied_30d": 1, "active_days_30d": 5,
            "bl_velocity_pct": 1.0, "pns_success_pct": 40.0,
            "hotleads_count": 0, "event_count": 1, "monthly_enq": 4,
        },
    ]
    _run_dir = os.path.join(os.path.dirname(__file__), "..", "..", "runs", "sample_run")
    out = run_phase4(_run_dir, _sample_sellers)
    print(json.dumps(out, indent=2, default=str))
