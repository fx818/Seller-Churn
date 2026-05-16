---
name: pre_call_brief
version: "1.0"
category: messaging
description: Generate a rep-ready 30-second pre-call brief card for at-risk sellers.
python_class: pre_call_brief

inputs:
  required:
    - key: glid
      source: snapshot.glid
      type: int
  optional:
    - key: company
      source: context.company
      type: str
    - key: city
      source: context.city
      type: str
    - key: enterprise
      source: context.custtype
      type: str
    - key: ctype
      source: context.custtype
      type: str
    - key: account_age_days
      source: context.account_age_days
      type: int
    - key: churn_score
      source: flow.churn_score
      type: int
    - key: risk
      source: flow.risk
      type: str
    - key: rca_category
      source: flow.rca_category
      type: str
    - key: rca_explanation_en
      source: flow.rca_explanation_en
      type: str
    - key: enq_30d
      source: behavioral.bl.received_30d
      type: int
    - key: bl_velocity_pct
      source: derived.bl_velocity_pct
      type: float
    - key: pns_success_pct
      source: derived.pns_success_pct
      type: float
    - key: cqs
      source: behavioral.activity.cqs
      type: float
    - key: active_days_30d
      source: behavioral.lms.lms_active_days_30d
      type: int
    - key: hotleads_count
      source: behavioral.bl.hotleads_count
      type: int
    - key: llm_risk_level
      source: flow.risk_level
      type: str
    - key: llm_bands
      source: flow.bands
      type: dict
    - key: llm_reasoning
      source: flow.reasoning
      type: str

outputs:
  - key: brief_text
    type: str
  - key: opening_line_en
    type: str
  - key: opening_line_hi
    type: str
  - key: key_signals
    type: list
  - key: suggested_actions
    type: list
  - key: call_type
    type: str
---

# Pre-Call Brief Skill

## Purpose
Generates a structured pre-call brief for field reps — covering key risk signals,
a personalized opening line (Hindi + English), and suggested talking points.

## How to Run
```bash
python -m churn_analysis skill pre_call_brief 11282573 --pretty
```

## Output Sections
- **Key signals** — severity-ranked signals (churn score, AI risk, BL trend, PNS rate)
- **Opening lines** — RCA-personalized in Hindi + English
- **Suggested actions** — top 3 recommended steps for the call
- **Do not mention** — topics to avoid (e.g. renewal price)
- **Estimated call duration** — 8–12 min

## RCA → Opening Line Mapping
| RCA | Opening |
|-----|---------|
| NO_LEADS / BL_DECLINE | Lead volume drop discussion |
| LOW_ENGAGEMENT | Platform activity check-in |
| POOR_CATALOG | Catalog improvement pitch |

## Example Output (brief_text)
```
SELLER: ABC Textiles | Lucknow | ME/BL Paid | Age: 180d
CHURN SCORE: 72/100 | RISK: Red | AI: Very High
MAIN ISSUE: BL_DECLINE — Leads dropped 38% last month
OPENING: ABC ji, leads dropped 38% last month. There's a specific reason I can explain.
ACTIONS: Diagnose lead volume drop cause; Suggest category adjustment; ⚠ AI-flagged high risk
```
