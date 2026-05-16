---
name: conversion_point
version: "1.0"
category: analysis
description: Detect seller journey inflection point — sudden cliff, gradual drift, or never engaged.
python_class: conversion_point

inputs:
  required:
    - key: monthly_enq
      source: derived.monthly_enq
      type: list
  optional:
    - key: account_age_days
      source: context.account_age_days
      type: int
    - key: peer_median_enq
      source: flow.peer_median_enq
      type: float
    - key: enq_30d
      source: behavioral.bl.received_30d
      type: int
    - key: active_days_30d
      source: behavioral.lms.lms_active_days_30d
      type: int
    - key: cqs
      source: behavioral.activity.cqs
      type: float
    - key: churn_score
      source: flow.churn_score
      type: int

outputs:
  - key: trajectory_type
    type: str
  - key: trajectory_label
    type: str
  - key: inflection_month
    type: int
  - key: severity
    type: str
---

# Conversion Point Skill

## Purpose
Detects where in a seller's journey the lead flow degraded. Three trajectory types:

- **TYPE_A** — Sudden Cliff: peak then 60%+ drop in <= 2 months
- **TYPE_B** — Gradual Drift: 3+ consecutive declining months
- **TYPE_C** — Never Engaged: never exceeded 10% of peer median from start

## How to Run
```bash
python -m churn_analysis skill conversion_point 11282573 --pretty
```

## Output
```json
{
  "trajectory_type": "TYPE_A",
  "trajectory_label": "Sudden Cliff",
  "inflection_month": 3,
  "severity": "critical"
}
```

## Notes
- Used in pipeline phase3_benchmark alongside peer_benchmark
- Helps field reps understand the pattern before the call
