# Unified Skills System Design

**Date:** 2026-05-16  
**Status:** Approved  
**Scope:** Merge `Skills_Ami/` (LLM-agent playbook) and `skills/` (Python pipeline) into a single AgentSkills-compliant system

---

## Problem

Two parallel systems exist for seller churn assessment:

| | `skills/` (Python pipeline) | `Skills_Ami/` (LLM agent) |
|---|---|---|
| Risk tiers | Red / Amber / Green | Critical / High / Moderate / Low |
| RCA | 8 SHAP reason tags | Free-text root_cause |
| Outreach | WhatsApp + call script (separate skills) | `drafted_outreach` in one card |
| Data source | Computed Python signals | Raw API via `get_seller_data` |
| Synthesis | Rule-based + LLM second-opinion | Full LLM reasoning |

They duplicate the same pipeline in two different architectures. The unified system makes the Python pipeline the computation layer and the LLM skill the interpretation layer.

---

## Design

### Architecture

```
skills/
├── seller-churn-assessment/       ← orchestrator (from Skills_Ami)
│   ├── SKILL.md                   ← LLM playbook; tool: run_pipeline(glid)
│   ├── references/                ← 5 stage refs (from Skills_Ami/references/)
│   └── scripts/
│       └── run_pipeline.py        ← wraps orchestrator.run_seller(); returns flow JSON
│
├── churn-scoring/                 ← leaf skills (structure updated, logic unchanged)
│   ├── SKILL.md                   ← frontmatter includes meta.yaml fields
│   └── scripts/
│       └── skill.py               ← moved from skill.py
│
├── shap-rca/                      ← same pattern as churn-scoring
├── ... (13 leaf skills total)
└── pipeline.md                    ← phase order + conditions (unchanged)
```

### Components

**`skills/seller-churn-assessment/` (orchestrator)**
- `SKILL.md` — LLM playbook from `Skills_Ami/Skill.md`. Tool `get_seller_data(glid)` replaced by `run_pipeline(glid)`. Five-stage playbook unchanged. Output contract unchanged (JSON risk card).
- `references/` — 5 files from `Skills_Ami/references/` moved verbatim: `decline-analysis.md`, `engagement-health.md`, `root-cause-diagnosis.md`, `risk-synthesis.md`, `action-outreach.md`.
- `scripts/run_pipeline.py` — thin CLI wrapper around `churn_analysis.agent.orchestrator.run_seller()`. Prints flow JSON to stdout. Maps `Red→Critical`, `Amber→High`, `Green→Low` before output.

**Leaf skills (`skills/<name>/`)**  
No logic changes. Structural changes only:
1. `meta.yaml` content merged into `SKILL.md` frontmatter under the `metadata:` key (AgentSkills spec extension point) — fields: `version`, `category`, `inputs`, `outputs`, `python_class`
2. `skill.py` → `scripts/skill.py`
3. `SKILL.md` gains `compatibility: Requires Python 3.11+, seller_survival package`

**`churn_analysis/skill_loader.py`**  
Updated to discover `scripts/skill.py` in addition to `skill.py` (backward-compatible during migration).

**`churn_analysis/skills/registry.py`**  
Updated to walk `scripts/skill.py` path alongside legacy `skill.py`.

**Tier vocabulary**  
Standardised to `Critical / High / Moderate / Low` everywhere. Mapping applied in `run_pipeline.py` output:
- `Red → Critical`
- `Amber → High`
- `Green → Low`
- `Moderate` used when onboarding or LLM cohort scorer elevates above Green but below Amber

---

### Data Flow (real-time, <5s)

```
UI request (glid)
       │
       ▼
seller-churn-assessment SKILL.md activated
       │
       ▼
run_pipeline(glid)  ← single script call, returns full flow_state JSON
  - cache-first API fetch via slim_loader
  - 13 leaf skills via orchestrator.run_seller()
  - tier vocabulary mapped to Critical/High/Moderate/Low
       │
       ▼
LLM reads flow_state
       │
       ▼
read_skill_reference("decline-analysis")
  → carry-forward: decline_severity, decline_notes
       │
       ▼
read_skill_reference("engagement-health")
  → carry-forward: engagement_verdict, engagement_notes
       │
       ▼
read_skill_reference("root-cause-diagnosis")
  → carry-forward: root_cause, category_context, diagnosis_notes
       │
       ▼
read_skill_reference("risk-synthesis")
  → produces: risk_tier, churn_score, confidence, evidence
       │
       ▼
  Critical/High only:
read_skill_reference("action-outreach")
  → produces: recommended_actions, drafted_outreach
       │
       ▼
Single JSON risk card → UI
```

**Latency budget:**

| Step | Expected |
|---|---|
| API fetch (cache hit) | ~200ms |
| 13 Python skills | ~300ms |
| LLM + 4–5 sequential ref loads | ~2.5–3.5s |
| **Total** | **~3–4s** |

Cache miss adds ~1–2s — still within 5s budget.

---

### Error Handling

- `run_pipeline.py` exits non-zero on fetch failure → LLM receives `{"error": "...", "_partial": true}` → existing partial-data fallback applies (lower confidence, gaps listed in `data_gaps[]`, no refusal)
- Individual leaf skill failures: `SkillResult(success=False)` — orchestrator continues, failed output marked `{"skipped": true, "error": "..."}` in flow_state
- Missing signals in LLM synthesis: existing hard guardrails in `SKILL.md` cover null handling per stage

---

### Migration Sequence

No breaking changes at any step:

1. Move `Skills_Ami/` → `skills/seller-churn-assessment/`
2. Add `scripts/run_pipeline.py` wrapper — test independently
3. Update `SKILL.md`: replace `get_seller_data` → `run_pipeline`
4. Update `registry.py` + `skill_loader.py` to discover `scripts/skill.py`
5. Migrate pilot leaf skill (`churn-scoring`): merge `meta.yaml` → `SKILL.md`, move `skill.py` → `scripts/skill.py`
6. Validate pilot end-to-end
7. Migrate remaining 12 leaf skills
8. Align tier vocabulary in orchestrator output
9. Delete `Skills_Ami/` and old `meta.yaml` files

---

## Constraints

- Real-time: single seller lookup, <5s total latency
- Output: rendered UI card (risk tier, score, evidence, actions, outreach draft)
- Both Python pipeline and LLM run fresh per request
- References load sequentially per AgentSkills progressive disclosure spec
- AgentSkills spec: `SKILL.md` frontmatter fields: `name`, `description`, `compatibility`; `scripts/` for executable code; `references/` for on-demand docs
