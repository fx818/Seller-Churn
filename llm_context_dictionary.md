# LLM Context Dictionary — Field Definitions for Agentic Pipeline

This file contains the complete, accurate context for every field the LLM will see when evaluating a seller. This is the source of truth for building the agent prompt.

---

## 1. Business Context

**IndiaMART** is India's largest B2B marketplace connecting buyers and suppliers. Over 3.5 Crore buyers search from 4.3 Crore products. Over 40 Lakh suppliers promote their businesses.

**What we do:** We call IndiaMART free sellers using an AI voicebot to fix (schedule) meetings with IndiaMART sales executives. We only call sellers who recently performed an activity on the platform.

**Ideal journey:** Bot calls seller → meeting is fixed → meeting is done → sale is closed (seller buys a paid package).

**Paid package hierarchy (low to high):**
MDC (Mini Dynamic Catalog — entry-level paid package, monthly or annual) → TrustSeal (higher than MDC, verified business badge) → Maximiser Pro → IM Leader / IM Star

---

## 2. Identifier Fields

- **GLID / `fk_glusr_usr_id` / `gluser_id` / `sts_fk_glusr_id`** — The seller's unique user ID on IndiaMART. This is the primary identifier used across all files. Different files use different column names but they all refer to the same thing.
- **`fk_sts_company_id`** — The company ID. This is DIFFERENT from the GLID. One company can have multiple GLIDs (see sibling_count). We always join on GLID, not company ID.

---

## 3. Seller Profile Fields

### Account Age
- **Field:** `creationdate` from seller_profile.csv
- **What it means:** Date the seller's profile was created on IndiaMART. Computed as days/years from this date to the call date.
- **Why it matters:** Older accounts may have established presence but could also be fatigued. New accounts may be more open to engagement.

### Paid History
- **Field:** `paid_history` from seller_profile.csv
- **Values:** "Yes" / "No"
- **What it means:** Whether the seller has PREVIOUSLY purchased a paid IndiaMART subscription. Since the bot only calls FREE sellers, paid_history=Yes means the seller was paid before but churned back to free.
- **Why it matters:** A churned paid seller has experience with IndiaMART's services — they know what they're getting. Their reason for churning may affect willingness to re-engage.

### RAG Category (Retainability / Buyer Demand)
- **Field:** `rag_category` from seller_profile.csv
- **Values:** Green+, Green, Amber, Red, Red-
- **What it means:** Predicts whether the seller will be retained long-term if onboarded to a paid package. Based on buyer demand in the seller's product category — more buyer demand = more business for the seller = higher retention.
  - **Green+ / Green** — Highly retainable. Many buyers search for this seller's product category.
  - **Amber** — Neutral.
  - **Red / Red-** — High risk of churn if onboarded. Few buyers search for this category.
- **Note:** Red/Red- sellers should generally be avoided from calling funnel.

### Customer Type (Custtype)
- **Field:** `glusr_usr_custtype_name` from seller_profile.csv
- **What it means:** Classifies sellers by their profile enrichment level on IndiaMART.

**Base types (profile enrichment):**

The raw data has 29 variants (e.g., "vgFCPplus with PNS(G)", "vgFCP with PNS(R)") but the suffixes ("with PNS", "(G)", "(R)") don't change the enrichment category. They just indicate PNS feature is enabled and the RAG color. **Group them into these categories:**

| Category | Raw values included | Meaning |
|---|---|---|
| **vgFCPplus** | vgFCPplus with PNS, vgFCPplus with PNS(G), vgFCPplus with PNS(R) | Highest enrichment: 3+ products with photos + GST verified + phone/OTP verified |
| **vgFCP** | vgFCP with PNS, vgFCP with PNS(G), vgFCP with PNS(R) | 3+ products with photos + GST verified (not phone verified) |
| **vFCP** | vFCP with PNS, vFCP with PNS(G), vFCP with PNS(R) | 3+ products with photos (no GST verification) |
| **qgFCPplus** | qgFCPplus with PNS, qgFCPplus with PNS(G), qgFCPplus with PNS(R) | GST verified + phone verified + 3 products but NO product photos |
| **qgFCP** | qgFCP with PNS, qgFCP with PNS(G), qgFCP with PNS(R) | 3 products, no photos, no GST |
| **gFCP** | gFCP | GST verified but not phone verified, may lack other enrichment |
| **mFCP** | mFCP | Mobile verified only — no GST, no email verification |
| **empFCP** | empFCP | Profile has IndiaMART executive's phone number (exec created/managed this profile) |
| **FCP / Other** | FCP, Other FCP, Default Cust Type, FREELIST, Travel FCP | Basic free catalog page, many details missing |
| **Paid** | BL Paid VgFCP, CATALOG, TSCATALOG, OthersPAID VFCP | Currently or previously on a paid package |
| **Disabled** | Disable Company | Suspended/blocked seller account |

