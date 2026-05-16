# Skills — Agent-Skill Architecture

This directory holds the **skill-based agent** for IndiaMART seller churn. Each skill is a self-contained folder with a `SKILL.md` (Claude-style frontmatter + instructions) and a `scripts/skill.py` runner. The top-level [`seller-churn-assessment/`](seller-churn-assessment/) skill is the **orchestrator** an LLM agent invokes; the rest are the 16 leaf skills it composes through [`pipeline.md`](pipeline.md).

---

## Layout

```
skills/
├── seller-churn-assessment/        ← orchestrator skill (agent entrypoint)
│   ├── SKILL.md                    ← playbook + output contract
│   ├── scripts/run_pipeline.py     ← runs all 16 leaf skills, returns flow_state
│   └── references/                 ← stage how-tos, lazily loaded
│       ├── decline-analysis.md
│       ├── engagement-health.md
│       ├── root-cause-diagnosis.md
│       ├── risk-synthesis.md
│       └── action-outreach.md
│
├── pipeline.md                     ← 7-phase pipeline definition
│
├── churn-scoring/                  ← leaf skill
│   ├── SKILL.md                    ← frontmatter (name, inputs, outputs) + docs
│   └── scripts/skill.py            ← Python runner
├── shap-rca/
├── peer-benchmark/
├── demand-index/
├── conversion-point/
├── onboarding-health/
├── llm-cohort-scorer/
├── pre-call-brief/
├── whatsapp-message/
├── script-generation/
├── gifted-lead/
├── cross-platform-intelligence/
├── bl-upgrade/
├── winback-priority/
├── bl-card/
└── call-summary/
```

