---
name: onboarding_health
version: "2.0"
category: scoring
description: 7-check health + city/category risk priors + LLM-personalized activation plan for new sellers.
python_class: onboarding_health

inputs:
  required:
    - key: glid
      source: snapshot.glid
      type: int
  optional:
    - key: account_age_days
      source: context.account_age_days
      type: int
      default: 0
    - key: city
      source: context.city
      type: str
    - key: enterprise
      source: context.custtype
      type: str
    - key: ctype
      source: context.custtype
      type: str
    - key: cqs
      source: behavioral.activity.cqs
      type: float
    - key: enq_30d
      source: behavioral.bl.received_30d
      type: int
      default: 0
    - key: replied_30d
      source: behavioral.bl.replied_90d
      type: int
      default: 0
    - key: paid_history
      source: context.paid_history
      type: bool
    - key: rag
      source: context.rag_category
      type: str
    - key: company
      source: context.company
      type: str
    - key: mcats
      source: context.mcats
      type: list

    # Catalog data (drives Check 7 — catalog completeness)
    - key: im_product_count
      source: flow.im_product_count
      type: int
    - key: approved_products
      source: behavioral.activity.approved_products
      type: int

    # Flow data — outputs from upstream phase0_benchmark skills
    - key: demand_tier
      source: flow.demand_tier
      type: str
    - key: demand_explanation
      source: flow.demand_explanation
      type: str
    - key: demand_index
      source: flow.demand_index
      type: int
    - key: enq_percentile
      source: flow.enq_percentile
      type: float
    - key: peer_median_enq
      source: flow.peer_median_enq
      type: float
    - key: gap_severity
      source: flow.gap_severity
      type: str

outputs:
  - key: health_score
    type: float
  - key: health_tier
    type: str
  - key: checks
    type: dict
  - key: risk_priors
    type: list
  - key: prior_penalty
    type: int
  - key: activation_plan
    type: dict
  - key: plan_method
    type: str
  - key: trigger_action
    type: str
  - key: alerts
    type: list
  - key: recommendations
    type: list
---

# Onboarding Health (v2.0)

7 weighted checks + 2 risk priors + LLM-personalized activation plan.

## Checks

| # | Check | Weight | Source | Tier thresholds |
|---|-------|--------|--------|-----------------|
| 1 | Category Demand     | 25% | `flow.demand_tier` | Green/Amber/Red from demand_index |
| 2 | Business Verification | 10% | `paid_history` + `rag` | Paid+healthy=100, Paid+Red=50, None=0 |
| 3 | Peer Benchmark Gap   | 10% | `flow.enq_percentile` | percentile-based, 60/30 threshold |
| 4 | First BL Response    | 15% | `enq_30d` + `replied_30d` | Replied=100, BLs-no-reply=0 |
| 5 | Package Type         | 10% | `ctype` | CATALOG/FCP/PNS=80, FREELIST=30 |
| 6 | **CQS Gate (NEW)**   | 15% | `behavioral.activity.cqs` | >=70 Green, >=50 Amber, <50 Red |
| 7 | **Catalog Completeness (NEW)** | 15% | `flow.im_product_count` or `approved_products` | vs age-based expectation |

## Risk Priors (flat penalties)

- **High-risk city** (Lucknow, Kanpur, Saharanpur, Surat, Jaipur, Agra, Varanasi, Meerut, Ghaziabad): −15 points
- **High-risk category** (Apparel, Textiles, Garments, Clothing, Fabric): −10 points

## Composite score

```
base_score      = Σ (check.score × check.weight)
health_score    = max(0, min(100, base_score − prior_penalty))
```

- `health_score ≥ 65` → Green → trigger `MONITOR_7D`
- `health_score 35–64` → Amber → trigger `WHATSAPP_SETUP_GUIDE`
- `health_score < 35`  → Red → trigger `HUMAN_CALL_24H`

## Activation Plan (LLM-personalized)

If `LLM_API_KEY` is set, calls the LLM with full seller context to generate:
- **3-5 tasks** (Hindi + English), each with: title, reason, effort_min, priority, rep_action
- `opening_pitch_hi` / `opening_pitch_en` — first 2 sentences for the activation call
- `tone`: urgent / supportive / educational (mapped to health_tier)
- `personalization_signals_used` — which signals the LLM referenced

Falls back to deterministic template if LLM unreachable.

## Expected Products (Check 7 target)

| Account age | Expected products |
|-------------|-------------------|
| ≤ 7 days    | 3 |
| ≤ 30 days   | 8 |
| ≤ 60 days   | 15 |
| > 60 days   | 20 |

## CLI

```bash
python -m churn_analysis skill onboarding_health <NEW_SELLER_GLID> --pretty
```
