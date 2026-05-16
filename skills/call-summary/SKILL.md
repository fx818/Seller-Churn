---
name: call-summary
description: Parse a rep's post-call transcript via LLM and return a 3-line summary, seller sentiment, updated RCA category, stated concern, and next action recommendation. Use this skill in the post-call flow (NOT in the main churn pipeline) to capture call outcome and inform the next intervention for a seller.
compatibility: Requires Python 3.11+, seller_survival package
metadata:
  version: "1.0"
  category: analysis
  python_class: call-summary
  inputs:
    required:
      - key: glid
        source: snapshot.glid
        type: int
    optional:
      - key: company
        source: context.company
        type: str
      - key: rca_category
        source: flow.rca_category
        type: str
  outputs:
    - key: summary_lines
      type: list
    - key: sentiment
      type: str
    - key: updated_rca
      type: str
    - key: stated_concern
      type: str
    - key: next_action
      type: str
    - key: next_action_detail
      type: str
---

# Call Summary Skill

## Instructions

Run after a sales rep finishes a retention / renewal / welcome / winback call. Accepts the raw transcript plus the pre-call RCA category and returns:

- 3-line structured summary
- Seller sentiment (positive / neutral / negative)
- Updated RCA category (may differ from pre-call RCA if the conversation revealed a different root cause)
- Stated concern (the seller's actual issue in their own words)
- Next action recommendation with detail

This skill is invoked from the Post-Call Summary page in the Streamlit UI — it is intentionally not part of the main `pipeline.md` flow. It expects `LLM_API_KEY` in the environment; without it the skill returns a fallback.

## Examples

```bash
# Standalone (transcript piped in via env var)
python -m churn_analysis skill call-summary 11282573 --pretty
```

```json
{
  "summary_lines": ["Seller asked about renewal pricing", "Reported missed buyer messages", "Agreed to enable PNS"],
  "sentiment": "neutral",
  "updated_rca": "LOW_PNS_RESPONSE",
  "stated_concern": "I'm not getting calls from buyers",
  "next_action": "ENABLE_PNS",
  "next_action_detail": "Walk seller through PNS activation on next follow-up call within 48h"
}
```
