"""Phase 2 — Churn Prediction & Tier Assignment.

Model A  : Early-life sellers (account_age_days <= 90 AND ctype == FREELIST)
Model B  : Established sellers (account_age_days > 90)

Runs churn_scoring + shap_rca for every seller.
For established sellers also runs llm_cohort_scorer when snapshots data exists.
"""
import os
import json
import sys
from datetime import datetime, timezone

from ..skills.registry import registry

# Path to cached loader data (snapshots.parquet presence signals enough history)
_CACHE_ROOT = os.path.join(
    os.path.dirname(__file__), "..", "..", "seller_survival", "data", "loader_cache"
)

TIER_RED_THRESHOLD = 65
TIER_AMBER_THRESHOLD = 35


def _llm_tier_rank(level: str) -> int:
    """Convert LLM risk level string to numeric rank (higher = worse)."""
    mapping = {"very high": 3, "high": 2, "medium": 1, "low": 0}
    return mapping.get(str(level).lower(), -1)


def _score_to_tier(score: float) -> str:
    if score >= TIER_RED_THRESHOLD:
        return "Red"
    if score >= TIER_AMBER_THRESHOLD:
        return "Amber"
    return "Green"


def _tier_rank(tier: str) -> int:
    return {"Red": 2, "Amber": 1, "Green": 0}.get(tier, -1)


def _has_snapshots(glid: str) -> bool:
    snap = os.path.join(_CACHE_ROOT, str(glid), "snapshots.parquet")
    return os.path.isfile(snap)


