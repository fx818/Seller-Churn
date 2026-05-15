"""Phase 1 — Onboarding Health Assessment.

Filters sellers with account_age_days <= 90 and runs onboarding_health,
demand_index, and peer_benchmark skills for each.
"""
import os
import json
import sys
from datetime import datetime, timezone

from ..skills.registry import registry


def run_phase1(run_dir: str, sellers: list, peer_benchmarks: dict = None) -> dict:
    """Run onboarding health assessment for new sellers (<= 90 days).

    Args:
        run_dir: Path like 'runs/run_20260515_120000/'
        sellers: List of seller dicts with standardised keys
        peer_benchmarks: Optional pre-computed peer benchmark data keyed by glid

    Returns:
        Full assessment dict (also written to disk)
    """
    peer_benchmarks = peer_benchmarks or {}

    new_sellers = [s for s in sellers if int(s.get("account_age_days", s.get("account_age", 0))) <= 90]

    out_dir = os.path.join(run_dir, "analysis")
    os.makedirs(out_dir, exist_ok=True)

    red_count = amber_count = green_count = 0
    assessments = {}

    for seller in new_sellers:
        glid = str(seller.get("glid", ""))
        try:
            age = int(seller.get("account_age_days", seller.get("account_age", 0)))

            # --- onboarding_health ---
            oh_result = registry.run("onboarding_health", {
                "glid": glid,
                "company": seller.get("company", ""),
                "account_age_days": age,
                "ctype": seller.get("ctype", ""),
                "enq_30d": seller.get("enq_30d", 0),
                "replied_30d": seller.get("replied_30d", 0),
                "active_days_30d": seller.get("active_days_30d", 0),
                "cqs": seller.get("cqs", 0),
                "paid_history": seller.get("paid_history", False),
                "mcats": seller.get("mcats", []),
                "pns_success_pct": seller.get("pns_success_pct", 0.0),
            })

            # --- demand_index ---
            di_result = registry.run("demand_index", {
                "glid": glid,
                "mcats": seller.get("mcats", []),
                "city": seller.get("city", ""),
                "enq_30d": seller.get("enq_30d", 0),
                "monthly_enq": seller.get("monthly_enq", 0),
            })

            # --- peer_benchmark ---
            pb_inputs = peer_benchmarks.get(glid, {})
            pb_result = registry.run("peer_benchmark", {
                "glid": glid,
                "ctype": seller.get("ctype", ""),
                "mcats": seller.get("mcats", []),
                "city": seller.get("city", ""),
                "enq_30d": seller.get("enq_30d", 0),
                "active_days_30d": seller.get("active_days_30d", 0),
                "cqs": seller.get("cqs", 0),
                **pb_inputs,
            })

            # Extract key fields from skill results
            oh_data = oh_result.data if oh_result.success else {}
            onboarding_risk = oh_data.get("risk_level", "Amber")
            onboarding_score = oh_data.get("score", 50)
            trigger_action = oh_data.get("trigger_action", "MONITOR")
            call_script_hint = oh_data.get("call_script_hint", "")

            check_results = {
                "onboarding_health": oh_data,
                "demand_index": di_result.data if di_result.success else {},
                "peer_benchmark": pb_result.data if pb_result.success else {},
            }

            # Tally risk counts
            risk_upper = str(onboarding_risk).upper()
            if "RED" in risk_upper:
                red_count += 1
            elif "AMBER" in risk_upper or "YELLOW" in risk_upper:
                amber_count += 1
            else:
                green_count += 1

            assessments[glid] = {
                "glid": glid,
                "company": seller.get("company", ""),
                "account_age_days": age,
                "onboarding_risk": onboarding_risk,
                "onboarding_score": onboarding_score,
                "check_results": check_results,
                "trigger_action": trigger_action,
                "call_script_hint": call_script_hint,
            }

        except Exception as exc:
            print(f"[phase1] ERROR for glid={glid}: {exc}", file=sys.stderr)
            assessments[glid] = {
                "glid": glid,
                "company": seller.get("company", ""),
                "account_age_days": int(seller.get("account_age_days", seller.get("account_age", 0))),
                "onboarding_risk": "Unknown",
                "onboarding_score": None,
                "check_results": {},
                "trigger_action": "MANUAL_REVIEW",
                "call_script_hint": "",
                "error": str(exc),
            }

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_new_sellers": len(new_sellers),
        "red_count": red_count,
        "amber_count": amber_count,
        "green_count": green_count,
        "assessments": assessments,
    }

    out_path = os.path.join(out_dir, "onboarding_assessments.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(result, ensure_ascii=False, default=str, indent=2))

    print(f"[phase1] Written {out_path}  (new={len(new_sellers)}, red={red_count}, amber={amber_count}, green={green_count})")
    return result


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    _sample_sellers = [
        {
            "glid": "9999001", "company": "Demo Textiles", "city": "Surat",
            "enterprise": False, "ctype": "FREELIST", "rag": "Red",
            "account_age": 30, "account_age_days": 30,
            "paid_history": False, "mcats": ["Textiles"], "cqs": 20,
            "enq_30d": 0, "replied_30d": 0, "active_days_30d": 0,
            "bl_velocity_pct": 0.0, "pns_success_pct": 0.0,
            "hotleads_count": 0, "event_count": 0, "monthly_enq": 0,
        },
        {
            "glid": "9999002", "company": "Old Machinery Co", "city": "Pune",
            "enterprise": True, "ctype": "CATALOG", "rag": "Green",
            "account_age": 200, "account_age_days": 200,
            "paid_history": True, "mcats": ["Industrial Machinery"], "cqs": 70,
            "enq_30d": 15, "replied_30d": 12, "active_days_30d": 20,
            "bl_velocity_pct": 5.0, "pns_success_pct": 80.0,
            "hotleads_count": 3, "event_count": 5, "monthly_enq": 18,
        },
    ]
    _run_dir = os.path.join(os.path.dirname(__file__), "..", "..", "runs", "sample_run")
    out = run_phase1(_run_dir, _sample_sellers)
    print(json.dumps(out, indent=2, default=str))
