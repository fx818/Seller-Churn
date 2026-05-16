---
name: demand_index
version: "1.0"
category: analysis
description: Assess buyer demand health in seller's category and city. Detects high-risk combos.
python_class: demand_index

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

## Purpose
Evaluates buyer demand signals in the seller's city and product category.
Identifies high-risk city+category combinations that often lead to low lead flow.

## How to Run
```bash
python -m churn_analysis skill demand_index 11282573 --pretty
```

## High-Risk Cities
lucknow, kanpur, saharanpur, surat, jaipur, agra, meerut, bareilly, moradabad

## High-Risk Categories
apparel, textile, garments, fabric, readymade, saree, kurti, leggings

## Output
```json
{
  "demand_health": "Low",
  "demand_index": 28,
  "city_risk": "high",
  "category_risk": "medium",
  "demand_index_result": {
    "slope": -0.45,
    "verdict": "Declining demand in category"
  }
}
```
