---
name: whatsapp-message
description: Generate a personalized warmup WhatsApp message in Hindi and English keyed to the seller's RCA category, with CTA and an estimated open rate. Use this skill in Phase 3 of the churn pipeline (Red/Amber sellers) to send before the rep's call so the seller is primed before pickup.
compatibility: Requires Python 3.11+, seller_survival package
metadata:
  version: "1.0"
  category: messaging
  python_class: whatsapp-message
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

## Instructions

Route by `flow.rca_category` to one of ~7 message templates. Personalise each with the seller's first name, city, enq_30d, CQS, and PNS rate. Return:

- `message_hi` — Hindi WhatsApp message
- `message_en` — English equivalent
- `cta` — short call-to-action (e.g. "Reply YES to schedule a 5-min walkthrough")
- `rca_used` — which RCA bucket drove the template choice
- `estimated_open_rate` — heuristic prediction based on RCA and message length

## Examples

```bash
python -m churn_analysis skill whatsapp-message 11282573 --pretty
```

```json
{
  "message_hi": "Ramesh Bhai, last 5 leads pe response nahi gaya. 5 min ki call mein dekh lete hain — kab convenient hai?",
  "message_en": "Ramesh, your last 5 leads went unanswered. Let's debug in a 5-min call — when's good?",
  "cta": "Reply with a convenient time",
  "rca_used": "LOW_ENGAGEMENT",
  "estimated_open_rate": 0.42
}
```