**"plus" in custtype:** The "plus" suffix means the seller's GST is verified through tactile (phone number match) or OTP verification — giving higher confidence that we have the correct contact details and are reaching the actual business owner.

- **Why it matters:** Higher enrichment = more invested in the platform = potentially more receptive to paid services. "plus" sellers have verified contact details = higher chance of reaching the right person.

### Negative Category Flag
- **Field:** `mcat_50_percent_negative` from seller_profile.csv
- **Values:** "Yes" / "No"
- **What it means:** Whether 50%+ of the seller's listed products are in negative/restricted product categories on IndiaMART. These are products not allowed to be sold on IndiaMART (e.g., tobacco, restricted goods).
- **Why it matters:** We do NOT call these sellers. If this flag is "Yes", the seller should not be in the calling funnel.

### Sibling Count
- **Field:** `sibling_count` from seller_profile.csv
- **What it means:** Count of other IndiaMART profiles related to this seller (if the gst number is same for both accounts). Indicates the seller may have multiple accounts.

---

## 4. GST (Tax Registration) Fields

### Nature of Business (NOB)
- **Field:** `business_activity_nature` from gst_data.csv
- **What it means:** The type of business as registered with GST. Can be comma-separated for multiple types.
- **Common types:** Manufacturer, Trader (Retailer/Wholesaler), Service Provider, Works Contract (construction), Import/Export, Warehouse/Depot, Office/Sale Office.
- **Why it matters:** Business type affects what IndiaMART services are relevant and the seller's buying behavior.

### Annual Turnover
- **Field:** `annual_turnover_slab` from gst_data.csv
- **Values (cleaned):** Rs. 0-40 Lakhs | Rs. 40L-1.5Cr | Rs. 1.5Cr-5Cr | Rs. 5Cr-25Cr | Rs. 25Cr-100Cr | Rs. 100Cr-500Cr | Rs. 500Cr+ | NA (no data)
- **What it means:** Annual revenue of the seller's company as reported on the GST portal.
- **NA** means we don't have turnover data for this seller.

### GST Verification Source
- **Field:** `fk_gst_verification_src_id` from gst_data.csv
- **Values:** 1, 2, 3
- **What it means:** How the seller's GST was verified by IndiaMART:
  - **1 = Matchmaking** — GST details entered by the seller on IndiaMART match the official GST portal records
  - **2 = Tactile** — Phone number on the seller's GST also matches their IndiaMART phone number
  - **3 = OTP** — Seller verified their GST using their phone number via OTP
- **Why it matters:** Sources 2 and 3 are MORE reliable — we are confirmed that we have the seller's correct contact details (phone/email) and are reaching the actual business owner. Source 1 only confirms the GST number is valid but doesn't confirm contact details.

### GST Status
- **Field:** `gstin_status` from gst_data.csv
- **Values:** Active, Cancelled, Cancelled on application of Taxpayer, Cancelled suo-moto, Suspended
- **What it means:** Current status of the seller's GST registration with the government. Treat all non-Active statuses as inactive — the distinctions between cancellation types don't matter for prediction.

### GST Verification
- **Field:** `gst_verification_status` from gst_data.csv
- **Values:** Verified, Non-Verified
- **What it means:** Whether IndiaMART has verified the seller's GST registration. A seller can have gstin_status=Active but still be Non-Verified by IndiaMART.
- **Why it matters:** Verified sellers have a higher trust level on the platform.

### GST Registration Date
- **Field:** `registration_date` from gst_data.csv
- **What it means:** When the seller registered their business with GST. Indicates business vintage — newer registration = potentially newer company; older registration = established business.

---

## 5. Resistance History

