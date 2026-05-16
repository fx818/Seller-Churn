# Risk Synthesis

## Purpose
Combine `decline_severity`, `engagement_verdict`, and `root_cause` into a
final risk tier, numeric churn score (0-100 for ranking), and confidence.
The diagnosis can upgrade OR downgrade the tier — this is what fixes
"everyone looks Critical".

## Inputs
- `decline_severity` from the decline-analysis stage
- `engagement_verdict` from the engagement-health stage
- `root_cause` and `diagnosis_notes` from the root-cause-diagnosis stage
- `derived.tenure_bucket`
- `data_gaps` if any inputs were null

## Tier guidance

| Tier | Pattern |
|---|---|
| **Critical** | decline_severity = sharp AND engagement_verdict in {collapsed, frustrated} AND root_cause is NOT niche_false_positive |
| **High** | decline_severity = moderate AND engagement_verdict != healthy; OR decline_severity = mild + root_cause in {structural_category, catalog_mismatch, catalog_quality_gap, geo_mismatch, newbie_ramp_failure} |
| **Moderate** | decline_severity = mild AND engagement_verdict != collapsed; OR root_cause in {catalog_mismatch, catalog_quality_gap, geo_mismatch, spec_mismatch} with engagement still alive (fixable) |
| **Low** | decline_severity = none; OR root_cause = niche_false_positive; OR engagement_verdict = healthy AND no structural concern |

**Downgrade rules:**
- `root_cause = niche_false_positive` → cap tier at Low regardless of other signals
- `engagement_verdict = healthy` AND `decline_severity in {none, mild}` → cap at Moderate
- Newbie tenure with all-null derived features → cap at Moderate (insufficient data to claim Critical)

**Upgrade rules:**
- `decline_severity = sharp` AND `root_cause = engagement_collapse` → Critical
- `root_cause = newbie_ramp_failure` AND `tenure_bucket = newbie` → at least High

## Churn score (0-100)

Map tier to a numeric range, then nudge inside the range based on inputs:

| Tier | Range | Nudge by |
|---|---|---|
| Critical | 75-100 | sharper decline + collapsed engagement → higher |
| High | 55-75 | structural category present → higher |
| Moderate | 30-55 | fixable diagnosis → middle; unclear → higher |
| Low | 0-30 | niche_false_positive → bottom of range |

The score is ordinal for sorting, NOT a calibrated probability.

## Confidence

| Confidence | When |
|---|---|
| high | All derived features non-null AND decline + engagement + diagnosis agree |
| medium | One or two features null OR signals partially conflict |
| low | More than two features null OR root_cause = unclear OR _partial fetch reported |

## Output style — synthesis-stage fields

The full per-field budget table lives in SKILL.md under "Output style".
When composing the synthesis-stage fields, hold to these limits:

- `risk_drivers[]`: ≤15 words each, fragment style. Lead with the concrete
  number or named field (`"Sharp 88% decline vs baseline"`), not a sentence
  about what the number means.
- `protective_factors[]`: ≤15 words each, fragment style. Same shape as
  drivers — name the signal and its value, not its implication.
- `evidence[]`: 5-8 rows max. `signal` is a 1-4 word field name;
  `value` is the number or string with no narration; `interpretation`
  is ≤12 words and frames where the value sits, not why it matters.
- `data_gaps[]`: ≤12 words each. Name the field and a brief reason it is
  null; do not paragraph about downstream consequences.

A driver line that reads as a full English sentence is too long. If you
catch yourself writing "indicating", "suggesting", or "which implies",
cut from there.

## Output

Emit the final card using the schema defined in SKILL.md. The schema lives
there (not here) because the model needs to know the target shape even if
this reference is never read — having it in SKILL.md is a deliberate
"low-freedom" guardrail for a fragile, consistency-critical output.

## Pitfalls

The most common error from the old engine was bucketing every seller as a
flavor of churn-shape. This stage exists to STOP that. If the diagnosis is
`niche_false_positive` or engagement is healthy, the tier MUST be Low even
when raw activity numbers look concerning. Trust the diagnosis.
