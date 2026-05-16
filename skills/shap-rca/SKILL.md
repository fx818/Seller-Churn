---
name: shap-rca
description: Map churn `reason_tags` from churn-scoring to a single primary Root Cause Analysis category (POOR_CATALOG / NO_LEADS / LOW_ENGAGEMENT / BL_DECLINE / LOW_PNS_RESPONSE / PEER_GAP / RAG_RISK / UNKNOWN), with confidence, a bilingual explanation, and an intervention hint. Use this skill in Phase 2 of the churn pipeline so downstream messaging / scripts / winback / cross-platform skills know the precise angle to pitch.
compatibility: Requires Python 3.11+, seller_survival package
---

# SHAP RCA Skill

## Instructions

Inspect the top contributors in `score_breakdown` from `churn-scoring`. The dominant feature maps to its RCA bucket:

- `reply_rate` / `active_days` → LOW_ENGAGEMENT
- `bl_velocity` → BL_DECLINE
- `pns` → LOW_PNS_RESPONSE
- `cqs` / `activity` → POOR_CATALOG (or LOW_ENGAGEMENT depending on co-signals)
- `enq` → NO_LEADS
- `rag` → RAG_RISK

Confidence is the top-contribution share of the total. Returns Hindi + English explanations and an intervention hint the rep can act on. Falls back to `UNKNOWN` if no signals.

## Examples

```bash
python -m churn_analysis skill shap-rca 11282573 --pretty
```

```json
{
  "rca_category": "LOW_ENGAGEMENT",
  "rca_explanation_en": "Seller has stopped responding to incoming buy leads — the dominant signal is a 0% reply rate.",
  "rca_explanation_hi": "...",
  "rca_hint": "Walk through reply flow; consider PNS activation"
}
```