### NI Count (Not Interested)
- **Field:** `ni_count` from ni_np_wn.csv
- **What it means:** Number of times the seller was marked "Not Interested" by IndiaMART sales executives in the last ~7 months of data.
- **Why it matters:** High NI = repeated resistance to sales outreach. Strongest predictor of NOT fixing a meeting.

### NP Count (Non-Prospective)
- **Field:** `np_count` from ni_np_wn.csv
- **What it means:** Number of times the seller was marked "Non-Prospective" — meaning not the right type of business for IndiaMART's paid services.

### WN Count (Wrong Number)
- **Field:** `wn_count` from ni_np_wn.csv
- **What it means:** Number of times the seller gave a wrong number. Could be genuinely wrong or an avoidance tactic.

---

## 6. Scorecard Activity Fields (Weekly Data)

These come from `scorecard_weekly.csv`. We use 4 weeks of data before the call week (call week excluded).

### Buyer Enquiries (`total_enq`)
- Order enquiries sent to this seller directly by IndiaMART buyers. Indicates buyers are interested in the seller's products/catalog.

### Callbacks (`callbacks`)
- Number of times the seller called buyers back after receiving a PNS call. Shows seller is actively engaging with interested buyers.

### PNS Calls Received (`pns_calls_recd`)
- Number of calls the seller received from buyers through IndiaMART's PNS (Pay-per-call) system. Indicates buyer interest in the seller's products.

### PNS Calls Answered (`pns_calls_ans`)
- Number of buyer PNS calls the seller actually answered.

### PNS Success % (`pns_success_prcnt`)
- Percentage of buyer calls answered by the seller (answered / received). Shows the seller's propensity to pick up calls. Scale: 0-100%.

### LMS Active Days (`lms_active_days`)
- Number of days the seller was active on the Lead Management System in that week. Range: 0-7 per week. This is specifically for the lead management module, not general app usage.

### Products Added (`prd_added`)
- Number of new products the seller added to their IndiaMART catalog that week.

### Products Modified (`prd_modified`)
- Number of existing products the seller updated/edited that week.

### Live Product Count (`live_prd_cnt`)
- Number of currently active product listings on IndiaMART.

### CQS — Catalogue Quality Score (`cqs`)
- Score measuring the quality of the seller's product catalog. Scale: 0-100 (approx). Calculated based on: product images quality, number of images per product, description quality, whether prices are listed.
- Higher CQS = better catalog = more likely to attract buyers.

### Buyer Ratings (`avg_ratings`)
- Average rating given to this seller by buyers. Scale: 0-5 (star rating). 0 may mean no ratings received or a 0 rating.

### Success Connect (`success_connect`)
- Count of times IndiaMART successfully connected with the seller that week. Includes: successful phone calls (>= 1 minute), video meetings, and physical meetings.

### Replies (`replies`)
- Count of replies the seller gave to buyer enquiries. Shows how actively the seller responds to buyer interest.

---

## 7. Hot Lead Types

Hot leads are seller activities on IndiaMART that indicate interest in the platform's services. They are categorized as **Top 3** (high conversion probability) or **Rest** (lower probability).

### Top 3 (High Intent)
| Code | Name | What it means |
|---|---|---|
| TF | Toll Free | Seller called IndiaMART's call center / requested help |
| PANF | Payment Failed - Annual | Seller attempted to pay for annual package but payment failed |
| PNCHF | Payment Failed - NACH | Seller attempted to pay for monthly/NACH package but payment failed |
| OLPR | Payment Done - BL | Seller successfully purchased a retail buylead (completed payment) |
| OLP | Payment Attempt - BL | Seller attempted payment for buyer-posted leads or visited IndiaMART payment page |
| PAM | Payment Attempt - MDC | Seller attempted payment on IndiaMART platform |
| SCHD | Schedule Demo | Seller requested a demo from IndiaMART |
| NURT | New User Top3 | New profile generated on IndiaMART |
| NVGT | New VGFCP Top3 | Seller just enriched their profile to highest level (new high-enrichment profile) |
| PUT | Power User Top3 | Manually tagged by IndiaMART for sellers with good catalog enrichment and high meeting potential |

