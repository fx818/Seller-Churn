# Phase 1 Plan — Seller Survival Intelligence System (Active Drift MVP)

## Context

The spec at `seller_survival_intelligence_architecture.md` describes a two-mode Seller Survival Intelligence System for IndiaMART. Phase 1 implements **Mode 2 only — Active Seller Drift Check**: given a current paying seller, score how much they look like historically churned sellers vs retained sellers, and emit a banded risk verdict + confidence + LLM reasoning.

The existing `data_sources/` folder is a working per-GLID feature builder (loader) that pulls from 4 IndiaMART sources (MERP API, ingestion API, Context API, Postgres) and produces a unified `seller_dict` per GLID. Phase 1 reuses a slim subset of this loader.

Two input files provide cohort labels:

- `winback_pool_2026 (1).csv` — 39,798 churned GLIDs + churn date — primary churn label source.
- `Feb leads data.xlsx` (`Main summary` sheet) — used **only** to extract the 38 GLIDs that are both `Sale(14D)=1` AND present in winback (= converted in Feb, later churned). No other columns from this file are used.

The cohort common-GLID analysis is at `common_sellers_feb_winback.md`.

**Cohort composition (locked):**

- Retained: all **146** sellers with `Sale(14D)=1` AND NOT in winback
- Churned: **146** = 38 (Cohort A: Sale=1 ∩ winback) + 108 randomly sampled from winback Apr-2026 expirations
- Total reference library: **292 sellers, 146 / 146 balanced**

Output surface: a CLI command that prints a scored JSON card for a target GLID.

---

## Recommended Approach

**LLM-as-judge architecture.** The 4 categorical fields (turnover, city, mcats, custtype) are used to filter the reference library to the most relevant historical sellers; the LLM then scores the target on three behavioral dimensions — BL consumption, LMS activity, and Activity trend — in Red / Amber / Green bands against that filtered cohort. A deterministic rubric maps the 3-band tuple to a final `risk_level`.

A Python package `seller_survival/` sits beside `data_sources/`. CLI only.

### Scope

**In:** seller snapshot extraction · cohort filter · LLM-driven R/A/G scoring · composite risk_level · confidence score · CLI JSON output.

**Out (deferred):** rule-table next-best-action · Hinglish caller scripts · outcome logger · automated validation gate · FastAPI / dashboard surfaces.

### Module breakdown

```
seller_survival/
├── __init__.py
├── cohort_builder.py            # ✅ built — produces cohort.csv (292 GLIDs labeled)
├── slim_loader.py               # 3-4 endpoints per GLID + per-GLID JSON cache
├── feature_schema.py            # extract Snapshot { context + behavioral } from seller_dict
├── mcat_embeddings.py           # OpenAI text-embedding-3-small with disk cache
├── build_reference_library.py   # cohort.csv → slim_loader → snapshots.parquet
├── cohort_filter.py             # given target context, filter library by 4-field similarity
├── llm_scorer.py                # prompt-build → Claude API → 3-band scoring + reasoning
├── cli.py                       # `python -m seller_survival build|score <GLID>`
└── data/
    ├── cohort.csv               # ✅ generated (292 rows)
    ├── loader_cache/            # per-GLID JSON cache of raw loader output
    ├── mcat_embeddings.json     # cached embeddings keyed by lowercased mcat
    └── snapshots.parquet        # reference library snapshots (context + behavioral)
```

---

## Pipeline

### Phase A — Build reference library (one-time, ~15-25 min for 292 GLIDs)

1. `cohort_builder` (already done) emits `cohort.csv` with columns `glid, label, source`.
2. For each GLID, `slim_loader.fetch_for_glid(glid)` hits only the endpoints we need (composite + scorecard_summary + product_details + scorecard_12m for trends). Output cached as `data/loader_cache/<glid>.json`. Reruns hit cache and are instant.
3. `feature_schema.extract_snapshot(seller_dict)` projects the raw seller_dict to the structured `Snapshot` below.
4. Persist all 292 snapshots to `data/snapshots.parquet`.
5. As a side effect, all unique mcats across the library are embedded via `mcat_embeddings.embed_batch()` and cached to `data/mcat_embeddings.json`.

