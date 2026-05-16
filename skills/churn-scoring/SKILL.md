---
name: churn-scoring
description: Score a seller's churn risk on a 0–100 scale using 14 severity-tiered behavioral signals, a compound multiplier for stacked Red flags, a trajectory adjustment from the conversion-point skill, and a final LLM second-opinion of ±10. Use this skill in Phase 2 of the churn pipeline as the canonical risk score that every downstream phase branches on (`flow.risk` ∈ Red/Amber/Green).
compatibility: Requires Python 3.11+, seller_survival package
---

# Churn Scoring Skill (v2.0)

## Instructions

Evaluate 14 behavioral signals with severity-tiered weights (e.g. reply_rate 0% adds +18; <15% adds +14; <40% adds +8). Sum into a `base_score`, then apply:

1. **Compound multiplier** when 4+ Red flags interact: ×1.08 (4+), ×1.15 (6+), else ×1.0.
2. **Trajectory adjustment** from `flow.trajectory_type`: TYPE_A cliff +3 (or +5 if drop ≤-50%); TYPE_B drift +1; TYPE_C never-engaged 0.
3. **LLM second-opinion** (±10): sends the sub-score breakdown and reasons to the LLM, which returns `{adjustment, justification}` clamped to ±10. Disabled by `force_no_llm` or missing `LLM_API_KEY`.

Final formula: `final = clamp(base × compound + trajectory_adj + llm_adj, 0, 100)`. Tiers: `≥72` Red, `42-71` Amber, `<42` Green.

Outputs include the full derivation (`base_score`, `compound_multiplier`, `trajectory_adjustment`, `pre_llm_score`, `llm_adjustment`, `llm_justification`, `red_flag_count`, per-signal `score_breakdown`) so the BL Card can render a step-by-step explanation for reps.

## Examples

```bash
python -m churn_analysis skill churn-scoring 11282573 --explain
```

```json
{
  "churn_score": 78,
  "risk": "Red",
  "base_score": 47,
  "compound_multiplier": 1.08,
  "trajectory_adjustment": 5,
  "pre_llm_score": 56,
  "llm_used": true,
  "llm_adjustment": 8,
  "llm_justification": "Combination of zero reply + zero active days + no events signals total disengagement.",
  "red_flag_count": 4,
  "reason_tags": ["ZERO_REPLY_RATE", "ZERO_ACTIVE_DAYS", "NO_ENQUIRY_FLOW", "TYPE_A_SUDDEN_CLIFF"]
}
```
