# IndiaMART Seller Churn Reduction — Full Implementation Plan (Integrated)

> **Version:** 2.0 | **Date:** 2026-05-15 | **Author:** Anurag Upadhyay
> **Hackathon Track:** Seller Retention + AI Personalisation

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Reference Library & Cohort Data](#2-reference-library--cohort-data)
3. [Pre-Analysis Pipeline](#3-pre-analysis-pipeline)
4. [Agent Skills System](#4-agent-skills-system) ← **Core Design**
5. [Phase 1 — Onboarding Health Check](#5-phase-1--onboarding-health-check)
6. [Phase 2 — Dual-Track Churn Predictor](#6-phase-2--dual-track-churn-predictor)
7. [Phase 3 — Three Parallel Retention Tracks](#7-phase-3--three-parallel-retention-tracks)
8. [Phase 4 — Buy Lead Upgrade Engine](#8-phase-4--buy-lead-upgrade-engine)
9. [Phase 5 — Renewal Window Boost](#9-phase-5--renewal-window-boost)
10. [Cross-Cutting Systems](#10-cross-cutting-systems)
11. [seller_survival Package](#11-seller_survival-package)
12. [File & Folder Structure](#12-file--folder-structure)
13. [Data Schemas](#13-data-schemas)
14. [Error Handling Strategy](#14-error-handling-strategy)
15. [Impact Metrics & Pinch Metrics](#15-impact-metrics--pinch-metrics)
16. [Implementation Sequence](#16-implementation-sequence)
17. [Web UI — GLID Scorer Interface](#17-web-ui--glid-scorer-interface)

---

## 1. System Architecture Overview

### What Exists Today (Current State)

```
pipeline.py
  ├── Step 1: fetch_all()        — 10 APIs x N GLIDs, 5-thread concurrent
  ├── Step 2: compute_signals()  — 7-signal churn scoring (0-100)
  ├── Step 3: seller dashboards  — per-seller HTML with charts
  └── Step 4: master_dashboard  — segment analytics, top-10 reasons

seller_survival/
  ├── cohort_builder.py          ✅ BUILT — 292-seller labeled cohort
  ├── cohort.csv                 ✅ BUILT — 146 retained + 146 churned GLIDs
  └── __init__.py                ✅ BUILT
```

Available signals from 10 APIs:
| Signal | Source API | Key Fields |
|--------|-----------|-----------|
| Enquiry volume | scorecard_summary | tot_enq.30d, enq_replied.30d |
| Active days | scorecard_summary | lms_active_days.30d |
| BL velocity | scorecard_6m | total_enq MoM delta |
| PNS answer rate | scorecard_6m | pns_success_prcnt |
| RAG category | composite | rag_category, rag_score |
| CQS | product_summary | CQS |
| Hotlead activity | hotleads | items[] |
| Clickstream | activity | event_count, events[] |
| Market size | competitors_counts | total_bl, total_paid_sellers |
| Competitor list | competitors | competitors[] |
| Long-term metrics | metrics | pns_received_90d, enq_received_90d, meetings_90d |

### What We Need to Build

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                           AGENT ORCHESTRATOR                                       │
│   Routes each seller through correct skills based on risk tier + churn reason      │
├──────────────┬──────────────┬──────────────┬──────────────┬──────────────────────┤
│ SKILL LAYER  │              │              │              │                      │
│ ChurnScoring │ SHAP_RCA     │ PeerBenchmark│ DemandIndex  │ OnboardingHealth     │
│ WhatsApp     │ PreCallBrief │ GiftedLead   │ CallSummary  │ WinbackPriority      │
│ ScriptGen    │ BLUpgrade    │LLMCohortScore│              │                      │
├──────────────┴──────────────┴──────────────┴──────────────┴──────────────────────┤
│                           DATA LAYER                                               │
│  runs/{run_id}/data/{glid}/*.json  +  analysis/  +  segments/  +  actions/        │
│  seller_survival/data/snapshots.parquet  (292-seller reference library)            │
├──────────────┬──────────────┬──────────────┬──────────────┬──────────────────────┤
│ PHASE 1      │ PHASE 2      │ PHASE 3      │ PHASE 4      │ PHASE 5              │
│ Onboarding   │ Dual-Track   │ Track A/B/C  │ BL Upgrade   │ Renewal Boost        │
│ Health Check │ Predictor +  │ Retention    │ Engine       │ Window               │
│              │ LLM Cohort   │              │              │                      │
└──────────────┴──────────────┴──────────────┴──────────────┴──────────────────────┘
```

### Design Principles

1. **Skills-first**: Every piece of logic is a callable skill with defined input/output schema
2. **Isolated runs**: Each pipeline invocation creates a fully isolated `runs/run_YYYYMMDD_HHMMSS/` directory
3. **Pre-analysis first**: Data quality gates run before any scoring or output
4. **Graceful degradation**: Missing API data → conservative scoring, never crash
5. **LLM-as-judge**: Cohort-calibrated AI scoring augments rule-based scores for established sellers
6. **Business impact visible**: Every output shows estimated ARR at risk and sellers saveable

---

## 2. Reference Library & Cohort Data

**This section covers the 292-seller reference library that powers the LLMCohortScorerSkill.**

### 2.1 Cohort Composition (LOCKED)

The reference library is built from two input files:
- `winback_pool_2026 (1).csv` — 39,798 churned GLIDs + churn date
- `Feb leads data.xlsx` (`Main summary` sheet) — columns `fk_glusr_usr_id` + `Sale (14D)` only

**Cohort split:**
| Label | Count | Source |
|-------|-------|--------|
| Retained | 146 | `Sale(14D)=1` AND NOT in winback |
| Churned (Cohort A) | 38 | `Sale(14D)=1` AND in winback (converted then churned) |
| Churned (winback Apr) | 108 | Random sample from winback Apr-2026 expirations |
| **Total** | **292** | **Balanced 146/146** |

**File:** `seller_survival/cohort.csv` — columns: `glid, label, source`
Status: ✅ Already generated (292 rows, verified).

### 2.2 Snapshot Shape (Per-GLID)

Each seller in the library (and each target seller when scored) is represented as a `Snapshot`:

```
Snapshot = {
  glid:  int,
  label: "retained" | "churned" | "target",
  context: {
    turnover:  str   # "GST turnover" — exact match for cohort filtering
    city:      str   # first token of "Locality / City"
    state:     str   # second token of "Locality / City"
    mcats:     list  # list of category strings — semantic match via embeddings
    custtype:  str   # "Custtype" — exact match
  },
  behavioral: {
    bl: {
      received_90d, viewed_90d, consumed_90d, replied_90d,
      consumption_rate, reply_rate, active_bl, blni_count_1yr,
      weekly_bl_active    # last 7 weeks array
    },
    lms: {
      call_attempts_90d, call_answered_90d, call_pickup_ratio_90d,
      calls_1min_plus_90d, last_succ_call_dt, last_call_summary
    },
    activity: {
      activity_30d, weekly_activity, monthly_activity, 3month_activity,
      monthly_trend,      # per-month metrics from scorecard_12m
      daily_activity      # per-day map
    }
  }
}
```

### 2.3 Reference Library Build (One-Time, ~15–25 min)

**Run before the first pipeline run:**
```bash
python -m seller_survival build
```

This:
1. Reads `cohort.csv` (292 GLIDs)
2. Fetches 3–4 API endpoints per GLID via `slim_loader` (cached to `data/loader_cache/<glid>.json`)
3. Extracts `Snapshot` for each GLID via `feature_schema.extract_snapshot()`
4. Embeds all unique mcats via `mcat_embeddings.embed_batch()` → `data/mcat_embeddings.json`
5. Writes `data/snapshots.parquet` (292 rows)

**Reruns hit cache — instant after first build.**

### 2.4 Cohort Filter Logic

When scoring a target seller, filter the 292-row library to find comparable historical sellers:

```python
filter_score(target, historical) = (
    1 if target.turnover == historical.turnover else 0
  + 1 if (target.city == historical.city AND target.state == historical.state) else 0
  + 1 if max_pairwise_cosine(target.mcats, historical.mcats) >= 0.7 else 0
  + 1 if target.custtype == historical.custtype else 0
) / 4
```

- Return top 10 churned + top 10 retained from sellers with `filter_score >= 0.5` (≥ 2/4 match)
- If fewer than 5 match at 0.5 threshold → relax to 0.25, flag run as `loose` context match

### 2.5 LLM Scoring Prompt

```
SYSTEM:
  You are a seller-survival analyst. Score the target seller on three
  dimensions using Red / Amber / Green bands, comparing against the
  provided cohort baseline. Calibrate the bands using the cohort —
  there are no hard-coded thresholds.

USER:
  Target seller behavioral snapshot:
    BL:       { received_90d: 142, consumed_90d: 5, reply_rate: 0.014, ... }
    LMS:      { call_attempts_90d: 31, pickup_ratio: 0.35, ... }
    Activity: { activity_30d: 17, monthly_trend: [...], ... }

  Cohort context:
    turnover: "0 - 40 L", city: "New Delhi", state: "Delhi NCR",
    mcats: [...], custtype: "Trader - Retailer"

  10 churned-seller snapshots: [{...}, ...]
  10 retained-seller snapshots: [{...}, ...]

  Score on three independent dimensions:
    1. BL consumption     R/A/G — emphasis on consumption_rate, reply_rate
    2. LMS activity       R/A/G — emphasis on pickup_ratio, call_attempts
    3. Activity trend     R/A/G — emphasis on direction of monthly_trend

  Return strict JSON only:
  {
    "bl_band":       "R" | "A" | "G",
    "lms_band":      "R" | "A" | "G",
    "activity_band": "R" | "A" | "G",
    "reasoning":     "2-3 sentences grounded in the cohort comparison",
    "churned_lookalikes":  [glid, glid, glid],
    "retained_lookalikes": [glid, glid, glid]
  }
```

### 2.6 Composite Risk Rubric (Post-LLM, Deterministic)

```
RRR                                        → "Critical"
RRA, RAR, ARR  (2 Reds + 1 Amber)         → "Very High"
RRG, RGR, GRR  (2 Reds + 1 Green)         → "High"
RAA, ARA, AAR  (1 Red + 2 Ambers)         → "High"
RAG, RGA, ARG, AGR, GRA, GAR  (1 of each) → "Moderate"
AAA                                        → "Moderate"
RGG, GRG, GGR  (1 Red + 2 Greens)         → "Moderate"
AAG, AGA, GAA  (2 Ambers + 1 Green)       → "Low"
AGG, GAG, GGA  (1 Amber + 2 Greens)       → "Low"
GGG                                        → "Very Low"
```

### 2.7 Confidence Score Formula

```python
confidence_score = round(100 * (
    0.5 * cohort_match_score        # mean filter_score of top 20 shown
  + 0.3 * cohort_size_score         # min(n_filtered_at_threshold / 20, 1.0)
  + 0.2 * data_completeness_score   # fraction of behavioral fields non-null
))
```

The LLM is NOT asked to self-rate confidence — deterministic formula only.

### 2.8 LLM Cohort Score → Pipeline Risk Tier Mapping

| LLM risk_level | Maps to pipeline risk tier |
|----------------|--------------------------|
| Critical | Red (override any lower rule-based score) |
| Very High | Red |
| High | Red (if rule-based also ≥ 50) OR Amber |
| Moderate | Amber |
| Low | Amber (if rule-based ≥ 35) OR Green |
| Very Low | Green |

**Final tier = max(rule_based_tier, llm_tier)** — never downgrade from rule-based Red.

---

## 3. Pre-Analysis Pipeline

**Purpose:** Before running any phase, validate data quality, flag coverage gaps, check reference library readiness, and produce a baseline report.

**Runs as:** `pre_analysis.py` — standalone script, must complete before `pipeline.py`.

### 3.1 Reference Library Readiness Check (NEW)

**First step of pre_analysis.py:**

```python
if not Path("seller_survival/data/snapshots.parquet").exists():
    print("WARNING: Reference library not built. Run: python -m seller_survival build")
    print("LLMCohortScorerSkill will be DISABLED for this run.")
    llm_scorer_available = False
else:
    llm_scorer_available = True
```

Write `llm_scorer_available` flag to `runs/{run_id}/analysis/coverage_report.json`.

### 3.2 Data Coverage Check

**File:** `pre_analysis/coverage_check.py`

```
Input:  runs/{run_id}/data/{glid}/*.json  (raw API responses)
Output: runs/{run_id}/analysis/coverage_report.json
```

For every GLID x API combination, record:
- `status` (200 / 4xx / 5xx / null)
- `has_data` (bool — status 200 AND non-empty data)
- `error` (string if failed)

Compute per-GLID coverage score = (APIs with 200) / 10.

**Coverage thresholds:**
| Coverage | Action |
|----------|--------|
| ≥ 8/10 APIs OK | Fully scoreable |
| 5-7/10 OK | Partially scoreable — note gaps in dashboard |
| < 5/10 OK | Flag as data-incomplete — exclude from aggregate stats |

**Error buckets:**
- `timeout` — API call timed out (retry once with 40s timeout)
- `auth_error` — 401/403 (credential issue — log and skip)
- `not_found` — 404 (GLID doesn't exist in that system)
- `future_date` — 400 with "as_of" message (fix AS_OF constant)
- `parse_error` — response not valid JSON (store raw, mark as degraded)

### 3.3 Schema Validation

For each API that returned 200, validate that expected keys are present:

| API | Required Keys | Optional Keys |
|-----|--------------|---------------|
| scorecard_summary | response.summary[0].tot_enq | enq_replied, lms_active_days |
| scorecard_6m | response.summary (array, len ≥ 1) | pns_success_prcnt per month |
| composite | data.profile.rag_category | rag_score, customer_type |
| product_summary | data.CQS OR data.data.CQS | — |
| hotleads | data.items (array) | — |
| activity | data.event_count | data.events |
| metrics | pns_received_90d, enq_received_90d | meetings_90d |
| competitors | response.competitors (array) | — |
| competitors_counts | response.mcat_data[0].total_bl | total_paid_sellers |

### 3.4 Baseline Distribution

Compute baseline stats across all scoreable GLIDs:
- Distribution of RAG categories
- Distribution of enterprise types (Proprietor / ME / BB)
- Distribution of ctype (CATALOG / FCP+PNS / FREELIST)
- City distribution
- Account age distribution (buckets: 0-90d, 91-180d, 181-365d, 365d+)
- Client tenure distribution

**Output:** `runs/{run_id}/analysis/baseline_distribution.json`

### 3.5 Peer Benchmark Pre-computation

Before scoring individuals, compute category/city peer medians across the full run dataset:
- Median tot_enq per (enterprise_type, ctype) group
- P25, P75 BL counts per group
- Median active_days per group
- Median CQS per group
- Median PNS answer rate per group

**Output:** `runs/{run_id}/analysis/peer_benchmarks.json`

```json
{
  "groups": {
    "Proprietor|CATALOG": {
      "n": 42,
      "median_enq_30d": 8,
      "p25_enq_30d": 3,
      "p75_enq_30d": 14,
      "median_active_days": 12,
      "median_cqs": 68,
      "median_pns_rate": 74
    }
  }
}
```

### 3.6 Pre-Analysis HTML Report

**File:** `runs/{run_id}/pre_analysis_report.html`

Dark-theme HTML showing:
- Reference library status (built / not built, 292 GLIDs, parquet size)
- Coverage matrix (GLIDs x APIs, green/red/amber cells)
- API success rate bar chart
- Baseline distribution charts (donut + bar)
- List of excluded GLIDs with reasons
- Peer benchmark table by segment

**Error handling:**
- If >30% GLIDs are data-incomplete → abort with warning
- If scorecard_summary fails for >20% → log critical warning
- Never crash — always produce partial report

---

## 4. Agent Skills System

**THIS IS THE CORE ARCHITECTURE.** Every feature is a composable Skill. The Agent Orchestrator chains skills based on seller tier and churn reason.

### 4.1 Skill Architecture

**Base class** (`skills/base_skill.py`):
```python
class Skill:
    name: str
    version: str
    required_inputs: list[str]
    optional_inputs: list[str]
    output_schema: dict

    def validate(self, inputs: dict) -> tuple[bool, str]: ...
    def invoke(self, inputs: dict) -> SkillResult: ...
    def fallback(self, inputs: dict, error: Exception) -> SkillResult: ...
```

**SkillResult:**
```python
@dataclass
class SkillResult:
    success: bool
    data: dict
    error: str | None
    confidence: float   # 0.0–1.0
    used_fallback: bool
    latency_ms: int
```

**Skill registry** (`skills/registry.py`):
- Singleton dict: skill name → Skill instance
- Loaded at agent startup
- Skills declare dependencies (other skills that must run first)

### 4.2 Agent Orchestrator

**File:** `agent/orchestrator.py`

```
For each seller signal dict:
  1. Run ChurnScoringSkill       → churn_score, risk_tier, raw_reasons
  2. Run SHAPRCASkill            → rca_category, shap_explanation, top_features
  3. Run PeerBenchmarkSkill      → peer_delta, peer_group_stats
  4. Run DemandIndexSkill        → demand_index, demand_tier
  5. Run LLMCohortScorerSkill    → risk_level, bands, reasoning, lookalikes
     (only if account_age_days > 90 AND snapshots.parquet exists)
  6. Compute final_tier = max(rule_based_tier, llm_cohort_tier)
  7. Based on final_tier:
       Red   → GiftedLeadSkill + PreCallBriefSkill + ScriptGenerationSkill
       Amber → WhatsAppMessageSkill + ScriptGenerationSkill
       Green → monitoring only
  8. Run WinbackPrioritySkill if seller is in winback pool
  9. Compile ActionPlan for each seller
  10. Write action_plans/{glid}_action.json + analysis/skill_outputs/{glid}_skills.json
```

### 4.3 Skill Execution Flow

```
                    ┌──────────────────────┐
                    │  Seller Signal Dict   │
                    └──────────┬───────────┘
                               │
             ┌─────────────────▼──────────────────┐
             │         ChurnScoringSkill            │
             │   score (0-100), risk_tier, tags     │
             └─────────────────┬──────────────────┘
               ┌───────────────┼───────────────┐
               │               │               │
         ┌─────▼──┐       ┌────▼───┐     ┌────▼──────┐
         │ SHAP   │       │  Peer  │     │  Demand   │
         │ RCA    │       │ Bench  │     │  Index    │
         └─────┬──┘       └────┬───┘     └────┬──────┘
               └───────────────┼───────────────┘
                               │
             ┌─────────────────▼──────────────────┐
             │        LLMCohortScorerSkill          │
             │  (established sellers only, if lib   │
             │   available)                         │
             │  bands (R/A/G ×3), risk_level,       │
             │  reasoning, lookalikes               │
             └─────────────────┬──────────────────┘
                               │
             ┌─────────────────▼──────────────────┐
             │      Final Tier = max(rule, llm)    │
             └──────────┬───────────┬─────────────┘
                        │           │
            ┌───────────▼──┐   ┌────▼────────────────┐
            │   RED TIER   │   │    AMBER TIER        │
            │ GiftedLead   │   │ WhatsAppMessage      │
            │ PreCallBrief │   │ ScriptGeneration     │
            │ ScriptGen    │   └─────────────────────┘
            └──────────────┘
                        │
            ┌───────────▼──────────────┐
            │      ActionPlan JSON     │
            │   per seller, per run    │
            └──────────────────────────┘
```

---

### 4.4 Skill Definitions

---

#### SKILL 1: ChurnScoringSkill

**File:** `skills/churn_scoring_skill.py`
**Purpose:** Compute 7-signal weighted churn score from seller signal dict.

**Inputs:**
```json
{
  "glid": "string",
  "enq_30d": "int",
  "replied_30d": "int",
  "active_days_30d": "int",
  "bl_velocity_pct": "float | null",
  "pns_success_pct": "float | null",
  "rag": "string",
  "cqs": "float | null",
  "hotleads_count": "int",
  "event_count": "int"
}
```

**Scoring logic:**

| Signal | Threshold | Points | Reason Tag |
|--------|-----------|--------|-----------|
| reply_rate < 40% (AND enq > 0) | < 40% | +20 | `LOW_REPLY_RATE` |
| active_days == 0 | 0 | +18 | `ZERO_ACTIVE_DAYS` |
| active_days ≤ 3 | 1–3 | +10 | `LOW_ACTIVE_DAYS` |
| enq_30d == 0 | 0 | +15 | `NO_ENQUIRY_FLOW` |
| bl_velocity ≤ -30% MoM | ≤ -30 | +22 | `BL_VELOCITY_CRITICAL` |
| bl_velocity ≤ -10% MoM | -10 to -30 | +10 | `BL_VELOCITY_DECLINING` |
| pns_success_pct < 60% | < 60 | +12 | `LOW_PNS_RATE` |
| rag == Red | exact | +25 | `RAG_RED` |
| rag == Amber | exact | +12 | `RAG_AMBER` |
| cqs < 60 | < 60 | +15 | `LOW_CQS_CRITICAL` |
| cqs < 75 | 60–74 | +7 | `LOW_CQS_MODERATE` |
| hotleads_count == 0 | 0 | +8 | `NO_HOTLEAD` |
| event_count == 0 | 0 | +12 | `NO_PLATFORM_ACTIVITY` |
| event_count < 10 | 1–9 | +6 | `LOW_PLATFORM_ACTIVITY` |

Cap at 100. Risk tiers: Red ≥ 65, Amber 35–64, Green < 35.

**Outputs:**
```json
{
  "churn_score": 72,
  "risk": "Red",
  "churn_reasons": ["Low reply rate: 22% (threshold 40%)", "RAG category: Red"],
  "reason_tags": ["LOW_REPLY_RATE", "RAG_RED"],
  "score_breakdown": {"reply_rate": 20, "rag": 25, "active_days": 10}
}
```

**Fallback:** If fewer than 4 signals available → `churn_score=null, confidence=0.2, used_fallback=true`

---

#### SKILL 2: SHAPRCASkill

**File:** `skills/shap_rca_skill.py`
**Purpose:** Map reason_tags → single primary RCA category + human-readable Hindi/English explanation.

**This is the pivot skill.** Its output determines which script, message, and intervention fires.

**Inputs:**
```json
{
  "glid": "string",
  "reason_tags": ["LOW_REPLY_RATE", "NO_ENQUIRY_FLOW"],
  "score_breakdown": {"reply_rate": 20, "enq": 15},
  "rag": "Red",
  "cqs": 45,
  "bl_velocity_pct": -35,
  "peer_delta_pct": -60
}
```

**RCA Category mapping (priority: highest score contribution wins):**

| RCA Category | Trigger Tags | Plain English | Hindi Opening |
|---|---|---|---|
| `NO_LEADS` | NO_ENQUIRY_FLOW, BL_VELOCITY_CRITICAL | Platform not delivering volume | "Aapki current city/category mein leads kum aa rahi hain" |
| `LOW_ENGAGEMENT` | ZERO_ACTIVE_DAYS, NO_PLATFORM_ACTIVITY, LOW_ACTIVE_DAYS | Seller not using platform | "Aapne platform pe login nahi kiya last few weeks" |
| `POOR_CATALOG` | LOW_CQS_CRITICAL, LOW_CQS_MODERATE | Profile/catalog quality issue | "Aapki product listing mein kuch gaps hain" |
| `LOW_PNS_RESPONSE` | LOW_PNS_RATE | Not answering PNS calls | "Kaafi incoming calls miss ho rahi hain" |
| `PEER_GAP` | peer_delta_pct < -40% | Getting leads but below peers | "Aapke competitors same area mein zyada leads le rahe hain" |
| `RAG_RISK` | RAG_RED | Platform health flagged | "Aapka account health score kuch signals show kar raha hai" |
| `BL_DECLINE` | BL_VELOCITY_CRITICAL, BL_VELOCITY_DECLINING | Lead volume dropping | "Aapke leads last month se kam ho gaye hain" |

**Outputs:**
```json
{
  "rca_category": "NO_LEADS",
  "rca_confidence": 0.85,
  "rca_explanation_en": "Seller's category has low buyer demand in current city. BL velocity dropped 35% MoM.",
  "rca_explanation_hi": "Aapki category mein is city ke buyers abhi kam hain. National buyers active hain.",
  "top_feature": "bl_velocity_pct",
  "top_feature_value": -35,
  "top_feature_contribution": 22,
  "shap_breakdown": [
    {"feature": "bl_velocity_pct", "contribution": 22, "direction": "negative"},
    {"feature": "enq_30d", "contribution": 15, "direction": "negative"}
  ],
  "intervention_hint": "Suggest national buyer expansion + gifted lead from different geography"
}
```

**Fallback:** If reason_tags is empty → `rca_category="UNKNOWN"`, confidence=0.1

---

#### SKILL 3: PeerBenchmarkSkill

**File:** `skills/peer_benchmark_skill.py`
**Purpose:** Compare seller metrics against peers in same enterprise_type + ctype group.

**Inputs:**
```json
{
  "glid": "string",
  "enterprise": "Proprietor",
  "ctype": "CATALOG",
  "enq_30d": 3,
  "active_days_30d": 5,
  "cqs": 45,
  "pns_success_pct": 55,
  "peer_benchmarks": {}
}
```

**Outputs:**
```json
{
  "peer_group": "Proprietor|CATALOG",
  "peer_n": 42,
  "enq_delta_abs": -5,
  "enq_delta_pct": -62.5,
  "enq_percentile": 18,
  "cqs_delta_abs": -23,
  "cqs_percentile": 12,
  "active_days_percentile": 22,
  "peer_median_enq": 8,
  "peer_p75_enq": 14,
  "peer_summary_line": "Peers in Proprietor|CATALOG get avg 8 leads/month. You got 3.",
  "gap_severity": "high"
}
```

**Fallback:** If peer group has < 5 sellers → use enterprise-level average.

---

#### SKILL 4: DemandIndexSkill

**File:** `skills/demand_index_skill.py`
**Purpose:** Assess buyer demand health in seller's category and city.

**Inputs:**
```json
{
  "glid": "string",
  "city": "Lucknow",
  "enterprise": "Proprietor",
  "ctype": "CATALOG",
  "total_bl_market": 340,
  "total_paid_market": 28,
  "monthly_enq": [8, 7, 6, 5, 4, 3]
}
```

**Logic:**
- Market BL per seller = total_bl_market / max(total_paid_market, 1)
- Trend direction = slope of monthly_enq (linear regression over 6 months)
- High-risk cities: Lucknow, Kanpur, Saharanpur, Surat, Jaipur (+15 risk points)
- High-risk categories: Apparel, Textiles (Proprietor + CATALOG)

**Outputs:**
```json
{
  "demand_index": 42,
  "demand_tier": "Amber",
  "market_bl_per_seller": 12.1,
  "trend": "declining",
  "trend_slope": -0.8,
  "is_high_risk_city": true,
  "city_risk_prior": 15,
  "demand_explanation": "Market has 12 BLs per paid seller but trend is declining.",
  "recommended_action": "Suggest national geography expansion"
}
```

---

#### SKILL 5: OnboardingHealthSkill

**File:** `skills/onboarding_health_skill.py`
**Purpose:** 5-check onboarding health assessment for new sellers (account_age_days ≤ 90).

**Inputs:**
```json
{
  "glid": "string",
  "account_age_days": 45,
  "city": "Kanpur",
  "enterprise": "Proprietor",
  "ctype": "CATALOG",
  "cqs": 52,
  "enq_30d": 0,
  "replied_30d": 0,
  "paid_history": false,
  "rag": "Green",
  "demand_index_result": {},
  "peer_benchmark_result": {}
}
```

**Checks:**
1. **Category Demand** (30%): demand_tier → Green/Amber/Red
2. **Business Verification** (15%): paid_history=true AND rag ≠ Red
3. **Peer Benchmark Gap** (15%): enq_percentile vs peer group
4. **First BL Response** (20%): replied_30d > 0 within first 30d
5. **Package Type** (20%): CATALOG/FCP+PNS = lower risk, FREELIST = higher early-churn risk

Score: 0–100. High-risk city/category adds +15 flat.

**Outputs:**
```json
{
  "onboarding_score": 68,
  "onboarding_risk": "Red",
  "check_results": {
    "demand": {"score": 30, "tier": "Amber", "note": "Low local demand"},
    "verification": {"score": 0, "tier": "Red", "note": "No paid history"},
    "peer_gap": {"score": 8, "tier": "Red", "note": "0 enquiries vs peer median 8"},
    "first_bl_response": {"score": 0, "tier": "Red", "note": "No response in 30d"},
    "package_type": {"score": 12, "tier": "Amber", "note": "CATALOG"}
  },
  "trigger_action": "HUMAN_CALL_24H",
  "call_script_hint": "Setup call: Lead management on mobile. Frame as activation, not sales."
}
```

---

#### SKILL 6: WhatsAppMessageSkill

**File:** `skills/whatsapp_message_skill.py`
**Purpose:** Generate personalized WhatsApp message from RCA + peer benchmark data.

**Inputs:**
```json
{
  "glid": "string",
  "company": "Ramesh Textiles",
  "seller_name": "Ramesh",
  "city": "Ahmedabad",
  "enterprise": "Proprietor",
  "rca_category": "NO_LEADS",
  "rca_explanation_hi": "...",
  "peer_delta_pct": -62,
  "peer_median_enq": 8,
  "enq_30d": 3,
  "cqs": 45,
  "days_to_renewal": null,
  "message_type": "retention_nudge",
  "llm_reasoning": "..."
}
```

**Message types:** `retention_nudge`, `onboarding_welcome`, `monthly_to_annual`, `winback`, `renewal_reminder`

**Templates per RCA category (Hindi-primary):**

`NO_LEADS`:
```
Ramesh Bhai, aapka account review kiya maine —
aapki category mein national buyers (Delhi, Mumbai) actively
search kar rahe hain abhi. Local se zyada reach milegi.
Ek setting change 2 min mein kar dete hain? 📱
```

`LOW_ENGAGEMENT`:
```
Ramesh Bhai, aapke 3 leads last week respond nahi hue —
koi notification issue toh nahi aaya? Mobile pe setup
karein saath mein, 5 minute mein ho jaata hai. 🔔
```

`POOR_CATALOG`:
```
Ramesh Bhai, aapke peer sellers jo zyada leads le rahe hain
unka ek simple difference hai — 7 extra product photos.
Aapka CQS {cqs} hai, {peer_cqs} tak laane se leads ~30% badhti hain.
```

`PEER_GAP`:
```
Ramesh Bhai, aapki city mein ek seller same category mein
last month {peer_median_enq} leads le gaya. Aapko {enq_30d} mili.
Woh ek specific cheez kar raha hai — bataaun? 👇
```

**Outputs:**
```json
{
  "message_hi": "...",
  "message_en": "...",
  "message_type": "retention_nudge",
  "rca_used": "NO_LEADS",
  "personalization_vars": ["city", "peer_median_enq", "enq_30d"],
  "cta": "Call back / Reply YES for settings help",
  "estimated_open_rate": 0.72
}
```

**Fallback:** If rca_category is UNKNOWN → generic engagement message.

---

#### SKILL 7: PreCallBriefSkill

**File:** `skills/pre_call_brief_skill.py`
**Purpose:** Generate rep-ready pre-call brief (30-second read) for Red-tier sellers.

**Inputs:**
```json
{
  "glid": "string",
  "company": "Ramesh Textiles",
  "city": "Ahmedabad",
  "enterprise": "ME",
  "ctype": "FCP+PNS",
  "churn_score": 78,
  "risk": "Red",
  "rca_category": "BL_DECLINE",
  "rca_explanation_en": "...",
  "peer_delta_pct": -55,
  "enq_30d": 2,
  "bl_velocity_pct": -40,
  "pns_success_pct": 48,
  "cqs": 61,
  "active_days_30d": 3,
  "account_age_days": 380,
  "hotleads_count": 0,
  "gifted_lead": null,
  "days_to_renewal": 45,
  "llm_risk_level": "Very High",
  "llm_bands": {"bl": "R", "lms": "A", "activity": "R"},
  "llm_reasoning": "...",
  "churned_lookalikes": [102449301, 60110967, 92870390],
  "retained_lookalikes": [9149400, 11282573, 41584202]
}
```

**Outputs:**
```json
{
  "brief_html": "...",
  "brief_text": "...",
  "opening_line_hi": "Ramesh Bhai, maine aapka account dekha — last month leads 40% kam ho gayi hain.",
  "opening_line_en": "Ramesh ji, leads dropped 40% last month. There's a specific reason I can explain.",
  "key_signals": [
    {"label": "Churn Score", "value": "78/100", "severity": "critical"},
    {"label": "AI Risk Level", "value": "Very High (cohort match)", "severity": "critical"},
    {"label": "BL Drop", "value": "-40% MoM", "severity": "critical"},
    {"label": "Peer Gap", "value": "-55% vs peers", "severity": "high"},
    {"label": "PNS Rate", "value": "48%", "severity": "high"}
  ],
  "suggested_actions": [
    "Fix PNS notification setup on mobile",
    "Suggest national geography expansion",
    "Offer gifted lead if available"
  ],
  "do_not_mention": ["renewal price", "subscription cost"],
  "call_type": "RETENTION",
  "estimated_call_duration": "8-12 min"
}
```

**HTML:** Card-format brief. Dark theme, mobile-first. UUID-linked, no login required.

---

#### SKILL 8: ScriptGenerationSkill

**File:** `skills/script_generation_skill.py`
**Purpose:** Generate full call script for human rep, routed by RCA.

**Inputs:**
```json
{
  "glid": "string",
  "rca_category": "NO_LEADS",
  "seller_name": "Ramesh",
  "company": "Ramesh Textiles",
  "city": "Ahmedabad",
  "enterprise": "Proprietor",
  "call_type": "RETENTION",
  "peer_median_enq": 8,
  "enq_30d": 2,
  "bl_velocity_pct": -40,
  "gifted_lead": {},
  "days_to_renewal": 45,
  "language": "hi",
  "llm_reasoning": "...",
  "llm_risk_level": "Very High"
}
```

**Script structure (5 parts):**
1. **Opening** — genuine check-in, not sales
2. **Diagnostic** — RCA-specific discovery question
3. **Value demonstration** — specific data point / gifted lead reveal
4. **Action** — one specific committed next step
5. **Close** — no renewal mention (only if seller raises it)

**Outputs:**
```json
{
  "script_parts": {
    "opening": "Ramesh Bhai, main aapke account dekh raha tha — kuch interesting chal raha hai. Ek minute hai?",
    "diagnostic": "Maine dekha leads kum aa rahi hain. Aap Delhi/Mumbai ke buyers tak reach kar sakte ho — kya try kiya?",
    "value_demo": "Aapke jaise ek seller ne geography expand ki — 8 se 14 leads ho gayi.",
    "gifted_lead_reveal": "Ek specific buyer hai abhi — Delhi se Cotton Fabric, 45,000 order value.",
    "action": "Main abhi setting change kar deta hoon — 2 minute.",
    "close": "Renewal ke baare mein pressure nahi hai. Pehle yeh lead pursue karo."
  },
  "objection_handlers": {
    "competitor_platform": "Bhai, serious buyers [category] mein specifically IM use karte hain.",
    "price_too_high": "Bhai, ek lead se ek order bhi aaya toh ROI positive hai.",
    "no_time": "Bilkul samajh aata hai — ek specific setting without login bhi check ho sakti hai."
  },
  "language": "hi",
  "rca_used": "NO_LEADS",
  "estimated_duration_min": 10
}
```

---

#### SKILL 9: GiftedLeadSkill

**File:** `skills/gifted_lead_skill.py`
**Purpose:** Select qualifying gifted Buy Lead for at-risk seller from hotleads pool.

**Qualification criteria (all 4 must pass):**
1. Posted within last 72 hours
2. Buyer has prior purchase history (`paid_history` signal)
3. Order value ≥ seller's historical average
4. Not yet distributed to maximum sellers

**Additional routing by RCA:**
- `NO_LEADS` → prefer lead from different geography than seller's city
- `LOW_ENGAGEMENT` → prefer high-urgency lead with short response window
- `PEER_GAP` → prefer lead that top peers received
- `POOR_CATALOG` → prefer lead where buyer requested detailed catalog

**Outputs (found):**
```json
{
  "lead_found": true,
  "lead_id": "HL_20260515_001",
  "buyer_city": "Delhi",
  "product": "Cotton Fabric",
  "order_qty": "500 meters",
  "order_value": 45000,
  "buyer_verified": true,
  "urgency": "high",
  "posted_hours_ago": 18,
  "follow_up_schedule": "2026-05-17"
}
```

**Outputs (not found):**
```json
{
  "lead_found": false,
  "reason": "No leads within 72h meeting quality gate",
  "fallback": "Use peer comparison data as value demonstration"
}
```

---

#### SKILL 10: CallSummarySkill

**File:** `skills/call_summary_skill.py`
**Purpose:** Parse call transcript → 3-line summary + updated RCA + next action.

**Eliminates 15–20 min post-call admin per call.**

**Inputs:**
```json
{
  "glid": "string",
  "transcript": "Rep: Ramesh Bhai... Seller: Haan bhai leads nahi aa rahi...",
  "call_type": "RETENTION",
  "pre_call_rca": "NO_LEADS",
  "call_date": "2026-05-15"
}
```

**Outputs:**
```json
{
  "summary_lines": [
    "Seller confirmed lead volume concern — agreed geography was limiting.",
    "Rep explained national buyer expansion, seller receptive.",
    "Gifted lead shared — seller will respond within 48h."
  ],
  "sentiment": "positive",
  "updated_rca": "NO_LEADS",
  "stated_concern": "Low lead volume from local city",
  "next_action": "FOLLOW_UP_48H",
  "next_action_detail": "Check if seller responded to gifted lead",
  "crm_entry": {
    "call_outcome": "ENGAGED",
    "next_step": "Follow up 2026-05-17",
    "notes": "Seller agreed to try national geography. Lead shared."
  },
  "churn_risk_updated": "Amber",
  "confidence": 0.82
}
```

---

#### SKILL 11: WinbackPrioritySkill

**File:** `skills/winback_priority_skill.py`
**Purpose:** Score churned sellers for winback team prioritization.

**Note:** The 146 churned sellers in `cohort.csv` are eligible for winback scoring and can be cross-referenced against current demand data.

**Inputs:**
```json
{
  "glid": "string",
  "churn_reason": "NO_LEADS",
  "churn_date": "2025-11-15",
  "account_age_days": 540,
  "enterprise": "ME",
  "ctype": "CATALOG",
  "historical_enq": 12,
  "current_demand_index": 78,
  "days_since_churn": 181,
  "cool_off_days_required": 180,
  "paid_history": true
}
```

**Priority score formula:**
```
winback_score = (
  historical_lead_quality × 0.30 +
  current_demand_index    × 0.35 +
  recoverability_score    × 0.25 +
  recency_bonus           × 0.10
)
```

**Recoverability by reason:**
| Churn Reason | Recoverability |
|---|---|
| NO_LEADS (demand now improved) | 90 |
| POOR_CATALOG (fixable) | 75 |
| BL_DECLINE | 60 |
| PRICE_ROI | 50 |
| COMPETITOR_PLATFORM | 45 |
| NOT_GIVING_TIME | 15 |
| BUSINESS_CLOSED | 5 |

**Outputs:**
```json
{
  "winback_score": 74,
  "priority": "HIGH",
  "cool_off_elapsed": true,
  "winback_pitch_type": "DEMAND_IMPROVED",
  "opening_line_hi": "Bhai, aap tab chale gaye the jab leads nahi aa rahi thi. Maine aaj check kiya — aapki category mein abhi [X] active buyers hain.",
  "gifted_lead_eligible": true,
  "estimated_conversion_probability": 0.28
}
```

---

#### SKILL 12: BLUpgradeSkill

**File:** `skills/bl_upgrade_skill.py`
**Purpose:** Identify sellers eligible for BL tier upgrade.

**Mode A — At-Risk Retention:**
- Trigger: churn_score ≥ 70 AND days_to_renewal ≤ 15 AND nudge_response=False
- Action: Flag for 3–5 BLs from next tier

**Mode B — Monthly-to-Annual Conversion:**
- Trigger: ctype == FREELIST AND account_age_days 25–35 AND active_days_30d ≥ 10 AND replied_30d > 0
- Action: Preview 2–3 Gold-tier leads + upgrade pitch

**Outputs:**
```json
{
  "eligible": true,
  "mode": "MONTHLY_TO_ANNUAL",
  "upgrade_leads_count": 3,
  "upgrade_message_hi": "Aap monthly pe hain — in leads tak access nahi. Annual pe switch karte hain toh yeh leads milenge.",
  "expected_conversion_uplift": 0.18,
  "action": "SEND_PREVIEW_LEADS"
}
```

---

#### SKILL 13: LLMCohortScorerSkill ← NEW

**File:** `skills/llm_cohort_scorer_skill.py`
**Purpose:** Score a seller against the 292-seller reference library using LLM-as-judge. Provides cohort-calibrated risk verdict with reasoning and behavioral lookalikes.

**Only runs for:** `account_age_days > 90` AND `snapshots.parquet` exists.

**Inputs:**
```json
{
  "glid": "string",
  "seller_dict": {},
  "snapshots_path": "seller_survival/data/snapshots.parquet",
  "mcat_embeddings_path": "seller_survival/data/mcat_embeddings.json",
  "model": "claude-sonnet-4-6"
}
```

**Processing:**
1. Extract Snapshot from seller_dict via `feature_schema.extract_snapshot()`
2. Filter library: `cohort_filter.filter_cohort(target.context, library)` → top 10 churned + top 10 retained
3. Build LLM prompt with target behavioral data + 20 cohort examples
4. Call Claude API (claude-sonnet-4-6) → parse strict JSON response
5. Apply composite rubric → risk_level
6. Compute confidence score (deterministic formula)

**Outputs:**
```json
{
  "risk_level": "Very High",
  "confidence_score": 64,
  "bands": {
    "bl": "R",
    "lms": "A",
    "activity": "R"
  },
  "reasoning": "Target consumed 5 of 142 BLs (3.5%) — retained sellers averaged 22%. Activity dropped from 42 (3-month) to 17 (30-day) — clear disengagement mirroring churned lookalikes.",
  "churned_lookalikes": [102449301, 60110967, 92870390],
  "retained_lookalikes": [9149400, 11282573, 41584202],
  "cohort_match": {
    "n_filtered": 28,
    "tier": "medium",
    "shown_to_llm": 20
  },
  "snapshot_context": {
    "turnover": "0 - 40 L",
    "city": "New Delhi",
    "state": "Delhi NCR",
    "mcats": ["Cotton Fabric", "Textiles"],
    "custtype": "Trader - Retailer"
  },
  "pipeline_tier": "Red"
}
```

**Fallback:**
- If `snapshots.parquet` missing → `used_fallback=true`, `risk_level=null`, skip LLM call
- If LLM response fails to parse → use rule-based tier only
- If cohort match < 5 sellers → relax threshold to 0.25, flag `loose_match=true`

**Prompt caching:** System prompt is static per run — qualify for Anthropic prompt caching to reduce cost on large GLID sets.

---

## 5. Phase 1 — Onboarding Health Check

**Scope:** Sellers with `account_age_days ≤ 90`
**Entry point:** `phases/phase1_onboarding.py`

*Note: LLMCohortScorerSkill does NOT run for new sellers — the reference library is built from established sellers and would not calibrate correctly for the onboarding context.*

### 5.1 Check 1: Category Demand Verification

- **Skill:** `DemandIndexSkill`
- Data: `competitors_counts` + `scorecard_6m`
- High-risk cities: Lucknow, Kanpur, Saharanpur, Surat, Jaipur
- High-risk categories: Apparel, Textiles (Proprietor + CATALOG)
- **Trigger:** Red → `ONBOARDING_CALL_24H` | Amber → `WHATSAPP_NATIONAL_BUYERS`

### 5.2 Check 2: Business Legitimacy

- Data: `composite` (paid_history, rag_category)
- Verified = paid_history=True AND rag ≠ Red
- **Trigger:** Red → `CALL_DOCUMENTATION_SUPPORT` | Amber → `WHATSAPP_DOCUMENTATION_REMINDER`

### 5.3 Check 3: Peer Benchmark Setting

- **Skill:** `PeerBenchmarkSkill`
- Use pre-computed `peer_benchmarks.json`
- Flag if sales promise > 2× peer median → `EXPECTATION_GAP_FLAG`

### 5.4 Check 4: First BL Response Signal

- Data: `scorecard_summary` (enq_30d, replied_30d) + `activity` (event_count)
- Fast (replied, high activity) → Green
- Slow (replied, low activity) → Amber: `WHATSAPP_LEAD_COACHING`
- None (enq > 0, replied == 0) → Red: `CALL_LEAD_SETUP_24H`

### 5.5 Check 5: Monthly vs Annual Package

- FREELIST → `MONTHLY_TRACK_EARLY_LIFE`
- CATALOG/FCP+PNS → `ANNUAL_TRACK_STANDARD`

### 5.6 Composite Onboarding Score

```python
onboarding_score = (
  demand_score      * 0.30 +
  city_risk_prior   * 0.20 +
  verification_score * 0.15 +
  peer_gap_score    * 0.15 +
  first_bl_score    * 0.20
)
```

**Output:** `runs/{run_id}/analysis/onboarding_assessments.json`

### 5.7 Error Handling — Phase 1

| Error | Handling |
|-------|----------|
| composite API missing | Skip verification, score sub-component as 0 |
| competitors_counts missing | Demand index = null, use enterprise averages |
| Account age unknown | Treat as established (skip Phase 1) |
| All checks null | Flag `DATA_INSUFFICIENT`, exclude from report |

---

## 6. Phase 2 — Dual-Track Churn Predictor

**Entry point:** `phases/phase2_predictor.py`

### 6.1 Model A — Early-Life Churn (Monthly Sellers, Days 30–90)

**Filter:** `ctype == FREELIST AND account_age_days <= 90`

| Feature | Source | Signal |
|---------|--------|--------|
| First EMI completion | composite.paid_history | Core predictor |
| Days since last login | activity.events (latest) | Engagement |
| First BL response | scorecard_summary.replied_30d > 0 | Early retention |
| BL consumption rate | bl_cons_30d / enq_30d | Engagement |
| Onboarding risk score | Phase 1 output | Carry-forward |
| Support call freq | scorecard_6m.pns_calls_recd | Frustration |

**Weights:**
- `paid_history=False` → +30
- `activity.last_seen` > 10d → +20
- `replied_30d == 0` AND `enq_30d > 0` → +18
- `bl_cons_30d == 0` → +15

### 6.2 Model B — Renewal Churn (Annual Sellers, Days -90 to Renewal)

**Filter:** `account_age_days > 90 AND ctype != FREELIST`

This model uses `ChurnScoringSkill` + `LLMCohortScorerSkill` together:

| Source | Signal |
|--------|--------|
| Rule-based churn_score | Current engagement degradation |
| LLM risk_level | Cohort-calibrated survival verdict |
| BL velocity drop % | Strongest renewal signal |
| Peer performance delta | Relative underperformance |

**Final Risk = max(rule_based_tier, llm_cohort_tier)**

### 6.3 SHAP Explanation Layer

Run `SHAPRCASkill` on every Red/Amber seller.
Run `LLMCohortScorerSkill` on every established Red/Amber seller.

**LLM cohort output consumed by:**
- `PreCallBriefSkill` (adds AI reasoning section to brief)
- `ScriptGenerationSkill` (uses reasoning to strengthen value demo)
- Master action plan (annotates each action with LLM confidence)
- Dashboard (shows lookalike GLIDs to rep as reference)

### 6.4 Daily Action Tiers

| Tier | Threshold | Action | Expected % |
|------|-----------|--------|-----------|
| Red | Rule ≥ 65 OR LLM Critical/Very High/High | Human caller + pre-call brief | 15-25% |
| Amber | Rule 35–64 OR LLM Moderate | Automated WhatsApp + nudge | 35-45% |
| Green | Rule < 35 AND LLM Low/Very Low | Monitoring only | 30-50% |

**Output:** `runs/{run_id}/analysis/action_tiers.json`

### 6.5 Error Handling — Phase 2

| Error | Handling |
|-------|----------|
| scorecard_6m missing | bl_velocity = null, skip component |
| LLMCohortScorerSkill fails | Use rule-based tier only, log fallback |
| Renewal date unknown | Estimate from account_age_days (365d cycles) |
| All signals null | Flag `UNSCOREABLE`, exclude from tiers |

---

## 7. Phase 3 — Three Parallel Retention Tracks

**Entry point:** `phases/phase3_retention.py`

### Track A: Seller Dashboard Comparison Engine

**Always-on for all sellers.**

**A1: Peer Performance Card**
- Anonymous top-3 performers in same enterprise + ctype group
- Metrics: monthly BL count, reply rate, active days, CQS
- Gap line: "You get 3 leads. Top performers get 14."

**A2: Gap Diagnosis with Fix Links**
```json
{
  "gap": "CQS 45 vs peer median 68",
  "fix": "Add 7 product photos",
  "impact": "+30% lead increase typical in this category",
  "action_link": "https://seller.indiamart.com/catalog/photos",
  "effort": "Low"
}
```

**A3: Progress Tracker**
Between runs: compare current vs previous `churn_signals.json`.
Show delta: "Your reply rate improved from 22% to 38%."

---

### Track B: Retention Nudge — Script + Gifted Lead

**Trigger:** Risk = Red or Amber, 30–60 days to predicted dropout.

**B1: Personalised Script** — `ScriptGenerationSkill`
- 5 variants: NO_LEADS / LOW_ENGAGEMENT / POOR_CATALOG / LOW_PNS / PEER_GAP
- LLM cohort reasoning woven into value demonstration section

**B2: AI Pre-Call Brief** — `PreCallBriefSkill`
- UUID-linked HTML card, mobile-first
- Includes LLM risk level + reasoning + churned/retained lookalike GLIDs

**B3: AI Call Summary + CRM Log** — `CallSummarySkill`
- Input: post-call transcript
- Output: 3-line summary + updated RCA + CRM entry JSON

**B4: Gifted Buy Lead** — `GiftedLeadSkill`
- Quality gate: 72h, buyer verified, value ≥ avg
- Routing by RCA
- 48h follow-up WhatsApp: "Bhai, us buyer se baat hui?"

**Output:** `runs/{run_id}/action_plans/{glid}_track_b.json`

---

### Track C: Winback — Post-Churn Re-engagement

**Trigger:** Cool-off elapsed (monthly: 6 months, annual: 3 months).
**Constraint:** Winback always pitches annual package only.

**C1: Winback Pool Prioritisation** — `WinbackPrioritySkill`
- The 146 churned sellers from `cohort.csv` seed this pool
- Additional churned sellers identified from run data
- Top 20% → High Priority

**C2: Reason-Routed Annual Pitch**
- `NO_LEADS` → "Demand improved since you left — here's proof"
- `LEAD_QUALITY` → "Setting issue is now fixed — let me show you"
- `PRICE_ROI` → "ROI calculator with real comps data"
- `COMPETITOR_PLATFORM` → "Buyers for your category come via IM specifically"

**C3: Gifted Lead as Re-entry**
Full contact, no obligation, before any renewal ask.

**Output:** `runs/{run_id}/action_plans/winback_pool.json`

### 7.1 Error Handling — Phase 3

| Error | Handling |
|-------|----------|
| hotleads pool empty | GiftedLeadSkill returns lead_found=false |
| Transcript missing | Skip CallSummarySkill, log manually |
| Language detection fails | Default to Hindi |
| LLM call fails in script gen | Use template without AI enrichment |
| Winback cool-off not elapsed | Skip Track C, flag for future run |

---

## 8. Phase 4 — Buy Lead Upgrade Engine

**Entry point:** `phases/phase4_bl_upgrade.py`

### 8.1 Mode A: At-Risk Seller BL Upgrade

- **Skill:** `BLUpgradeSkill (mode=AT_RISK)`
- Trigger: `churn_score ≥ 70 AND days_to_renewal ≤ 15 AND nudge_response=False`
- Action: Flag 3–5 BLs from next tier
- Additional trigger: LLM risk_level = Critical or Very High (regardless of rule score)

### 8.2 Mode B: Monthly-to-Annual Conversion

- **Skill:** `BLUpgradeSkill (mode=MONTHLY_TO_ANNUAL)`
- Trigger: `ctype == FREELIST AND account_age_days 25–35 AND active_days_30d ≥ 10`
- Preview: 2–3 Gold-tier leads

### 8.3 Lead Quality Gate (Non-Negotiable)

```python
def lead_qualifies(lead):
    return (
        lead.posted_hours_ago <= 72 and
        lead.buyer_verified == True and
        lead.order_value >= seller_avg_order_value and
        lead.current_distribution < lead.max_distribution
    )
```

If no qualifying lead → **do not fire Phase 4**.

**Output:** `runs/{run_id}/action_plans/bl_upgrade_flags.json`

---

## 9. Phase 5 — Renewal Window Boost

**Entry point:** `phases/phase5_renewal.py`
**Scope:** Annual sellers (CATALOG / FCP+PNS) only.

### 9.1 Pre-Renewal Lead Boost (Day -7)

- Unlock 3–5 higher-quality BLs for ALL annual sellers approaching renewal
- Message: "Aapki IM ke saath anniversary aa rahi hai — kuch special leads unlock ki hain."

### 9.2 Renewal Day Immediate Delivery

- At payment confirmation: push 1 fresh high-quality lead immediately
- Creates memory: "I just paid → I immediately got value"

### 9.3 Post-Renewal Reinforcement (Days +1 to +7)

- Elevated lead quality for 7 days post-renewal
- WhatsApp Day +3: "Aapki renewal ke baad kaisi chal rahi hain leads?"

**Output:** `runs/{run_id}/action_plans/renewal_boost_flags.json`

---

## 10. Cross-Cutting Systems

### 10.1 WhatsApp Delivery Cascade

**File:** `cross_cutting/delivery_cascade.py`

1. **WhatsApp** (primary) — `WhatsAppMessageSkill` output
2. **SMS fallback** — if unread after 48h
3. **IVR call** — if SMS unread after 72h
4. **Human PNS call** — final escalation for Red tier

### 10.2 Action Plan Aggregator

**File:** `cross_cutting/action_plan_aggregator.py`

```json
{
  "run_id": "run_20260515_120000",
  "red_sellers": [
    {
      "glid": "268280949",
      "company": "Ramesh Textiles",
      "churn_score": 78,
      "llm_risk_level": "Very High",
      "llm_confidence": 64,
      "rca": "NO_LEADS",
      "action": "HUMAN_CALL",
      "brief_url": "action_plans/268280949_brief.html",
      "gifted_lead": {},
      "priority_rank": 1
    }
  ],
  "summary": {
    "total_actions": 87,
    "human_calls_required": 22,
    "whatsapp_messages": 65,
    "llm_scored": 89,
    "llm_overrides_rule": 7,
    "gifted_leads_allocated": 18,
    "estimated_arr_at_risk": 330000
  }
}
```

### 10.3 Impact Dashboard

**File:** `cross_cutting/impact_dashboard.py`

`runs/{run_id}/impact_report.html`:
- Pinch metrics (Section 15)
- Estimated ARR at risk
- LLM vs rule-based tier agreement rate
- Rep productivity before vs after
- Winback potential ARR

---

## 11. seller_survival Package

**Location:** `seller_survival/` (beside `churn_analysis/`)

This package implements the LLM-as-judge cohort scoring. The `LLMCohortScorerSkill` in `churn_analysis/skills/` calls into this package.

### 11.1 Module Breakdown

```
seller_survival/
├── __init__.py                  ✅ BUILT
├── cohort_builder.py            ✅ BUILT — produces cohort.csv (292 GLIDs labeled)
├── slim_loader.py               # Fetch 3-4 endpoints per GLID + per-GLID JSON cache
├── feature_schema.py            # extract_snapshot(seller_dict) -> Snapshot
├── mcat_embeddings.py           # OpenAI text-embedding-3-small + disk cache
├── build_reference_library.py   # cohort.csv → slim_loader → snapshots.parquet
├── cohort_filter.py             # filter_cohort(target_context, library, k=10) -> (churned, retained)
├── llm_scorer.py                # prompt-build → Claude API → 3-band JSON → risk_level + confidence
├── cli.py                       # python -m seller_survival build|score <GLID>
└── data/
    ├── cohort.csv               ✅ generated (292 rows)
    ├── loader_cache/            # per-GLID JSON cache of raw loader output
    ├── mcat_embeddings.json     # cached embeddings keyed by lowercased mcat
    └── snapshots.parquet        # 292-seller reference library
```

### 11.2 Module Specifications

#### slim_loader.py

Fetches only the 3–4 endpoints needed for Snapshot extraction (not all 10 pipeline APIs):
- `composite` → custtype, turnover, city/state
- `scorecard_summary` → BL consumption, reply rate
- `scorecard_12m` → monthly_trend for activity
- `activity` → event counts

Caches output as `data/loader_cache/<glid>.json`. Reruns are instant.

Reuses from existing `data_sources/`:
- `api_client.py` → `build_api_client_session`, `fetch_all_for_glid_with_session`
- `ingestion_client.py` → ingestion overlay (composite endpoint → custtype/turnover)
- `context_client.py` → context overlay (kycdetails fallback)
- `api_transforms.py`, `ingestion_transforms.py`, `context_transforms.py`

#### feature_schema.py

```python
def extract_snapshot(seller_dict: dict, label: str = "target") -> Snapshot:
    """Project raw seller_dict to structured Snapshot."""
    context = {
        "turnover": seller_dict.get("GST turnover"),
        "city": seller_dict.get("Locality / City", "").split(",")[0].strip(),
        "state": seller_dict.get("Locality / City", "").split(",")[1].strip() if "," in seller_dict.get("Locality / City", "") else "",
        "mcats": seller_dict.get("mcats", []),
        "custtype": seller_dict.get("Custtype")
    }
    behavioral = {
        "bl": { ... },    # received_90d, consumed_90d, reply_rate, etc.
        "lms": { ... },   # call_attempts_90d, pickup_ratio, etc.
        "activity": { ... }  # activity_30d, monthly_trend, etc.
    }
    return Snapshot(glid=seller_dict["glid"], label=label, context=context, behavioral=behavioral)
```

#### mcat_embeddings.py

```python
# OpenAI text-embedding-3-small with disk cache
def embed_batch(mcats: list[str]) -> dict[str, list[float]]:
    """Embed a list of mcats. Cache keyed by lowercased mcat."""

def max_pairwise_cosine(mcats_a: list[str], mcats_b: list[str]) -> float:
    """Return max cosine similarity across all mcat pairs."""
```

#### cohort_filter.py

```python
def filter_cohort(target_context: dict, library: pd.DataFrame, k: int = 10) -> tuple:
    """
    Returns (churned_examples[:k], retained_examples[:k]).
    filter_score = (turnover_match + city_state_match + mcat_match + custtype_match) / 4
    Threshold: 0.5 (strict), relax to 0.25 if < 5 matches at strict.
    """
```

#### llm_scorer.py

```python
COMPOSITE_RUBRIC = {
    ("R","R","R"): "Critical",
    ("R","R","A"): "Very High", ("R","A","R"): "Very High", ("A","R","R"): "Very High",
    ("R","R","G"): "High",      ("R","G","R"): "High",      ("G","R","R"): "High",
    ("R","A","A"): "High",      ("A","R","A"): "High",      ("A","A","R"): "High",
    ("R","A","G"): "Moderate",  ("R","G","A"): "Moderate",  ("A","R","G"): "Moderate",
    ("A","G","R"): "Moderate",  ("G","R","A"): "Moderate",  ("G","A","R"): "Moderate",
    ("A","A","A"): "Moderate",
    ("R","G","G"): "Moderate",  ("G","R","G"): "Moderate",  ("G","G","R"): "Moderate",
    ("A","A","G"): "Low",       ("A","G","A"): "Low",       ("G","A","A"): "Low",
    ("A","G","G"): "Low",       ("G","A","G"): "Low",       ("G","G","A"): "Low",
    ("G","G","G"): "Very Low",
}

def score(target: Snapshot, churned: list[Snapshot], retained: list[Snapshot], model: str) -> dict:
    """Build prompt → call Claude API → parse bands → apply rubric → compute confidence."""
```

#### cli.py

```bash
# Build reference library (one-time)
python -m seller_survival build
# → enriches 292 GLIDs, writes snapshots.parquet

# Score a single GLID
python -m seller_survival score 27257635 --model claude-sonnet-4-6
# → prints scored JSON card

# Score with different model
python -m seller_survival score 27257635 --model claude-haiku-4-5-20251001
```

### 11.3 Environment Variables for seller_survival

| Variable | Purpose |
|----------|---------|
| `IM_INTERNAL_JWT` | MERP auth |
| `IM_EMPID` | MERP auth |
| `INGESTION_URL` | Ingestion API URL |
| `INGESTION_API_KEY` | Ingestion API key |
| `ANTHROPIC_API_KEY` | Claude API (LLM scorer) |
| `OPENAI_API_KEY` | text-embedding-3-small (mcat semantic match) |
| `DEEP_AGENT_USE_INGESTION=1` | Enable ingestion overlay |
| `DEEP_AGENT_USE_CONTEXT=1` | Enable context overlay |
| `DEEP_AGENT_USE_DB` | **Leave OFF** — Postgres creds not available |

### 11.4 Verification

```bash
# Smoke checks
python -c "from seller_survival.llm_scorer import COMPOSITE_RUBRIC; assert COMPOSITE_RUBRIC[('R','R','R')] == 'Critical' and COMPOSITE_RUBRIC[('G','G','G')] == 'Very Low'; print('rubric OK')"
python -c "from seller_survival.cohort_builder import build_cohort; r = build_cohort(); assert len(r) == 292; print('cohort OK')"

# End-to-end build
python -m seller_survival build
# Expected: 146 retained, 146 churned, snapshots.parquet written

# Score Cohort A seller (expect High/Very High/Critical)
python -m seller_survival score 27257635
```

---

## 12. File & Folder Structure

```
Hackathon/
├── glids.txt                              # Master GLID list (target sellers)
├── home.html                              # Homepage — all runs index
├── FINAL PLAN.md
├── implementation_plan.md                 # This file
│
├── seller_survival/                       # LLM Cohort Scoring Package
│   ├── __init__.py                        ✅ BUILT
│   ├── cohort_builder.py                  ✅ BUILT
│   ├── slim_loader.py                     # To build
│   ├── feature_schema.py                  # To build
│   ├── mcat_embeddings.py                 # To build
│   ├── build_reference_library.py         # To build
│   ├── cohort_filter.py                   # To build
│   ├── llm_scorer.py                      # To build
│   ├── cli.py                             # To build
│   └── data/
│       ├── cohort.csv                     ✅ BUILT (292 rows)
│       ├── loader_cache/                  # Per-GLID API cache (auto-created)
│       ├── mcat_embeddings.json           # Auto-created on first build
│       └── snapshots.parquet              # Auto-created on first build
│
├── churn_analysis/                        # Main pipeline directory
│   ├── pipeline.py                        ✅ EXISTING
│   ├── update_metrics.py                  ✅ EXISTING
│   ├── build_master_dashboard.py          ✅ EXISTING
│   ├── pre_analysis.py                    # NEW
│   │
│   ├── skills/                            # Agent Skills Layer
│   │   ├── __init__.py
│   │   ├── base_skill.py
│   │   ├── registry.py
│   │   ├── churn_scoring_skill.py         # SKILL 1
│   │   ├── shap_rca_skill.py              # SKILL 2
│   │   ├── peer_benchmark_skill.py        # SKILL 3
│   │   ├── demand_index_skill.py          # SKILL 4
│   │   ├── onboarding_health_skill.py     # SKILL 5
│   │   ├── whatsapp_message_skill.py      # SKILL 6
│   │   ├── pre_call_brief_skill.py        # SKILL 7
│   │   ├── script_generation_skill.py     # SKILL 8
│   │   ├── gifted_lead_skill.py           # SKILL 9
│   │   ├── call_summary_skill.py          # SKILL 10
│   │   ├── winback_priority_skill.py      # SKILL 11
│   │   ├── bl_upgrade_skill.py            # SKILL 12
│   │   └── llm_cohort_scorer_skill.py     # SKILL 13 — NEW
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   └── orchestrator.py
│   │
│   ├── phases/
│   │   ├── __init__.py
│   │   ├── phase1_onboarding.py
│   │   ├── phase2_predictor.py
│   │   ├── phase3_retention.py
│   │   ├── phase3_track_a.py
│   │   ├── phase4_bl_upgrade.py
│   │   └── phase5_renewal.py
│   │
│   ├── cross_cutting/
│   │   ├── __init__.py
│   │   ├── delivery_cascade.py
│   │   ├── action_plan_aggregator.py
│   │   └── impact_dashboard.py
│   │
│   ├── templates/
│   │   ├── pre_call_brief.html
│   │   ├── impact_report.html
│   │   └── pre_analysis_report.html
│   │
│   └── runs/
│       └── run_YYYYMMDD_HHMMSS/
│           ├── data/
│           │   └── {glid}/
│           │       ├── scorecard_summary.json
│           │       ├── scorecard_6m.json
│           │       ├── scorecard_12m.json
│           │       ├── composite.json
│           │       ├── product_summary.json
│           │       ├── hotleads.json
│           │       ├── metrics.json
│           │       ├── activity.json
│           │       ├── competitors.json
│           │       ├── competitors_counts.json
│           │       └── dashboard.html
│           │
│           ├── analysis/
│           │   ├── coverage_report.json          # includes llm_scorer_available flag
│           │   ├── baseline_distribution.json
│           │   ├── peer_benchmarks.json
│           │   ├── churn_signals.json
│           │   ├── onboarding_assessments.json
│           │   ├── action_tiers.json
│           │   └── skill_outputs/
│           │       └── {glid}_skills.json        # includes llm_cohort_scorer output
│           │
│           ├── action_plans/
│           │   ├── {glid}_action.json
│           │   ├── {glid}_brief.html             # includes LLM reasoning section
│           │   ├── {glid}_script.json
│           │   ├── winback_pool.json
│           │   ├── bl_upgrade_flags.json
│           │   ├── renewal_boost_flags.json
│           │   └── master_action_plan.json
│           │
│           ├── index.html
│           ├── master_dashboard.html
│           ├── impact_report.html
│           └── pre_analysis_report.html
```

---

## 13. Data Schemas

### 13.1 Seller Signal Dict (core, extended)

```json
{
  "glid": "string",
  "company": "string",
  "city": "string",
  "enterprise": "Proprietor | ME | BB | Partnership",
  "ctype": "CATALOG | FCP+PNS | FREELIST | LEADER | BL Paid | Other",
  "client_since": "YYYY-MM",
  "account_age_days": 380,
  "paid_history": true,
  "rag": "Red | Amber | Green",
  "rag_score": 42,
  "cqs": 68,
  "enq_30d": 5,
  "replied_30d": 3,
  "reply_rate_30d": 60.0,
  "active_days_30d": 8,
  "bl_cons_30d": 5,
  "bl_velocity_pct": -22.5,
  "pns_success_pct": 74.0,
  "pns_received_90d": 12,
  "pns_answered_90d": 9,
  "enq_received_90d": 18,
  "enq_replies_90d": 14,
  "meetings_90d": 2,
  "hotleads_count": 3,
  "event_count": 28,
  "last_seen": "2026-05-10",
  "total_bl_market": 480,
  "total_paid_market": 32,
  "monthly_enq": [8, 7, 9, 6, 4, 5],
  "monthly_labels": ["Dec 2025", "Jan 2026"],
  "monthly_pns": [4, 4, 3, 2, 1, 2],
  "churn_score": 48,
  "risk": "Amber",
  "churn_reasons": ["BL velocity declining: -22.5% MoM"],
  "reason_tags": ["BL_VELOCITY_DECLINING"],
  "score_breakdown": {"bl_velocity": 10},
  "llm_risk_level": "High",
  "llm_confidence": 72,
  "llm_bands": {"bl": "R", "lms": "A", "activity": "A"},
  "llm_reasoning": "...",
  "final_risk_tier": "Red"
}
```

### 13.2 Skill Output Schema (per seller, extended)

```json
{
  "glid": "string",
  "run_id": "string",
  "generated_at": "ISO timestamp",
  "skills_run": ["ChurnScoringSkill", "SHAPRCASkill", "LLMCohortScorerSkill"],
  "churn_scoring": {},
  "shap_rca": {},
  "peer_benchmark": {},
  "demand_index": {},
  "llm_cohort_scorer": {
    "risk_level": "Very High",
    "confidence_score": 64,
    "bands": {"bl": "R", "lms": "A", "activity": "R"},
    "reasoning": "...",
    "churned_lookalikes": [102449301, 60110967, 92870390],
    "retained_lookalikes": [9149400, 11282573, 41584202],
    "cohort_match": {"n_filtered": 28, "tier": "medium", "shown_to_llm": 20},
    "pipeline_tier": "Red"
  },
  "whatsapp_message": {},
  "pre_call_brief": {},
  "script": {},
  "gifted_lead": {},
  "bl_upgrade": {},
  "errors": [],
  "fallbacks_used": ["GiftedLeadSkill"]
}
```

### 13.3 Master Action Plan Schema

```json
{
  "run_id": "string",
  "generated_at": "ISO timestamp",
  "summary": {
    "total_sellers": 131,
    "red": 22,
    "amber": 65,
    "green": 44,
    "llm_scored": 89,
    "llm_upgraded_to_red": 7,
    "human_calls_queued": 22,
    "whatsapp_queued": 65,
    "gifted_leads_allocated": 14,
    "winback_eligible": 8,
    "bl_upgrades_flagged": 10,
    "estimated_arr_at_risk": 330000,
    "estimated_arr_saveable": 198000,
    "coverage_pct": 0.91
  },
  "action_queue": [
    {
      "priority": 1,
      "glid": "268280949",
      "company": "Ramesh Textiles",
      "churn_score": 78,
      "llm_risk_level": "Very High",
      "rca": "NO_LEADS",
      "action_type": "HUMAN_CALL",
      "urgency": "SAME_DAY",
      "brief_url": "action_plans/268280949_brief.html",
      "gifted_lead_available": true
    }
  ]
}
```

### 13.4 Coverage Report Schema (extended)

```json
{
  "run_id": "string",
  "total_glids": 131,
  "fully_scoreable": 118,
  "partially_scoreable": 9,
  "data_incomplete": 4,
  "llm_scorer_available": true,
  "reference_library_glids": 292,
  "reference_library_path": "seller_survival/data/snapshots.parquet",
  "api_success_rates": {
    "scorecard_summary": 0.94,
    "scorecard_6m": 0.91,
    "composite": 0.99,
    "product_summary": 0.87
  },
  "glid_coverage": {
    "268280949": {
      "coverage_score": 0.7,
      "coverage_tier": "partial",
      "failed_apis": ["metrics"]
    }
  }
}
```

---

## 14. Error Handling Strategy

### 14.1 Layered Error Architecture

```
Layer 1: API fetch errors           → retry once, store error, continue
Layer 2: Parse errors               → store raw, mark degraded, score conservatively
Layer 3: Skill errors               → call skill.fallback(), log, mark used_fallback=True
Layer 3b: LLM API errors            → use rule-based tier only, log LLM failure
Layer 4: Orchestrator errors        → skip seller, log to error_log.json, continue
Layer 5: Phase errors               → complete remaining phases, flag incomplete
Layer 6: Critical failures          → abort, preserve partial output
```

### 14.2 Retry Policy

```
API timeout:          retry once with timeout × 1.5
HTTP 429:             wait 5s, retry once
HTTP 5xx:             retry once after 2s
HTTP 4xx (not 429):   no retry
LLM API timeout:      retry once after 3s
LLM parse failure:    use rule-based only (no retry — don't waste tokens)
Max retries per GLID: 1 per API
```

### 14.3 Conservative Scoring Policy

- Missing `bl_velocity_pct` → treat as 0% (no penalty, no bonus)
- Missing `cqs` → skip CQS component (0 added)
- Missing `rag` → treat as "Unknown" (no penalty)
- Missing `enq_30d` → treat as 0 (apply NO_ENQUIRY_FLOW only if composite confirms activity)
- LLM call fails → use rule-based tier only, do NOT penalize seller

**Principle:** Never assign maximum-risk scores from missing data. Missing ≠ churned.

### 14.4 Skill Fallback Chains

| Skill | Fallback |
|-------|---------|
| LLMCohortScorerSkill | Use rule-based tier only; log `llm_scorer_skipped=true` |
| GiftedLeadSkill | Return peer comparison data as substitute |
| SHAPRCASkill | `rca_category="UNKNOWN"`, use generic script |
| PeerBenchmarkSkill | Enterprise-level averages if group < 5 |
| WhatsAppMessageSkill | Generic engagement template |
| PreCallBriefSkill | Minimal brief: score + top reason only |
| DemandIndexSkill | competitors_counts market data only |

### 14.5 Data Integrity Guards

```python
score = max(0, min(100, score))
reply_rate = round(rep/enq * 100, 1) if enq > 0 else 0
velocity = round((last - prev)/prev * 100, 1) if prev > 0 else 0
# default=str in json.dump — no None in JSON output
```

### 14.6 Error Log Format

```json
{
  "run_id": "run_20260515_120000",
  "errors": [
    {
      "glid": "268280949",
      "phase": "phase2_predictor",
      "skill": "LLMCohortScorerSkill",
      "api": "anthropic",
      "error_type": "parse_failure",
      "error_msg": "JSON decode error in LLM response",
      "action_taken": "using rule-based tier only",
      "timestamp": "2026-05-15T12:05:32"
    }
  ]
}
```

---

## 15. Impact Metrics & Pinch Metrics

### 15.1 Business Impact Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Earliest churn detection | Month 11 (renewal day) | Day 0 (onboarding score) | **New capability** |
| Intervention timing | Day 0 (renewal) | Day -90 | **90 days earlier** |
| Scoring method | Rule-based only | Rule + LLM cohort | **Calibrated against real churned/retained data** |
| WhatsApp open rate | 8-12% | 65-80% | **7-8×** |
| Rep pre-call prep | 15-20 min | 30 seconds | **~30× reduction** |
| Post-call CRM entry | 15-20 min | 0 (auto-logged) | **Complete elimination** |
| Rep calls per day | ~40 | ~80 | **2×** |
| Retention conversion | 40-50% (at cancellation) | 60-70% (90d earlier) | **1.5× on larger pool** |
| Winback conversion | 10-15% | 25-35% | **2-3×** |
| Winback team output | Baseline | 3× calls × 2.5× conversion | **~7.5-10×** |

### 15.2 Pinch Metrics (Hackathon Demo)

```
┌──────────────────────────────────────────────────────────────┐
│  HEADLINE: 10× ROI from winback team investment               │
├──────────────────────────────────────────────────────────────┤
│  Red Tier Sellers      : {n}  (immediate intervention)        │
│  Estimated ARR at Risk : Rs {n}  (Red × Rs 15k avg)          │
│  ARR Saveable (60% cr) : Rs {n}                              │
├──────────────────────────────────────────────────────────────┤
│  AI Cohort Scoring (NEW):                                     │
│  Reference library     : 292 sellers (146 retained/churned)   │
│  LLM scored this run   : {n} established sellers             │
│  LLM upgraded to Red   : {n} sellers (rule-based missed)     │
│  LLM confidence avg    : {n}%                                │
├──────────────────────────────────────────────────────────────┤
│  Sellers in Month 1-3 (newly identified cohort): {n}          │
│  → First time any system reaches these sellers               │
├──────────────────────────────────────────────────────────────┤
│  Rep productivity:                                            │
│  Before: 40 calls/day, 25 min prep+admin per call            │
│  After:  80 calls/day, 30 sec prep, 0 min admin              │
├──────────────────────────────────────────────────────────────┤
│  Primary RCA breakdown:                                       │
│  No Leads: {n}%  | Low Engagement: {n}%                      │
│  Poor Catalog: {n}% | Peer Gap: {n}% | Other: {n}%           │
└──────────────────────────────────────────────────────────────┘
```

### 15.3 Solution Completeness Checklist

| Feature | Status |
|---------|--------|
| ✅ Data pipeline (10 APIs, concurrent) | Built |
| ✅ 7-signal churn scoring | Built |
| ✅ Per-seller HTML dashboards | Built |
| ✅ Master analytics dashboard | Built |
| ✅ Run isolation | Built |
| ✅ Homepage across runs | Built |
| ✅ Cohort builder (292 sellers) | Built |
| ✅ cohort.csv (146 retained / 146 churned) | Built |
| 🔲 seller_survival: slim_loader | To build |
| 🔲 seller_survival: feature_schema | To build |
| 🔲 seller_survival: mcat_embeddings | To build |
| 🔲 seller_survival: build_reference_library | To build |
| 🔲 seller_survival: cohort_filter | To build |
| 🔲 seller_survival: llm_scorer | To build |
| 🔲 seller_survival: cli | To build |
| 🔲 Pre-analysis + coverage report | To build |
| 🔲 Peer benchmark pre-computation | To build |
| 🔲 Skills architecture (base_skill + registry) | To build |
| 🔲 SKILL 1: ChurnScoringSkill | To build |
| 🔲 SKILL 2: SHAPRCASkill | To build |
| 🔲 SKILL 3: PeerBenchmarkSkill | To build |
| 🔲 SKILL 4: DemandIndexSkill | To build |
| 🔲 SKILL 5: OnboardingHealthSkill | To build |
| 🔲 SKILL 6: WhatsAppMessageSkill | To build |
| 🔲 SKILL 7: PreCallBriefSkill | To build |
| 🔲 SKILL 8: ScriptGenerationSkill | To build |
| 🔲 SKILL 9: GiftedLeadSkill | To build |
| 🔲 SKILL 10: CallSummarySkill | To build |
| 🔲 SKILL 11: WinbackPrioritySkill | To build |
| 🔲 SKILL 12: BLUpgradeSkill | To build |
| 🔲 SKILL 13: LLMCohortScorerSkill | To build |
| 🔲 Agent orchestrator | To build |
| 🔲 Phase 1 onboarding assessment | To build |
| 🔲 Phase 2 dual-track predictor | To build |
| 🔲 Phase 3 Track A peer card | To build |
| 🔲 Phase 3 Track B nudge engine | To build |
| 🔲 Phase 3 Track C winback pool | To build |
| 🔲 Phase 4 BL upgrade flags | To build |
| 🔲 Phase 5 renewal boost flags | To build |
| 🔲 Master action plan aggregator | To build |
| 🔲 Impact dashboard | To build |

### 15.4 Solution Robustness

| Dimension | Implementation |
|-----------|----------------|
| API failures | Graceful skip, conservative scoring |
| LLM failures | Fall back to rule-based tier, never block pipeline |
| Cohort miss | Relax threshold to 0.25, flag loose_match |
| Missing data | Never crash — degrade confidence, flag incomplete |
| Timeout resilience | 25s API + 1 retry; 30s LLM + 1 retry |
| JSON safety | `default=str`, `safe_parse()` for nested strings |
| Score bounds | Hard cap 0-100, tier always defined |
| Skill fallbacks | Every skill has `fallback()` method |
| Run isolation | Each run in own directory, no shared state |

---

## 16. Implementation Sequence

### Stage 0: Reference Library + Foundation (Day 1, Morning)

**Goal:** seller_survival package working + skills architecture ready.

1. Build `seller_survival/slim_loader.py` (cache-first, 3-4 endpoints)
2. Build `seller_survival/feature_schema.py` (`extract_snapshot()`)
3. Build `seller_survival/mcat_embeddings.py` (OpenAI embed + disk cache)
4. Build `seller_survival/build_reference_library.py` (cohort.csv → snapshots.parquet)
5. Run `python -m seller_survival build` → verify 292 snapshots written
6. Create `skills/` with `base_skill.py` + `registry.py`
7. Port `compute_signals()` into `ChurnScoringSkill`
8. Build `SHAPRCASkill` (rule-based RCA)

**Deliverable:** `python -m seller_survival build` completes. `ChurnScoringSkill` + `SHAPRCASkill` work standalone.

### Stage 1: LLM Cohort Scorer + Peer Benchmark (Day 1, Afternoon)

**Goal:** LLM scoring works end-to-end on a single GLID.

9. Build `seller_survival/cohort_filter.py`
10. Build `seller_survival/llm_scorer.py` (COMPOSITE_RUBRIC + Claude API call)
11. Build `seller_survival/cli.py` → test `python -m seller_survival score 27257635`
12. Build `skills/llm_cohort_scorer_skill.py` (wraps seller_survival into Skill interface)
13. Build `PeerBenchmarkSkill` + pre-computation in `pre_analysis.py`
14. Build `DemandIndexSkill`

**Deliverable:** `python -m seller_survival score 27257635` returns scored JSON. GLID 27257635 (Cohort A churned) scores High/Very High/Critical.

### Stage 2: Core Action Skills + Orchestrator (Day 1–2)

**Goal:** Every seller gets action output.

15. Build `coverage_check.py` + `pre_analysis_report.html`
16. Build `WhatsAppMessageSkill` (5 RCA × 5 message types)
17. Build `PreCallBriefSkill` + brief HTML template (includes LLM reasoning section)
18. Build `ScriptGenerationSkill` (5 RCA routes, Hindi primary)
19. Build `GiftedLeadSkill` (quality gate + RCA routing)
20. Build `agent/orchestrator.py` (routes seller through skill chain, computes final_tier)
21. Integrate orchestrator into `pipeline.py` after `compute_signals()`

**Deliverable:** Every Red/Amber seller gets `{glid}_brief.html` + WhatsApp message + LLM cohort score in `action_plans/`.

### Stage 3: Phases 1 + 2 (Day 2)

**Goal:** Onboarding + dual-track predictor visible in dashboard.

22. Build `phase1_onboarding.py` + add onboarding card to `dashboard.html`
23. Build `phase2_predictor.py` — early-life vs renewal split + LLM cohort integration
24. Add `early_life_risk`, `renewal_risk`, `llm_risk_level` to `churn_signals.json`
25. Add `action_tiers.json` output
26. Update `master_dashboard.html` — Phase 1 cohort + Phase 2 tier breakdown + LLM summary

### Stage 4: Retention Tracks + Winback (Day 2–3)

**Goal:** Full retention + winback with gifted lead.

27. Build `phase3_retention.py` + `phase3_track_a.py`
28. Build `WinbackPrioritySkill` → `winback_pool.json` (seeded from cohort.csv churned GLIDs)
29. Build `CallSummarySkill` (demo on sample transcript)
30. Build `delivery_cascade.py`

### Stage 5: Impact + Polish (Day 3)

**Goal:** Demo-ready.

31. Build `impact_dashboard.py` + `impact_report.html` (includes LLM cohort stats)
32. Build `action_plan_aggregator.py` → `master_action_plan.json`
33. Build `phase4_bl_upgrade.py` + `phase5_renewal.py`
34. Full end-to-end test on existing GLID set
35. Polish `home.html` — links to impact report + pre-analysis report

### Hackathon Demo Flow

```
0. python -m seller_survival build          → reference library (one-time)
1. Upload glids.txt
2. python pre_analysis.py glids.txt         → coverage report + library check
3. python pipeline.py glids.txt            → all dashboards + action plans + LLM scoring
4. Open home.html                           → run homepage
5. Open impact_report.html                  → pinch metrics, LLM cohort stats, ARR at risk
6. Open master_dashboard.html              → segment breakdown
7. Open action_plans/268280949_brief.html  → rep pre-call brief (with LLM reasoning)
8. Show WhatsApp message for seller        → personalized Hindi script
9. python -m seller_survival score 27257635 → live LLM scoring demo
10. Show winback_pool.json ranking          → prioritized recovery list
```

---

## 17. Web UI — GLID Scorer Interface

**Purpose:** A browser-based interface where the user enters a GLID and sees the full pipeline run in real-time — churn score, LLM cohort verdict, RCA, action plan, WhatsApp message, pre-call brief, and call script — without touching the terminal.

**Stack:** Flask backend + plain HTML/JS frontend (no React, no build step). Runs locally.

**File:** `churn_analysis/app.py`

---

### 17.1 Architecture

```
Browser (scorer.html)
  │
  │  POST /score  { glid: "268280949" }
  │  ← SSE stream (text/event-stream)
  │    event: step_start   { step: "ChurnScoringSkill" }
  │    event: step_done    { step: "ChurnScoringSkill", result: {...} }
  │    event: step_start   { step: "LLMCohortScorerSkill" }
  │    event: step_done    { step: "LLMCohortScorerSkill", result: {...} }
  │    ...
  │    event: complete     { action_plan: {...}, brief_url: "..." }
  │
Flask app.py
  ├── GET  /               → serves scorer.html
  ├── POST /score          → validates GLID, starts pipeline thread, returns SSE stream
  ├── GET  /brief/<glid>   → serves {glid}_brief.html from action_plans/
  ├── GET  /status         → returns { library_ready: bool, last_run: "..." }
  └── GET  /runs           → lists all run directories for history dropdown
```

---

### 17.2 UI Pages

#### Page 1: Scorer (main page — `scorer.html`)

```
┌─────────────────────────────────────────────────────────────────┐
│  IndiaMART Seller Intelligence                        [History ▾]│
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Enter Seller GLID                                              │
│   ┌──────────────────────────────────┐  ┌──────────────────┐   │
│   │  268280949                       │  │   Analyse Seller  │   │
│   └──────────────────────────────────┘  └──────────────────┘   │
│                                                                  │
│   ● Reference library: Ready (292 sellers)                       │
│                                                                  │
├──────────── PROGRESS (appears after submit) ────────────────────┤
│                                                                  │
│   ✅ Fetching APIs (10/10)                         0.8s         │
│   ✅ Computing signals                             0.1s         │
│   ✅ ChurnScoringSkill          score: 72, Red    0.1s         │
│   ✅ SHAPRCASkill               rca: NO_LEADS     0.1s         │
│   ✅ PeerBenchmarkSkill         gap: -55%         0.1s         │
│   ✅ DemandIndexSkill           tier: Amber       0.1s         │
│   ⏳ LLMCohortScorerSkill       calling Claude…               │
│   ○  GiftedLeadSkill                                            │
│   ○  PreCallBriefSkill                                          │
│   ○  ScriptGenerationSkill                                      │
│   ○  WhatsAppMessageSkill                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Page 2: Results (same page, scrolls in after complete)

```
┌─────────────────────────────────────────────────────────────────┐
│  GLID: 268280949 — Ramesh Textiles, Ahmedabad           [Red ●] │
├────────────────────────┬────────────────────────────────────────┤
│  Rule Score: 72/100    │  AI Cohort Risk: Very High             │
│  RCA: NO_LEADS         │  AI Confidence: 64%                    │
│  Final Tier: RED       │  Bands: BL=R  LMS=A  Activity=R       │
├────────────────────────┴────────────────────────────────────────┤
│  [Pre-Call Brief]  [WhatsApp Msg]  [Call Script]  [Raw JSON]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TAB: Pre-Call Brief                                             │
│  ─────────────────────────────────────────────                  │
│  Opening line (Hindi):                                           │
│  "Ramesh Bhai, maine aapka account dekha — last month leads     │
│   40% kam ho gayi hain. Ek specific reason hai..."              │
│                                                                  │
│  AI Reasoning:                                                   │
│  "Target consumed 5/142 BLs (3.5%). Retained peers avg 22%.    │
│   Activity dropped 42→17. Mirrors churned seller 102449301."    │
│                                                                  │
│  Key Signals:                                                    │
│  ● Churn Score    72/100          CRITICAL                       │
│  ● AI Risk        Very High       CRITICAL                       │
│  ● BL Velocity   -40% MoM        CRITICAL                       │
│  ● Peer Gap      -55%            HIGH                           │
│  ● PNS Rate       48%            HIGH                           │
│  ● Active Days    3/30           HIGH                           │
│                                                                  │
│  Gifted Lead Available:                                          │
│  Delhi buyer · Cotton Fabric · 500m · ₹45,000 · Posted 18h ago │
│                                                                  │
│  Do NOT mention: renewal price, subscription cost               │
│                                                                  │
│  [Open Full Brief HTML ↗]                                       │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  TAB: WhatsApp Message                                           │
│  ─────────────────────────────────────────────                  │
│  Ramesh Bhai, aapka account review kiya maine —                 │
│  aapki category mein national buyers (Delhi, Mumbai)            │
│  actively search kar rahe hain abhi. Local se zyada            │
│  reach milegi. Ek setting change 2 min mein? 📱                 │
│                                                                  │
│  [Copy to clipboard]                                             │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  TAB: Call Script                                                │
│  ─────────────────────────────────────────────                  │
│  Opening:    "Ramesh Bhai, main aapke account dekh raha tha…"  │
│  Diagnostic: "Maine dekha aapki city setting se leads kum…"    │
│  Value Demo: "Ek seller ne geography expand ki — 8→14 leads."  │
│  Lead Reveal:"Delhi buyer, Cotton Fabric, ₹45,000. Share karta"│
│  Action:     "Main abhi setting change kar deta hoon — 2 min." │
│  Close:      "Renewal pressure nahi. Pehle yeh lead pursue karo"│
│                                                                  │
│  Objection Handlers: [competitor] [price] [no time]            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 17.3 Backend — `app.py`

```python
from flask import Flask, request, Response, send_from_directory
import json, threading, queue

app = Flask(__name__)

@app.route("/")
def index():
    return send_from_directory("templates", "scorer.html")

@app.route("/score", methods=["POST"])
def score():
    glid = request.json.get("glid", "").strip()
    if not glid.isdigit():
        return {"error": "Invalid GLID"}, 400

    q = queue.Queue()

    def run_pipeline():
        # Each step pushes SSE events into the queue
        emit = lambda evt, data: q.put(f"event: {evt}\ndata: {json.dumps(data)}\n\n")

        try:
            emit("step_start", {"step": "fetch_apis"})
            seller_dict = fetch_all(glid)                        # existing pipeline
            emit("step_done",  {"step": "fetch_apis", "ok": True})

            emit("step_start", {"step": "compute_signals"})
            signals = compute_signals(glid, seller_dict)
            emit("step_done",  {"step": "compute_signals", "ok": True})

            for skill_name, skill_fn in SKILL_SEQUENCE:
                emit("step_start", {"step": skill_name})
                result = skill_fn(signals)
                signals.update(result)
                emit("step_done",  {"step": skill_name, "result": result})

            emit("complete", build_action_plan(signals))
        except Exception as e:
            emit("error", {"msg": str(e)})
        finally:
            q.put(None)   # sentinel

    threading.Thread(target=run_pipeline, daemon=True).start()

    def stream():
        while True:
            item = q.get()
            if item is None:
                break
            yield item

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/brief/<glid>")
def brief(glid):
    # Serve the pre-call brief HTML for this GLID from the latest run
    brief_path = find_latest_brief(glid)
    return send_from_directory(brief_path.parent, brief_path.name)

@app.route("/status")
def status():
    from pathlib import Path
    return {
        "library_ready": Path("seller_survival/data/snapshots.parquet").exists(),
        "cohort_size": 292
    }

if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
```

**Skill sequence constant:**
```python
SKILL_SEQUENCE = [
    ("ChurnScoringSkill",     churn_scoring_skill.invoke),
    ("SHAPRCASkill",          shap_rca_skill.invoke),
    ("PeerBenchmarkSkill",    peer_benchmark_skill.invoke),
    ("DemandIndexSkill",      demand_index_skill.invoke),
    ("LLMCohortScorerSkill",  llm_cohort_scorer_skill.invoke),  # skipped if new seller
    ("GiftedLeadSkill",       gifted_lead_skill.invoke),
    ("PreCallBriefSkill",     pre_call_brief_skill.invoke),
    ("ScriptGenerationSkill", script_generation_skill.invoke),
    ("WhatsAppMessageSkill",  whatsapp_message_skill.invoke),
]
```

---

### 17.4 Frontend — `templates/scorer.html`

Single HTML file. No framework. Inline CSS (dark theme). Vanilla JS.

**Key JS logic:**

```javascript
async function runScorer(glid) {
  showProgress();

  const resp = await fetch("/score", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ glid })
  });

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop();                        // keep incomplete chunk

    for (const block of lines) {
      const eventMatch = block.match(/^event: (\w+)/m);
      const dataMatch  = block.match(/^data: (.+)/m);
      if (!eventMatch || !dataMatch) continue;

      const event = eventMatch[1];
      const data  = JSON.parse(dataMatch[1]);

      if (event === "step_start") markStepPending(data.step);
      if (event === "step_done")  markStepDone(data.step, data.result);
      if (event === "complete")   showResults(data);
      if (event === "error")      showError(data.msg);
    }
  }
}

document.getElementById("analyseBtn").addEventListener("click", () => {
  const glid = document.getElementById("glidInput").value.trim();
  if (!glid) return;
  runScorer(glid);
});
```

---

### 17.5 How to Run

```bash
# Terminal 1 — one-time reference library build
python -m seller_survival build

# Terminal 2 — start the UI server
cd churn_analysis
python app.py
# → Running on http://localhost:5000

# Browser
open http://localhost:5000
# Enter GLID → click Analyse Seller → watch steps stream in → see results
```

---

### 17.6 UI File Structure

```
churn_analysis/
├── app.py                        # Flask server
└── templates/
    ├── scorer.html               # Main UI (GLID input + live progress + results)
    └── scorer_brief.html         # Pre-call brief template (also served standalone)
```

---

### 17.7 Error States in UI

| Scenario | What UI Shows |
|----------|---------------|
| Invalid GLID (non-numeric) | Inline error: "Enter a valid numeric GLID" |
| GLID not found in any API | Red banner: "No data found for this GLID. Check GLID and credentials." |
| Reference library not built | Yellow banner: "AI cohort scoring unavailable. Run: python -m seller_survival build" |
| LLM API fails | Step shows ⚠ warning, results continue with rule-based score only |
| Partial API data | Step shows amber warning "3 APIs failed — partial scoring" |
| All APIs fail | Pipeline aborts, red error: "Could not fetch seller data. Check API credentials." |

---

### 17.8 Batch Mode (Multiple GLIDs)

For running the full `glids.txt` list instead of one GLID:

```
┌────────────────────────────────────────────────────────────┐
│  [Single GLID]  [Batch Run ▾]                              │
├────────────────────────────────────────────────────────────┤
│  Upload glids.txt  or  paste GLIDs (one per line)          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  268280949                                           │  │
│  │  12345678                                            │  │
│  │  87654321                                            │  │
│  └──────────────────────────────────────────────────────┘  │
│  [Run Batch]                                               │
│                                                            │
│  Progress: ████████░░░░░░░░  47/131 sellers               │
│  Red: 12  Amber: 35  Green: 0  (so far)                   │
│                                                            │
│  [View master_dashboard.html when done]                    │
│  [Download master_action_plan.json]                        │
└────────────────────────────────────────────────────────────┘
```

Batch mode runs `pipeline.py` as a subprocess, streaming its stdout into the progress bar.

---

### 17.9 Implementation Notes

- **No auth required** — local-only tool, no login screen
- **Port 5000** — standard Flask dev port
- **Dark theme** — matches existing `dashboard.html` aesthetic
- **No JS framework** — plain HTML avoids build step, easier to demo
- **SSE not WebSocket** — simpler, one-way stream is enough for progress updates
- **Brief served from disk** — `PreCallBriefSkill` writes HTML to `action_plans/`, Flask serves it at `/brief/<glid>`
- **Copy buttons** — WhatsApp message tab has one-click copy for rep convenience

---

---

## 18. Phase 6 — Cross-Platform Product Intelligence

**Entry point:** `phases/phase6_cross_platform.py`
**Trigger:** Red or Amber sellers where `rca_category in (POOR_CATALOG, PEER_GAP, NO_LEADS, LOW_ENGAGEMENT)`
**Dependency:** Playwright + Chromium installed (`pip install playwright && playwright install chromium`)

### 18.1 Purpose

Discover whether the seller has a presence on competing B2B/B2C platforms (JustDial, TradeIndia, Shopify) and compare their product catalog quality there vs on IndiaMART. If the seller maintains a better catalog elsewhere, this is the most compelling retention argument: "Your other platform profile already has 24 products and 5 photos each — it takes 20 minutes to mirror this on IndiaMART, which has 3× more B2B buyer traffic."

### 18.2 Skill 14: CrossPlatformIntelligenceSkill

**File:** `skills/cross_platform_intelligence_skill.py`

**Inputs:**
```json
{
  "glid": "string",
  "company": "Ramesh Textiles",
  "city": "Ahmedabad",
  "mcats": ["Cotton Fabric", "Textile"],
  "im_products": [{"name": "...", "price": "...", "photos": 3}],
  "rca_category": "POOR_CATALOG",
  "ctype": "CATALOG"
}
```

**Scraping Pipeline (Playwright MCP — async, headless Chromium):**

1. **JustDial search:** `"{company_name}" "{city}" site:justdial.com`
   - Extract: business listing URL, product/service count, categories listed, photo count, review count, rating
2. **TradeIndia search:** `"{company_name}" site:tradeindia.com`
   - Extract: product count, catalog category breadth, photo count per product
3. **Shopify detection:** Google query `site:myshopify.com "{company_name}"` or `"{company_name}" shopify store`
   - Extract: product count, price range, product categories if store found
4. **Google Maps/Business:** Extract reviews + business category as verification signal

**Comparison Logic:**
```python
im_catalog_gap = {
    "im_products":        len(im_products),
    "other_avg_products": mean([jd_count, ti_count]) if either found,
    "gap_pct":            (im - other_avg) / max(other_avg, 1) * 100,
    "im_photos_avg":      mean([p["photos"] for p in im_products]),
    "other_photos_avg":   mean scraped from competitor profiles,
    "categories_overlap": cosine similarity of mcats vs scraped categories,
    "severity":           "high" if gap_pct < -40 else "medium" if gap_pct < -20 else "low"
}
```

**Outputs:**
```json
{
  "platforms_found": ["justdial", "tradeindia"],
  "platform_data": {
    "justdial": {
      "found": true,
      "url": "https://www.justdial.com/...",
      "product_count": 24,
      "categories": ["Cotton Fabric", "Textile"],
      "photos_avg": 5.2,
      "reviews": 12,
      "rating": 4.2
    },
    "tradeindia": {
      "found": true,
      "product_count": 18,
      "photos_avg": 4.1,
      "categories": ["Textile", "Fabric"]
    },
    "shopify": {"found": false}
  },
  "im_catalog_gap": {
    "im_products": 8,
    "other_avg_products": 21,
    "gap_pct": -62,
    "im_photos_avg": 2.3,
    "other_photos_avg": 4.6,
    "severity": "high"
  },
  "competitive_positioning": "seller_stronger_elsewhere",
  "call_card": {
    "headline_hi": "Ramesh Bhai, aapka JustDial pe 24 products hain — IM pe sirf 8 hain. IM pe B2B buyers 3× zyada hain.",
    "headline_en": "Your JustDial listing has 24 products. IndiaMART shows only 8. IM has 3× more B2B buyers.",
    "data_points": [
      "JustDial: 24 products vs IndiaMART: 8 products",
      "JustDial: avg 5 photos vs IndiaMART: avg 2 photos",
      "12 JustDial reviews confirm active business"
    ],
    "suggested_action": "Mirror JustDial catalog on IndiaMART — 20 min upload session together",
    "effort_estimate": "20 minutes",
    "urgency": "high"
  },
  "scrape_status": "success",
  "scrape_latency_ms": 8400,
  "platforms_not_found": ["shopify"]
}
```

**Fallback handling:**
- Playwright not installed → `used_fallback=true`, skip scrape, return `platforms_found=[]`
- All platforms return no match → return empty data, note in brief "Seller appears IM-exclusive"
- Partial scrape failure → use successfully scraped platforms only, note gaps
- Anti-bot block → retry once with 3s delay + different user-agent; if fails, skip platform

### 18.3 Orchestrator Integration

`CrossPlatformIntelligenceSkill` runs **after** `WhatsAppMessageSkill` and **only for Red/Amber POOR_CATALOG or PEER_GAP sellers**. It enriches the `PreCallBriefSkill` output with a cross-platform card.

Updated orchestrator step after Step 7 (WhatsAppMessage):

```python
# ── STEP 8b: CrossPlatformIntelligenceSkill (conditional) ──────────────────
if risk_tier in ("Red", "Amber") and rca_category in ("POOR_CATALOG", "PEER_GAP", "NO_LEADS"):
    emit("cross_platform", {"status": "running"})
    r_cp = registry.run("cross_platform_intelligence", {
        "glid":         glid,
        "company":      signals.get("company"),
        "city":         signals.get("city"),
        "mcats":        signals.get("mcats", []),
        "rca_category": rca_category,
        "ctype":        signals.get("ctype"),
    })
    results["cross_platform"] = r_cp.data
    emit("cross_platform", {"status": "done", **r_cp.data})
else:
    results["cross_platform"] = {"skipped": True, "reason": f"tier={risk_tier}, rca={rca_category}"}
    emit("cross_platform", {"status": "skipped"})
```

`PreCallBriefSkill` and `ScriptGenerationSkill` both accept `cross_platform_result` as an optional input — if present and `severity == "high"`, the call card headline is elevated as the primary value demonstration.

### 18.4 Phase 6 Output Files

```
runs/{run_id}/action_plans/
  {glid}_cross_platform.json    # full scrape result
  {glid}_cross_platform_card.html   # rep-facing card (dark theme, mobile-first)
```

**Card structure:**
```
┌──────────────────────────────────────────────────────────────┐
│  Cross-Platform Catalog Intelligence — Ramesh Textiles        │
├──────────────────────────────────────────────────────────────┤
│  JustDial Profile Found ✓        TradeIndia Found ✓           │
│  JD Products: 24                 TI Products: 18              │
│  JD Photos/product: 5.2          TI Photos: 4.1               │
│                                                                │
│  IndiaMART Profile:                                           │
│  Products: 8   ← 62% fewer than competitor profiles          │
│  Photos/product: 2.3                                          │
├──────────────────────────────────────────────────────────────┤
│  Opening line (Hindi):                                        │
│  "Ramesh Bhai, aapka JustDial pe 24 products hain — IM pe    │
│   sirf 8 hain. IM pe B2B buyers 3× zyada hain."              │
│                                                                │
│  Suggested Action:                                            │
│  Mirror JustDial catalog on IndiaMART — 20 min upload        │
└──────────────────────────────────────────────────────────────┘
```

### 18.5 Setup and Dependencies

```bash
pip install playwright
playwright install chromium

# Verify
python -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"
```

**Environment variables (optional):**
```
PLAYWRIGHT_HEADLESS=true           # default true — set false for debugging
CPPI_TIMEOUT_MS=15000              # per-platform timeout (default 15s)
CPPI_MAX_PLATFORMS=3               # cap parallel browser pages
```

**Rate limiting:** 2–3 second delay between platform searches to avoid bot detection. Total skill latency: 8–20 seconds. Always runs async from main pipeline — does not block action plan generation.

---

## 19. Conversion Point Detection

### 19.1 Purpose

Every churn story has an inflection point — the exact month when a seller's trajectory shifted. Knowing this point tells the rep:
- **What to ask**: "Maine dekha 7 mahine pehle sab theek tha — Oct mein kuch badla, kya hua?"
- **How urgent the intervention is**: sudden cliff = emergency, gradual drift = proactive, never engaged = onboarding reset
- **Which script to use**: different journey types need fundamentally different conversations

### 19.2 Three Trajectory Types

| Type | Pattern | Signal | Urgency |
|------|---------|--------|---------|
| **TYPE_A** | Active → Churned | Peak ≥ 8 leads/month, last 1–2 months dropped > 60% | EMERGENCY — intervene within 24h |
| **TYPE_B** | Active → Inactive → Churned | 3+ consecutive declining months, gradual slope | PROACTIVE — 7-day window |
| **TYPE_C** | Never Engaged → Churned | Activity < 10% of peer median throughout all months | ONBOARDING_RESET — mandatory check |

### 19.3 Skill 15: ConversionPointSkill

**File:** `skills/conversion_point_skill.py`

**Inputs:**
```json
{
  "glid": "string",
  "monthly_trend": [...],
  "account_age_days": 380,
  "enq_30d": 3,
  "active_days_30d": 2,
  "peer_median_enq": 8,
  "ctype": "CATALOG"
}
```

**Detection Algorithm:**

```python
def detect_trajectory(monthly_trend, peer_median_enq):
    enqs = [m.get("total_enq", 0) for m in monthly_trend]
    
    if not enqs or len(enqs) < 2:
        return "TYPE_C", None, 0

    peak_val = max(enqs)
    peer_threshold = max(peer_median_enq * 0.1, 1)  # 10% of peer median

    # TYPE_C: never engaged — activity never exceeded 10% of peer median
    if peak_val <= peer_threshold:
        return "TYPE_C", None, peak_val

    peak_idx = enqs.index(peak_val)

    # TYPE_A: sudden cliff — last 1-2 months dropped > 60% from peak
    recent = enqs[max(0, len(enqs)-2):]
    if max(recent) < peak_val * 0.4:
        months_since_peak = len(enqs) - 1 - peak_idx
        if months_since_peak <= 2:
            return "TYPE_A", peak_idx, peak_val

    # TYPE_B: gradual drift — find first month of 3-consecutive-decline sequence
    consecutive_drops = 0
    conversion_idx = None
    for i in range(1, len(enqs)):
        if enqs[i] < enqs[i-1] * 0.9:  # >10% drop = meaningful decline
            consecutive_drops += 1
            if consecutive_drops == 3 and conversion_idx is None:
                conversion_idx = i - 2  # first month of the decline sequence
        else:
            consecutive_drops = 0

    if consecutive_drops >= 3 and conversion_idx is not None:
        return "TYPE_B", conversion_idx, peak_val

    # Default to TYPE_A if peak was recent
    return "TYPE_A", peak_idx, peak_val
```

**Outputs (TYPE_A — sudden drop):**
```json
{
  "trajectory_type": "TYPE_A",
  "trajectory_label": "Active → Churned",
  "conversion_point_month": "Mar 2026",
  "conversion_point_idx": 10,
  "peak_month": "Feb 2026",
  "peak_enq": 18,
  "current_enq": 3,
  "decline_pct": -83,
  "months_since_conversion": 2,
  "decline_duration_months": 2,
  "velocity_trend": "cliff",
  "intervention_urgency": "EMERGENCY",
  "trajectory_description": "Seller peaked at 18 leads/month in Feb 2026, dropped 83% in 2 months — sudden cliff pattern.",
  "call_frame_hi": "Ramesh Bhai, Feb mein 18 leads aa rahi thi — March ke baad ekdum kuch ho gaya. Kya hua tab?",
  "call_frame_en": "You were getting 18 leads in Feb. Something changed sharply in March. What happened then?"
}
```

**Outputs (TYPE_B — gradual drift):**
```json
{
  "trajectory_type": "TYPE_B",
  "trajectory_label": "Active → Inactive → Churned",
  "conversion_point_month": "Oct 2025",
  "conversion_point_idx": 4,
  "peak_month": "Aug 2025",
  "peak_enq": 14,
  "current_enq": 3,
  "decline_pct": -79,
  "months_since_conversion": 7,
  "decline_duration_months": 5,
  "velocity_trend": "gradual",
  "intervention_urgency": "PROACTIVE",
  "trajectory_description": "Active Aug–Sep 2025 (14 leads/month), began declining Oct 2025, now at 3/month — 79% drop over 7 months.",
  "call_frame_hi": "Maine dekha 7 mahine pehle Oct mein kuch badla. Tab se leads dheere dheere kum ho rahi hain — kya koi cheez change ki thi?",
  "call_frame_en": "I noticed something shifted 7 months ago in October. Leads have been gradually declining since — did anything change then?"
}
```

**Outputs (TYPE_C — never engaged):**
```json
{
  "trajectory_type": "TYPE_C",
  "trajectory_label": "Never Engaged → Churned",
  "conversion_point_month": null,
  "peak_enq": 0,
  "current_enq": 0,
  "decline_pct": 0,
  "intervention_urgency": "ONBOARDING_RESET",
  "mandatory_onboarding_check": true,
  "trajectory_description": "Seller never exceeded peer baseline activity — onboarding failure pattern.",
  "call_frame_hi": "Bhai, account tha lekin shuru se hi setup nahi hua laga. Chaliye saath mein 10 minute mein properly set up karte hain.",
  "call_frame_en": "Looks like the account was never fully set up from the start. Let's spend 10 minutes to set it up properly together."
}
```

### 19.4 Orchestrator Integration

`ConversionPointSkill` runs as **Step 0** — before `ChurnScoringSkill` — since trajectory type enriches the scoring context and all downstream scripts.

```python
# ── STEP 0: ConversionPointSkill ─────────────────────────────────────────────
emit("conversion_point", {"status": "running"})
r0 = registry.run("conversion_point", {
    "glid":             glid,
    "monthly_trend":    signals.get("monthly_enq_raw", []),
    "account_age_days": signals.get("account_age", 0),
    "enq_30d":          signals.get("enq_30d", 0),
    "active_days_30d":  signals.get("active_days_30d", 0),
    "peer_median_enq":  0,  # updated after PeerBenchmarkSkill runs
    "ctype":            signals.get("ctype"),
})
results["conversion_point"] = r0.data
emit("conversion_point", {"status": "done", **r0.data})

trajectory_type    = r0.data.get("trajectory_type", "TYPE_B")
intervention_urgency = r0.data.get("intervention_urgency", "PROACTIVE")
call_frame_hi      = r0.data.get("call_frame_hi", "")
```

**Downstream consumers of ConversionPoint output:**

| Skill | How it uses trajectory |
|-------|----------------------|
| `ChurnScoringSkill` | TYPE_A cliff adds +10 urgency to score; TYPE_C forces onboarding checks |
| `SHAPRCASkill` | `trajectory_type` becomes a primary RCA input signal |
| `PreCallBriefSkill` | `call_frame_hi/en` becomes opening line; `trajectory_description` goes in brief body |
| `ScriptGenerationSkill` | TYPE_A script = emergency recovery; TYPE_B = proactive check-in; TYPE_C = setup call |
| `WhatsAppMessageSkill` | Message tone/urgency adapts to trajectory type |
| `OnboardingHealthSkill` | TYPE_C always triggers mandatory onboarding health check regardless of account age |

### 19.5 TYPE_C Override Rule

When `trajectory_type == TYPE_C`, `OnboardingHealthSkill` **always runs** — even if `account_age_days > 90`. This is because a seller who was never engaged is effectively still in onboarding regardless of calendar time.

```python
# In orchestrator Step 5 (OnboardingHealth):
run_onboarding = (account_age <= 90) or (trajectory_type == "TYPE_C")
```

### 19.6 Churn Score Modifier (TYPE_A Urgency Bonus)

TYPE_A (sudden cliff) adds a +10 urgency modifier to the rule-based churn score since sudden drops are higher-conversion opportunities — the cause is often recent, specific, and fixable.

```python
# In ChurnScoringSkill:
if trajectory_type == "TYPE_A" and months_since_conversion <= 2:
    score = min(100, score + 10)
    reason_tags.append("SUDDEN_CLIFF")
```

### 19.7 UI Integration — New "Journey" Tab

Add a **Journey** tab to the results panel in `scorer.html`:

```
TAB: Journey
─────────────────────────────────────────────────────
Trajectory:  Active → Inactive → Churned  (TYPE_B)
Urgency:     PROACTIVE

Timeline:
  Aug 2025 ██████████ 14 leads  ← PEAK
  Sep 2025 ████████   11 leads
  Oct 2025 ██████     8 leads   ← CONVERSION POINT
  Nov 2025 ████       6 leads
  Dec 2025 ██         4 leads
  Jan 2026 █          3 leads   ← NOW

Months since conversion: 7   |   Decline: -79%

Opening line (Hindi):
"Maine dekha 7 mahine pehle Oct mein kuch badla..."

Opening line (English):
"I noticed something shifted 7 months ago in October..."
─────────────────────────────────────────────────────
```

### 19.8 Error Handling

| Error | Handling |
|-------|---------|
| `monthly_trend` empty | Default to TYPE_C, flag `data_insufficient=true` |
| Only 1 month of data | Default to TYPE_A, `confidence=low` |
| All months zero | TYPE_C with `mandatory_onboarding_check=true` |
| `account_age_days` missing | Use `len(monthly_trend) * 30` as estimate |

---

## 20. Updated Orchestrator Flow (with Skills 14 + 15)

```
Seller Signal Dict
        │
   ┌────▼────────────────────────┐
   │  STEP 0: ConversionPoint    │  ← NEW — trajectory type, call frame
   │  TYPE_A / TYPE_B / TYPE_C   │
   └────┬────────────────────────┘
        │  trajectory_type, call_frame_hi
   ┌────▼────────────────────────┐
   │  STEP 1: ChurnScoring       │  ← TYPE_A adds +10; TYPE_C forces onboarding
   └────┬────────────────────────┘
        │
   ┌────▼────────────────────────┐
   │  STEP 2: SHAP RCA           │  ← trajectory_type as input signal
   └────┬────────────────────────┘
        │
   ┌────▼────────────────────────┐
   │  STEP 3: PeerBenchmark      │  ← peer_median_enq fed back to ConversionPoint
   └────┬────────────────────────┘
        │
   ┌────▼────────────────────────┐
   │  STEP 4: DemandIndex        │
   └────┬────────────────────────┘
        │
   ┌────▼────────────────────────────────────────────────┐
   │  STEP 5: OnboardingHealth                            │
   │  Runs if: account_age ≤ 90 OR trajectory == TYPE_C  │  ← TYPE_C override
   └────┬────────────────────────────────────────────────┘
        │
   ┌────▼────────────────────────┐
   │  STEP 6: LLMCohortScorer    │  ← established sellers only
   └────┬────────────────────────┘
        │
   ┌────▼────────────────────────┐
   │  final_tier = max(rule, llm) │
   └────┬────────────────────────┘
        │
   ┌────▼────────────────────────────────────────────────┐
   │  STEP 7: WhatsAppMessage                             │
   │  Tone adapts: TYPE_A=urgent, TYPE_B=curious,        │
   │               TYPE_C=setup                          │
   └────┬────────────────────────────────────────────────┘
        │
   ┌────▼────────────────────────┐
   │  STEP 8: PreCallBrief       │  ← Red only; includes trajectory card
   └────┬────────────────────────┘
        │
   ┌────▼──────────────────────────────────────────────────────┐
   │  STEP 9: CrossPlatformIntelligence                        │  ← NEW
   │  Runs if: Red/Amber AND rca in (POOR_CATALOG, PEER_GAP,  │
   │           NO_LEADS, LOW_ENGAGEMENT)                       │
   └────┬──────────────────────────────────────────────────────┘
        │
   ┌────▼────────────────────────┐
   │  ActionPlan                 │
   └─────────────────────────────┘
```

---

## 21. Updated File Structure (additions only)

```
churn_analysis/skills/
  ├── conversion_point_skill.py      # SKILL 15 — NEW
  └── cross_platform_intelligence_skill.py  # SKILL 14 — NEW

churn_analysis/phases/
  └── phase6_cross_platform.py       # NEW

runs/{run_id}/action_plans/
  ├── {glid}_cross_platform.json     # CPPI scrape result
  └── {glid}_cross_platform_card.html  # Rep card (dark theme, mobile)

templates/scorer.html
  └── Journey tab (new tab alongside Overview, BL Signals, etc.)
```

**Updated Skill registry** (`skills/registry.py`):
```python
# Add to _auto_register():
from .conversion_point_skill import ConversionPointSkill
from .cross_platform_intelligence_skill import CrossPlatformIntelligenceSkill
registry.register(ConversionPointSkill())
registry.register(CrossPlatformIntelligenceSkill())
```

**pct_map and label_map** additions in `app.py`:
```python
pct_map["conversion_point"]  = 42   # runs before churn_scoring
pct_map["cross_platform"]    = 90   # runs after pre_call_brief

label_map["conversion_point"] = "Detecting journey trajectory..."
label_map["cross_platform"]   = "Scanning competitor platforms (Playwright)..."
```

---

## 22. Updated Implementation Sequence (additions)

### Stage 6: Conversion Point Detection (add after Stage 2)

36. Build `skills/conversion_point_skill.py` — trajectory detection algorithm
37. Add Step 0 to `agent/orchestrator.py` — ConversionPointSkill before ChurnScoringSkill
38. Update `ChurnScoringSkill` to accept `trajectory_type` input (+10 for TYPE_A cliff)
39. Update `SHAPRCASkill` to use `trajectory_type` as input signal
40. Update `PreCallBriefSkill` — use `call_frame_hi/en` as opening line when available
41. Update `WhatsAppMessageSkill` — adapt tone by trajectory type
42. Update `OnboardingHealthSkill` — TYPE_C override (always run if TYPE_C)
43. Add Journey tab to `templates/scorer.html` — timeline chart + opening line display

**Deliverable:** Every scored seller gets a trajectory type. Opening lines in brief/script reference the specific conversion month. TYPE_C sellers always trigger onboarding checks.

### Stage 7: Cross-Platform Intelligence (add after Stage 4)

44. Install Playwright: `pip install playwright && playwright install chromium`
45. Build `skills/cross_platform_intelligence_skill.py`
    - JustDial scraper (search + extract product count, photos, reviews)
    - TradeIndia scraper (search + extract product count, photos)
    - Shopify detector (Google search `site:myshopify.com "{company}"`)
    - Comparison logic: `im_catalog_gap` computation
    - Call card generation (Hindi + English headline + data points)
46. Add Step 9 (conditional) to `agent/orchestrator.py`
47. Update `PreCallBriefSkill` to accept `cross_platform_result` — elevate call card in brief
48. Update `ScriptGenerationSkill` — use cross-platform data points in value demo section
49. Build `phases/phase6_cross_platform.py` — batch runner for multiple GLIDs
50. Build `{glid}_cross_platform_card.html` template
51. Add Cross-Platform section to `templates/scorer.html` results panel

**Deliverable:** Red/Amber POOR_CATALOG sellers get a cross-platform card in their pre-call brief. Rep sees: "Your JustDial has 24 products — IM shows 8."

---

## 23. Updated Checklist (new items)

| Feature | Status |
|---------|--------|
| 🔲 SKILL 15: ConversionPointSkill | To build |
| 🔲 SKILL 14: CrossPlatformIntelligenceSkill | To build |
| 🔲 Orchestrator Step 0 (ConversionPoint) | To build |
| 🔲 TYPE_C OnboardingHealth override | To build |
| 🔲 TYPE_A urgency bonus in ChurnScoringSkill | To build |
| 🔲 Journey tab in scorer.html | To build |
| 🔲 Playwright setup + JustDial scraper | To build |
| 🔲 TradeIndia scraper | To build |
| 🔲 Shopify detector | To build |
| 🔲 Cross-platform call card template | To build |
| 🔲 Phase 6 batch runner | To build |

---

## Appendix A: API Credentials Reference

| System | URL | Auth |
|--------|-----|------|
| DWH | `https://imdwh.intermesh.net/api/go` | JWT in request body |
| MERP | `https://merp.intermesh.net` | AK=JWT in URL param |
| Ingestion | `https://ingestion-service-kntbneg73q-el.a.run.app` | x-api-key header |
| Metrics AS_OF | `2026-01-01` | Must be past date |
| LLM Provider | `LLM_BASE_URL` (env) | `LLM_API_KEY` (env) — OpenAI-compatible |
| Embeddings | local sentence-transformers | no API key — `all-MiniLM-L6-v2` |

## Appendix B: Hard-Coded Business Priors

| Prior | Value | Source |
|-------|-------|--------|
| High-risk cities | Lucknow, Kanpur, Saharanpur, Surat, Jaipur | FINAL PLAN |
| Monthly cool-off | 6 months | FINAL PLAN |
| Annual cool-off | 3 months | FINAL PLAN |
| Winback package | Annual only | FINAL PLAN |
| Red threshold | Score ≥ 65 (rule) OR LLM Critical/Very High/High | Current pipeline + LLM |
| Amber threshold | Score ≥ 35 (rule) OR LLM Moderate | Current pipeline + LLM |
| Avg ARR Red seller | Rs 15,000 | Assumption |
| Lead quality window | 72 hours | FINAL PLAN |
| Gifted lead follow-up | +48 hours | FINAL PLAN |
| Reference library size | 292 sellers (146/146 balanced) | cohort.csv |
| LLM model default | `LLM_MODEL` env var (Groq: openai/gpt-oss-120b) | OpenAI-compatible |
| Cohort filter threshold | 0.5 (strict), 0.25 (loose) | plan_part1 |
| Cohort examples per LLM call | 10 churned + 10 retained | plan_part1 |

## Appendix C: Cohort GLID Reference

**Retained sellers (146):** Use `seller_survival/cohort.csv` where `label == "retained"` (source: `feb_sale1_not_winback`)

**Churned sellers (146):**
- Cohort A (38): `label == "churned"`, `source == "feb_sale1_winback"` — converted in Feb, later churned
- Winback Apr sample (108): `label == "churned"`, `source == "winback_apr_sample"`

Key Cohort A GLIDs for demo/testing (known churned sellers):
`27257635, 41584202, 60110967, 92870390, 102449301, 264396252, 264492755`

Key retained GLIDs for reference:
`9149400, 11282573, 41584202` (lookalike examples in LLM prompt)

---

*IndiaMART Churn Reduction + Seller Survival Intelligence — Integrated Implementation Plan*
*Version 2.0 | 2026-05-15 | Confidential — Hackathon Use Only*
