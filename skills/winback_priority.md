---
name: winback_priority
version: "2.0"
category: action
description: Score churned/Red-tier sellers for re-engagement priority with weighted sub-scores, RCA-confidence weighting, paid-history, trajectory, peer-recovery, interaction multiplier, and LLM second-opinion (±10).
python_class: winback_priority

inputs:
  required:
    - key: glid
      source: snapshot.glid
      type: int
  optional:
    # RCA
    - key: rca_category
      source: flow.rca_category
      type: str
    - key: rca_confidence
      source: flow.rca_confidence
      type: float
    - key: churn_score
      source: flow.churn_score
      type: int

    # Account context
    - key: account_age_days
      source: context.account_age_days
      type: int
    - key: city
      source: context.city
      type: str
    - key: ctype
      source: context.custtype
      type: str
    - key: enterprise
      source: context.custtype
      type: str
    - key: paid_history
      source: context.paid_history
      type: bool

    # Recent activity
    - key: enq_30d
      source: behavioral.activity.enq_30d
      type: int
    - key: replied_30d
      source: behavioral.activity.replied_30d
      type: int
    - key: reply_rate_30d
      source: flow.reply_rate_30d
      type: float
    - key: active_days_30d
      source: behavioral.activity.active_days_30d
      type: int

    # Demand / peer / trajectory
    - key: current_demand_index
      source: flow.demand_index
      type: int
    - key: peer_delta_pct
      source: flow.peer_delta_pct
      type: float
    - key: trajectory_type
      source: flow.trajectory_type
      type: str
    - key: cqs
      source: behavioral.cqs
      type: float

    # LLM controls
    - key: force_no_llm
      source: context.force_no_llm
      type: bool

outputs:
  - key: winback_score
    type: int
  - key: priority
    type: str
  - key: pre_llm_score
    type: int
  - key: llm_used
    type: bool
  - key: llm_adjustment
    type: int
  - key: llm_justification
    type: str
  - key: interaction_bonus
    type: float
  - key: sub_scores
    type: dict
  - key: weights
    type: dict
  - key: rca_used
    type: str
  - key: rca_confidence
    type: float
  - key: demand_provided
    type: bool
  - key: cool_off_required_days
    type: int
  - key: cool_off_elapsed
    type: bool
  - key: cool_off_days_remaining
    type: int
  - key: winback_pitch_type
    type: str
  - key: opening_line_hi
    type: str
  - key: pitch
    type: str
  - key: gifted_lead_eligible
    type: bool
  - key: estimated_conversion_probability
    type: float
  - key: recommended_package
    type: str
---

# Winback Priority Skill (v2.0)

## Purpose
Scores at-risk / churned sellers for re-engagement prioritisation and chooses the
right pitch angle. v2.0 replaces the static 4-factor formula with a richer 7-factor
weighted base, interaction multiplier, hard cool-off gate, and LLM second opinion.

## Formula

```
base = 0.20·historical_quality   # enq_30d (60%) + reply_rate (40%)
     + 0.25·demand_score          # current_demand_index / 100
     + 0.20·recoverability        # RCA lookup · rca_confidence
     + 0.10·paid_history_bonus    # 1.0 paid, 0.3 freelist
     + 0.10·trajectory_factor     # TYPE_B 1.0 > TYPE_A 0.7 > TYPE_C 0.2
     + 0.05·peer_recovery         # peer_delta_pct trend
     + 0.10·recency_bonus         # post cool-off decay over 365d
```

If `current_demand_index` is missing, its 0.25 weight is redistributed to
`recoverability` instead of silently defaulting to 50.

**Interaction multiplier** (applied to base):
- demand ≥ 0.7 AND recoverability ≥ 0.7 → ×1.10
- demand ≥ 0.5 AND recoverability ≥ 0.5 → ×1.05
- else → ×1.00

**LLM second opinion (±10):** if `LLM_API_KEY` is set and `force_no_llm` is false,
the LLM reviews the sub-score breakdown and returns `{adjustment, justification}`.
Adjustment is clamped to ±10.

```
pre_llm_score = round(100 · base · interaction_bonus)
winback_score = clamp(pre_llm_score + llm_adjustment, 0, 100)
```

## Recoverability by RCA
| RCA               | Recoverability |
|-------------------|---------------:|
| NO_LEADS          | 90 |
| POOR_CATALOG      | 75 |
| BL_DECLINE        | 60 |
| LOW_ENGAGEMENT    | 55 |
| LOW_PNS_RESPONSE  | 50 |
| PEER_GAP          | 50 |
| RAG_RISK          | 40 |
| UNKNOWN           | 30 |

Multiplied by `rca_confidence` (clamped to [0,1], default 0.6).

## Priority Tiers
Cool-off **hard-gates** HIGH:
- **HIGH**   — `winback_score ≥ 65` AND `cool_off_elapsed`
- **MEDIUM** — `winback_score ≥ 65` but cool-off NOT elapsed (forced down), OR `40 ≤ score < 65`
- **LOW**    — `winback_score < 40`

Cool-off requirement: 180 days for FREELIST, 90 days otherwise.

## How to Run
```bash
python -m churn_analysis skill winback_priority 11282573 --pretty
python -m churn_analysis skill winback_priority 11282573 --explain   # show full derivation
```

## Output (example)
```json
{
  "winback_score": 72,
  "priority": "HIGH",
  "pre_llm_score": 67,
  "llm_used": true,
  "llm_adjustment": 5,
  "llm_justification": "Strong recent reply rate + improving peer position warrants priority.",
  "interaction_bonus": 1.10,
  "sub_scores": {
    "historical_quality": 0.62,
    "demand_score": 0.78,
    "recoverability_score": 0.81,
    "paid_history_bonus": 1.0,
    "trajectory_factor": 1.0,
    "peer_recovery": 0.7,
    "recency_bonus": 0.85
  },
  "weights": { "historical_quality": 0.20, "demand_score": 0.25, ... },
  "cool_off_elapsed": true,
  "winback_pitch_type": "DEMAND_IMPROVED",
  "opening_line_hi": "Bhai, aap tab gaye the jab leads nahi aa rahi thi. Maine aaj check kiya — aapki category mein abhi 78 active buyers hain.",
  "gifted_lead_eligible": true,
  "estimated_conversion_probability": 0.29,
  "recommended_package": "annual"
}
```
