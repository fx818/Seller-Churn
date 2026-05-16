# Decline Analysis

## Purpose
Measure whether the seller's recent activity has dropped relative to their own
historical baseline. Time-anchored and baseline-relative, NOT pattern-matched
to churned-seller archetypes.

## Inputs
- `derived.recent_vs_baseline_activity` — ratio of last 2 months enquiry avg
  to prior 6 months avg. 1.0 = stable, < 1 = decline, > 1 = growth, null =
  insufficient history.
- `derived.bl_consumption_rate` — monthly BL consumption / monthly-equivalent
  BL received. Healthy sellers are competitive on the BL queue.
- `derived.bl_reply_rate` — buyer enquiry replies / received. Captures
  follow-through after a lead lands.

## How to read the signal

**recent_vs_baseline_activity**

| Value | Interpretation |
|---|---|
| ≥ 0.9 | Stable or growing — no decline |
| 0.6 – 0.9 | Mild decline (10-40% drop) |
| 0.3 – 0.6 | Moderate decline (40-70% drop) |
| < 0.3 | Sharp decline (>70% drop) |
| null | Insufficient history — note as data gap, do not assume decline |

**bl_consumption_rate**

| Value | Interpretation |
|---|---|
| ≥ 0.3 | Competitive on the BL queue |
| 0.05 – 0.3 | Weak BL engagement |
| < 0.05 | Effectively not grabbing BLs (slow login or checked out) |
| null | No BLs to consume — seller may be in a low-demand niche |

**bl_reply_rate**

| Value | Interpretation |
|---|---|
| ≥ 0.05 | Following through on leads |
| < 0.05 with received > 0 | Receiving but not engaging |

## How to weigh

Decline severity is set by `recent_vs_baseline_activity` if it is non-null.
The two BL ratios corroborate or contradict — if recent_vs_baseline shows
"mild decline" but consumption and reply rates are both strong, the seller
is engaged and the decline may be category-side (down-weight to "none").

## Carry-forward

`decline_severity`: one of `none | mild | moderate | sharp | unknown`
`decline_notes`: 1-2 sentences citing the ratios.

## Pitfalls

Do NOT pattern-match this seller's data to "Flatline" / "Active Cliff" /
"Plateau" archetypes — those archetypes were learned from already-churned
sellers and force every seller into a churn-shaped bucket.

Do NOT call low absolute activity "Critical" without checking the baseline.
A niche B2B seller with 5 enquiries/month who stays at 5 enquiries/month is
NOT in decline — `recent_vs_baseline_activity` ≈ 1.0 protects this case.
