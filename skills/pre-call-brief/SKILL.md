---
name: pre-call-brief
description: Assemble a 30-second pre-call briefing card for at-risk sellers, containing a Hindi+English opening line, key risk signals (severity-coded), suggested talking points, BL/LMS/Activity bands, and a "do not mention" list. Use this skill in Phase 3 of the churn pipeline (Red/Amber sellers) so reps can stop spending 5 minutes assembling CRM context before each call.
compatibility: Requires Python 3.11+, seller_survival package
---

# Pre-Call Brief Skill

## Instructions

Consume the seller's churn signals, RCA, peer-benchmark gap, LLM cohort reasoning, and the latest behavioural numbers (CQS, reply rate, BL velocity, PNS, active days, hotleads) to produce:

- `opening_line_hi` and `opening_line_en` — the first sentence the rep should say, personalised to the top risk signal
- `key_signals` — list of `{label, value, severity}` for the brief card
- `suggested_actions` — 3-5 talking points
- `brief_text` — single plain-text summary the rep can scan in 30 seconds
- `call_type` — one of RETENTION / RENEWAL / WELCOME / WINBACK

Skipped when risk is Green.

## Examples

```bash
python -m churn_analysis skill pre-call-brief 11282573 --pretty
```

```json
{
  "opening_line_hi": "Bhai, aapke last 5 leads pe response nahi gaya...",
  "opening_line_en": "I noticed you haven't replied to your last 5 leads...",
  "key_signals": [{"label": "Reply Rate", "value": "0%", "severity": "critical"}, ...],
  "suggested_actions": ["Check PNS settings", "Walk through reply flow", "..."],
  "call_type": "RETENTION"
}
```
