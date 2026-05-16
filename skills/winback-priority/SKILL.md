---
name: winback-priority
description: Score churned / Red-tier sellers for re-engagement priority using 7 weighted sub-scores (historical quality, demand, RCA-confidence-weighted recoverability, paid history, trajectory factor, peer recovery, recency bonus) with a demand×recoverability interaction multiplier (×1.05 or ×1.10), a hard cool-off tier gate (HIGH only after 90d paid / 180d freelist), an LLM second-opinion of ±10, and a personalised Hindi pitch. Use this skill in Phase 5 of the churn pipeline for Red sellers, to pick the top winback candidates out of the churned pool.
compatibility: Requires Python 3.11+, seller_survival package
---

# Winback Priority Skill (v2.0)

## Instructions

Compute 7 normalised sub-scores (each 0..1) for the seller:

1. **historical_quality** — 60% enq_30d capped at 20 + 40% reply_rate capped at 50%
2. **demand_score** — `current_demand_index / 100`
3. **recoverability** — RCA lookup table (NO_LEADS=90, POOR_CATALOG=75, ...) multiplied by `rca_confidence` clamped [0,1]
4. **paid_history_bonus** — 1.0 if paid history, 0.3 if freelist
5. **trajectory_factor** — TYPE_B 1.0 > TYPE_A 0.7 > TYPE_C 0.2
6. **peer_recovery** — peer_delta_pct >= 0 → 1.0, ≥ -20 → 0.7, ≥ -50 → 0.4, else 0.1
7. **recency_bonus** — 0 before cool-off elapses; then linear decay to 0 over the next 365 days

Weighted base = 0.20·HQ + 0.25·D + 0.20·R + 0.10·PH + 0.10·T + 0.05·PR + 0.10·Rec.

Apply interaction multiplier (D ≥ 0.7 AND R ≥ 0.7 → ×1.10; D ≥ 0.5 AND R ≥ 0.5 → ×1.05; else ×1.0), get `pre_llm_score`. LLM second-opinion (±10) clamped, added, clamped to [0,100].

Tiers — cool-off **hard-gates HIGH**: ≥65 + cool-off elapsed = HIGH; 40-64 or score ≥65 pre-cool-off = MEDIUM; <40 = LOW. If demand_index is missing, its 25% weight is redistributed to recoverability rather than defaulting to 50.

Also emits namespaced aliases (`winback_pre_llm_score`, `winback_sub_scores`, etc.) so the BL Card aggregator can render the derivation without colliding with churn-scoring's same-named keys.

## Examples

```bash
python -m churn_analysis skill winback-priority 29656 --explain
```

```json
{
  "winback_score": 72,
  "priority": "HIGH",
  "pre_llm_score": 67,
  "llm_used": true,
  "llm_adjustment": 5,
  "interaction_bonus": 1.10,
  "sub_scores": {"historical_quality": 0.62, "demand_score": 0.78, "recoverability_score": 0.81, ...},
  "weights": {"historical_quality": 0.20, "demand_score": 0.25, ...},
  "cool_off_elapsed": true,
  "winback_pitch_type": "DEMAND_IMPROVED",
  "opening_line_hi": "Bhai, aap tab gaye the jab leads nahi aa rahi thi. Maine aaj check kiya — aapki category mein abhi 78 active buyers hain.",
  "gifted_lead_eligible": true,
  "estimated_conversion_probability": 0.29,
  "recommended_package": "annual"
}
```