### Rest (Lower Intent)
| Code | Name | What it means |
|---|---|---|
| PIM | Payment Interest - MDC | Seller browsed IndiaMART pages showing paid package information (interest, not attempt) |
| NUR | New User Registration | Seller completed new user registration |
| UATF | Toll Free - Other | Other toll-free call activity |
| PUA | Premium Activity - Online | Seller performed higher-priority activities like GST verification, buylead shortlist |
| UA | Other Activity - Online | Seller performed low-priority activities like normal navigation, general profile views |
| PNSR | PNS Received | Seller received a PNS call from a buyer |
| PNSM | PNS Missed | Seller missed a PNS call from a buyer |
| ENQR | Enquiry Received | Seller received an order enquiry from a buyer |
| DHL | Data Hot Lead | Seller's activity suggests they are not ready to be sold yet (e.g., added 1-2 products after years of inactivity). Passed to freelancers to first enrich the seller's profile before a sales exec visits. |

---

## 8. Qualitative Data

### Executive Call Comments (`comments` from call_data.csv)
- Notes written by IndiaMART sales executives after calling a seller.
- **Common abbreviations:**
  - Ni / Nii = Not Interested
  - Nr = Not Reachable (could not reach the seller)
  - Na = Not Available
  - Np = Non-Prospective
  - Mf = Meeting Fixed
  - Cb = Callback requested
  - Fu = Follow Up
  - Ntf = Need to Follow
  - Tc = Take Care (sales exec thinks this seller should be followed up / taken care of)
  - DV = Direct Visit (cold/unscheduled meeting — sales exec visited seller without prior appointment)
  - MDC = Mini Dynamic Catalog (paid package being pitched)
  - WIP = Work in Progress
- **Important:**  The LLM should NEVER see the bot call summary for the CURRENT call (same day) — it can leak the outcome. Older bot call summaries from previous calls are safe to use.

