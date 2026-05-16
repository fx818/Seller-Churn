---
name: bl_upgrade
version: "1.0"
category: action
description: Identify sellers eligible for BL tier upgrade. Two modes — risk-based and engagement-based.
python_class: bl_upgrade

inputs:
  required:
    - key: glid
      source: snapshot.glid
      type: int
  optional:
    - key: churn_score
      source: flow.churn_score
      type: int
    - key: ctype
      source: context.custtype
      type: str
    - key: account_age_days
      source: context.account_age_days
      type: int
    - key: active_days_30d
      source: behavioral.lms.lms_active_days_30d
      type: int
    - key: replied_30d
      source: behavioral.bl.replied_90d
      type: int
    - key: enq_30d
      source: behavioral.bl.received_30d
      type: int
    - key: llm_risk_level
      source: flow.risk_level
      type: str

outputs:
  - key: upgrade_eligible
    type: bool
  - key: upgrade_mode
    type: str
  - key: recommended_tier
    type: str
  - key: upgrade_reason
    type: str
  - key: pitch_angle
    type: str
---

# BL Upgrade Skill

## Purpose
Identifies if a seller is eligible for a Buy Lead tier upgrade.
Two modes:
- **Mode A** (churn_score >= 70) — Retention upgrade: offer upgrade as part of churn prevention
- **Mode B** (churn_score < 35) — Growth upgrade: reward healthy, active sellers

## How to Run
```bash
python -m churn_analysis skill bl_upgrade 11282573 --pretty
```

## Eligibility Criteria
**Mode A (Retention):** churn_score >= 70 AND account_age >= 90 days
**Mode B (Growth):** churn_score < 35 AND active_days >= 15 AND replied_30d >= 5

## Output
```json
{
  "upgrade_eligible": true,
  "upgrade_mode": "RETENTION",
  "recommended_tier": "BL_PLUS",
  "upgrade_reason": "High churn risk — upgrade as retention lever before renewal",
  "pitch_angle": "More leads before renewal window to demonstrate value"
}
```