Every leaf skill follows the same shape: a `SKILL.md` with spec-compliant frontmatter (`name`, `description`, `compatibility`), a sibling `meta.yaml` with the runner schema (`python_class`, `inputs`, `outputs`), and a `scripts/skill.py` invoked by `pipeline_runner` and the CLI. The split keeps SKILL.md compliant with the Agent Skills spec (https://agentskills.io/specification) while preserving the rich input/output schema the local runner needs.

---

## The Orchestrator: `seller-churn-assessment`

The agent skill an LLM is given. Its two tools:

| Tool | Purpose |
|---|---|
| `run_pipeline(glid)` | Executes all 16 leaf skills end-to-end via `scripts/run_pipeline.py`, returns a `flow_state` JSON (`derived.*`, `phases.*`, `final_tier`). Call **once** per assessment. |
| `read_skill_reference(name)` | Lazily reads a stage how-to from `references/` (e.g. `"decline-analysis"`). Keeps the system prompt focused — references load on demand. |

### Playbook (5 stages, each consumes the previous carry-forward)

1. **`decline-analysis`** — recent vs baseline activity, BL consumption, reply rate → `decline_severity`
2. **`engagement-health`** — PNS pickup, CQS, BLNI, signal breakdown → `engagement_verdict`
3. **`root-cause-diagnosis`** — mcats + city + peer benchmark + SHAP RCA + world knowledge → `root_cause`, `category_context`
4. **`risk-synthesis`** — combine carry-forwards into final `risk_tier`, `churn_score`, `confidence`. May downgrade (`niche_false_positive`) or upgrade (`newbie_ramp_failure`) the pipeline's `final_tier`.
5. **`action-outreach`** — up to 3 root-cause-driven actions; outreach drafted only for Critical/High.

Output is a single fenced JSON card per the schema in `seller-churn-assessment/SKILL.md`.

### Hard guardrails (enforced in the skill prompt)

- NACH / payment-status fields are the churn **label**, never a predictor.
- High BLNI = engagement (frustrated), not churn.
- Do not pattern-match onto memorised "churn-shape" curves — anchor on the seller's own baseline.
- A human RM sends every outreach; drafts are copy-paste only.
- Product-rank distributions are weak signals; never lead with them.

---

## Quick Start

```bash
# Run the orchestrator for one seller (returns the structured card)
python skills/seller-churn-assessment/scripts/run_pipeline.py 11282573

# List all leaf skills
python -m churn_analysis skills

# Run one leaf skill standalone
python -m churn_analysis skill churn-scoring 11282573 --pretty
python -m churn_analysis skill churn-scoring 11282573 --explain   # full derivation
python -m churn_analysis skill winback-priority 11282573 --explain

# Full pipeline (all 7 phases per pipeline.md)
python -m churn_analysis pipeline --glid 11282573
python -m churn_analysis pipeline --glids-file glids.txt --no-llm

# Build reference library (required for llm-cohort-scorer)
python -m seller_survival build
```

---

## Skills Index (16 leaf skills)

### Scoring
| Skill | Description |
|-------|-------------|
| [`churn-scoring`](churn-scoring/SKILL.md) | 14-signal score 0-100, severity-tiered weights, compound multiplier, trajectory adj, LLM ±10 |
| [`llm-cohort-scorer`](llm-cohort-scorer/SKILL.md) | LLM cohort comparison against churned/retained lookalikes |
| [`onboarding-health`](onboarding-health/SKILL.md) | Early-life health (≤90d) — 7 checks + city/category risk priors + LLM activation plan |

### Analysis
| Skill | Description |
|-------|-------------|
| [`shap-rca`](shap-rca/SKILL.md) | Rule-based attribution mapped to 7 RCA buckets with confidence |
| [`peer-benchmark`](peer-benchmark/SKILL.md) | `mcat × city × ctype` cohort percentiles, gap severity |
| [`demand-index`](demand-index/SKILL.md) | 0-100 market demand index from saturation + trend + risk priors |
| [`conversion-point`](conversion-point/SKILL.md) | Classify 12-month trajectory: cliff / drift / never-engaged |
| [`call-summary`](call-summary/SKILL.md) | Post-call LLM summary, sentiment, updated RCA + risk tier |

### Messaging
| Skill | Description |
|-------|-------------|
| [`pre-call-brief`](pre-call-brief/SKILL.md) | Phone-card brief — opening line (Hi+En), signals, suggested actions |
| [`whatsapp-message`](whatsapp-message/SKILL.md) | Pre-call WhatsApp template (Hi+En) routed by RCA |
| [`script-generation`](script-generation/SKILL.md) | 5-part LLM-personalised call script, template fallback |

### Action
| Skill | Description |
|-------|-------------|
| [`gifted-lead`](gifted-lead/SKILL.md) | Allocate a high-quality un-served lead from seller's `mcat × city` pool |
| [`cross-platform-intelligence`](cross-platform-intelligence/SKILL.md) | Playwright scrape of JustDial / TradeIndia / Shopify / own site; IM-vs-others gap |
| [`bl-upgrade`](bl-upgrade/SKILL.md) | Tier upgrade / downgrade / hold eligibility from bands |
| [`winback-priority`](winback-priority/SKILL.md) | 7 sub-scores + cool-off hard gate + LLM ±10 |
| [`bl-card`](bl-card/SKILL.md) | Final aggregator — verdict, priority, summary text for CRM |

### Library
| Skill | Description |
|-------|-------------|
| [`build_library`](build_library.md) | Build reference `snapshots.parquet` |
| [`score_seller`](score_seller.md) | Full score via `seller_survival` |

### Pipeline
| File | Description |
|------|-------------|
| [`pipeline.md`](pipeline.md) | 7-phase pipeline — phases, conditions, skill order |

---

## SKILL.md Format

```yaml
---
name: churn-scoring
description: One-paragraph trigger description. Use whenever ...
compatibility: Requires Python 3.11+, seller_survival package
---

# Instructions, examples, derivation notes ...
```

The runner schema (`python_class`, `inputs`, `outputs`) lives in a sibling `meta.yaml` file:

```yaml
version: "2.0"
category: scoring
python_class: churn-scoring
inputs:
  required:
    - key: glid
      source: snapshot.glid
      type: int
  optional:
    - key: rag
      source: context.rag_category
      type: str
outputs:
  - key: churn_score
    type: int
```

### Source Path Namespaces

| Namespace | Maps to |
|-----------|---------|
| `snapshot.*` | `snap[...]` |
| `context.*` | `snap["context"][...]` |
| `behavioral.bl.*` | `snap["behavioral"]["bl"][...]` |
| `behavioral.lms.*` | `snap["behavioral"]["lms"][...]` |
| `behavioral.activity.*` | `snap["behavioral"]["activity"][...]` |
| `derived.*` | Computed fields — `bl_velocity_pct`, `pns_success_pct`, `monthly_enq`, `recent_vs_baseline_activity`, `bl_consumption_rate`, `bl_reply_rate`, `pns_pickup_ratio`, `cqs_band`, `blni_volume`, `snapshots_exist`, … |
| `flow.*` | Output from an upstream skill in the pipeline |

`derived.*` was recently extended with 8 playbook fields surfaced to `flow_state` so the orchestrator stages can consume them directly (see commit `16956e8`).

---

## Pipeline

[`pipeline.md`](pipeline.md) defines the full execution graph used by `run_pipeline`:

- Phase 0 — Benchmarks (always)
- Phase 1 — Onboarding Health (`account_age_days ≤ 90`)
- Phase 2 — Churn Scoring + RCA (always)
- Phase 2b — LLM Cohort (`age > 90 AND snapshots exist`)
- Phase 3 — Action skills (`risk ∈ [Red, Amber]`)
- Phase 3c — Cross-Platform (`Red/Amber AND rca ∈ {POOR_CATALOG, PEER_GAP, NO_LEADS, LOW_ENGAGEMENT, BL_DECLINE}`)
- Phase 4 — BL Upgrade (always)
- Phase 5 — Winback (`risk == Red`)
- Phase 6 — BL Card (always — aggregator)

Edit `pipeline.md` to reorder, add conditions, or insert a new skill — no Python changes required.

---

## Adding a New Skill

1. `mkdir skills/<name>/scripts && touch skills/<name>/SKILL.md skills/<name>/scripts/skill.py`
2. Fill `SKILL.md` frontmatter — `name`, `description`, `compatibility` only. Put runner schema (`python_class`, `inputs`, `outputs`) in a sibling `meta.yaml`.
3. Implement `scripts/skill.py` — subclass `Skill` with `name`, `version`, `required_inputs`, `optional_inputs`, `invoke()`, `fallback()`.
4. Register in [`churn_analysis/skills/registry.py`](../churn_analysis/skills/registry.py).
5. Add to a phase in [`pipeline.md`](pipeline.md) with a condition if applicable.
6. (Optional) Add a UI renderer in `churn_ui.py` `SKILL_RENDERERS` and a pretty-printer in `cli.py`.

If the new skill should be visible to the orchestrator, surface its key outputs into `derived.*` or add a stage reference under `seller-churn-assessment/references/`.
