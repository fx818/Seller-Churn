---
name: onboarding-health
description: Run 7 weighted activation checks on a new seller (≤90 days old) — Category Demand, Business Verification, Peer Gap, First BL Response, Package Type, CQS Gate, Catalog Completeness — combined with 2 risk priors (high-risk city, high-risk category) and an LLM-personalized 4-task activation plan with Hindi+English opening pitches. Use this skill in Phase 1 of the churn pipeline only for sellers whose account_age_days ≤ 90.
compatibility: Requires Python 3.11+, seller_survival package
---

# Onboarding Health Skill (v2.0)

## Instructions

Compute a health score from 7 weighted checks (Category Demand, Business Verification, Peer Gap, First BL Response, Package Type, CQS Gate ≥70 Green / ≥50 Amber, Catalog Completeness vs `_expected_products_for_age` of 3/8/15/20 by day 7/30/60/60+). Subtract 15 points each for the two risk priors (high-risk city ∈ {Lucknow, Kanpur, Saharanpur, Surat, Jaipur, Agra, Varanasi, Meerut, Ghaziabad}, high-risk category ∈ {apparel, textiles, garments, clothing, fabric}).

Tier: ≥75 GREEN, ≥50 AMBER, <50 RED.

If `LLM_API_KEY` is set, generate a personalised 4-task activation plan with Hindi + English opening pitches, tone, and `signals_used`. Falls back to a deterministic template plan when the LLM is unavailable.

Depends on Phase 0 outputs — `demand_tier`, `enq_percentile`, `peer_median_enq`, `gap_severity` are read from `flow.*` so the checks are accurate.

## Examples

```bash
python -m churn_analysis skill onboarding-health 28765 --pretty
```

```json
{
  "health_score": 42,
  "health_tier": "RED",
  "checks": {"category_demand": {...}, "cqs_gate": {...}, "catalog_completeness": {...}, ...},
  "risk_priors": ["high_risk_city:lucknow", "high_risk_category:apparel"],
  "prior_penalty": -30,
  "activation_plan": {"tasks": [...], "opening_pitch_hi": "...", "opening_pitch_en": "..."},
  "plan_method": "llm",
  "trigger_action": "ASSIGN_ACTIVATION_COACH"
}
```
