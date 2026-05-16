---
name: score_seller
version: "1.0"
category: scoring
description: Full seller score — snapshot + LLM cohort risk. Wraps seller_survival CLI.
python_class: score_seller

inputs:
  required:
    - key: glid
      source: snapshot.glid
      type: int
  optional:
    - key: model
      source: flow.model
      type: str
    - key: no_llm
      source: flow.no_llm
      type: bool

outputs:
  - key: risk_level
    type: str
  - key: confidence_score
    type: float
  - key: bands
    type: dict
  - key: llm_output
    type: dict
---

# Score Seller

## Purpose
Full seller scoring via the `seller_survival` package. Fetches APIs, extracts snapshot,
and optionally runs LLM cohort scoring (requires snapshots.parquet).

## How to Run
```bash
# Via seller_survival CLI (recommended)
python -m seller_survival score 11282573
python -m seller_survival score 11282573 --no-llm
python -m seller_survival score 11282573 --model gpt-4o-mini
```

## Prerequisites
- Build reference library: `python -m seller_survival build`

## Output
Full JSON card:
```json
{
  "glid": 11282573,
  "snapshot": { "context": {...}, "behavioral": {...} },
  "llm_cohort": {
    "risk_level": "Very High",
    "confidence_score": 0.87,
    "bands": {"bl": "R", "lms": "R", "activity": "A"},
    "llm_output": {"reasoning": "...", "churned_lookalikes": [...]}
  }
}
```
