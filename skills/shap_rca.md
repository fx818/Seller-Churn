---
name: shap_rca
version: "1.0"
category: analysis
description: Map churn reason_tags to a primary RCA category with Hindi+English explanation.
python_class: shap_rca

inputs:
  required:
    - key: glid
      source: snapshot.glid
      type: int
  optional:
    - key: reason_tags
      source: flow.reason_tags
      type: list
    - key: bl_velocity_pct
      source: derived.bl_velocity_pct
      type: float
    - key: cqs
      source: behavioral.activity.cqs
      type: float
    - key: enq_30d
      source: behavioral.bl.received_30d
      type: int

outputs:
  - key: rca_category
    type: str
  - key: rca_explanation_en
    type: str
  - key: rca_explanation_hi
    type: str
  - key: rca_hint
    type: str
---

# SHAP RCA Skill

## Purpose
Maps reason tags from `churn_scoring` to a primary Root Cause Analysis (RCA) category
with bilingual (Hindi + English) explanations for field reps.

## How to Run
```bash
python -m churn_analysis skill shap_rca 11282573 --pretty
```

## RCA Categories (priority order)
| Category | Trigger Tags |
|----------|-------------|
| BL_DECLINE | BL_VELOCITY_CRITICAL |
| NO_LEADS | NO_ENQUIRY_FLOW, BL_VELOCITY_DECLINING |
| LOW_ENGAGEMENT | ZERO_ACTIVE_DAYS, NO_PLATFORM_ACTIVITY, LOW_ACTIVE_DAYS |
| POOR_CATALOG | LOW_CQS_CRITICAL, LOW_CQS_MODERATE |
| LOW_PNS_RESPONSE | LOW_PNS_RATE |
| RAG_RISK | RAG_RED, RAG_AMBER |
| PEER_GAP | PEER_GAP (from flow) |

## Example Output
```json
{
  "rca_category": "BL_DECLINE",
  "rca_explanation_en": "Enquiry volume dropped sharply (-38% MoM). Lead pipeline is drying up.",
  "rca_explanation_hi": "Aapke leads last month se 38% kam ho gaye hain.",
  "rca_hint": "Diagnose why BL volume dropped — geography expansion or category demand discussion."
}
```

## Notes
- Runs best after `churn_scoring` (uses `flow.reason_tags`)
- In pipeline: always runs in phase2_churn after churn_scoring