### Meeting Comments (`comments` from meeting_data.csv)
- Notes written by sales executives after meeting with a seller.
- **Common abbreviations:**
  - BAH = Bada Aasaan Hai — a standardized sales presentation (7-8 slides) shown during meetings to explain what IndiaMART is and how the seller can benefit from paid services, to convince them to take a plan
  - MDC = Mini Dynamic Catalog package (monthly or annual)
  - MDC Pro = a different, higher-tier package
  - TS = TrustSeal package
  - CA = Current Account (the seller's bank account)
  - Pitch: annual/monthly = exec pitched annual or monthly payment plan
  - Bank names (HDFC/ICICI/BOB/PNB/SBI) = seller's bank, noted for payment processing
  - BL = Buyleads
  - DM = Decision Maker
  - BM = Branch Manager
  - TL = Team Lead
  - Ntf = Need to Follow

### Hot Lead History (from hotlead_data.csv)
- Chronological list of seller activities on IndiaMART platform with timestamps. See Hot Lead Types section above for code definitions.

### Bot Call Summary (`call_summary` from bot_call_data.csv)
- AI-generated summary of the bot's conversation with the seller.
- **LEAKAGE RULE:** Never show the current call's summary to the LLM during prediction. Only older call summaries (from previous calls) are safe.

### Callback Fixed (`callback_fixed` from bot_call_data.csv)
- Whether the seller asked for a callback instead of fixing a meeting. Separate from meeting_fixed. Indicates some interest but not enough to commit to a meeting.

---

## 9. Package Hierarchy (for understanding meeting comments)

```
MDC Monthly/Annual (entry-level paid, basic visibility)
    ↓
TrustSeal (verified business badge, higher trust)
    ↓
Maximiser Pro (premium visibility and features)
    ↓
IM Leader / IM Star (top-tier packages)
```

The bot is trying to fix a meeting where a sales exec will pitch one of these packages to the seller.

---

## 10. Meeting Type & Status Codes

### Meeting Type (`sts_dsr_sales_type`)
| Code | Meaning |
|---|---|
| 1 | Fresh meeting — sales executive is meeting the seller for the first time (the seller may or may not have met other sales executive form indiamart but this particular executive is meeting him for the first time)|
| 2 | Follow-up meeting — exec has met the seller before |
| 3 | WIP (Work in Progress) — seller has taken a paid plan, exec is collecting details to enrich the seller's profile |

### Meeting Status (`sts_dsr_sales_status`)
| Code | Meaning |
|---|---|
| 8 | Prospect Hot — seller is a hot prospect (high interest) |
| 2 | Prospect Warm — seller shows some interest |
| 9 | Prospect Cold — seller shows low interest |
| 7 | WIP — work in progress |
| 3 | Not Met — meeting did not happen |

---

## 11. Call Disposition Codes

### Call Result (`bl_call_result` / `sts_dsr_call_result`)

**Category: Not-Talked**
| Disposition | ID | Sub-disposition | Sub ID | Meaning |
|---|---|---|---|---|
| No Response | 18 | — | — | Could not reach the seller |
| No Response | 18 | — | 0 | Could not reach (no sub-disposition) |
| Wrong Number | 11 | — | — | Wrong number |

**Category: Talked**
| Disposition | ID | Sub-disposition | Sub ID | Meaning |
|---|---|---|---|---|
| Sts Update | 395 | — | — | STS Update — status update call (talked to seller, updated their status in the system) |
| Sts Update | 395 | No Response NI/NR | 55 | STS Update — no response / not interested / not reachable |
| Disposition | ID | Sub-disposition | Sub ID | Meaning |
|---|---|---|---|---|
| Follow up | 19 | General | 51 | General follow up needed |
| Follow up | 19 | MDC Pitched | 52 | MDC package was pitched, need follow up |
| Follow up | 19 | Meeting Fix | 230 | Meeting was fixed during the call |
| MDC Pitched | 16 | Online | 53 | MDC pitched online |
| MDC Pitched | 16 | Offline | 54 | MDC pitched offline |
| Interested | 4 | — | 0 | Seller is interested (hot prospect) |
| Interested | 4 | — | 231 | Seller interested (specific sub-type) |
| Not Interested | 20 | No Need | 57 | Seller says no need |
| Not Interested | 20 | No Response NI/NR | 55 | NI or not reachable |
| Not Interested | 20 | Already Paid Elsewhere | 56 | Seller already using competitor/other paid service |
| Not Interested | 20 | Fund Issue | 58 | Seller has financial constraints |
| Not Interested | 20 | Other NI Reason | 59 | Other not interested reason |
| Non Prospective | 14 | Negative Industry/Service | 62 | Seller is in a restricted industry |
| Non Prospective | 14 | Business Closed | 63 | Seller's business is closed |

**Category: Meeting (bl_call_result used for meeting dispositions)**
| Disposition | ID | Sub-disposition | Sub ID | Meaning |
|---|---|---|---|---|
| Meeting - Follow Up | 251 | Prospect Warm | 260 | Meeting done, seller shows some interest, needs follow up |
| Meeting - Follow Up | 251 | Prospect Cold | 259 | Meeting done, seller shows low interest |
| Meeting - Follow Up | 251 | Need Time | 257 | Meeting done, seller asked for time to decide |
| Meeting - Follow Up | 251 | Other Follow Up | 258 | Meeting done, other follow up reason |
| Meeting - Interested | 250 | — | 0 | Meeting done, seller is interested |
| Meeting - WIP | 252 | WIP | 273 | Work in progress — seller already on paid plan, collecting details |
| Meeting - WIP | 252 | BAH Done | 715 | BAH presentation completed during meeting |
| Meeting - WIP | 252 | Proposal Shared | 264 | Proposal/pricing shared with seller |
| Meeting - WIP | 252 | Documents Collected | 263 | Documents collected from seller |
| Meeting - WIP | 252 | Other WIP | 267 | Other work in progress |
| Meeting - WIP | 252 | Payment Processing | 276 | Payment is being processed |
| Meeting - Not Met | 730 | — | — | Meeting was scheduled but did not happen |

**Category: Video**
| Disposition | ID | Sub-disposition | Sub ID | Meaning |
|---|---|---|---|---|
| Video Call | 595 | MDC Pitched | 596 | MDC pitched during video call |
| Video Call | 595 | Follow Up | 597 | Follow up after video call |

**Note:** Sub-disposition ID = 0 means no specific sub-disposition was selected.

---

## 12. Hot Lead Activity Descriptions

Some hot lead activities have specific descriptions:
- **"SOI Click on Sell-on-Indiamart"** — Seller was trying to create a new profile on IndiaMART or wasn't able to complete account creation
- **"Similar Leads"** — Seller was browsing leads in related product categories, exploring the platform for relevant buyer demand
- **"Premium Activity - Enquiry Received"** — An enquiry received that is categorized as premium/higher-value activity
