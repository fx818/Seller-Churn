---
name: gifted-lead
description: Pick the best qualifying Buy Lead to gift to an at-risk seller during a retention call, giving the rep a tangible carrot to demonstrate platform value. Use this skill in Phase 3 of the churn pipeline (Red/Amber sellers only) when a rep needs a closing offer for a fence-sitter.
compatibility: Requires Python 3.11+, seller_survival package
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
