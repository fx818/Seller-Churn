#!/usr/bin/env python3
"""run_pipeline.py — pipeline entry point for seller-churn-assessment skill.

Usage: python skills/seller-churn-assessment/scripts/run_pipeline.py <glid>

Runs all Python leaf skills via PipelineRunner, enriches result with derived
signals, maps risk vocabulary to Critical/High/Moderate/Low, and prints JSON.
"""
import json
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_SKILLS_DIR = os.path.join(_ROOT, "skills")
_TIER_MAP = {"Red": "Critical", "Amber": "High", "Green": "Low"}


def map_tiers(obj):
    """Recursively map Red/Amber/Green to Critical/High/Low in any dict/list."""
    if isinstance(obj, dict):
        return {
            k: (_TIER_MAP.get(v, v) if k == "risk" and isinstance(v, str) else map_tiers(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [map_tiers(item) for item in obj]
    return obj


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: run_pipeline.py <glid>", "_partial": True}))
        sys.exit(1)

    try:
        glid = int(sys.argv[1])
    except ValueError:
        print(json.dumps({"error": f"Invalid glid: {sys.argv[1]!r}", "_partial": True}))
        sys.exit(1)

    try:
        from churn_analysis.pipeline_runner import PipelineRunner
        from churn_analysis.skill_loader import compute_derived
        from seller_survival.slim_loader import fetch_for_glid
        from seller_survival.feature_schema import extract_snapshot

        api_resp = fetch_for_glid(glid, verbose=False)
        snap = extract_snapshot(glid, "target", api_resp)
        derived = compute_derived(snap)

        runner = PipelineRunner(_SKILLS_DIR)
        result = runner.run_seller(glid, verbose=False)

        result["derived"] = derived
        result = map_tiers(result)

        churn_data = (
            result.get("phases", {})
            .get("phase2_churn", {})
            .get("churn-scoring", {})
            .get("data", {})
        )
        result["final_tier"] = churn_data.get("risk", "Low")

        print(json.dumps(result, ensure_ascii=False, default=str))

    except Exception as exc:
        print(json.dumps({"error": str(exc), "_partial": True, "glid": glid}))
        sys.exit(1)


if __name__ == "__main__":
    main()
