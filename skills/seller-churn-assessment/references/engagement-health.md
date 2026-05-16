# Engagement Health

## Purpose
Assess seller-side responsiveness and platform stickiness. Seller-side only
in v1; RM-side reciprocity is out of scope.

## Inputs
- `derived.pns_pickup_ratio` - PNS calls answered / received over 90D
- `derived.bl_reply_rate` - already computed in the decline-analysis stage,
  re-read here
- `derived.cqs_band` - catalog quality band (high / medium / low / very_low)
- `derived.blni_volume` - raw count of BLNI markings in the last year
- BLNI breakdown inside `behavioral.activity.weekly_activity`
  and `monthly_activity` (`blni_loc`, `blni_spec`, `blni_wrng_product`)
- `behavioral.lms.meeting_comments_dated` and
  `behavioral.lms.call_transcripts_text` if present, for
  qualitative call context

## How to read

**pns_pickup_ratio**

| Value | Interpretation |
|---|---|
| >= 0.6 | Responsive to buyer calls |
| 0.3 - 0.6 | Mixed responsiveness |
| < 0.3 with received > 0 | Not picking up buyer calls |
| null | No PNS calls in window - read in conjunction with BL engagement |

**cqs_band**

A "high" or "medium" CQS means the catalog is well-formed; a "low" or
"very_low" CQS reduces the seller's BL matching odds - a leading indicator
of future low BL volume.

**blni_volume + breakdown - read together with BL consumption**

- High BLNI + low BL consumption + visible activity drop -> seller is
  ENGAGED but FRUSTRATED, signalling lead irrelevance. Retention-recoverable.
- Low BLNI + low BL consumption -> seller is CHECKED OUT, not even reading.
  Harder to save.
- Low BLNI + high BL consumption -> engaged and satisfied with leads.

Do NOT treat "high BLNI" as a churn signal. BLNI marking IS engagement.

## How to weigh

Healthy engagement (high PNS pickup + replying to enquiries + non-zero BLNI)
is a strong protective factor - note it explicitly so the synthesis stage
can use it to downgrade ambiguous cases.

Collapsed engagement (low PNS pickup AND low replies AND zero BLNI)
corroborates any decline signal from the decline-analysis stage - escalate.

Qualitative call comments and transcripts can tip a borderline case:
positive, specific next steps are protective; repeated complaints about
lead quality, category fit, or missing assets support the frustrated path.

## Carry-forward

`engagement_verdict`: one of `healthy | mixed | frustrated | collapsed`
`engagement_notes`: 1-2 sentences citing the inputs.

## Pitfalls

"Frustrated" vs "Collapsed" is a critical distinction. Frustrated sellers are
the highest-leverage retention targets - they're still engaging, they're just
not getting value. Collapsed sellers may already be too far gone.
