# Seller Churn Intelligence — MD-Driven Skills Framework

> **An AI-augmented churn detection, root-cause, retention, and winback system for IndiaMART
> field reps and CRM. Built as a pluggable "skills" architecture — each capability is a
> Markdown spec + Python skill, runnable individually or chained through a pipeline.**

---

## Table of Contents

1. [Why This Exists — The IndiaMART Problem](#1-why-this-exists--the-indiamart-problem)
2. [Architecture Overview](#2-architecture-overview)
3. [Pipeline — End-to-End Flow](#3-pipeline--end-to-end-flow)
4. [Skill Catalogue (13 skills, 7 phases)](#4-skill-catalogue)
   - [4.1 Peer Benchmark](#41-peer-benchmark)
   - [4.2 Demand Index](#42-demand-index)
   - [4.3 Conversion Point Detection](#43-conversion-point-detection)
   - [4.4 Onboarding Health (v2.0)](#44-onboarding-health-v20)
   - [4.5 Churn Scoring (v2.0)](#45-churn-scoring-v20)
   - [4.6 SHAP-based RCA](#46-shap-based-rca)
   - [4.7 LLM Cohort Scorer](#47-llm-cohort-scorer)
   - [4.8 Pre-Call Brief](#48-pre-call-brief)
   - [4.9 WhatsApp Message](#49-whatsapp-message)
   - [4.10 Script Generation (LLM-personalised)](#410-script-generation-llm-personalised)
   - [4.11 Gifted Lead](#411-gifted-lead)
   - [4.12 Cross-Platform Intelligence (Playwright)](#412-cross-platform-intelligence-playwright)
   - [4.13 BL Upgrade](#413-bl-upgrade)
   - [4.14 Winback Priority (v2.0)](#414-winback-priority-v20)
   - [4.15 BL Card (Aggregator)](#415-bl-card-aggregator)
   - [4.16 Call Summary (post-call)](#416-call-summary-post-call)
5. [User Interfaces](#5-user-interfaces)
6. [Business Impact at IndiaMART](#6-business-impact-at-indiamart)
7. [How to Run](#7-how-to-run)
8. [Environment](#8-environment)
9. [Extending the Framework](#9-extending-the-framework)
10. [Repository Layout](#10-repository-layout)

---

## 1. Why This Exists — The IndiaMART Problem

IndiaMART has ~8M registered sellers across paid (BL/Mini-BL) and FreeListing tiers.
The seller retention team faces five compounding pains every day:

| Pain | What it looks like today | Cost |
|---|---|---|
| **Late detection of churn** | Reps notice churn only when the seller stops paying / responding. By then it's too late. | High churn rate; lost LTV. |
| **No root cause** | Reps know a seller is at risk but not **why** — no leads? bad catalog? competitor on JustDial? | Wrong pitch → wasted calls. |
| **Generic call scripts** | Reps read template scripts unrelated to the actual seller's signals (low CQS, 0% reply, peer gap). | Sellers tune out. |
| **No competitive intel** | Reps don't know whether the seller is investing more on JustDial / TradeIndia / their own website. | Mis-framed retention argument. |
| **Winback is a guess** | Of 50K churned sellers, which 5K to call this week? Today it's ranked by recency alone. | Wasted outreach. |

**The system below addresses each pain by phase**, producing a single **BL Card** per
seller that a rep can call from end-to-end.

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         skills/*.md  (specs + docs)                       │
│  human-readable + machine-parseable: inputs, outputs, formula, version    │
└──────────────────────────────────────────────────────────────────────────┘
                                  │  loaded by
                                  ▼
        ┌────────────────────────────────────────────────────────┐
        │   SkillLoader  →  Registry  →  PipelineRunner          │
        │   resolves snapshot.* / context.* / behavioral.*       │
        │   /flow.*  inputs from upstream skills                 │
        └────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                churn_analysis/skills/*.py  (Skill subclasses)
                                  │
                                  ▼
       ┌──────────────┬───────────────┬────────────────────────┐
       │  Streamlit   │  Python CLI   │  Batch JSON Reports    │
       │  (churn_ui)  │  (--pretty /  │  runs/run_<ts>/        │
       │              │   --explain)  │                        │
       └──────────────┴───────────────┴────────────────────────┘
```

**Core design principles**

| Principle | Implementation |
|---|---|
| **Spec-first** | Every skill has a `.md` with YAML frontmatter declaring inputs/outputs. Tooling can read these without touching Python. |
| **Composable phases** | The pipeline reads `skills/pipeline.md` — phases and their conditions are data, not code. |
| **Data flows forward** | Each skill's output is merged into `flow`. Later skills declare `source: flow.<key>` to consume upstream outputs. |
| **Hybrid stats + LLM** | Quantitative scoring → LLM second-opinion (±10) → final score. LLM never reasons in a vacuum. |
| **Standalone runnable** | Every skill can be invoked alone for debugging (`python -m churn_analysis skill <name> <GLID>`). |
| **Two UIs** | Streamlit for inspection; CLI with `--pretty` / `--explain` for terminal use & CI. |

---

## 3. Pipeline — End-to-End Flow

`skills/pipeline.md` defines 7 phases, ordered by data dependency:

```
Phase 0 — Benchmarks            [always runs]
  └─ peer_benchmark + demand_index + conversion_point

Phase 1 — Onboarding Health     [account_age_days <= 90]
  └─ onboarding_health  (consumes Phase 0 outputs)

Phase 2 — Churn Scoring + RCA   [always runs]
  └─ churn_scoring (v2.0) + shap_rca

Phase 2b — LLM Cohort           [account_age_days > 90 AND snapshots exist]
  └─ llm_cohort_scorer

Phase 3 — Action Skills         [risk in [Red, Amber]]
  └─ pre_call_brief + whatsapp_message + script_generation + gifted_lead

Phase 3c — Cross-Platform       [Red/Amber AND rca in [POOR_CATALOG, PEER_GAP,
  └─ cross_platform_intelligence    NO_LEADS, LOW_ENGAGEMENT, BL_DECLINE]]

Phase 4 — BL Upgrade            [always runs]
  └─ bl_upgrade

Phase 5 — Winback Priority      [risk == Red]
  └─ winback_priority (v2.0)

Phase 6 — BL Card               [always runs — aggregator]
  └─ bl_card
```

**Why this order matters**

- Benchmarks (Phase 0) MUST run first so onboarding (Phase 1) and churn scoring
  (Phase 2) can use `flow.demand_index`, `flow.peer_delta_pct`, `flow.trajectory_type`.
- Cross-platform (3c) runs only when RCA hints at a catalog/lead/engagement issue —
  saves Playwright scraping cost for ~60% of sellers where it would add no signal.
- BL Card (6) runs last and aggregates every prior output.

---

## 4. Skill Catalogue

> Each skill below follows the same template: **Problem → Solution → Inputs →
> Formula → Outputs → IndiaMART Impact**.

---

### 4.1 Peer Benchmark
**File:** `churn_analysis/skills/peer_benchmark_skill.py`  ·  **Spec:** `skills/peer_benchmark.md`

| | |
|---|---|
| **Problem** | A seller getting 5 enquiries/month could be excellent (rare category) or terrible (saturated category). Without peers, no signal. |
| **Solution** | Compare seller's last-30d enq, BL count, CQS against same `mcat × city × ctype` cohort percentiles. |
| **Inputs** | `mcat`, `city`, `ctype`, `enq_30d`, `bl_count`, `cqs` |
| **Formula** | `enq_percentile = (peers below seller / total peers) * 100`; `gap_pct = (enq_30d − peer_median)/peer_median * 100`; severity tiers `<-50% RED`, `-50..-20% AMBER`, `≥-20% GREEN` |
| **Outputs** | `peer_group`, `peer_n`, `enq_percentile`, `peer_median_enq`, `gap_severity`, `peer_summary_line` |
| **Impact** | Reps stop comparing seller to themselves; they compare against same-city same-category peers. Removes "we're a small town" excuses. |

---

### 4.2 Demand Index
**File:** `churn_analysis/skills/demand_index_skill.py`  ·  **Spec:** `skills/demand_index.md`

| | |
|---|---|
| **Problem** | Some categories collapse (e.g. mask manufacturers post-COVID). Reps blame the seller; really the market vanished. |
| **Solution** | Compute a 0-100 demand index for the seller's `mcat × city` from market BL count, BL-per-seller saturation, and trend. |
| **Inputs** | `mcat`, `city`, `bl_30d_market`, `seller_count_market`, `historical_bl_30d` |
| **Formula** | `demand_index = clamp(50 + 25*saturation_score + 25*trend_score, 0, 100)` where `saturation_score = 1 - (sellers/bl)` and `trend_score = +1 if rising, -1 if falling`. Risk priors subtract for high-risk categories/cities. |
| **Outputs** | `demand_index`, `demand_tier` (HIGH/MED/LOW), `market_bl_per_seller`, `trend`, `is_high_risk_category`, `city_risk_prior`, `demand_explanation`, `recommended_action` |
| **Impact** | Distinguishes "seller fault" from "market fault". Avoids retention spend on dying categories; redirects to upgrades on rising ones. |

---

### 4.3 Conversion Point Detection
**File:** `churn_analysis/skills/conversion_point_skill.py`  ·  **Spec:** `skills/conversion_point.md`

| | |
|---|---|
| **Problem** | Two sellers with identical "low enq today" need different interventions: one had a sudden cliff (servicing/quality issue), another a slow drift (catalog rot), another was never engaged (onboarding gap). |
| **Solution** | Classify monthly enquiry history into 3 trajectories. |
| **Inputs** | `monthly_enq` (12-month array) |
| **Formula** | `cliff_drop_pct` = largest month-over-month drop. `TYPE_A` if any drop ≥-50% (cliff); `TYPE_C` if total lifetime enq ≤5 (never engaged); else `TYPE_B` (gradual drift). |
| **Outputs** | `trajectory_type`, `trajectory_label`, `cliff_drop_pct`, `inflection_month`, `explanation` |
| **Impact** | Pre-call brief uses this to pick the OPENING line: cliff → "kya hua suddenly?", drift → "let's diagnose catalog", never engaged → "onboarding reset". |

---

### 4.4 Onboarding Health (v2.0)
**File:** `churn_analysis/skills/onboarding_health_skill.py`  ·  **Spec:** `skills/onboarding_health.md`

| | |
|---|---|
| **Problem** | New sellers (≤90d) churn fastest. Activation gaps are silent killers — no leads, missing catalog, low CQS, wrong category. |
| **Solution** | 7 weighted health checks + 2 risk priors + LLM activation plan. |
| **Inputs** | `account_age_days`, `cqs`, `approved_products`, `kyc_done`, `first_lead_received`, `first_reply_sent`, `package_type`, `mcats`, `company`, `city`, `demand_tier`, `gap_severity`, `enq_percentile`, `peer_median_enq` |
| **Checks** | (1) Category Demand · (2) Business Verification · (3) Peer Gap · (4) First BL Response · (5) Package Type · (6) **CQS Gate** (≥70 Green, ≥50 Amber) · (7) **Catalog Completeness** vs `_expected_products_for_age()` (3/8/15/20 by day 7/30/60/60+) |
| **Risk Priors** | High-risk city (Lucknow, Kanpur, Saharanpur, Surat, Jaipur, Agra, Varanasi, Meerut, Ghaziabad) and high-risk category (apparel, textiles, garments, clothing, fabric) — each adds +15 penalty |
| **Formula** | `health_score = Σ(check_weight × check_pass) − Σ(risk_prior_penalty)`. Tiers: `≥75 GREEN`, `≥50 AMBER`, `<50 RED`. |
| **LLM** | If `LLM_API_KEY` set, generates a personalised 4-task activation plan with Hindi + English opening pitches, tone, and signals_used. Falls back to deterministic template. |
| **Outputs** | `health_score`, `health_tier`, `checks` (7 sub-dicts), `risk_priors`, `prior_penalty`, `activation_plan` (tasks + opening pitches), `plan_method` (llm/template), `trigger_action` |
| **Impact** | Lifts new-seller activation by surfacing gaps in week 1 instead of month 3. Reduces "ghost listings" — sellers who paid but never converted. |

---

### 4.5 Churn Scoring (v2.0 — Calibrated)
**File:** `churn_analysis/skills/churn_scoring_skill.py`  ·  **Spec:** `skills/churn_scoring.md`

> **The heart of the system.** All downstream skills branch on `flow.risk` (Red/Amber/Green).

| | |
|---|---|
| **Problem** | v1 used flat penalties: any reply_rate <40% added the same +10; no compounding; no awareness of trajectory; no LLM sanity check. The early v2 was over-strict — too many sellers landed in Red. |
| **Solution** | 4 upgrades — severity tiers, compound multiplier, trajectory adjustment, LLM second opinion — plus a calibration pass that lowered base weights ~30%, softened compounding, and raised tier thresholds. |
| **Inputs** | `enq_30d`, `replied_30d`, `active_days_30d`, `bl_velocity_pct`, `pns_success_pct`, `rag`, `cqs`, `hotleads_count`, `event_count`, `trajectory_type`, `cliff_drop_pct` |
| **Severity-tiered weights (calibrated)** | `reply_rate` 0% → +18, <15% → +14, <40% → +8. `active_days` 0 → +14, ≤3 → +8, ≤7 → +4. `enq` 0 → +10, <3 → +4. `bl_velocity` ≤-50% → +18, ≤-30% → +14, ≤-10% → +7, ≤0 → +2. `pns` <30% → +10, <60% → +6. `rag` Red → +15, Amber → +8. `cqs` <40 → +13, <60 → +8, <75 → +3. `hotleads` 0 → +4. `events` 0 → +8, <10 → +3. |
| **Compound penalty** | `red_flag_count ≥ 6` → `×1.15`; `≥ 4` → `×1.08`; else `×1.0`. Threshold raised from 3-Red to 4-Red so genuine moderate-risk sellers don't get unfairly compounded. |
| **Trajectory adjustment** | `TYPE_A` (cliff) +3 (or +5 if drop ≤-50%); `TYPE_B` (drift) +1; `TYPE_C` (never engaged) 0 — TYPE_C routes to onboarding-reset, not retention. |
| **LLM second opinion** | Sends sub-score breakdown + reasons to LLM; returns `{adjustment: -10..+10, justification: str}`. Catches "model thinks Red but seller paid yesterday — should be Amber" cases. |
| **Final formula** | `base = Σ(weighted penalties)` → `compounded = base × compound_multiplier` → `pre_llm = compounded + trajectory_adj` → `final = clamp(pre_llm + llm_adjustment, 0, 100)` |
| **Tiers** | `≥72` Red · `42-71` Amber · `<42` Green |
| **Outputs** | `churn_score`, `risk`, `base_score`, `compound_multiplier`, `compounded_score`, `trajectory_adjustment`, `pre_llm_score`, `llm_used`, `llm_adjustment`, `llm_justification`, `score_breakdown`, `churn_reasons`, `reason_tags`, `red_flag_count`, `signals_available`, `reply_rate_30d` |
| **Calibration impact** | GLID 29656 (zero reply rate + zero active days + no events): pre-calibration 90/Red → post-calibration 55/Amber. Same signals flagged, fairer tiering. |
| **Impact** | More accurate Red identification → reps prioritise the right 20% of sellers without over-flagging. LLM justification gives the rep a one-line "why" without reading every signal. |

---

### 4.6 SHAP-based RCA
**File:** `churn_analysis/skills/shap_rca_skill.py`  ·  **Spec:** `skills/shap_rca.md`

| | |
|---|---|
| **Problem** | Churn score tells *how bad*; rep needs to know *why* (catalog? leads? engagement?). |
| **Solution** | Rule-based attribution mapped to 7 RCA buckets, with confidence. |
| **RCA Categories** | `POOR_CATALOG`, `NO_LEADS`, `LOW_ENGAGEMENT`, `BL_DECLINE`, `LOW_PNS_RESPONSE`, `PEER_GAP`, `RAG_RISK`, `UNKNOWN` |
| **Formula** | Inspects `score_breakdown`; the top-contributing feature maps to its RCA bucket (e.g. `reply_rate` → `LOW_ENGAGEMENT`, `bl_velocity` → `BL_DECLINE`). Confidence = top contribution / total. |
| **Outputs** | `rca_category`, `rca_confidence`, `rca_explanation_en`, `rca_explanation_hi`, `intervention_hint`, `top_feature` |
| **Impact** | Reps get a precise *angle* for the call. RCA confidence feeds into winback_priority weighting. |

---

### 4.7 LLM Cohort Scorer
**File:** `churn_analysis/skills/llm_cohort_scorer_skill.py`  ·  **Spec:** `skills/llm_cohort_scorer.md`

| | |
|---|---|
| **Problem** | Statistical scoring can miss qualitative cohort patterns (e.g. "sellers with declining BL velocity AND poor PNS AND in saturated city tend to churn within 60 days"). |
| **Solution** | LLM looks at seller's BL/LMS/Activity bands and compares to ~50 known churned and ~50 retained sellers (cohort prompt). |
| **Inputs** | Seller bands, peer lookalikes from reference library (`peer_lookalikes_paid.parquet`) |
| **Outputs** | `risk_level` (Critical/High/Medium/Low), `pipeline_tier`, `confidence_score`, `bands` (bl/lms/activity), `reasoning`, `cohort_match`, `churned_lookalikes` (GLID list), `retained_lookalikes` (GLID list) |
| **Impact** | Provides a second opinion to the churn score. Lookalike GLIDs give reps real precedents — "this seller looks like X who churned and Y who recovered". |

---

### 4.8 Pre-Call Brief
**File:** `churn_analysis/skills/pre_call_brief_skill.py`  ·  **Spec:** `skills/pre_call_brief.md`

| | |
|---|---|
| **Problem** | Reps stare at CRM for 5 minutes before each call assembling context. |
| **Solution** | Single phone-card brief: opening line (Hi+En), key signals (with severity colors), suggested actions, BL/LMS/Activity bands, do-not-mention list. |
| **Outputs** | `opening_line_en`, `opening_line_hi`, `key_signals`, `suggested_actions`, `bands_display`, `brief_text`, `do_not_mention` |
| **Impact** | Reduces pre-call prep time from 5min → 30sec. Increases calls/rep/day. |

---

### 4.9 WhatsApp Message
**File:** `churn_analysis/skills/whatsapp_message_skill.py`  ·  **Spec:** `skills/whatsapp_message.md`

| | |
|---|---|
| **Problem** | Reps draft WhatsApp messages manually; tone and CTA vary wildly. |
| **Solution** | Pre-call WhatsApp template (Hindi + English) routed by RCA category, with personalised data points. |
| **Outputs** | `message_hi`, `message_en`, `cta` |
| **Impact** | Boosts seller pick-up rates by warming them up before the call. Consistent CTA → measurable conversion. |

---

### 4.10 Script Generation (LLM-personalised)
**File:** `churn_analysis/skills/script_generation_skill.py`  ·  **Spec:** `skills/script_generation.md`

| | |
|---|---|
| **Problem** | v1 had ~12 hardcoded scripts per RCA — every seller in a category heard the same words. |
| **Solution** | LLM-generated 5-part call script (opening, diagnostic, value_demo, action, close) personalised with the seller's actual signals; fallback to RCA template. |
| **Inputs** | All RCA + score + peer + demand context |
| **Outputs** | `script_parts` (Hi), `script_parts_en` (En), `objection_handlers`, `estimated_duration_min`, `generation_method` (llm/template), `personalization_signals_used`, `rca_used` |
| **Impact** | Reps sound human instead of robotic. Higher seller engagement during call → better intervention acceptance. |

---

### 4.11 Gifted Lead
**File:** `churn_analysis/skills/gifted_lead_skill.py`  ·  **Spec:** `skills/gifted_lead.md`

| | |
|---|---|
| **Problem** | When a seller says "I'll think about renewing", reps have no carrot to close. |
| **Solution** | Allocate a high-quality un-served lead from the seller's `mcat × city` pool — given on the call as proof of platform value. |
| **Outputs** | `lead_found`, `lead` (GLID + enq detail), `fallback`, `total_qualifying` |
| **Impact** | Closes 10-15% of fence-sitters on the same call. Direct retention lift. |

---

### 4.12 Cross-Platform Intelligence (Playwright)
**File:** `churn_analysis/skills/cross_platform_intelligence_skill.py`  ·  **Spec:** `skills/cross_platform_intelligence.md`

| | |
|---|---|
| **Problem** | If a seller has 24 products on JustDial and only 8 on IndiaMART, reps don't know — and can't push catalog improvement. |
| **Solution** | Headless Playwright + JSON-LD + `__NEXT_DATA__` scraping of JustDial, TradeIndia, Shopify, and the seller's own website. Counts products, photos, ratings; computes IM-vs-others gap. |
| **Counting** | JSON-LD schema → JS heuristics → CSS selectors → text-pattern fallback. JustDial fallback chain: `ev_svc → sc_count → price_count → dimages_cnt → photocnt`. Autoscroll for lazy-loaded grids. |
| **Gap formula** | If platforms have **similar** product counts (within 30% spread) → `MAX(other counts)` is used. If counts **differ widely** (different inventory split) → `SUM` of all platforms. Then `gap_pct = (IM − other_total) / other_total * 100`. |
| **Outputs** | `platforms_found`, `platform_data` (per-platform: found, product_count, rating, photos, url), `im_product_count`, `im_catalog_gap`, `call_card` (`headline_hi`, `headline_en`, `data_points`, `suggested_action`), `competitive_positioning`, `scrape_status`, `scrape_latency_ms` |
| **Impact (a)** | Reps can say "Aap JustDial pe 24 products list kar rahe ho, IndiaMART pe sirf 8" — a fact, not a guess. |
| **Impact (b)** | Cross-platform gap feeds into BL Card final churn adjustment (`+10` if gap < -40%, `+5` if < -20%) — surfaces sellers who are actively migrating away. |

---

### 4.13 BL Upgrade
**File:** `churn_analysis/skills/bl_upgrade_skill.py`  ·  **Spec:** `skills/bl_upgrade.md`

| | |
|---|---|
| **Problem** | Some Amber/Green sellers are actually undersold — they should be on a higher tier but the rep never offered. |
| **Solution** | Check if seller's BL/LMS/Activity bands warrant upgrade (e.g. high engagement + lower-tier package). |
| **Outputs** | `eligible`, `mode` (UPGRADE/DOWNGRADE/HOLD), `reason` |
| **Impact** | Revenue uplift on healthy accounts the team would otherwise leave alone. |

---

### 4.14 Winback Priority (v2.0)
**File:** `churn_analysis/skills/winback_priority_skill.py`  ·  **Spec:** `skills/winback_priority.md`

| | |
|---|---|
| **Problem** | v1 scored winback on lifetime enq + RCA + demand only. Missed: RCA confidence, recent activity, paid history, trajectory, peer recovery, signal interactions. Cool-off was a soft factor. |
| **Solution** | 7 weighted sub-scores + interaction multiplier + cool-off hard gate + LLM second opinion (±10). |
| **Sub-scores (0..1)** | `historical_quality` (60% enq_30d + 40% reply_rate) · `demand_score` (current_demand_index/100) · `recoverability` (RCA lookup × rca_confidence) · `paid_history_bonus` (1.0 paid / 0.3 freelist) · `trajectory_factor` (TYPE_B 1.0 > TYPE_A 0.7 > TYPE_C 0.2) · `peer_recovery` (peer_delta_pct trend) · `recency_bonus` (post cool-off decay over 365d) |
| **Weights** | 20% · 25% · 20% · 10% · 10% · 5% · 10%. If `demand_index` missing → weight redistributed to recoverability (no silent 50 default). |
| **Recoverability lookup** | NO_LEADS 90, POOR_CATALOG 75, BL_DECLINE 60, LOW_ENGAGEMENT 55, LOW_PNS_RESPONSE 50, PEER_GAP 50, RAG_RISK 40, UNKNOWN 30 |
| **Interaction bonus** | demand ≥ 0.7 AND recoverability ≥ 0.7 → ×1.10; both ≥ 0.5 → ×1.05; else ×1.00 |
| **LLM second opinion** | `±10` adjustment with one-line justification — same pattern as churn scoring |
| **Cool-off hard gate** | 180d for FREELIST, 90d for paid. **HIGH** tier requires `cool_off_elapsed` AND score ≥ 65; otherwise forced to MEDIUM. Prevents calling too early. |
| **Final formula** | `pre_llm = round(100 × base × interaction_bonus)`; `winback_score = clamp(pre_llm + llm_adjustment, 0, 100)` |
| **Tiers** | HIGH (≥65 + cool-off elapsed) · MEDIUM (40-64, or ≥65 pre-cool-off) · LOW (<40) |
| **Outputs** | `winback_score`, `priority`, `pre_llm_score`, `llm_used`, `llm_adjustment`, `llm_justification`, `interaction_bonus`, `sub_scores`, `weights`, `rca_used`, `rca_confidence`, `demand_provided`, `cool_off_required_days`, `cool_off_elapsed`, `cool_off_days_remaining`, `winback_pitch_type`, `opening_line_hi`, `gifted_lead_eligible`, `estimated_conversion_probability` (= score/100 × 0.40), `recommended_package` |
| **Impact** | Of ~50K churned sellers, surfaces the top ~5K worth calling this week. Saves call capacity, raises winback conversion. |

---

### 4.15 BL Card (Aggregator)
**File:** `churn_analysis/skills/bl_card_skill.py`  ·  **Spec:** `skills/bl_card.md`

| | |
|---|---|
| **Problem** | Outputs from 13 skills are spread across `flow`. Reps and CRM need a single document. |
| **Solution** | Final aggregator. Reads all `flow.*` keys, builds a structured card with sections: `header`, `scores`, `root_cause`, `signals`, `action_plan`, `messaging`, `interventions`, `lookalikes`, `cross_platform`, and `summary_text` (plain-text CRM paste). |
| **Cross-platform adjustment** | Applies +10/+5 to `final_churn_score` based on competitor gap (since CP runs after churn_scoring). |
| **Verdict logic** | `Red OR churn_score ≥ 70` → **CRITICAL** · `Amber OR ≥ 40` → **AT RISK** · LLM-flagged Critical/High → **AT RISK** · else **HEALTHY** |
| **Priority (0-100)** | Score that lets the team queue sellers cleanly. |
| **Impact** | One card = one call. End-to-end. |

---

### 4.16 Call Summary (post-call)
**File:** `churn_analysis/skills/call_summary_skill.py`  ·  **Spec:** `skills/call_summary.md`

| | |
|---|---|
| **Problem** | Post-call notes are inconsistent; nobody knows the next action; sentiment is lost. |
| **Solution** | Paste the call transcript → LLM returns 3-line summary, sentiment, updated RCA, next-action card, updated churn-risk tier. |
| **Inputs** | `glid`, `call_type` (RETENTION/RENEWAL/WELCOME/WINBACK), pre-call RCA, transcript |
| **Outputs** | `summary` (3 lines), `sentiment`, `updated_rca`, `next_action`, `updated_risk_tier` |
| **UI** | Separate **Post-Call Summary** page in Streamlit (does not run full pipeline). |
| **Impact** | Closes the loop. Today's call output becomes tomorrow's intervention input. Reps stop forgetting commitments. |

---

## 5. User Interfaces

### Streamlit (`churn_ui.py`)
- **Pipeline Analysis** page: enter GLID → full BL Card at top with 5-column header
  (Verdict / Priority / Churn Score / Risk / **🏠 IM Products**) → cross-platform
  pill grid → 13 skill-specific renderers, each in a phase block.
- **Score derivation dropdowns** for both Churn Score (6-step) and Winback Score
  (6-step) — `st.expander` reveals: per-sub-score table, weight × value = contribution,
  interaction bonus, LLM justification, cool-off warning.
- **Cross-platform section** shows all 4 platforms (JustDial / TradeIndia / Own Site /
  Shopify) as pills with product counts and IM-vs-others gap bar.
- **Post-Call Summary** page: transcript paste → call_summary skill output.

### Python CLI (`python -m churn_analysis ...`)
- `skills` — list all available skills
- `skill <name> <GLID> [--pretty|--explain|--json]` — run one skill
  - `--pretty` = concise summary
  - `--explain` = full SCORE DERIVATION box (works for `churn_scoring` and `winback_priority`)
  - `--json` = compact JSON for piping
- `pipeline --glid <GLID> [--no-llm]` — full pipeline for one seller
- `pipeline --glids-file FILE [--no-llm] [--out-dir DIR]` — batch

---

## 6. Business Impact at IndiaMART

| Lever | Mechanism | Expected uplift |
|---|---|---|
| **Earlier churn detection** | Phase 2 churn scoring + Phase 0 trajectory catches cliffs in week 1 of the drop instead of month 3. | 15-25% reduction in time-to-detect for Red sellers. |
| **Accurate root cause** | SHAP RCA + LLM second-opinion + cohort lookalikes give the rep a precise angle. | Higher first-call resolution rate. |
| **Personalised scripts** | LLM script generation eliminates robotic templates. | Higher seller engagement on calls. |
| **Competitive intel** | Cross-platform scraping shows where the seller is investing instead. | Reframes retention argument from "renew" to "consolidate". |
| **Activation lift for new sellers** | Onboarding v2.0 + city/category risk priors + LLM activation plan address gaps in week 1. | Reduces silent ghost-listings; raises activation rate. |
| **Smarter winback** | Winback v2.0's 7-factor scoring + cool-off gate + LLM filter selects truly recoverable sellers. | Higher winback conversion per call attempt. |
| **Closed-loop learning** | Post-call summary updates RCA + risk tier; the next pipeline run sees the new state. | Continuous improvement without manual CRM updates. |
| **Rep productivity** | Pre-call brief replaces 5-min CRM trawl with a 30-sec card. | More calls/rep/day. |
| **Standardised retention** | One BL Card == one process == one CRM paste. Reduces rep-to-rep variance. | Easier QA and coaching. |

---

## 7. How to Run

### One-time setup
```bash
pip install -r requirements.txt          # or: pip install streamlit pyarrow requests playwright
python -m playwright install chromium    # for cross-platform scraping
```

### Single-seller pipeline
```bash
python -m churn_analysis pipeline --glid 11282573
```

### Streamlit UI
```bash
streamlit run churn_ui.py
```

### Run one skill (with derivation)
```bash
python -m churn_analysis skill churn_scoring   11282573 --explain
python -m churn_analysis skill winback_priority 11282573 --explain
python -m churn_analysis skill cross_platform_intelligence 53449 --pretty
```

### Batch
```bash
python -m churn_analysis pipeline --glids-file glids.txt --out-dir ./runs/batch1 --no-llm
```

---

## 8. Environment

| Var | Purpose | Default |
|---|---|---|
| `LLM_API_KEY` | OpenAI-compatible API key. If unset, LLM skills fall back to templates. | — |
| `LLM_BASE_URL` | OpenAI-compatible base URL. | `https://api.openai.com/v1` |
| `LLM_MODEL` | Model name for chat completions. | `gpt-4o-mini` |
| `_CHURN_EXPLAIN` | Internal flag set by `--explain`; reveals derivation breakdowns. | unset |
| `PYTHONIOENCODING` | Set to `utf-8` on Windows to avoid `cp1252` errors with Hindi/em-dash output. | — |

---

## 9. Extending the Framework

To add a new skill:

1. **Write `skills/<name>.md`** with YAML frontmatter declaring `name`, `version`,
   `python_class`, `inputs` (required/optional with `source:` resolvers), `outputs`.
2. **Create `churn_analysis/skills/<name>_skill.py`** subclassing `Skill`, with
   `name`, `version`, `required_inputs`, `optional_inputs`, `invoke()`, `fallback()`.
3. **Register** in `churn_analysis/skills/registry.py`.
4. **Add to a phase** in `skills/pipeline.md` (with a condition if applicable).
5. **Optional**: add a renderer in `churn_ui.py` `SKILL_RENDERERS` and a pretty-printer
   in `cli.py`.

The `SkillLoader` automatically resolves `source: snapshot.*`, `context.*`,
`behavioral.*`, `derived.*`, `flow.*` — no plumbing code required.

---

## 10. Repository Layout

```
Hackathon/
├── README.md                       ← (this file)
├── churn_ui.py                     ← Streamlit UI (Pipeline + Post-Call pages)
├── implementation_plan.md          ← original product spec
├── skills/                         ← machine-parseable specs + docs
│   ├── pipeline.md                 ← phase definitions
│   ├── churn_scoring.md            ← + 14 other skill specs
│   └── ...
├── churn_analysis/
│   ├── __main__.py                 ← `python -m churn_analysis`
│   ├── cli.py                      ← CLI entry + pretty printers
│   ├── pipeline_runner.py          ← reads pipeline.md + executes phases
│   ├── skill_loader.py             ← parses MD specs, resolves input sources
│   └── skills/
│       ├── base_skill.py
│       ├── registry.py
│       ├── churn_scoring_skill.py
│       ├── winback_priority_skill.py
│       ├── cross_platform_intelligence_skill.py
│       └── ... (13 skill implementations)
└── seller_survival/                ← snapshot fetch + feature extraction layer
    ├── slim_loader.py
    └── feature_schema.py
```

---

**Built for the IndiaMART seller retention team. Designed to be transparent
(every score is explainable), composable (every skill runs standalone), and
extensible (every capability is one MD + one Python file away).**
