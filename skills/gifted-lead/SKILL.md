---
name: gifted-lead
description: Pick the best qualifying Buy Lead to gift to an at-risk seller during a retention call, giving the rep a tangible carrot to demonstrate platform value. Use this skill in Phase 3 of the churn pipeline (Red/Amber sellers only) when a rep needs a closing offer for a fence-sitter.
compatibility: Requires Python 3.11+, seller_survival package
metadata:
  version: "1.0"
  category: action
  python_class: gifted-lead
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

## Instructions

Scan recent hotlead activity for a buy lead that matches the seller's `mcats` and city. Return the single best lead the rep can offer on the call. Eligibility prioritises freshness, mcat overlap, and locality. If no qualifying lead exists, return a fallback message the rep can use instead.

## Examples

```bash
python -m churn_analysis skill gifted-lead 11282573 --pretty
```

```json
{
  "eligible": true,
  "gifted_lead": {"buyer_name": "...", "mcat": "...", "enq_text": "...", "received_at": "..."},
  "gift_reason": "Strong mcat overlap and same city",
  "total_qualifying": 4
}
```
