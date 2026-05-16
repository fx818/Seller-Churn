---
name: cross-platform-intelligence
description: Headless-browser scrape of the seller's footprint on JustDial, TradeIndia, their own website (from email domain), and Shopify, then compute the catalog gap vs IndiaMART using product-name matching with Jaccard similarity to deduplicate cross-listed inventory. Use this skill in Phase 3c of the churn pipeline (only for Red/Amber sellers with catalog/lead/engagement RCAs) to surface where the seller is investing instead of IndiaMART.
compatibility: Requires Python 3.11+, seller_survival package
---

# Cross-Platform Intelligence Skill

## Instructions

For each Red or Amber seller whose RCA is `POOR_CATALOG`, `PEER_GAP`, `NO_LEADS`, `LOW_ENGAGEMENT`, or `BL_DECLINE`:

1. Resolve the seller's company name + email domain via the IndiaMART context API.
2. Discover JustDial profile via `__NEXT_DATA__` JSON (fast requests-based phase) and fall back to Playwright if needed.
3. Search TradeIndia for the company; navigate to its profile.
4. If the email domain is non-generic, visit the own-website domain to check for a product catalog.
5. On each platform, count products via JSON-LD → JS DOM heuristics → CSS selectors → text-pattern fallback chain. Also extract product titles for name-matching.
6. Compute the IM catalog gap: if titles are scraped, cluster them across platforms via Jaccard token overlap + substring containment to get the true unique-product count (`unique_via_names`); otherwise fall back to a count-based heuristic (`max_overlap` if counts are within 30% of each other, else `sum_distinct`).
7. Build a `call_card` with bilingual headlines and a suggested action for the rep.

Outputs include per-platform product counts, the catalog gap (severity high/medium/low), competitive positioning (`seller_stronger_elsewhere` / `parity` / `seller_stronger_on_im`), and scrape status. The BL Card aggregator applies a churn-score penalty (+5 to +10) when the seller is meaningfully stronger elsewhere.

## Examples

```bash
python -m churn_analysis skill cross-platform-intelligence 53449 --pretty
```

```json
{
  "platforms_found": ["justdial", "tradeindia"],
  "platform_data": {"justdial": {"product_count": 24, "rating": 4.2, "product_titles": ["LED Bulb 9W", "..."]}},
  "im_catalog_gap": {"im_products": 8, "other_total_products": 22, "gap_pct": -63.6, "severity": "high", "match_method": "names"},
  "competitive_positioning": "seller_stronger_elsewhere",
  "call_card": {"headline_hi": "...", "suggested_action": "Update catalog on IM in 20 mins"}
}
```
