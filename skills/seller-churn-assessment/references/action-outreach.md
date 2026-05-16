# Action & Outreach

## Purpose
Produce prioritized retention actions and a ready-to-send draft. Actions are
tied to the `root_cause` from the diagnosis stage, not just the `risk_tier`.

## Inputs
The card object built in the synthesis stage.

## Action mapping

| root_cause | Top action |
|---|---|
| catalog_mismatch | Audit seller's catalog: surface products mapped to mismatched MCATs; offer to re-tag |
| catalog_quality_gap | Enrich weak listings: add missing assets, improve PQS, and lift high-volume products toward rank A |
| geo_mismatch | Tighten BL geo-filter for this seller; surface the location-mismatch BLNI count |
| structural_category | Pitch differentiation: feature-package upgrade, annual lock-in, or premium-tier service |
| spec_mismatch | Expand catalog or refine product specs to match buyer demand profile |
| niche_false_positive | No urgent action — light check-in only |
| engagement_collapse | RM-led save call within 7 days; retention discount or service review in scope |
| newbie_ramp_failure | Onboarding intervention: reset expectations, review feature usage, schedule training |
| unclear | RM diagnostic call to identify the specific issue |

## Outreach

For Critical and High only:
- `channel`: usually `call_script` for Critical, `email` acceptable for High
- `subject`: ≤10 words. Reference the specific diagnosis ("Quick check on
  your buy-lead relevance" beats generic "Important account update")
- `body`: **3 sentences max, ≤80 words total.** Reference the seller's
  category + city + one specific evidence point from the card. Sign as
  "Your IndiaMART team". An RM copy-pastes this; longer drafts get edited
  down anyway, so don't pad.

For Moderate and Low: omit `drafted_outreach` from the card entirely.

## Priorities

Populate `recommended_actions` ONLY when `risk_tier` is **Critical or High**.
For these tiers, output 1-3 actions: priority 1 is the top action from the
mapping table above (driven by `root_cause`, not just tier); priorities 2-3
are supporting (e.g., monitor next 30 days, schedule renewal conversation
early).

Each entry has tight budgets:
- `action`: 1 sentence, ≤25 words. Concrete imperative the RM can act on
  ("Audit catalog mapping for the 3 mismapped products"), not a strategy
  brief.
- `rationale`: **one phrase, ≤15 words.** Name the gating factor, do not
  re-explain the diagnosis. "Catalog quality is the gating factor for BL
  volume" — not a paragraph.

For **Moderate and Low** tiers, return `recommended_actions` as an empty
list `[]`. These sellers are healthy enough that RM time is better spent
on Critical/High accounts; an analytical card (drivers, evidence,
category_context, data_gaps) is sufficient on its own. Do NOT fabricate
"monitor next quarter" filler — silence on Low/Moderate is the contract.

## Pitfalls

A human RM sends the outreach — never auto-send. Draft text should fit a
copy-paste workflow.

Do NOT populate `recommended_actions` for Low or Moderate tiers. The empty
list is a deliberate signal that no RM intervention is warranted right now;
the analytical fields (`risk_drivers`, `protective_factors`, `evidence`,
`category_context`) carry the full picture without forcing the RM to read
boilerplate next-step text. This mirrors the `drafted_outreach` gating —
both action artifacts ship only for Critical/High.