### Snapshot shape

```
Snapshot = {
  glid:  int,
  label: "retained" | "churned" | "target",
  context: {                          # used to filter cohort BEFORE LLM call
    turnover:  "GST turnover"          (exact match)
    city:      first token of "Locality / City"  (city AND state must match)
    state:     second token of "Locality / City"
    mcats:     list of strings from "mcats"      (semantic overlap via embeddings)
    custtype:  "Custtype"              (exact match)
  },
  behavioral: {                       # what the LLM scores on
    bl: {                              # → BL consumption band (R/A/G)
      received_90d, viewed_90d, consumed_90d, replied_90d,
      consumption_rate, reply_rate, active_bl, blni_count_1yr,
      weekly_bl_active                 (last 7 weeks array)
    },
    lms: {                             # → LMS activity band (R/A/G)
      call_attempts_90d, call_answered_90d, call_pickup_ratio_90d,
      calls_1min_plus_90d, last_succ_call_dt, last_call_summary
    },
    activity: {                        # → Activity trend band (R/A/G)
      activity_30d, weekly_activity, monthly_activity, 3month_activity,
      monthly_trend                   (array of per-month metrics from scorecard_12m),
      daily_activity                  (per-day map)
    }
  }
}
```

### Phase B — Score a target (online, per query)

1. `slim_loader.fetch_for_glid(target_glid)` → seller_dict (cached).
2. `feature_schema.extract_snapshot()` → target `Snapshot`.
3. `cohort_filter.filter_cohort(target.context, library)` ranks the 292-row library by deterministic 4-field similarity and returns the top 10 churned + top 10 retained:

   ```
   filter_score(target, hist) = (
       1 if target.turnover == hist.turnover else 0
     + 1 if (target.city == hist.city AND target.state == hist.state) else 0
     + 1 if max_pairwise_cosine(target.mcats, hist.mcats) ≥ 0.7 else 0
     + 1 if target.custtype == hist.custtype else 0
   ) / 4
   ```

   Pick from sellers with `filter_score ≥ 0.5` (≥ 2 of 4 fields match). If fewer than 5 historicals match at that threshold, relax to ≥ 0.25 and label the run as a `loose` context match.
4. `llm_scorer.score(target, churned_examples, retained_examples)` builds the prompt below, calls Claude, parses the strict-JSON response, applies the composite rubric, computes confidence, and returns the final card.

### LLM scoring prompt

```
SYSTEM:
  You are a seller-survival analyst. Score the target seller on three
  dimensions using Red / Amber / Green bands, comparing against the
  provided cohort baseline. Calibrate the bands using the cohort — there
  are no hard-coded thresholds.

USER:
  Target seller behavioral snapshot:
    BL:       { received_90d: 142, consumed_90d: 5, reply_rate: 0.014, ... }
    LMS:      { call_attempts_90d: 31, pickup_ratio: 0.35, ... }
    Activity: { activity_30d: 17, monthly_trend: [...], ... }

  Cohort context (so you know what's comparable):
    turnover: "0 - 40 L", city: "New Delhi", state: "Delhi NCR",
    mcats: [...], custtype: "Trader - Retailer"

  10 churned-seller snapshots:  [{...}, ...]
  10 retained-seller snapshots: [{...}, ...]

  Score on three independent dimensions:
    1. BL consumption     R/A/G — emphasis on consumption_rate, reply_rate
    2. LMS activity       R/A/G — emphasis on pickup_ratio, call_attempts
    3. Activity trend     R/A/G — emphasis on direction of monthly_trend,
                                   what the seller appears to want from the platform

  Return strict JSON only:
  {
    "bl_band":       "R" | "A" | "G",
    "lms_band":      "R" | "A" | "G",
    "activity_band": "R" | "A" | "G",
    "reasoning":     "2-3 sentences grounded in the cohort comparison",
    "churned_lookalikes":  [glid, ...],   // top 3 of the 10 churned snapshots
    "retained_lookalikes": [glid, ...]    // top 3 of the 10 retained snapshots
  }
```

