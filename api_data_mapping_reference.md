# API Data Mapping Reference

Maps each endpoint to the specific data fields it returns. Use this to understand data sources and avoid redundant calls.

**Last Updated:** 2026-05-14

---

## Overview

| Layer | Source | Auth | Purpose |
|-------|--------|------|---------|
| **DWH** | imdwh.intermesh.net | None | Historical warehouse data (90d+ summaries) |
| **MERP** | merp.intermesh.net | JWT | Real-time seller activity & call records |
| **Context** | merp.intermesh.net | JWT | Full enriched seller profile |
| **Ingestion** | ingestion-service-*.run.app | API Key | Processed/normalized data views |

---

## 1. DWH POST Endpoints (imdwh.intermesh.net)

### `scorecard_summary`
**Endpoint:** `POST /api/go/cust_wh_summary_api`  
**Auth:** None  
**Returns:** Single record per GLID

#### Data Fields (from example GLID 488587):
```json
{
  "glid": 488587,
  "gl_state_code": "DL",                    // Seller state
  "gl_city_name": "New Delhi",             // Seller city
  "client_since": "1Y",                    // Tenure (1Y, 2Y, etc.)
  "enterprise_type": "Proprietor",         // Business structure
  "major_cities_list": {...},              // Geographic reach
  
  // Activity (7d, 30d, 90d windows)
  "seller_init_conn": {"7d": 0, "30d": 0, "90d": 0},    // Seller initiated
  "buyers_responded": {"7d": 0, "30d": 0, "90d": 0},    // Buyer responses
  "wp_enq_count": {"7d": 0, "30d": 0, "90d": 0},        // WholesalePartner enquiries
  "non_wp_enq_wp_conv_count": {...},                     // Non-WP conversions
  "lms_active_days": {"7d": 0, "30d": 0, "90d": 1},     // LMS activity days
  "tot_enq": {"7d": 1, "30d": 6, "90d": 15},            // Total enquiries
  
  // Call activity
  "pns_calls_recd": {"7d": 1, "30d": 3, "90d": 8},      // PNS calls received
  "call_answered": {"7d": 2, "30d": 2, "90d": 2},       // Calls answered
  "call_answered_1m_plus": {"7d": 1, "30d": 1, "90d": 1}, // Calls >1min
  
  // Lead sources
  "direct_enq": {"7d": 0, "30d": 3, "90d": 7},          // Direct enquiries
  "ast_buy_enq": {"7d": 0, "30d": 0, "90d": 0},         // Assisted buyer enquiries
  
  // Meeting activity
  "video_meet": {"7d": 0, "30d": 0, "90d": 0},          // Video meetings
  "physical_meet": {"7d": 0, "30d": 0, "90d": 0},       // Physical meetings
  
  // Catalog quality
  "catalog_bl_cons": {"7d": 0, "30d": 0, "90d": 0},     // Catalog BL consultations
  "cqs": 77,                                             // Catalog Quality Score
  "name_only_prd": 0,                                    // Products with name only
  "prod_wo_image": 0,                                    // Products without images
  "prd_wo_isq": 1,                                       // Products without ISQ
  "prd_no_prices": 1,                                    // Products without prices
  "live_prd_cnt": 33,                                    // Live products
  
  // Engagement metrics
  "top_10_categories": [...],                            // Top performing categories
  "top_10_cities": {...},                                // Top geographic markets
  "weekly_bl_active_days": {"w0": 0, ..., "w4": 0},     // Weekly BL activity
  
  // KYC & legal
  "legal_status": 4,                                     // Verification status
  
  // Dates
  "last_succ_call_dt": "2026-05-08",                     // Last successful call
  "last_video_meet_dt": "2025-05-15",                    // Last video meeting
  "last_physical_meet_dt": "2025-08-07",                 // Last physical meeting
  
  // Tickets & repeat
  "total_tickets": 0,                                    // Support tickets
  "deactivation_tickets": 0,                             // Deactivation requests
  "repeat_60d": 0,                                       // Repeat buyers in 60d
  
  // Ranking
  "a_rank_wo_prim_prd": 0,                               // A-rank without primary product
  "d_rank_mcats": 0,                                     // D-rank categories
  "count_of_number_mapped": 2,                           // Phone numbers mapped
  "production_wip": 0,                                   // Products in WIP
  
  // Scheduling
  "physical_meet_scheduled": "..."                       // Scheduled physical meetings
}
```

**Use for:**
- Historical performance trends (90+ days)
- Catalog quality assessment
- Engagement quality baseline
- Repeat buyer tracking

---

### `scorecard_6m` 
**Endpoint:** `POST /api/go/cust_scorecard_api`  
**Auth:** None  
**Returns:** 6-month historical scorecard (detailed structure TBD)

**Use for:**
- Medium-term trend analysis
- Seasonal patterns
- 6-month engagement history

---

### `scorecard_12m`
**Endpoint:** `POST /api/go/cust_wh_apiv2`  
**Auth:** None  
**Returns:** 12-month historical scorecard

