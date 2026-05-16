---
name: demand-index
description: Evaluate the buyer demand health in the seller's city × category combination and flag high-risk combos (e.g. dying mcat, oversaturated city). Use this skill in Phase 0 of the churn pipeline so churn-scoring and winback-priority can distinguish "seller fault" from "market collapsed" — sellers in dying categories should not be retention-spent the same way as sellers in healthy markets.
compatibility: Requires Python 3.11+, seller_survival package
metadata:
  version: "1.0"
  category: analysis
  python_class: demand-index
  inputs:
    required:
      - key: glid
        source: snapshot.glid
        type: int
    optional:
      - key: city
        source: context.city
        type: str
      - key: mcats
        source: context.mcats
        type: list
      - key: weekly_bl_active
        source: behavioral.bl.weekly_bl_active
        type: list
      - key: monthly_enq
        source: derived.monthly_enq
        type: list
  outputs:
    - key: demand_health
      type: str
    - key: demand_index
      type: int
    - key: city_risk
      type: str
    - key: category_risk
      type: str
    - key: demand_index_result
      type: dict
---

# Demand Index Skill

## Instructions

Compute a 0-100 demand index from the seller's market BLs, BL-per-seller saturation, and recent trend. Subtract risk priors when the city or category is on the high-risk list (apparel/textiles/garments in Lucknow/Kanpur/Surat etc.). Return:

- `demand_index` (0-100 numeric score)
- `demand_tier` (HIGH / MED / LOW)
- `city_risk` and `category_risk` labels
- A natural-language `demand_explanation` and `recommended_action` the rep can use

Winback-priority consumes this as one of its 7 sub-scores; if missing it redistributes the weight rather than defaulting to 50.

## Examples

```bash
python -m churn_analysis skill demand-index 11282573 --pretty
```

```json
{
  "demand_index": 72,
  "demand_tier": "HIGH",
  "city_risk": "low",
  "category_risk": "low",
  "demand_index_result": {"market_bl_per_seller": 4.2, "trend": "rising"}
}
```
