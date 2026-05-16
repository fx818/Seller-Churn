---
name: churn_scoring
version: "2.0"
category: scoring
description: Weighted 14-signal churn score with trajectory-aware bonuses, compound multiplier for 3+ Red flags, and LLM second-opinion adjustment.
python_class: churn_scoring

inputs:
  required:
    - key: glid
      source: snapshot.glid
      type: int
  optional:
    - key: enq_30d
      source: behavioral.bl.received_30d
      type: int
      default: 0
    - key: replied_30d
      source: behavioral.bl.replied_90d
      type: int
      default: 0
    - key: active_days_30d
      source: behavioral.lms.lms_active_days_30d
      type: int
      default: 0
    - key: bl_velocity_pct
      source: derived.bl_velocity_pct
      type: float
    - key: pns_success_pct
      source: derived.pns_success_pct
      type: float
    - key: rag
      source: context.rag_category
      type: str
    - key: cqs
      source: behavioral.activity.cqs
      type: float
    - key: hotleads_count
      source: behavioral.bl.hotleads_count
      type: int
      default: 0
    - key: event_count
      source: behavioral.activity.event_count
      type: int
      default: 0

    # Trajectory (from Phase 0 conversion_point)
    - key: trajectory_type
      source: flow.trajectory_type
      type: str
    - key: trajectory_label
      source: flow.trajectory_label
      type: str
    - key: cliff_drop_pct
      source: flow.cliff_drop_pct
      type: float

outputs:
  - key: churn_score
    type: int
  - key: risk
    type: str
  - key: churn_reasons
    type: list
  - key: reason_tags
    type: list
  - key: score_breakdown
    type: dict
  - key: reply_rate_30d
    type: float
  - key: base_score
    type: float
  - key: compound_multiplier
    type: float
  - key: trajectory_adjustment
    type: int
  - key: pre_llm_score
    type: int
  - key: llm_adjustment
    type: int
  - key: llm_justification
    type: str
  - key: llm_used
    type: bool
  - key: red_flag_count
    type: int
---

# Churn Scoring Skill

## Purpose
Score a seller's churn risk on a 0–100 scale using 14 behavioral signals. Higher score = higher risk.

## How to Run
```bash
python -m churn_analysis skill churn_scoring 11282573
python -m churn_analysis skill churn_scoring 11282573 --pretty
python run_skill.py churn_scoring 11282573
```

## Risk Thresholds
| Band | Score |
|------|-------|
| Red (High Risk) | >= 65 |
| Amber (Medium) | 35 – 64 |
| Green (Healthy) | < 35 |

## Signals (in priority order)
| Signal | Points | Condition |
|--------|--------|-----------|
| RAG Red | 25 | rag == "Red" |
| BL velocity critical | 22 | bl_vel <= -30% MoM |
| Low reply rate | 20 | reply_rate < 40% |
| Zero active days | 18 | active_30d == 0 |
| Zero enquiry flow | 15 | enq_30d == 0 |
| Low CQS critical | 15 | cqs < 60 |
| RAG Amber | 12 | rag == "Amber" |
| Low PNS rate | 12 | pns_pct < 60% |
| Zero platform activity | 12 | event_count == 0 |
| BL velocity declining | 10 | bl_vel <= -10% MoM |
| Low active days | 10 | active_30d <= 3 |
| Low CQS moderate | 7 | cqs < 75 |
| Low platform activity | 6 | event_count < 10 |
| No hotleads | 8 | hotleads_count == 0 |

## Example Output
```json
{
  "churn_score": 72,
  "risk": "Red",
  "reason_tags": ["RAG_RED", "ZERO_ACTIVE_DAYS", "BL_VELOCITY_CRITICAL"],
  "churn_reasons": [
    "RAG category: Red — highest churn risk tier",
    "Zero LMS active days in last 30d",
    "BL velocity drop: -38% MoM (critical)"
  ],
  "score_breakdown": {"rag": 25, "active_days": 18, "bl_velocity": 22},
  "reply_rate_30d": 0.0
}
```