**Use for:**
- Annual performance review
- Year-over-year trends
- Long-term engagement patterns

---

### `mcat`
**Endpoint:** `POST /api/go/mcatLocDtls`  
**Auth:** None  
**Returns:** Marketplace category details

**Data:** (structure TBD — likely marketplace category mappings, performance per category)

**Use for:**
- Category-level metrics
- Category-specific insights

---

### `competitors`
**Endpoint:** `POST /api/go/nsdprepplus?comp_flag=1`  
**Auth:** None  
**Returns:** Competitor analysis

**Data:** (structure TBD)

**Use for:**
- Competitive positioning
- Market intelligence

---

### `competitors_counts`
**Endpoint:** `POST /api/go/nsdprepplus?comp_flag=2`  
**Auth:** None  
**Returns:** Competitor count summaries

**Data:** (structure TBD)

**Use for:**
- Competitor count metrics

---

## 2. MERP GET Endpoints (merp.intermesh.net)

### `history`
**Endpoint:** `GET /index.php/Userlist/newHistory?glid={GLID}&empid={EMPID}&tab=history&platform=VoiceEval&duration=7`  
**Auth:** Bearer JWT  
**Returns:** Recent 7-day call/activity history (may be HTML)

**Status:** ⚠️ **Currently returns "Token Expired"** (JWT needs refresh)

**Use for:**
- Last 7 days activity log
- Call attempt history
- Recent interactions

---

### `dsr` (Daily Sales Report)
**Endpoint:** `GET /bi/reports/dsr/glusrDSR?glid={GLID}&empid={EMPID}&modid=WEBERP&screen_name=DSR`  
**Auth:** Bearer JWT  
**Returns:** Call connect records with transcript flags

#### Data Fields:
```json
{
  "data": {
    "dsr_connects": [
      {
        "pk_col_name": "click_to_call_id",           // Identifier name
        "pk_col_value": "{C2CID}",                   // Call ID
        "connect_dtls": {
          "Details": {
            "CALL_TRANSCRIPT_FLAG": "1",             // Has transcript?
            // ... other connect details
          }
        }
      }
      // ... more connect entries
    ]
  }
}
```

**Use for:**
- **Extract C2CID** (Click-To-Call IDs) for transcript fetching
- Call connect records
- Availability of call transcripts

---

### `transcript` (Chained from DSR)
**Endpoint:** `GET /go/api/genericMod/v1/calltranscriptread?empid={EMPID}&c2cid={C2CID}&modid=VoiceAI&screen_name=VoiceAI`  
**Auth:** Bearer JWT  
**Returns:** Full call transcript + metadata

#### Data Fields:
```json
{
  "c2cid": "{C2CID}",           // Call ID
  "data": {
    "transcript": "...",         // Full call text
    "duration": 120,             // Call duration (seconds)
    "date": "2026-05-08",        // Call date
    // ... metadata about the call
  }
}
```

**Prerequisite:** Must extract C2CID from DSR response first

**Use for:**
- Call quality assessment
- Verbal communication analysis
- Call duration & engagement

---

### `product_summary`
**Endpoint:** `GET /go/api/csd/v1/qualityScoreDetails?glid={GLID}&empid={EMPID}&flag=summary`  
**Auth:** Bearer JWT  
**Returns:** Product quality summary (single record)

**Data:** (structure TBD — likely product count, quality score, avg rating)

**Use for:**
- Quick product quality overview

---

### `product_details` (Paginated)
**Endpoint:** `GET /go/api/csd/v1/qualityScoreDetails?glid={GLID}&empid={EMPID}&limit=20&offset=0`  
**Auth:** Bearer JWT  
**Returns:** Individual product records (paginated, max 2000)

#### Data Fields (per product):
```json
{
  "product_id": "...",
  "name": "...",
  "category": "...",
  "quality_score": 85,
  "rating": 4.5,
  "image_count": 5,
  "has_prices": true,
  // ... product-level metrics
}
```

**Use for:**
- Product-by-product quality assessment
- Image completeness
- Pricing completeness
- Category-level distribution

---

## 3. Context API (merp.intermesh.net)

### `generateContextUID` (Step 1)
**Endpoint:** `POST /go/api/globalcontext/v1/generateContextUID`  
**Auth:** JWT (as `ak`), EMPID in body  
**Returns:** Time-limited UUID (valid ~15 min)

```json
{
  "data": {
    "mapping_id": "{UUID}"  // Use in Step 2
  }
}
```

---

### `getContext` (Step 2)
**Endpoint:** `GET /go/api/globalcontext/v1/x/getContext?mapping_id={MAPPING_ID}&data_keys=all`  
**Auth:** None (UUID is the credential)  
**Returns:** Full enriched seller profile

#### Data Sections:
```json
{
  "kycdetails": {
    // KYC verification status
    "gstin": "...",
    "pan": "...",
    "verification_status": "verified"
  },
  
  "activitydetails": {
    // Activity metrics (similar to scorecard_summary)
    "calls_30d": 5,
    "enquiries_90d": 15,
    "last_login": "2026-05-14"
  },
  
  "connectdetails": {
    // Call records and interactions
    "dsr_connects": [...],     // Similar to DSR endpoint
    "recent_calls": [...]
  },
  
  "BLdetails": {
    // Business listing information
    "listing_status": "active",
    "completeness_score": 95
  }
  
  // ... other enrichment segments
}
```

