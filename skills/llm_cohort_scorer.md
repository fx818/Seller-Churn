---
name: llm_cohort_scorer
version: "1.0"
category: scoring
description: LLM-based churn risk using 292-seller cohort comparison. Requires snapshots.parquet.
python_class: llm_cohort_scorer

inputs:
  required:
    - key: glid
      source: snapshot.glid
      type: int
  optional:
    - key: account_age_days
      source: context.account_age_days
      type: int
    - key: api_responses
      source: flow.api_responses
      type: dict
    - key: model
      source: flow.model
      type: str

outputs:
  - key: risk_level
    type: str
  - key: pipeline_tier
    type: str
  - key: confidence_score
    type: float
  - key: bands
    type: dict
  - key: reasoning
    type: str
  - key: churned_lookalikes
    type: list
  - key: retained_lookalikes
    type: list
---

# LLM Cohort Scorer Skill

## Purpose
Uses Claude LLM to assess churn risk by comparing seller against 10 churned + 10 retained
sellers from the 292-seller reference cohort. Returns risk level + reasoning.

## Prerequisites
- `seller_survival/data/snapshots.parquet` must exist — run `python -m seller_survival build` first
- `.env` must have `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`
- Account age must be > 90 days (insufficient history otherwise)

## How to Run
```bash
# Build reference library first
python -m seller_survival build

# Score
python -m churn_analysis skill llm_cohort_scorer 11282573 --pretty
```

## Risk Levels
`Very High` → `High` → `Medium` → `Low`

Maps to pipeline tiers: Very High/High = Red, Medium = Amber, Low = Green

## Output
```json
{
  "risk_level": "Very High",
  "pipeline_tier": "Red",
  "confidence_score": 0.87,
  "bands": {"bl": "R", "lms": "R", "activity": "A"},
  "reasoning": "Seller shows BL velocity drop (-42%) with zero LMS active days...",
  "churned_lookalikes": ["Similar seller had 0 active days and churned at renewal"],
  "retained_lookalikes": ["Retained seller had similar CQS but responded to gifted leads"]
}
```

## Notes
- Skipped automatically if account_age_days <= 90
- Skipped if snapshots.parquet doesn't exist
- Use `--no-llm` flag in pipeline to skip all LLM skills
