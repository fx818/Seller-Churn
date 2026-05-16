---
name: script_generation
version: "2.0"
category: messaging
description: LLM-personalized 5-part Hindi-primary call script using the seller's actual signals (with template fallback).
python_class: script_generation

inputs:
  required:
    - key: glid
      source: snapshot.glid
      type: int
  optional:
    # Identity & context
    - key: seller_name
      source: context.company
      type: str
    - key: company
      source: context.company
      type: str
    - key: city
      source: context.city
      type: str
    - key: enterprise
      source: context.custtype
      type: str
    - key: ctype
      source: context.custtype
      type: str
    - key: account_age_days
      source: context.account_age_days
      type: int

    # Scoring
    - key: churn_score
      source: flow.churn_score
      type: int
    - key: risk
      source: flow.risk
      type: str
    - key: llm_risk_level
      source: flow.llm_risk_level
      type: str
    - key: llm_reasoning
      source: flow.reasoning
      type: str

    # Signals
    - key: churn_reasons
      source: flow.churn_reasons
      type: list
    - key: reply_rate_30d
      source: flow.reply_rate_30d
      type: float
    - key: bl_velocity_pct
      source: derived.bl_velocity_pct
      type: float
    - key: pns_success_pct
      source: derived.pns_success_pct
      type: float
    - key: active_days_30d
      source: behavioral.lms.lms_active_days_30d
      type: int
    - key: cqs
      source: behavioral.activity.cqs
      type: float
    - key: enq_30d
      source: behavioral.bl.received_30d
      type: int

    # RCA
    - key: rca_category
      source: flow.rca_category
      type: str
    - key: rca_explanation_en
      source: flow.rca_explanation_en
      type: str
    - key: rca_explanation_hi
      source: flow.rca_explanation_hi
      type: str
    - key: intervention_hint
      source: flow.intervention_hint
      type: str

    # Peer & demand (from phase0_benchmark)
    - key: peer_median_enq
      source: flow.peer_median_enq
      type: float
    - key: peer_summary_line
      source: flow.peer_summary_line
      type: str
    - key: demand_tier
      source: flow.demand_tier
      type: str
    - key: demand_explanation
      source: flow.demand_explanation
      type: str

    # Trajectory
    - key: trajectory_type
      source: flow.trajectory_type
      type: str
    - key: trajectory_label
      source: flow.trajectory_label
      type: str
    - key: explanation
      source: flow.explanation
      type: str

    # Cross-platform (Playwright)
    - key: platforms_found
      source: flow.platforms_found
      type: list
    - key: platform_data
      source: flow.platform_data
      type: dict
    - key: im_catalog_gap
      source: flow.im_catalog_gap
      type: dict
    - key: call_card
      source: flow.call_card
      type: dict

    # Other
    - key: days_to_renewal
      source: flow.days_to_renewal
      type: int
    - key: language
      source: flow.language
      type: str

outputs:
  - key: script_parts
    type: dict
  - key: script_parts_en
    type: dict
  - key: objection_handlers
    type: dict
  - key: estimated_duration_min
    type: int
  - key: llm_used
    type: bool
  - key: generation_method
    type: str
  - key: personalization_signals_used
    type: list
  - key: rca_used
    type: str
---

# Script Generation Skill (LLM-personalized)

## Purpose
Generates a 5-part Hindi-primary call script that is **personalized to the seller's
specific signals** (churn reasons, peer gap, demand tier, trajectory, cross-platform
catalog gap). The LLM references real numbers — the rep can read it almost verbatim.

## How it works
1. Reads rich seller signals from snapshot + upstream flow state
2. Builds a structured LLM prompt with all relevant data points
3. Calls the chat-completions LLM (`LLM_API_KEY` env var) with a fixed JSON schema
4. Parses the response → 5 parts in Hindi + English + signals_used metadata
5. Falls back to deterministic RCA-template if LLM is unreachable

## Script Parts
| # | Part | Goal |
|---|------|------|
| 1 | `opening`    | Personalized hook in first 10s using one specific seller stat |
| 2 | `diagnostic` | Open question probing the root cause (RCA-aware) |
| 3 | `value_demo` | Concrete data point or peer/cross-platform comparison |
| 4 | `action`     | One specific step the rep + seller do together on the call |
| 5 | `close`      | Low-pressure commitment that respects the seller |

## Environment
```bash
LLM_API_KEY=sk-...                     # required for LLM path
LLM_BASE_URL=https://api.openai.com/v1 # optional override
LLM_MODEL=gpt-4o-mini                  # optional override
```

## CLI
```bash
python -m churn_analysis skill script_generation 53449 --pretty
```

## Output
```json
{
  "script_parts": {
    "opening":    "Gupta Bhai, last 30 din mein 0% reply rate dekha — kuch important miss ho raha hai.",
    "diagnostic": "...",
    "value_demo": "Aapke peer sellers Ludhiana mein avg 8 leads le rahe hain — aapko 0 mil rahi hain.",
    "action":     "Mobile app pe notifications turn on karte hain — 3 minute.",
    "close":      "..."
  },
  "script_parts_en": {...},
  "estimated_duration_min": 7,
  "llm_used": true,
  "generation_method": "llm",
  "personalization_signals_used": ["reply_rate", "peer_gap", "demand_tier"]
}
```

## Fallback
If LLM is missing or fails, returns deterministic RCA-routed templates (the previous
behavior) with `generation_method: "template"` and `confidence: 0.7`.