### Composite risk mapping (deterministic, post-LLM)

A 27-cell rubric encoded as `llm_scorer.COMPOSITE_RUBRIC: dict[tuple[str,str,str], str]`:

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

### Confidence (light, derived — no extra ML)

```
confidence_score = round(100 × (
    0.5 × cohort_match_score        # mean filter_score of the top 20 shown
  + 0.3 × cohort_size_score         # min(n_filtered_at_threshold / 20, 1.0)
  + 0.2 × data_completeness_score   # fraction of behavioral fields non-null on target
))
```

The LLM is **not** asked to self-rate confidence — too unreliable.

### Output JSON shape

```json
{
  "glid": 27257635,
  "snapshot": {
    "context": {
      "turnover": "0 - 40 L",
      "city": "New Delhi",
      "state": "Delhi NCR",
      "mcats": ["Children Hair Accessories", "Hair Bands"],
      "custtype": "Trader - Retailer"
    },
    "behavioral": {
      "bl":       { "received_90d": 142, "consumed_90d": 5, "reply_rate": 0.014, "...": "..." },
      "lms":      { "call_attempts_90d": 31, "pickup_ratio": 0.35, "...": "..." },
      "activity": { "activity_30d": 17, "monthly_trend": [...], "...": "..." }
    }
  },
  "bands": { "bl": "R", "lms": "A", "activity": "R" },
  "risk_level": "Very High",
  "confidence_score": 64,
  "cohort_match": { "n_filtered": 28, "tier": "medium", "shown_to_llm": 20 },
  "llm_output": {
    "reasoning": "Target consumed 5 of 142 BLs (3.5%) — in the cohort, retained sellers averaged 22%. Pickup ratio of 0.35 is mid-pack but trending down per monthly_trend. Activity dropped from 42 (3-month) to 17 (30-day) — clear disengagement signal that mirrors top churned-lookalikes.",
    "churned_lookalikes":  [102449301, 60110967, 92870390],
    "retained_lookalikes": [9149400, 11282573, 41584202]
  }
}
```

---

## Critical Files

### New (to be created)

| Path | Purpose | Status |
|---|---|---|
| `seller_survival/__init__.py` | Package marker | ✅ done |
| `seller_survival/cohort_builder.py` | Build 292-seller cohort.csv | ✅ done |
| `seller_survival/slim_loader.py` | Fetch only 3-4 endpoints we need per GLID + per-GLID JSON cache | pending |
| `seller_survival/feature_schema.py` | `extract_snapshot(seller_dict) -> Snapshot` with `context` + `behavioral` blocks | pending |
| `seller_survival/mcat_embeddings.py` | OpenAI `text-embedding-3-small` wrapper with on-disk JSON cache | pending |
| `seller_survival/build_reference_library.py` | Iterate cohort.csv → slim_loader → extract_snapshot → write `snapshots.parquet` | pending |
| `seller_survival/cohort_filter.py` | `filter_cohort(target_context, library, k=10) -> (churned, retained)` | pending |
| `seller_survival/llm_scorer.py` | Prompt build + Claude API + parse 3-band JSON + composite risk_level + confidence | pending |
| `seller_survival/cli.py` | `python -m seller_survival build` and `score <GLID>` | pending |

### Reused (no edits)

