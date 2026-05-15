"""Phase 3 Track A — Peer Performance Card Generator.

Builds a peer comparison card for every seller using peer_benchmark
and demand_index skill results.
"""
import os
import json
import sys
from datetime import datetime, timezone

from ..skills.registry import registry

# Fix suggestion map keyed by rca_category (up to 3 items per category)
_FIX_SUGGESTIONS = {
    "NO_LEADS": [
        "Add at least 5 products with photos and prices to attract buyers.",
        "Complete your company profile — verified sellers get 3x more leads.",
        "Upgrade to a Catalog subscription to unlock active lead delivery.",
    ],
    "LOW_REPLY": [
        "Reply to enquiries within 1 hour to increase conversion rate.",
        "Enable mobile notifications so you never miss a new enquiry.",
        "Use Quick Reply templates to respond faster.",
    ],
    "LOW_ACTIVITY": [
        "Log in daily to boost listing freshness in search results.",
        "Refresh product listings every week to stay ranked higher.",
        "Add new products to signal active engagement.",
    ],
    "LOW_CQS": [
        "Upload high-resolution product images (min 800x800 px).",
        "Add GST, certifications, and export details to your profile.",
        "Fill in all product attributes — buyers filter by spec.",
    ],
    "BL_STAGNANT": [
        "Request buyers to share positive feedback after each deal.",
        "Respond to all enquiries — unanswered leads hurt your score.",
        "Participate in IndiaMART verification drive to boost credibility.",
    ],
    "UNKNOWN": [
        "Complete your profile to 100% for better search visibility.",
        "Add minimum 10 products to your listing.",
        "Enable WhatsApp notifications for real-time lead alerts.",
    ],
}

_GAP_SEVERITY_THRESHOLDS = {"high": 0.5, "medium": 0.75}  # seller_enq / peer_p75_enq ratios


def _get_fix_items(gap_severity: str, rca_category: str) -> list:
    base = _FIX_SUGGESTIONS.get(rca_category, _FIX_SUGGESTIONS["UNKNOWN"])
    if gap_severity == "high":
        return base[:3]
    return base[:2]


def run_track_a(
    run_dir: str,
    sellers: list,
    phase2_results: dict = None,
    peer_benchmarks: dict = None,
) -> dict:
    """Generate peer comparison cards for all sellers.

    Args:
        run_dir: Path like 'runs/run_20260515_120000/'
        sellers: List of seller dicts
        phase2_results: Raw skill outputs per GLID from phase2 '_phase2_results'
        peer_benchmarks: Optional pre-computed peer benchmark data keyed by glid

    Returns:
        Peer cards dict (also written to disk)
    """
    phase2_results = phase2_results or {}
    peer_benchmarks = peer_benchmarks or {}

    out_dir = os.path.join(run_dir, "analysis")
    os.makedirs(out_dir, exist_ok=True)

    cards = {}

    for seller in sellers:
        glid = str(seller.get("glid", ""))
        try:
            p2 = phase2_results.get(glid, {})
            pb_inputs = peer_benchmarks.get(glid, {})
            rca_category = (
                p2.get("shap_rca", {}).get("rca_category")
                or p2.get("rca_category", "UNKNOWN")
            )
            enq_30d = int(seller.get("enq_30d", 0))

            # --- peer_benchmark ---
            pb_result = registry.run("peer_benchmark", {
                "glid": glid,
                "ctype": seller.get("ctype", ""),
                "mcats": seller.get("mcats", []),
                "city": seller.get("city", ""),
                "enq_30d": enq_30d,
                "active_days_30d": seller.get("active_days_30d", 0),
                "cqs": seller.get("cqs", 0),
                **pb_inputs,
            })
            pb_data = pb_result.data if pb_result.success else {}

            # --- demand_index ---
            di_result = registry.run("demand_index", {
                "glid": glid,
                "mcats": seller.get("mcats", []),
                "city": seller.get("city", ""),
                "enq_30d": enq_30d,
                "monthly_enq": seller.get("monthly_enq", 0),
            })
            di_data = di_result.data if di_result.success else {}

            peer_group = pb_data.get("peer_group", f"{seller.get('ctype','')}_{seller.get('city','')}")
            peer_n = pb_data.get("peer_n", pb_data.get("peer_count", 0))
            peer_median_enq = pb_data.get("peer_median_enq", pb_data.get("median_enq", 0))
            peer_p75_enq = pb_data.get("peer_p75_enq", pb_data.get("p75_enq", peer_median_enq))

            # Gap severity
            if peer_p75_enq and peer_p75_enq > 0:
                ratio = enq_30d / peer_p75_enq
            else:
                ratio = 1.0

            if ratio <= _GAP_SEVERITY_THRESHOLDS["high"]:
                gap_severity = "high"
            elif ratio <= _GAP_SEVERITY_THRESHOLDS["medium"]:
                gap_severity = "medium"
            else:
                gap_severity = "low"

            gap_line = f"You get {enq_30d} leads. Top peers get {peer_p75_enq}."

            fix_items = _get_fix_items(gap_severity, rca_category)

            # Progress delta — requires a previous run snapshot; none available by default
            progress_delta = None
            prev_enq = p2.get("prev_enq_30d")  # populated if phase2 carried history
            if prev_enq is not None:
                progress_delta = enq_30d - int(prev_enq)

            cards[glid] = {
                "glid": glid,
                "company": seller.get("company", ""),
                "city": seller.get("city", ""),
                "peer_group": peer_group,
                "peer_n": peer_n,
                "peer_median_enq": peer_median_enq,
                "peer_p75_enq": peer_p75_enq,
                "seller_enq_30d": enq_30d,
                "gap_severity": gap_severity,
                "gap_line": gap_line,
                "fix_items": fix_items,
                "rca_category": rca_category,
                "demand_index": di_data.get("demand_index", di_data.get("index")),
                "progress_delta": progress_delta,
            }

        except Exception as exc:
            print(f"[track_a] ERROR for glid={glid}: {exc}", file=sys.stderr)
            cards[glid] = {
                "glid": glid,
                "company": seller.get("company", ""),
                "error": str(exc),
            }

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_sellers": len(sellers),
        "cards": cards,
    }

    out_path = os.path.join(out_dir, "peer_cards.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(result, ensure_ascii=False, default=str, indent=2))

    print(f"[track_a] Written {out_path}  (total={len(sellers)})")
    return result


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    _sample_sellers = [
        {
            "glid": "9999001", "company": "Demo Textiles", "city": "Surat",
            "ctype": "FREELIST", "rag": "Red",
            "account_age": 30, "account_age_days": 30,
            "paid_history": False, "mcats": ["Textiles"], "cqs": 20,
            "enq_30d": 1, "replied_30d": 0, "active_days_30d": 2,
            "bl_velocity_pct": 0.0, "pns_success_pct": 0.0,
            "hotleads_count": 0, "event_count": 0, "monthly_enq": 1,
        },
    ]
    _run_dir = os.path.join(os.path.dirname(__file__), "..", "..", "runs", "sample_run")
    out = run_track_a(_run_dir, _sample_sellers)
    print(json.dumps(out, indent=2, default=str))
