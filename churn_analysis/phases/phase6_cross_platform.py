"""
Phase 6 — Cross-Platform Product Intelligence

Runs CrossPlatformIntelligenceSkill for Red/Amber sellers with catalog-related RCA
(POOR_CATALOG, PEER_GAP, NO_LEADS, LOW_ENGAGEMENT). Writes call cards per seller.

Entry point: run_phase6(run_dir, sellers, phase2_results=None, api_map=None) -> dict
"""
import os, sys, json, time
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ..skills.registry import registry

_TARGET_TIERS = ("Red", "Amber")


def _extract_im_product_count(api_responses: dict) -> int:
    pd_resp = api_responses.get("product_details") or {}
    data = pd_resp.get("data") or {}
    if isinstance(data, dict):
        items = data.get("data") or data.get("products") or data.get("items") or []
        if isinstance(items, list) and items:
            return len(items)
        total = data.get("total_count") or data.get("count")
        if total:
            return int(total)
    ps = api_responses.get("product_summary") or {}
    ps_data = ps.get("data") or {}
    if isinstance(ps_data, dict):
        count = ps_data.get("total_products") or ps_data.get("product_count")
        if count:
            return int(count)
    return 0


def run_phase6(
    run_dir: str,
    sellers: list[dict],
    phase2_results: dict | None = None,
    api_map: dict | None = None,
) -> dict:
    """
    Run cross-platform intelligence for eligible Red/Amber sellers.

    phase2_results: dict keyed by str(glid) with 'final_tier', 'rca_category'
    api_map:        dict keyed by str(glid) with raw API responses
    """
    phase2_results = phase2_results or {}
    api_map        = api_map or {}
    os.makedirs(os.path.join(run_dir, "action_plans"), exist_ok=True)

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_scanned": 0,
        "playwright_available": False,
        "platforms_found_count": 0,
        "high_gap_count": 0,
        "results": {},
    }

    # Check playwright once
    try:
        import playwright  # noqa: F401
        output["playwright_available"] = True
    except ImportError:
        output["playwright_available"] = False

    eligible = []
    for s in sellers:
        glid_str = str(s.get("glid", ""))
        p2 = phase2_results.get(glid_str, {})
        tier = p2.get("final_tier") or "Green"
        rca  = p2.get("rca_category") or "UNKNOWN"
        if tier in _TARGET_TIERS:
            eligible.append((s, tier, rca))

    output["total_scanned"] = len(eligible)
    print(f"[phase6] Cross-platform scan: {len(eligible)} eligible sellers "
          f"(playwright={'yes' if output['playwright_available'] else 'no'})")

    for s, tier, rca in eligible:
        glid = s.get("glid")
        glid_str = str(glid)
        api_resp = api_map.get(glid_str, {})
        im_count = _extract_im_product_count(api_resp)

        try:
            r = registry.run("cross_platform_intelligence", {
                "glid":             glid,
                "company":          s.get("company", ""),
                "city":             s.get("city", ""),
                "mcats":            s.get("mcats", []),
                "rca_category":     rca,
                "ctype":            s.get("ctype", ""),
                "im_product_count": im_count,
            })
            result = r.data
            result["_tier"]  = tier
            result["_rca"]   = rca
            result["_company"] = s.get("company", "")

            # Count stats
            if result.get("platforms_found"):
                output["platforms_found_count"] += 1
            gap_sev = (result.get("im_catalog_gap") or {}).get("severity", "")
            if gap_sev == "high":
                output["high_gap_count"] += 1

            output["results"][glid_str] = result

            # Write per-seller call card
            card_path = os.path.join(run_dir, "action_plans", f"{glid}_cross_platform.json")
            with open(card_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)

        except Exception as e:
            print(f"  [phase6] GLID {glid} error: {e}", file=sys.stderr)
            output["results"][glid_str] = {"error": str(e), "skipped": True}

    # Write summary
    out_path = os.path.join(run_dir, "action_plans", "cross_platform_summary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"[phase6] Written {out_path} "
          f"(scanned={output['total_scanned']}, "
          f"found={output['platforms_found_count']}, "
          f"high_gap={output['high_gap_count']})")
    return output


if __name__ == "__main__":
    # Standalone test with mock data
    mock_sellers = [{
        "glid": 488587, "company": "Hind Polybags", "city": "Delhi",
        "enterprise": "SME", "ctype": "CATALOG", "mcats": ["Polybags", "Plastic"],
        "account_age_days": 500,
    }]
    mock_p2 = {"488587": {"final_tier": "Amber", "rca_category": "POOR_CATALOG"}}
    run_dir = "runs/test_phase6"
    os.makedirs(os.path.join(run_dir, "action_plans"), exist_ok=True)
    result = run_phase6(run_dir, mock_sellers, mock_p2)
    print(json.dumps(result, indent=2, default=str))
