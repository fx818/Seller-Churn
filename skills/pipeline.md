---
name: pipeline
version: "1.0"
description: Full churn analysis pipeline — all phases using MD-driven skills

phases:
  - id: phase0_benchmark
    name: "Phase 0 — Benchmarks (Peer + Demand + Trajectory)"
    condition: null
    skills:
      - peer_benchmark
      - demand_index
      - conversion_point

  - id: phase1_onboarding
    name: "Phase 1 — Onboarding Health"
    condition: "context.account_age_days <= 90"
    skills:
      - onboarding_health

  - id: phase2_churn
    name: "Phase 2 — Churn Scoring + RCA"
    condition: null
    skills:
      - churn_scoring
      - shap_rca

  - id: phase2_llm
    name: "Phase 2b — LLM Cohort Scoring"
    condition: "context.account_age_days > 90 AND derived.snapshots_exist"
    skills:
      - llm_cohort_scorer

  - id: phase3_actions
    name: "Phase 3 — Action Skills (Red + Amber only)"
    condition: "flow.risk in [Red, Amber]"
    skills:
      - pre_call_brief
      - whatsapp_message
      - script_generation
      - gifted_lead

  - id: phase3c_cross_platform
    name: "Phase 3c — Cross-Platform Intelligence (Playwright)"
    condition: "flow.risk in [Red, Amber] AND flow.rca_category in [POOR_CATALOG, PEER_GAP, NO_LEADS, LOW_ENGAGEMENT, BL_DECLINE]"
    skills:
      - cross_platform_intelligence

  - id: phase4
    name: "Phase 4 — BL Upgrade"
    condition: null
    skills:
      - bl_upgrade

  - id: phase5
    name: "Phase 5 — Winback Priority"
    condition: "flow.risk == Red"
    skills:
      - winback_priority

  - id: phase6_card
    name: "Phase 6 — BL Card (Aggregated Briefing)"
    condition: null
    skills:
      - bl_card
---

# Pipeline — Full Churn Analysis

This file is the **executable definition** of the churn analysis pipeline.
The `PipelineRunner` reads the frontmatter above and runs each phase in order.

## How It Works

1. **Fetch APIs** — `seller_survival.slim_loader.fetch_for_glid()` (cache-first)
2. **Extract snapshot** — `seller_survival.feature_schema.extract_snapshot()`
3. **Run phases** — each phase's `condition` is evaluated; if true, its skills run
4. **Data flows forward** — skill outputs are merged into `flow` state for downstream skills
5. **Write output** — JSON report saved to `churn_analysis/runs/run_<timestamp>/`

## Condition Syntax

Conditions support:
- `context.<field> <= <value>` — compare snapshot context field
- `derived.<field>` — computed values (bl_velocity_pct, snapshots_exist, etc.)
- `flow.<field> in [Val1, Val2]` — check flow state membership
- `flow.<field> == Val` — equality check
- `A AND B` — logical AND
- `NOT <cond>` — negation
- `null` — always runs

## CLI Usage

```bash
# Single seller
python -m churn_analysis pipeline --glid 11282573

# Batch
python -m churn_analysis pipeline --glids-file glids.txt

# Skip LLM (faster)
python -m churn_analysis pipeline --glids-file glids.txt --no-llm

# Specify output directory
python -m churn_analysis pipeline --glid 11282573 --out-dir ./my_run
```

## Output Structure

```
churn_analysis/runs/run_20260515_143022/
├── report.json           ← full pipeline output for all sellers
├── seller_<GLID>.json    ← per-seller results
└── summary.json          ← Red/Amber/Green counts, timing
```
