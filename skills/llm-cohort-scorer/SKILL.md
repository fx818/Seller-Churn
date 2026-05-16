---
name: llm-cohort-scorer
description: LLM-based churn risk assessment that compares the seller against 10 churned + 10 retained look-alike sellers from the 292-seller reference cohort, returning a qualitative risk level, confidence score, BL/LMS/Activity bands, narrative reasoning, and the two lookalike GLID lists. Use this skill in Phase 2b of the churn pipeline as a qualitative second opinion alongside the quantitative `churn-scoring`, especially for sellers older than 90 days with a snapshot history.
compatibility: Requires Python 3.11+, seller_survival package
---

# LLM Cohort Scorer Skill

## Instructions

Requires the 292-seller `seller_survival/data/snapshots.parquet` reference library and `LLM_API_KEY` in the environment. The skill:

1. Filters the cohort to sellers similar to the target (same enterprise + mcat band).
2. Picks ~10 known-churned + ~10 known-retained lookalikes.
3. Sends the target's bands + the lookalike comparison to the LLM.
4. Returns `risk_level` (Critical / High / Medium / Low / Very Low), a `pipeline_tier` recommendation, a `confidence_score`, BL/LMS/Activity bands, narrative `reasoning`, and the GLID lists for both lookalike groups.

The BL Card aggregates this and the orchestrator may upgrade the final risk tier based on `llm_risk_level`.

## Examples

```bash
python -m churn_analysis skill llm-cohort-scorer 11282573 --pretty
```

```json
{
  "risk_level": "High",
  "pipeline_tier": "Red",
  "confidence_score": 0.78,
  "bands": {"bl": "R", "lms": "A", "activity": "R"},
  "reasoning": "Bands closely mirror 7 of 10 churned lookalikes...",
  "churned_lookalikes": [12345, 67890, ...],
  "retained_lookalikes": [...]
}
```
