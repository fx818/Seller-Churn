---
name: call_summary
version: "1.0"
category: analysis
description: Parse call transcript via LLM and return 3-line summary, updated RCA, next action.
python_class: call_summary

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

## Purpose
Parses a call transcript using the LLM and extracts:
- 3-line structured summary
- Seller sentiment (positive/neutral/negative)
- Updated RCA category (may differ from pre-call RCA)
- Seller's stated main concern
- Recommended next action with timeline

## How to Run
This skill requires a `transcript` input — pass it directly:
```python
from churn_analysis.skills.registry import registry
result = registry.run("call_summary", {
    "glid": 11282573,
    "transcript": "Rep: Hello ABC ji...\nSeller: Haan bhai...",
    "rca_category": "BL_DECLINE",
    "seller_name": "ABC Bhai"
})
```

## Output
```json
{
  "summary_lines": [
    "Seller confirmed lead volume drop in last 2 months",
    "Interested in geography expansion to Delhi/Mumbai",
    "Agreed to try national buyer filter next week"
  ],
  "sentiment": "positive",
  "updated_rca": "NO_LEADS",
  "stated_concern": "Not getting enough local buyers for their product category",
  "next_action": "FOLLOW_UP_48H",
  "next_action_detail": "Send geography expansion guide + schedule follow-up call"
}
```

## Notes
- Requires LLM API (configured in .env)
- Not included in default pipeline — call explicitly after a real call transcript is available
