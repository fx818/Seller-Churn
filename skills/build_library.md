---
name: build_library
version: "1.0"
category: library
description: Build the 292-seller reference library (snapshots.parquet) from cohort.csv.
python_class: build_library

inputs:
  required: []
  optional: []

outputs:
  - key: path
    type: str
  - key: retained
    type: int
  - key: churned
    type: int
  - key: total
    type: int
---

# Build Reference Library

## Purpose
Fetches API data for all 292 sellers in cohort.csv and builds `snapshots.parquet`.
This is required before running `llm_cohort_scorer` or `score_seller` with LLM.

## How to Run
```bash
python -m seller_survival build
```

## What It Does
1. Loads `cohort.csv` (292 sellers, labeled retained/churned)
2. Fetches 8 APIs per seller via `slim_loader` (cache-first — safe to re-run)
3. Extracts snapshot features via `feature_schema`
4. Embeds product categories via sentence-transformers
5. Writes `seller_survival/data/snapshots.parquet`

## Output
```
Cohort: 292 sellers
Embedding 47 unique mcats...
Wrote seller_survival/data/snapshots.parquet
  retained=146, churned=146, total=292
Done -> /path/to/snapshots.parquet
```

## Notes
- Safe to re-run — cached API responses are reused (no re-fetching)
- Takes ~20s if all responses are cached, ~5-10 min on first run
- Required by: llm_cohort_scorer, score_seller (with LLM)
