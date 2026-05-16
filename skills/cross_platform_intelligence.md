---
name: cross_platform_intelligence
version: "1.0"
category: analysis
description: Scrape JustDial / TradeIndia / own website via Playwright to compare seller catalog with IndiaMART.
python_class: cross_platform_intelligence

inputs:
  required:
    - key: glid
      source: snapshot.glid
      type: int
    - key: company
      source: context.company
      type: str
    - key: city
      source: context.city
      type: str
  optional:
    - key: mcats
      source: context.mcats
      type: list
    - key: rca_category
      source: flow.rca_category
      type: str
    - key: ctype
      source: context.custtype
      type: str
    - key: im_product_count
      source: behavioral.activity.approved_products
      type: int

outputs:
  - key: platforms_found
    type: list
  - key: platform_data
    type: dict
  - key: im_catalog_gap
    type: dict
  - key: call_card
    type: dict
  - key: competitive_positioning
    type: str
  - key: scrape_status
    type: str
  - key: company_name_used
    type: str
  - key: im_product_count
    type: int
  - key: own_website_domain
    type: str
---

# Cross-Platform Intelligence Skill

## Purpose
Use Playwright + Chromium (with `__NEXT_DATA__` fallback) to detect seller presence
on **JustDial**, **TradeIndia**, and **own website**, then compare their catalog there
vs IndiaMART. The biggest value: if a seller maintains a 24-product JustDial profile
but only 8 on IM, that becomes the strongest retention pitch.

## Triggers
- Risk tier in [Red, Amber]
- RCA in [POOR_CATALOG, PEER_GAP, NO_LEADS, LOW_ENGAGEMENT, BL_DECLINE]

## Scraping Phases
1. **Fast (requests):** JustDial discovery via Google + `__NEXT_DATA__` JSON
2. **Playwright (headless Chromium with anti-bot):**
   - JustDial: product count from profile page (tries `/products`, `/catalogue`)
   - TradeIndia: full search + product count
   - Own website: detected from seller's verified email domain

## Output Sections

### `platforms_found` — list of platforms where seller is listed
e.g. `["justdial", "tradeindia"]`

### `platform_data` — per-platform details
```json
{
  "justdial":     {"found": true, "url": "...", "product_count": 24, "photos_avg": 5.2, "reviews": 12, "rating": 4.2},
  "tradeindia":   {"found": true, "url": "...", "product_count": 18, "photos_avg": 4.1},
  "own_website":  {"found": true, "domain": "...", "product_count": 30}
}
```

### `im_catalog_gap` — comparison
```json
{
  "im_products": 8,
  "other_avg_products": 21,
  "gap_pct": -62,
  "severity": "high"
}
```

### `call_card` — retention pitch
```json
{
  "headline_hi": "Ramesh Bhai, aapka JustDial pe 24 products hain — IM pe sirf 8...",
  "headline_en": "Your JustDial listing has 24 products. IM shows only 8...",
  "data_points": ["..."],
  "suggested_action": "Mirror JustDial catalog on IM — 20 min upload",
  "urgency": "high"
}
```

## CLI
```bash
python -m churn_analysis skill cross_platform_intelligence 53449 --pretty
```

## Fallback
- Playwright not installed → `skipped=true`, `reason="playwright not installed"`
- Anti-bot block → retry with delay; if still fails, skip that platform
- All platforms return no match → `platforms_found=[]`, note "Seller appears IM-exclusive"

## Dependencies
```bash
pip install playwright
playwright install chromium
```
