---
name: script-generation
description: Generate a 5-part Hindi-primary call script (opening, diagnostic, value_demo, action, close) personalised to the seller's actual signals via LLM, plus English translation, objection handlers, estimated duration, and the list of signals the LLM used. Falls back to RCA-routed templates when LLM is unavailable. Use this skill in Phase 3 of the churn pipeline (Red/Amber sellers) so reps stop reading the same generic template to every seller in a category.
compatibility: Requires Python 3.11+, seller_survival package
---

# Script Generation Skill (LLM-personalised)

## Instructions

Send the seller's churn signals, RCA, peer gap, demand, trajectory, cross-platform findings, and behavioural metrics to the LLM with a system prompt that asks for a 5-part script:

1. **opening** — greet by company/first name, anchor to top signal
2. **diagnostic** — open-ended question about the underlying cause
3. **value_demo** — show a tangible benefit (peer comparison, demand index, gifted lead)
4. **action** — propose a concrete next step
5. **close** — confirm + schedule

Returns Hindi (`script_parts`) and English (`script_parts_en`) keyed by stage, plus `objection_handlers`, `estimated_duration_min`, `language`, `rca_used`, `llm_used`, `generation_method` (llm / template), and the `personalization_signals_used` list. When LLM fails or `LLM_API_KEY` is missing, falls back to a deterministic RCA-routed template that still produces a usable 5-part script.

## Examples

```bash
python -m churn_analysis skill script-generation 11282573 --pretty
```

```json
{
  "script_parts": {"opening": "...", "diagnostic": "...", "value_demo": "...", "action": "...", "close": "..."},
  "script_parts_en": {...},
  "objection_handlers": {"too_expensive": "...", "not_useful": "..."},
  "estimated_duration_min": 10,
  "llm_used": true,
  "generation_method": "llm",
  "personalization_signals_used": ["reply_rate_0_percent_with_5_BLs", "demand_HIGH", "peer_-45%"]
}
```
