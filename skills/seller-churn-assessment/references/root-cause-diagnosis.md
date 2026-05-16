# Root Cause Diagnosis

## Purpose
Diagnose WHY the seller is drifting. This is the engine's most important
stage: the diagnosis drives both the risk tier in synthesis and the retention
action in outreach.

## Inputs
- `context.mcats`: list of seller's product categories.
- `context.city`: seller's city.
- `context.nob`: the seller's GST-registered Nature of Business — one of
  `Manufacturer`, `Trader - Retailer`, `Trader - Wholesaler/Distributor`,
  `Service Provider and Others`, or `NA`. Populated for ~100% of sellers.
  Use as a reliable structural corroborator for `spec_mismatch` and
  `structural_category` patterns — it does not depend on whether the RM
  has written a call summary.
- `context.customer_vintage_months` and `derived.tenure_bucket`.
- BLNI reason-code breakdown in `behavioral.bl.blni_breakdown`
  (`location`, `specification`, `wrong_product`, `other`, `total`). If absent,
  fall back to reason-code keys inside weekly/monthly activity.
- Product list in `behavioral.activity.product_catalog`, if present.
- Category-level product summary in
  `behavioral.activity.category_product_summary`, if present.
- Bottom-quality examples in
  `behavioral.activity.bottom_quality_products`, if present.
- `behavioral.lms.last_call_summary`: free-text RM note from the
  most recent successful call with the seller, when present. Often names the
  cause directly (complaints, category fit, RM-flagged issues, competitor
  mentions) and is the highest-signal qualitative input you have.
- `behavioral.lms.last_succ_call_dt`: date of that call, for
  recency context. A summary older than ~4 months may be stale.
- The carry-forwards from the decline-analysis and engagement-health stages
  (`decline_severity`, `engagement_verdict`).

## What To Look For

Apply world knowledge to the seller's category and city. Identify the most
likely root cause from the patterns below. Multiple may apply; surface the
strongest.

### Read the call summary first, when present

If `last_call_summary` is non-empty, read it before applying the numeric
patterns. RMs frequently name the cause in plain language ("seller says
machines are down", "deleted products", "no leads from IndiaMART",
"comparing prices with competitor X"). When the summary maps cleanly onto
one of the patterns below, prefer it as primary evidence and use the BLNI
breakdown / catalog data to corroborate. When it is empty or stale (older
than ~4 months per `last_succ_call_dt`), fall back to the numeric reasoning.
Cite the specific phrase you used in `diagnosis_notes` so the RM can verify.

### Pattern A - Catalog-MCAT Mismatch
- High `blni_breakdown.wrong_product` count relative to other BLNI reasons.
- OR product names do not match the mapped MCATs, for example MCAT says
  "Cotton T-Shirts" but products are "Boys Footwear".
- Diagnosis: irrelevant BLs are flowing because the catalog tells the
  platform the seller is in the wrong category.
- Action target: audit catalog mapping and re-tag mismapped products.

### Pattern B - Catalog Quality Gap
Lead signals (use these to identify the pattern):
- Many listings are missing critical assets — photo, price, description,
  video, or brochure. These are concrete gaps that directly block buyer
  conversion.
- Low PQS (Product Quality Score) on the seller's highest-volume MCATs,
  and/or `cqs_band` of `low` / `very_low` — composite quality signal.
- Buyer-outcome evidence: under-consuming BLs OR weak reply rate despite
  reasonable BL volume — confirms the quality gap is *actually* costing
  the seller leads, not just a number on a dashboard.

Diagnosis: the catalog is relevant (product names map to MCATs), but listing
quality is suppressing BL allocation, buyer trust, or conversion.

Action target: enrich listings — start with the specific missing assets on
the highest-volume products, then improve PQS where it's lowest.

Important caveat on rank distribution:
- A/B/C/D rank counts (e.g. "only 3 A-rank out of 56") are a **weak signal**.
  Rank is an internal scoring artifact, not buyer behavior. Cite rank at most
  *once* as a corroborator for low PQS / missing assets. Never lead drivers
  with rank counts, and never use rank as standalone evidence.
