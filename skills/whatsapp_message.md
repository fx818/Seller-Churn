---
name: whatsapp_message
version: "1.0"
category: messaging
description: Generate personalized Hindi+English WhatsApp message by RCA category.
python_class: whatsapp_message

inputs:
  required:
    - key: glid
      source: snapshot.glid
      type: int
  optional:
    - key: company
      source: context.company
      type: str
    - key: city
      source: context.city
      type: str
    - key: enterprise
      source: context.custtype
      type: str
    - key: rca_category
      source: flow.rca_category
      type: str
    - key: enq_30d
      source: behavioral.bl.received_30d
      type: int
    - key: cqs
      source: behavioral.activity.cqs
      type: float
    - key: pns_success_pct
      source: derived.pns_success_pct
      type: float
    - key: bl_velocity_pct
      source: derived.bl_velocity_pct
      type: float

outputs:
  - key: message_hi
    type: str
  - key: message_en
    type: str
  - key: cta
    type: str
  - key: rca_used
    type: str
  - key: estimated_open_rate
    type: float
---

# WhatsApp Message Skill

## Purpose
Generates a personalized WhatsApp message for the seller in Hindi + English,
tailored to the RCA category identified by `shap_rca`.

## How to Run
```bash
python -m churn_analysis skill whatsapp_message 11282573 --pretty
```

## RCA → Message Templates
| RCA | Theme |
|-----|-------|
| NO_LEADS | National geography expansion opportunity |
| LOW_ENGAGEMENT | Notification setup / unanswered leads |
| POOR_CATALOG | CQS improvement = 30% more leads |
| PEER_GAP | Competitor insight — what peers do differently |
| LOW_PNS_RESPONSE | Missed buyer calls — phone setup fix |
| BL_DECLINE | Lead drop — specific reason + fix |
| RAG_RISK | General account review call |

## Example Output
```json
{
  "message_hi": "ABC Bhai, aapki category mein Delhi/Mumbai buyers actively search kar rahe hain. Ek setting change 2 min mein?",
  "message_en": "Hi ABC, buyers from Delhi/Mumbai are actively searching your category. Quick geography fix — 2 min?",
  "cta": "Reply YES for a quick setup call",
  "rca_used": "NO_LEADS",
  "estimated_open_rate": 0.72
}
```

## Notes
- Estimated open rate: 72% for personalized messages vs 45% generic
- Do not include renewal pricing in messages
