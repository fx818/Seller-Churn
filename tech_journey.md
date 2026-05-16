# Technical Journey — Skill-Based Agent for Seller Churn

How this system actually got built. Architecture overview first, then the decisions and dead ends that shaped it.

---

## What it is

A skill-based agent that takes one IndiaMART seller (`GLID`) and returns a structured risk card. Sixteen leaf skills do the work; one orchestrator skill (`seller-churn-assessment`) drives them.

```
skills/
├── seller-churn-assessment/    ← orchestrator (agent entrypoint)
│   ├── SKILL.md                ← playbook + output contract
│   ├── scripts/run_pipeline.py ← runs all 16 leaf skills
│   └── references/             ← stage how-tos, lazy-loaded
├── pipeline.md                 ← 7-phase definition
└── <leaf-skill>/               ← SKILL.md + meta.yaml + scripts/skill.py
```

Each leaf skill is self-contained: `SKILL.md` for the spec-compliant frontmatter (`name`, `description`, `compatibility`), `meta.yaml` for the runner schema (`python_class`, `inputs`, `outputs`), `scripts/skill.py` for the Python.

### The 16 leaf skills

| Group | Skills |
|---|---|
| Scoring | `churn-scoring` · `onboarding-health` · `llm-cohort-scorer` |
| Analysis | `peer-benchmark` · `demand-index` · `conversion-point` · `shap-rca` · `call-summary` |
| Messaging | `pre-call-brief` · `whatsapp-message` · `script-generation` |
| Action | `gifted-lead` · `cross-platform-intelligence` · `bl-upgrade` · `winback-priority` · `bl-card` |

### Pipeline (`pipeline.md`)

7 phases, each phase is a list of skills with an optional condition. Phase 0 always runs (benchmarks); Phase 1 only for `age ≤ 90d`; Phase 3 only for `risk ∈ {Red, Amber}`; Phase 3c only when RCA hints at catalog / leads / engagement; Phase 5 only for Red. Phase 6 (BL Card) aggregates everything.

### Orchestrator

Two tools — `run_pipeline(glid)` runs the whole pipeline once; `read_skill_reference(name)` lazily reads a stage how-to. Then five interpretive stages: **decline → engagement → root-cause → synthesis → action**. Output is one JSON card per the schema in `seller-churn-assessment/SKILL.md`.

---

## Technical Journey

### 1. Started as one monolithic notebook

First cut: one Python file, ~20 if-statements, prints a verdict. Worked for one seller; broke the moment we had to explain *why* the score was what it was. **Lesson:** scoring logic must be inspectable — every penalty addressable by name.

### 2. Split into "skills"

Fifteen small files, each owning one capability, all implementing the same `Skill` interface (`name`, `required_inputs`, `optional_inputs`, `invoke()`, `fallback()`). Standalone-runnable, swappable, composable.

### 3. Specs as first-class artifacts

Nobody outside the team could tell what inputs a skill needed without reading Python. Every skill got a `SKILL.md` with YAML frontmatter declaring inputs and where each one comes from (`snapshot.*`, `context.*`, `flow.*`). `SkillLoader` resolves inputs automatically — no manual plumbing.

### 4. Pipeline as data

Phase order used to live in Python. Moved it into `pipeline.md` with conditions like `risk in [Red, Amber]`. Reordering, adding a gate, inserting a skill = a markdown edit. No Python diff.

### 5. Hybrid stats + LLM (and the calibration disaster)

v1 used flat penalties — any reply_rate &lt; 40% added the same +10. Flagged everything Red or nothing.

v2 introduced **severity tiers** (0% → +18, &lt;15% → +14, &lt;40% → +8) and a **compound multiplier** for stacked red flags. Overshot — 70% of sellers landed in Red.

**Calibration:** lowered base weights ~30%, raised compound threshold from 3 → 4 flags, lifted Red cutoff from 65 → 72. Validated against a hand-labelled set. GLID 29656 went from 90/Red to 55/Amber — same signals, fairer tier.

**LLM ±10 second opinion.** Bounded adjustment with a one-line justification. The cap matters — uncapped, the model occasionally swung the score 40 points on vibes.

### 6. Cross-platform scraping — the hard one

Playwright across JustDial / TradeIndia / Shopify / own-site. Three lessons:

- Product counts need **four fallback strategies**: JSON-LD → `__NEXT_DATA__` → CSS heuristics → text patterns. JustDial alone needed `ev_svc → sc_count → price_count → dimages_cnt → photocnt`.
- **Autoscroll** lazy grids or counts come back as 8 for a seller with 60.
- **Gap formula:** if platform counts are within 30% of each other → take MAX (same catalog mirrored); if they diverge → SUM (different inventory). We summed naively the first two times and got nonsense.

Runs only when RCA hints catalog / leads / engagement — saves the ~60% of sellers where scraping adds no signal.

