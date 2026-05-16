---
name: conversion-point
description: Detect where in a seller's lead-flow history the trajectory broke and classify it as one of three patterns — TYPE_A Sudden Cliff (peak then ≥60% drop in <=2 months), TYPE_B Gradual Drift (slow steady decline), or TYPE_C Never Engaged (lifetime enq <=5). Use this skill in Phase 0 of the churn pipeline to provide the trajectory signal that churn-scoring, pre-call-brief, and winback-priority all consume.
compatibility: Requires Python 3.11+, seller_survival package
metadata:
  version: "1.0"
  category: analysis
  python_class: conversion-point
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

## Instructions

Read the seller's 12-month monthly enquiry array (`derived.monthly_enq`) and classify the trajectory:

- **TYPE_A — Sudden Cliff**: peak month followed by ≥60% drop in the next 1-2 months. The largest month-over-month drop is reported as `cliff_drop_pct`.
- **TYPE_B — Gradual Drift**: slow steady decline with no single sharp cliff.
- **TYPE_C — Never Engaged**: total lifetime enquiries ≤5; seller never gained traction.

Outputs include `trajectory_type`, a human-readable `trajectory_label`, the `inflection_month` index, and a severity tier. The trajectory drives downstream urgency: TYPE_A → EMERGENCY (24h call), TYPE_B → PROACTIVE (7d), TYPE_C → ONBOARDING_RESET.

## Examples

```bash
python -m churn_analysis skill conversion-point 11282573 --pretty
```

```json
{
  "trajectory_type": "TYPE_A",
  "trajectory_label": "Sudden Cliff",
  "inflection_month": -3,
  "severity": "high",
  "cliff_drop_pct": -68.0
}
```