**Use for:**
- Complete seller profile in single call
- KYC verification status
- Enriched context for decision-making
- Replaces multiple individual calls

---

## 4. Ingestion Service (ingestion-service-*.run.app)

### `composite`
**Endpoint:** `GET /api/v1/sellers/{GLID}`  
**Auth:** x-api-key header  
**Returns:** Merged seller profile (normalized)

**Data:** (processed/normalized version of Context + DSR)

**Use for:**
- Normalized seller data
- Easier parsing (compared to raw MERP)

---

### `calls`
**Endpoint:** `GET /api/v1/sellers/{GLID}/calls`  
**Auth:** x-api-key header  
**Returns:** Normalized call history

**Data:** (cleaned-up version of DSR + transcripts)

**Use for:**
- Call history without MERP complexity
- Pre-processed call records

---

### `hotleads`
**Endpoint:** `GET /api/v1/sellers/{GLID}/hotleads`  
**Auth:** x-api-key header  
**Returns:** High-priority leads for this seller

**Use for:**
- Hot lead identification
- Priority engagement opportunities

---

### `blni` (Business Listing Normalized Index)
**Endpoint:** `GET /api/v1/sellers/{GLID}/blni`  
**Auth:** x-api-key header  
**Returns:** Normalized business listing data

**Use for:**
- Business listing quality
- Listing completeness

---

### `metrics`
**Endpoint:** `GET /api/v1/sellers/{GLID}/metrics?as_of=YYYY-MM-DD`  
**Auth:** x-api-key header  
**Returns:** Time-windowed aggregate metrics

**Use for:**
- Point-in-time metrics as of a date
- Historical metric snapshots

---

### `activity`
**Endpoint:** `GET /api/v1/sellers/{GLID}/activity`  
**Auth:** x-api-key header  
**Returns:** 30-day clickstream (seller dashboard events)

**Data:** (user interaction events)

**Use for:**
- User behavior on dashboard
- Engagement with platform features

---

## Data Overlap Matrix

| Data | DWH scorecard | MERP DSR | MERP history | Context API | Ingestion |
|------|---------------|----------|--------------|-------------|-----------|
| Call counts | ✓ (90d) | ✓ (recent) | ✓ (7d) | ✓ (merged) | ✓ |
| Call transcripts | ✗ | C2CID only | ✗ | ✓ (via DSR) | ✓ |
| Product quality | ✓ | Via product endpoint | ✗ | ✓ | ✓ |
| KYC status | ✗ | ✗ | ✗ | ✓ | ✓ |
| Engagement metrics | ✓ (historical) | ✓ (current) | ✓ (7d) | ✓ (merged) | ✓ |
| Call details | ✗ | ✓ | ✗ | ✓ | ✓ |
| Video/physical meets | ✓ | ✗ | ✗ | ✓ | Partial |

---

## Recommended Call Sequence

### Minimal (fastest):
1. **`scorecard_summary`** (DWH) → Historical baseline
2. **`dsr`** (MERP) → Current call records
3. **`transcript`** (MERP) → Call details (if CALL_TRANSCRIPT_FLAG=1)

### Complete:
1. **`getContext`** (Context API Step 1 + 2) → Full enriched profile
2. **`product_details`** (MERP, paginated) → All product metrics
3. **`transcript`** (MERP, if needed) → Call quality deep-dive

### Normalized (preferred if available):
1. **`composite`** (Ingestion) → Merged seller profile
2. **`calls`** (Ingestion) → Clean call history
3. **`metrics?as_of=DATE`** (Ingestion) → Historical snapshots

---

## Known Issues

| Issue | Endpoint | Status | Workaround |
|-------|----------|--------|-----------|
| Token Expired | MERP GET (history, dsr, products, transcripts) | ⚠️ Active | Refresh `IM_INTERNAL_JWT` in .env |
| HTML instead of JSON | `history` | Observed | Code fallback: capture as text |
| No auth required (advantage) | DWH POST | ✓ Working | Use when MERP JWT is invalid |

---

## Field Naming Convention

- **`{GLID}`** = Global ID (seller ID, numeric)
- **`{C2CID}`** = Click-To-Call ID (call interaction ID, numeric)
- **`{EMPID}`** = Employee ID (call center employee, numeric)
- **`{JWT}`** = IM_INTERNAL_JWT (authentication token)
- **`7d/30d/90d`** = 7-day, 30-day, 90-day windows respectively

---

## Caching Strategy

- **DWH data**: Cache 24h (historical, slow-changing)
- **MERP DSR**: Cache 1h (current calls, frequent updates)
- **Context UID**: Regenerate every 10min (15min validity)
- **Transcripts**: Cache indefinitely (immutable)
- **Product details**: Cache 12h (updates are rare)