| Path | What it gives us |
|---|---|
| `data_sources/api_client.py` → `build_api_client_session`, `fetch_all_for_glid_with_session` | MERP fetcher (slim_loader will call a subset of endpoints) |
| `data_sources/ingestion_client.py` → `build_ingestion_session`, `fetch_raw_for_glid_with_session` | Ingestion overlay (composite endpoint gives custtype + turnover) |
| `data_sources/context_client.py` → `build_context_session`, `fetch_context_for_glid_with_session` | Context overlay (kycdetails has fallback custtype/turnover) |
| `data_sources/api_transforms.py`, `ingestion_transforms.py`, `context_transforms.py` | Normalize raw JSON into the keys feature_schema reads (`"GST turnover"`, `"Locality / City"`, `"mcats"`, `"Custtype"`, BL/LMS/activity keys) |

### Input data files

| Path | Use |
|---|---|
| `winback_pool_2026 (1).csv` | Churn label, churn-date metadata, Apr-2026 sample pool |
| `Feb leads data.xlsx` (Main summary) | Read `fk_glusr_usr_id` and `Sale (14D)` columns only |

### Integration note

The loader's imports use `from agent.data_sources.api_client import ...`. The IndiaSTAY working dir doesn't have an `agent/` package root. Decision deferred to build time: either vendor `agent/data_sources/` symlink/copy at IndiaSTAY root, or drop `seller_survival/` into the parent `claude_seller_cards/agent/` tree.

---

## Environment / Configuration

Required `.env`:

- `IM_INTERNAL_JWT`, `IM_EMPID` — MERP auth (user-provided)
- `INGESTION_URL`, `INGESTION_API_KEY` — ingestion auth (user-provided)
- `ANTHROPIC_API_KEY` — for LLM scorer (user-provided)
- `OPENAI_API_KEY` — for `text-embedding-3-small` semantic mcat matching (user-provided)
- `DEEP_AGENT_USE_INGESTION=1`, `DEEP_AGENT_USE_CONTEXT=1` — turn on API overlays
- **`DEEP_AGENT_USE_DB` intentionally LEFT OFF** — Postgres creds not available; the loader's `_load_api_df_async` falls back cleanly to the pure-API path. All 4 context fields + the BL/LMS/activity fields are covered by MERP + Context + Ingestion endpoints.

LLM model: deferred — pick Sonnet 4.6 vs Opus 4.7 vs Haiku 4.5 at build time via `--model` CLI flag.

Embeddings stored in `seller_survival/data/mcat_embeddings.json` after first build; reused thereafter. Cache keyed by lowercased mcat string.

---

## Verification

End-to-end smoke flow:

```bash
# Build reference library (one-time, ~15-25 min for 292 GLIDs)
python -m seller_survival build

# Expected:
#   cohort: 146 retained, 146 churned (38 Cohort A + 108 winback Apr)
#   slim_loader: enriched 292/292 sellers (cache miss first run)
#   embeddings: N unique mcats cached
#   wrote seller_survival/data/snapshots.parquet

# Score a single GLID
python -m seller_survival score 27257635
# (GLID 27257635 is in Cohort A — expect High/Very High/Critical)
```

Manual JSON inspection — confirm output matches the shape above (bands tuple, risk_level from rubric, confidence_score in 0-100, churned + retained lookalike GLIDs present).

Math smoke check (no full pytest suite):

```bash
python -c "from seller_survival.llm_scorer import COMPOSITE_RUBRIC; assert COMPOSITE_RUBRIC[('R','R','R')] == 'Critical' and COMPOSITE_RUBRIC[('G','G','G')] == 'Very Low'; print('rubric OK')"
python -c "from seller_survival.cohort_builder import build_cohort; r = build_cohort(); assert len(r) == 292; print('cohort OK')"
```

---

## Out of Scope (deferred to later phases)

- Mode 1 — Onboarding Fit Check
- Rule-table next-best-action mapping
- Hinglish caller scripts / archetype names beyond LLM reasoning
- Outcome logger (SQLite write-through per spec §13)
- Automated validation gate (Cohort B 15-seller test) and full pytest suite
- Lifecycle-stage matcher with multiple snapshot libraries
- Feedback loop / weight re-tuning
- FastAPI service, dashboard, Streamlit surfaces
- Production monitoring, calibration drift, alerting