def run_phase2(run_dir: str, sellers: list, peer_benchmarks: dict = None, model=None) -> dict:
    """Run churn prediction for all sellers and assign Red/Amber/Green tiers.

    Args:
        run_dir: Path like 'runs/run_20260515_120000/'
        sellers: List of seller dicts
        peer_benchmarks: Optional pre-computed peer benchmark data keyed by glid
        model: Unused placeholder (kept for orchestrator compatibility)

    Returns:
        Full tiers dict (also written to disk)
    """
    peer_benchmarks = peer_benchmarks or {}

    out_dir = os.path.join(run_dir, "analysis")
    os.makedirs(out_dir, exist_ok=True)

    red_n = amber_n = green_n = llm_scored_n = 0
    tiers = {}
    phase2_results = {}  # per-GLID raw skill outputs — returned for downstream phases

    for seller in sellers:
        glid = str(seller.get("glid", ""))
        try:
            age = int(seller.get("account_age_days", seller.get("account_age", 0)))
            ctype = str(seller.get("ctype", "")).upper()

            # ----------------------------------------------------------------
            # Core skills (every seller)
            # ----------------------------------------------------------------
            cs_result = registry.run("churn_scoring", {
                "glid": glid,
                "company": seller.get("company", ""),
                "ctype": ctype,
                "rag": seller.get("rag", ""),
                "account_age_days": age,
                "paid_history": seller.get("paid_history", False),
                "enq_30d": seller.get("enq_30d", 0),
                "replied_30d": seller.get("replied_30d", 0),
                "active_days_30d": seller.get("active_days_30d", 0),
                "cqs": seller.get("cqs", 0),
                "bl_velocity_pct": seller.get("bl_velocity_pct", 0.0),
                "pns_success_pct": seller.get("pns_success_pct", 0.0),
                "hotleads_count": seller.get("hotleads_count", 0),
                "event_count": seller.get("event_count", 0),
                "monthly_enq": seller.get("monthly_enq", 0),
                "mcats": seller.get("mcats", []),
            })
            cs_data = cs_result.data if cs_result.success else {}
            churn_score = float(cs_data.get("churn_score", cs_data.get("score", 50)))

            shap_result = registry.run("shap_rca", {
                "glid": glid,
                "reason_tags":     cs_data.get("reason_tags", []),
                "score_breakdown": cs_data.get("score_breakdown", {}),
                "rag":             seller.get("rag", ""),
                "cqs":             seller.get("cqs", 0),
                "bl_velocity_pct": seller.get("bl_velocity_pct", 0.0),
                "pns_success_pct": seller.get("pns_success_pct", 0.0),
            })
            shap_data = shap_result.data if shap_result.success else {}
            rca_category = shap_data.get("rca_category", shap_data.get("top_driver", "UNKNOWN"))

            # ----------------------------------------------------------------
            # Model A — Early-life (FREELIST, <= 90 days)
            # ----------------------------------------------------------------
            used_model = "renewal"
            final_score = churn_score

            if age <= 90 and ctype == "FREELIST":
                used_model = "early_life"
                extra_risk = 0
                if not seller.get("paid_history", False):
                    extra_risk += 30
                if int(seller.get("active_days_30d", 0)) == 0:
                    extra_risk += 20
                if int(seller.get("replied_30d", 0)) == 0 and int(seller.get("enq_30d", 0)) > 0:
                    extra_risk += 18
                if int(seller.get("enq_30d", 0)) == 0:
                    extra_risk += 15
                final_score = min(100.0, extra_risk + churn_score * 0.3)

            # ----------------------------------------------------------------
            # Model B — Established: optionally run LLM cohort scorer
            # ----------------------------------------------------------------
            llm_risk_level = None
            llm_confidence = None
            llm_tier = None

            if age > 90 and _has_snapshots(glid):
                llm_result = registry.run("llm_cohort_scorer", {
                    "glid": glid,
                    "company": seller.get("company", ""),
                    "churn_score": churn_score,
                    "rca_category": rca_category,
                    "account_age_days": age,
                    "enq_30d": seller.get("enq_30d", 0),
                    "active_days_30d": seller.get("active_days_30d", 0),
                    "cqs": seller.get("cqs", 0),
                    "mcats": seller.get("mcats", []),
                    "snapshots_path": os.path.join(_CACHE_ROOT, glid, "snapshots.parquet"),
                })
                if llm_result.success:
                    llm_scored_n += 1
                    llm_risk_level = llm_result.data.get("risk_level")
                    llm_confidence = llm_result.data.get("confidence")
                    llm_tier = llm_result.data.get("tier") or _score_to_tier(
                        {"very high": 80, "high": 65, "medium": 50, "low": 20}.get(
                            str(llm_risk_level).lower(), 50
                        )
                    )

            # ----------------------------------------------------------------
            # Determine final tier (take whichever is worse)
            # ----------------------------------------------------------------
            score_tier = _score_to_tier(final_score)
            if llm_tier and _tier_rank(llm_tier) > _tier_rank(score_tier):
                final_tier = llm_tier
            else:
                final_tier = score_tier

            if final_tier == "Red":
                red_n += 1
            elif final_tier == "Amber":
                amber_n += 1
            else:
                green_n += 1

            tiers[glid] = {
                "glid": glid,
                "company": seller.get("company", ""),
                "city": seller.get("city", ""),
                "churn_score": round(churn_score, 2),
                "final_score": round(final_score, 2),
                "final_tier": final_tier,
                "model": used_model,
                "rca_category": rca_category,
                "llm_risk_level": llm_risk_level,
                "llm_confidence": llm_confidence,
            }

            # Store raw outputs for downstream phases
            phase2_results[glid] = {
                "churn_scoring": cs_data,
                "shap_rca": shap_data,
                "final_score": round(final_score, 2),
                "final_tier": final_tier,
                "rca_category": rca_category,
                "model": used_model,
            }
            if llm_risk_level is not None:
                phase2_results[glid]["llm_cohort_scorer"] = {
                    "risk_level": llm_risk_level,
                    "confidence": llm_confidence,
                    "tier": llm_tier,
                }

        except Exception as exc:
            print(f"[phase2] ERROR for glid={glid}: {exc}", file=sys.stderr)
            tiers[glid] = {
                "glid": glid,
                "company": seller.get("company", ""),
                "city": seller.get("city", ""),
                "churn_score": None,
                "final_score": None,
                "final_tier": "Unknown",
                "model": "error",
                "rca_category": "UNKNOWN",
                "llm_risk_level": None,
                "llm_confidence": None,
                "error": str(exc),
            }
            phase2_results[glid] = {"error": str(exc)}

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_sellers": len(sellers),
        "red": red_n,
        "amber": amber_n,
        "green": green_n,
        "llm_scored": llm_scored_n,
        "tiers": tiers,
        "_phase2_results": phase2_results,  # internal — consumed by phase3/4/5
    }

    out_path = os.path.join(out_dir, "action_tiers.json")
    # Write without internal _phase2_results for cleaner public output
    public = {k: v for k, v in result.items() if k != "_phase2_results"}
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(public, ensure_ascii=False, default=str, indent=2))

    print(f"[phase2] Written {out_path}  (total={len(sellers)}, red={red_n}, amber={amber_n}, green={green_n}, llm={llm_scored_n})")
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
            "enterprise": True, "ctype": "CATALOG", "rag": "Amber",
            "account_age": 200, "account_age_days": 200,
            "paid_history": True, "mcats": ["Industrial Machinery"], "cqs": 55,
            "enq_30d": 3, "replied_30d": 1, "active_days_30d": 5,
            "bl_velocity_pct": 1.0, "pns_success_pct": 40.0,
            "hotleads_count": 0, "event_count": 1, "monthly_enq": 4,
        },
    ]
    _run_dir = os.path.join(os.path.dirname(__file__), "..", "..", "runs", "sample_run")
    out = run_phase2(_run_dir, _sample_sellers)
    print(json.dumps({k: v for k, v in out.items() if k != "_phase2_results"}, indent=2, default=str))
