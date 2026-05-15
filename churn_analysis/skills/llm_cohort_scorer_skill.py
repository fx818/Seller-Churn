"""SKILL 13 — LLMCohortScorerSkill: Wrap seller_survival scoring as a Skill."""
import os, sys
from .base_skill import Skill, SkillResult

_SNAPSHOTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "seller_survival", "data", "snapshots.parquet"
)

_TIER_MAP = {
    "Critical":  "Red",
    "Very High": "Red",
    "High":      "Amber",
    "Moderate":  "Amber",
    "Low":       "Green",
    "Very Low":  "Green",
}


class LLMCohortScorerSkill(Skill):
    name = "llm_cohort_scorer"
    version = "1.0"
    required_inputs = ["glid"]
    optional_inputs = [
        "api_responses", "account_age_days", "model",
        "snapshots_path",
    ]

    def invoke(self, inputs: dict) -> SkillResult:
        glid        = inputs["glid"]
        age         = inputs.get("account_age_days") or 0
        api_resp    = inputs.get("api_responses") or {}
        model       = inputs.get("model") or os.getenv("LLM_MODEL", "gpt-4o-mini")
        snap_path   = inputs.get("snapshots_path") or _SNAPSHOTS_PATH

        # Guard: only for established sellers with built library
        if age <= 90:
            return SkillResult(
                success=True,
                data={"skipped": True, "reason": f"account_age_days={age} ≤ 90 — not enough history"},
                confidence=1.0,
            )

        if not os.path.exists(snap_path):
            return SkillResult(
                success=True,
                data={"skipped": True, "reason": "snapshots.parquet not found — run: python -m seller_survival build"},
                confidence=1.0,
            )

        # Import seller_survival from Hackathon root
        hackathon_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if hackathon_root not in sys.path:
            sys.path.insert(0, hackathon_root)

        from seller_survival.feature_schema import extract_snapshot
        from seller_survival.build_reference_library import load_library
        from seller_survival.cohort_filter import filter_cohort, filter_stats
        from seller_survival.llm_scorer import score as llm_score

        snap    = extract_snapshot(glid, "target", api_resp)
        library = load_library()
        ctx     = snap["context"]

        stats = filter_stats(ctx, library)
        churned_ex, retained_ex, mean_score, tier = filter_cohort(ctx, library, k=5)

        result = llm_score(
            snap,
            churned_ex,
            retained_ex,
            mean_match_score=mean_score,
            n_filtered=stats["n_filtered"],
            model=model,
        )

        pipeline_tier = _TIER_MAP.get(result["risk_level"], "Amber")

        return SkillResult(
            success=True,
            data={
                "skipped":            False,
                "risk_level":         result["risk_level"],
                "pipeline_tier":      pipeline_tier,
                "confidence_score":   result["confidence_score"],
                "bands":              result["bands"],
                "reasoning":          result["llm_output"]["reasoning"],
                "churned_lookalikes": result["llm_output"]["churned_lookalikes"],
                "retained_lookalikes": result["llm_output"]["retained_lookalikes"],
                "cohort_match": {
                    "n_filtered":   stats["n_filtered"],
                    "tier":         tier,
                    "shown_to_llm": len(churned_ex) + len(retained_ex),
                },
                "snapshot_context":   ctx,
            },
            confidence=result["confidence_score"] / 100,
        )

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=False,
            data={"skipped": True, "reason": f"LLM error: {str(error)[:120]}"},
            error=str(error), confidence=0.1, used_fallback=True,
        )
