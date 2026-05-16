---
name: gifted_lead
version: "1.0"
category: action
description: Select the best qualifying buy lead to gift to an at-risk seller.
python_class: gifted_lead

inputs:
  required:
    - key: glid
      source: snapshot.glid
      type: int
  optional:
    - key: rca_category
      source: flow.rca_category
      type: str
    - key: city
      source: context.city
      type: str
    - key: mcats
      source: context.mcats
      type: list
    - key: enq_30d
      source: behavioral.bl.received_30d
      type: int

outputs:
  - key: gifted_lead
    type: dict
  - key: gift_reason
    type: str
  - key: eligible
    type: bool
---

# Gifted Lead Skill

## Purpose
Identifies the best qualifying Buy Lead from recent hotlead activity to gift to an at-risk seller.
Used as an engagement trigger — giving a seller a real lead creates a commitment moment.

## How to Run
```bash
python -m churn_analysis skill gifted_lead 11282573 --pretty
```

## Selection Criteria
1. Match seller's product categories (mcats)
2. Recent lead (within last 7 days preferred)
3. Buyer from high-value city if seller is local-only

## Output
```json
{
  "eligible": true,
  "gifted_lead": {
    "buyer_name": "Raj Enterprises",
    "lead_date": "2026-05-12",
    "category": "Textile Machinery",
    "buyer_city": "Delhi"
  },
  "gift_reason": "Buyer from Delhi matching seller's primary category"
}
```