### 7. Extracting the orchestrator

Sixteen pipeline outputs still needed human interpretation. Built `seller-churn-assessment` as a Claude-style agent skill: one `run_pipeline` call, five interpretive stages via lazily-loaded references, one JSON card out.

Key choice: **the orchestrator can override the pipeline's tier**. Two named overrides — `niche_false_positive` (downgrade a "Critical" niche seller in a tiny but stable category) and `newbie_ramp_failure` (upgrade a "Moderate" newbie who never activated). Without this, every low-activity niche seller got bucketed as Critical.

### 8. Surfacing the right signals to the orchestrator

Orchestrator stages couldn't dig into raw `behavioral.*` paths cleanly. Extended `compute_derived` with 8 playbook fields (`recent_vs_baseline_activity`, `bl_consumption_rate`, `bl_reply_rate`, `pns_pickup_ratio`, `cqs_band`, `blni_volume`, …) and surfaced the behavioral subtree to `flow_state` (commit `16956e8`). Each stage reads exactly the fields its reference names.

### 9. Spec compliance split

Frontmatter started as one block. Agent Skills spec only allows `name`, `description`, `compatibility` at the top level. Split: `SKILL.md` keeps spec-compliant fields, sibling `meta.yaml` holds the runner schema. Portable across spec-compliant runtimes; local runner still gets typed I/O.

---

## Implementation Notes

| Decision | Why |
|---|---|
| Every skill has a `fallback()` | LLM-backed skills must degrade to deterministic templates when `LLM_API_KEY` is missing. No silent crashes. |
| `force_no_llm` flag | Batch runs skip every LLM call. Deterministic for diffing, cheap for evaluation. |
| `_CHURN_EXPLAIN` env var | Set by `--explain`. Attaches full derivation (`base_score`, `compound_multiplier`, per-signal `score_breakdown`) so the CLI prints a 6-step explanation. |
| `PYTHONIOENCODING=utf-8` on Windows | Hindi + em-dash crashed under `cp1252`. Documented once. |
| No `try/except` swallowing | Failing skill marks itself `_partial: true` with `_errors`. Orchestrator lowers confidence and lists the gap in `data_gaps[]`. Partial > silent. |
| References load lazily | Not preloaded into the system prompt. Read on demand via `read_skill_reference(name)`. Keeps the prompt focused on the playbook. |

---

## What we'd do differently

- **Define the calibration set earlier.** We rewrote churn scoring twice because we lacked a hand-labelled validation set until late. Now it's the first artifact for any scoring change.
- **Pipeline conditions as a tiny DSL,** not string-templated Python.
- **Cross-platform should be async.** Four sequential scrapes → 4× latency cut available for free.
- **One shared LLM-second-opinion helper.** Churn scoring, winback, and onboarding each have their own ±10 wrapper. Same shape, three copies.

---

## Quick Start

```bash
# Orchestrator for one seller (returns the structured card)
python skills/seller-churn-assessment/scripts/run_pipeline.py 11282573

# One leaf skill standalone
python -m churn_analysis skill churn-scoring 11282573 --explain

# Full pipeline, batch, no LLM
python -m churn_analysis pipeline --glids-file glids.txt --no-llm
```

---

## SKILL.md + meta.yaml format

```yaml
# SKILL.md frontmatter — spec-compliant
---
name: churn-scoring
description: One-paragraph trigger description. Use whenever ...
compatibility: Requires Python 3.11+, seller_survival package
---
```

```yaml
# meta.yaml — local runner schema
version: "2.0"
category: scoring
python_class: churn-scoring
inputs:
  required:
    - { key: glid, source: snapshot.glid, type: int }
  optional:
    - { key: rag, source: context.rag_category, type: str }
outputs:
  - { key: churn_score, type: int }
```

### Source path namespaces

| Namespace | Maps to |
|---|---|
| `snapshot.*` | `snap[...]` |
| `context.*` | `snap["context"][...]` |
| `behavioral.{bl,lms,activity}.*` | `snap["behavioral"][...][...]` |
| `derived.*` | Computed — `bl_velocity_pct`, `pns_success_pct`, `recent_vs_baseline_activity`, `bl_consumption_rate`, `cqs_band`, … |
| `flow.*` | Output from an upstream skill |

---

## Adding a new skill

1. `mkdir skills/<name>/scripts && touch skills/<name>/{SKILL.md,meta.yaml,scripts/skill.py}`
2. Fill `SKILL.md` (spec frontmatter) and `meta.yaml` (runner schema).
3. Subclass `Skill` in `scripts/skill.py` — `name`, `version`, inputs, `invoke()`, `fallback()`.
4. Register in `churn_analysis/skills/registry.py`.
5. Add to a phase in `pipeline.md` with a condition if applicable.
6. To make it visible to the orchestrator: surface key outputs into `derived.*`, or add a stage reference under `seller-churn-assessment/references/`.