- Do NOT call this a mapping mismatch unless product names and mapped MCATs
  actually disagree (that's Pattern A).

### Pattern C - Geographic Mismatch
- High `blni_breakdown.location` count relative to other BLNI reasons.
- Often combined with a city in a regional/hub market, for example Surat
  textile sellers getting non-Gujarat BLs.
- Diagnosis: BL geo-targeting is failing for this seller.
- Action target: tighten geo-filter in BL allocation.

### Pattern D - Structural Category Fragility
- Seller's MCATs are in commoditized, price-driven, oversupplied B2B
  categories such as apparel, textiles, generic chemicals, or low-end consumer
  goods. Apparel/textiles is the canonical IndiaMART example.
- A `Service Provider and Others` NOB in a product-listing-heavy MCAT is a
  structural-category signal by itself — the platform is built around product
  catalogs, and service sellers struggle to convert via that surface.
- Diagnosis: category itself has structural churn pressure independent of
  this seller's engagement.
- Action target: pitch differentiation, annual lock-in, or premium service tier.

### Pattern E - Spec Mismatch / Niche Overshoot
- High `blni_breakdown.specification` count.
- A `Manufacturer` or `Trader - Wholesaler/Distributor` NOB receiving frequent
  `specification` BLNI rejections is a stronger spec_mismatch signal than the
  BLNI count alone: the seller's *business model* is bulk/B2B but the BL
  allocation is feeding retail-sized or off-spec leads. The mirror case —
  a `Trader - Retailer` NOB receiving bulk B2B enquiries — is also spec_mismatch.
- Diagnosis: seller's product specs do not match the average buyer's specs
  in their category; either product range is too narrow or in the wrong segment.
- Action target: catalog expansion guidance, or BL allocation rules tuned to
  the seller's NOB (e.g., order-value/quantity filters for Manufacturers).

### Pattern F - Niche-Seller False Positive
- Activity is low in absolute terms BUT `recent_vs_baseline_activity` is
  approximately 1.0; the seller has always been low-volume.
- Tenure is mature and engagement is steady.
- Diagnosis: long-tail niche seller renewing despite low activity.
- This DOWNGRADES the risk tier.

### Pattern G - Engagement Collapse
- `decline_severity = sharp` AND `engagement_verdict = collapsed`.
- No structural pattern explains it.
- Diagnosis: seller has checked out: relationship issue, competitor shift, or
  external business problem.
- Action target: RM-led save call; retention discount or service review in scope.

### Pattern H - Newbie Ramp Failure
- `tenure_bucket = newbie` AND low everything across the board.
- No baseline yet, but consumption rate < 0.05 and pickup ratio < 0.3.
- Diagnosis: never ramped, will likely fail their next EMI.
- Action target: onboarding intervention, expectation reset.

## Carry-Forward

`root_cause`: one of `catalog_mismatch | catalog_quality_gap | geo_mismatch | structural_category | spec_mismatch | niche_false_positive | engagement_collapse | newbie_ramp_failure | unclear`

`category_context`: 1 sentence, ≤25 words, on the seller's category + city as you read it. Name the segment (B2B/retail, bulk/niche), not adjectives.

`diagnosis_notes`: 1-2 sentences citing the BLNI breakdown, product catalog,
category summary, or other evidence.

## Pitfalls

A single pattern rarely fits cleanly. Pick the dominant one, but note
secondary contributors in `diagnosis_notes`.

`unclear` is a valid output. If no pattern dominates, say so; the synthesis
stage will weight the risk tier lower in confidence rather than overcommitting.

Do NOT use NACH / payment-status fields as predictive signals. They are the
churn label itself.

The call summary is a single snapshot in time. Cross-check `last_succ_call_dt`
before leaning on it. A six-month-old summary describing a problem the seller
may have already resolved is weaker evidence than a fresh BLNI breakdown.

Do NOT lead `risk_drivers` or `evidence` rows with product-rank counts (for
example "Only 1 A-rank product out of 26", "0 A-rank, 29 B-rank, 27 C-rank").
Rank distribution is an internal scoring artifact, not buyer behavior — it
correlates loosely with outcomes at best. If you cite rank at all, pair it
with a buyer-outcome signal (BL consumption, reply rate, BLNI breakdown,
PNS pickup) that the rank actually predicted; otherwise omit it.
