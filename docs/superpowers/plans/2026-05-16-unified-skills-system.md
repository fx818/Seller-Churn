# Unified Skills System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge `Skills_Ami/` (LLM-agent playbook) and `skills/` (Python pipeline) into a single AgentSkills-compliant system where the Python pipeline is the computation layer and the LLM skill is the interpretation layer.

**Architecture:** `skills/seller-churn-assessment/` becomes the LLM orchestrator skill. It calls `scripts/run_pipeline.py` (which wraps `PipelineRunner.run_seller()`) to execute all 16 Python leaf skills, then interprets the `flow_state` JSON using its 5-stage reference playbook. Each leaf skill's `skill.py` moves to `scripts/skill.py` and `meta.yaml` content merges into `SKILL.md` frontmatter under `metadata:`.

**Tech Stack:** Python 3.11+, pytest, PyYAML, AgentSkills spec (agentskills.io/specification)

---

## File Map

**Create:**
- `skills/seller-churn-assessment/SKILL.md`
- `skills/seller-churn-assessment/references/decline-analysis.md`
- `skills/seller-churn-assessment/references/engagement-health.md`
- `skills/seller-churn-assessment/references/root-cause-diagnosis.md`
- `skills/seller-churn-assessment/references/risk-synthesis.md`
- `skills/seller-churn-assessment/references/action-outreach.md`
- `skills/seller-churn-assessment/scripts/run_pipeline.py`
- `tests/test_registry_discovery.py`
- `tests/test_run_pipeline.py`
- `skills/<each>/scripts/skill.py` (moved from `skills/<each>/skill.py`)

**Modify:**
- `churn_analysis/skills/registry.py` — discover `scripts/skill.py`
- `churn_analysis/skill_loader.py` — merge `metadata:` frontmatter fields

**Delete (Task 6 only):**
- `Skills_Ami/` folder
- All `skills/<name>/meta.yaml`
- All `skills/<name>/skill.py` (root-level, after moving to `scripts/`)

---

## Task 1: Update registry.py to discover `scripts/skill.py`

**Files:**
- Modify: `churn_analysis/skills/registry.py:61-66`
- Create: `tests/test_registry_discovery.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_registry_discovery.py
import os, sys, importlib, shutil, textwrap, pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

SKILL_DIR = os.path.join(REPO, "skills")

def test_registry_discovers_scripts_skill_py(tmp_path):
    """Registry must register a skill whose skill.py lives in scripts/."""
    from churn_analysis.skills.base_skill import Skill, SkillResult

    # Create a throwaway skill folder with scripts/skill.py layout
    skill_folder = tmp_path / "test-scripts-skill"
    scripts_dir = skill_folder / "scripts"
    scripts_dir.mkdir(parents=True)

    (skill_folder / "SKILL.md").write_text(
        "---\nname: test-scripts-skill\ndescription: test\n---\n"
    )
    (scripts_dir / "skill.py").write_text(textwrap.dedent("""
        from churn_analysis.skills.base_skill import Skill, SkillResult

        class TestScriptsSkill(Skill):
            name = "test-scripts-skill"
            def run(self, inputs):
                return SkillResult(success=True, data={"ok": True})
    """))

    # Point a fresh registry at this tmp dir
    from churn_analysis.skills import registry as reg_module
    from importlib import reload

    original_dir = reg_module._SKILLS_DIR
    reg_module._SKILLS_DIR = str(tmp_path)

    # Re-run discovery
    reg_module.registry._skills.clear()
    reg_module._discover_and_register()

    result = reg_module.registry.run("test-scripts-skill", {})
    assert result.success is True, f"Expected success, got error: {result.error}"

    # Restore
    reg_module._SKILLS_DIR = original_dir
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/Users/Imart/Desktop/Hackathon
python -m pytest tests/test_registry_discovery.py -v
```
Expected: FAIL — registry does not discover `scripts/skill.py`

- [ ] **Step 3: Update registry.py discovery logic**

In `churn_analysis/skills/registry.py`, replace lines 65-67:
```python
        skill_py = os.path.join(folder, "skill.py")
        if not os.path.isfile(skill_py):
            continue
```
With:
```python
        skill_py = os.path.join(folder, "skill.py")
        scripts_py = os.path.join(folder, "scripts", "skill.py")
        if os.path.isfile(scripts_py):
            skill_py = scripts_py
        elif not os.path.isfile(skill_py):
            continue
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_registry_discovery.py -v
```
Expected: PASS

- [ ] **Step 5: Smoke-test existing skills still load**

```bash
python -m churn_analysis skills
```
Expected: all 16 skills listed (bl-card, bl-upgrade, call-summary, churn-scoring, conversion-point, cross-platform-intelligence, demand-index, gifted-lead, llm-cohort-scorer, onboarding-health, peer-benchmark, pre-call-brief, script-generation, shap-rca, whatsapp-message, winback-priority)

- [ ] **Step 6: Commit**

```bash
git add churn_analysis/skills/registry.py tests/test_registry_discovery.py
git commit -m "feat: registry discovers scripts/skill.py alongside root skill.py"
```

---

## Task 2: Update skill_loader.py to merge `metadata:` frontmatter fields

**Files:**
- Modify: `churn_analysis/skill_loader.py:96-107` (the `_load_all` method's merge block)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_registry_discovery.py`:

```python
def test_skill_loader_reads_metadata_frontmatter(tmp_path):
    """SkillLoader must read version/category/inputs/outputs/python_class from metadata: key."""
    from churn_analysis.skill_loader import SkillLoader

    skill_folder = tmp_path / "test-meta-skill"
    skill_folder.mkdir()
    (skill_folder / "SKILL.md").write_text(textwrap.dedent("""
        ---
        name: test-meta-skill
        description: test metadata merge
        metadata:
          version: "3.0"
          category: scoring
          python_class: test-meta-skill
          inputs:
            required:
              - key: glid
                source: snapshot.glid
                type: int
          outputs:
            - key: score
              type: int
        ---
        # body
    """))

    loader = SkillLoader(str(tmp_path))
    spec = loader.get("test-meta-skill")
    assert spec is not None
    assert spec.version == "3.0"
    assert spec.category == "scoring"
    assert spec.python_class == "test-meta-skill"
    assert len(spec.inputs_required) == 1
    assert spec.inputs_required[0].key == "glid"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_registry_discovery.py::test_skill_loader_reads_metadata_frontmatter -v
```
Expected: FAIL — spec.version is "1.0" (default), not "3.0"

- [ ] **Step 3: Update skill_loader.py `_load_all` merge block**

In `churn_analysis/skill_loader.py`, replace lines 102-107:
```python
            # Merge: SKILL.md provides name + description; meta.yaml provides everything else.
            merged = dict(meta)
            merged["name"]        = front.get("name")
            merged["description"] = front.get("description", "")
```
With:
```python
            # Merge: SKILL.md provides name + description; metadata: key provides
            # extension fields (version, category, inputs, outputs, python_class).
            # meta.yaml (if present) wins over frontmatter metadata for backward compat.
            front_meta = front.get("metadata") or {}
            merged = {**front_meta, **dict(meta)}
            merged["name"]        = front.get("name")
            merged["description"] = front.get("description", "")
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/test_registry_discovery.py -v
```
Expected: both tests PASS

- [ ] **Step 5: Smoke-test skills list unchanged**

```bash
python -m churn_analysis skills
```
Expected: 16 skills listed, versions/categories unchanged

- [ ] **Step 6: Commit**

```bash
git add churn_analysis/skill_loader.py tests/test_registry_discovery.py
git commit -m "feat: skill_loader merges metadata: frontmatter key alongside meta.yaml"
```

---

## Task 3: Create `scripts/run_pipeline.py`

**Files:**
- Create: `skills/seller-churn-assessment/scripts/run_pipeline.py`
- Create: `tests/test_run_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_run_pipeline.py
import json, subprocess, sys, os, pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(REPO, "skills", "seller-churn-assessment", "scripts", "run_pipeline.py")

def test_run_pipeline_missing_glid():
    """Script exits 1 and returns partial error JSON when no glid given."""
    result = subprocess.run(
        [sys.executable, SCRIPT],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data.get("_partial") is True
    assert "error" in data

def test_run_pipeline_invalid_glid():
    """Script exits 1 and returns partial error JSON for non-integer glid."""
    result = subprocess.run(
        [sys.executable, SCRIPT, "not_a_number"],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data.get("_partial") is True

def test_run_pipeline_tier_map():
    """map_tiers() converts Red→Critical, Amber→High, Green→Low."""
    # Import the map function directly without running main
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_pipeline", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    result = mod.map_tiers({
        "final_tier": "Red",
        "phases": {
            "phase2": {
                "churn-scoring": {"data": {"risk": "Amber"}}
            }
        }
    })
    assert result["final_tier"] == "Critical"
    assert result["phases"]["phase2"]["churn-scoring"]["data"]["risk"] == "High"

    # Green → Low
    assert mod.map_tiers({"risk": "Green"})["risk"] == "Low"
    # Unknown values pass through unchanged
    assert mod.map_tiers({"risk": "Unknown"})["risk"] == "Unknown"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_run_pipeline.py -v
```
Expected: FAIL — script does not exist yet

- [ ] **Step 3: Create `skills/seller-churn-assessment/scripts/` directory**

```bash
mkdir -p "skills/seller-churn-assessment/scripts"
```

- [ ] **Step 4: Write `run_pipeline.py`**

Create `skills/seller-churn-assessment/scripts/run_pipeline.py`:

```python
#!/usr/bin/env python3
"""run_pipeline.py — pipeline entry point for seller-churn-assessment skill.

Usage: python skills/seller-churn-assessment/scripts/run_pipeline.py <glid>

Runs all Python leaf skills via PipelineRunner, enriches result with derived
signals, maps risk vocabulary to Critical/High/Moderate/Low, and prints JSON.
"""
import json
import os
import sys

# Resolve repo root: skills/seller-churn-assessment/scripts/ → 3 levels up
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_SKILLS_DIR = os.path.join(_ROOT, "skills")
_TIER_MAP = {"Red": "Critical", "Amber": "High", "Green": "Low"}


def map_tiers(obj):
    """Recursively map Red/Amber/Green to Critical/High/Low in any dict/list."""
    if isinstance(obj, dict):
        return {
            k: (_TIER_MAP.get(v, v) if k == "risk" and isinstance(v, str) else map_tiers(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [map_tiers(item) for item in obj]
    return obj


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: run_pipeline.py <glid>", "_partial": True}))
        sys.exit(1)

    try:
        glid = int(sys.argv[1])
    except ValueError:
        print(json.dumps({"error": f"Invalid glid: {sys.argv[1]!r}", "_partial": True}))
        sys.exit(1)

    try:
        from churn_analysis.pipeline_runner import PipelineRunner
        from churn_analysis.skill_loader import compute_derived
        from seller_survival.slim_loader import fetch_for_glid
        from seller_survival.feature_schema import extract_snapshot

        api_resp = fetch_for_glid(glid, verbose=False)
        snap = extract_snapshot(glid, "target", api_resp)
        derived = compute_derived(snap)

        runner = PipelineRunner(_SKILLS_DIR)
        result = runner.run_seller(glid, verbose=False)

        # Attach derived signals so LLM playbook stages can read them directly
        result["derived"] = derived

        # Map tier vocabulary before LLM sees the output
        result = map_tiers(result)

        # Surface final_tier at top level for LLM convenience
        churn_data = (
            result.get("phases", {})
            .get("phase2_churn", {})
            .get("churn-scoring", {})
            .get("data", {})
        )
        result["final_tier"] = churn_data.get("risk", "Low")

        print(json.dumps(result, ensure_ascii=False, default=str))

    except Exception as exc:
        print(json.dumps({"error": str(exc), "_partial": True, "glid": glid}))
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_run_pipeline.py -v
```
Expected: all 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add skills/seller-churn-assessment/scripts/run_pipeline.py tests/test_run_pipeline.py
git commit -m "feat: add run_pipeline.py wrapper with tier vocabulary mapping"
```

---

## Task 4: Create `skills/seller-churn-assessment/` orchestrator skill

**Files:**
- Create: `skills/seller-churn-assessment/SKILL.md`
- Create: `skills/seller-churn-assessment/references/` (5 files moved from `Skills_Ami/references/`)

The `SKILL.md` content is identical to `Skills_Ami/Skill.md` with two changes:
1. Tool `get_seller_data(glid)` renamed and redescribed as `run_pipeline`
2. AgentSkills-compliant frontmatter (`name`, `description`, `compatibility`)

- [ ] **Step 1: Create `SKILL.md`**

Create `skills/seller-churn-assessment/SKILL.md`:

```markdown
---
name: seller-churn-assessment
description: Assess an IndiaMART paid seller's risk of downgrading to free in the next 60-90 days from their behavioral + context snapshot. Use whenever evaluating seller churn or retention risk, scoring a seller for renewal likelihood, diagnosing why a paid seller is disengaging, or producing a retention action card — even if the request only says "is this seller at risk?" or names a GLID. Produces a structured card with risk tier, 0-100 churn score, root cause, evidence, recommended actions, and (for Critical/High) drafted outreach. The diagnosis can downgrade as well as upgrade tiers, which is what stops the engine bucketing every seller as Critical.
compatibility: Requires Python 3.11+, seller_survival package, churn_analysis package
---

# Seller Churn Assessment

You are a churn-risk analyst for IndiaMART paid sellers. Your job: take ONE active paid seller's snapshot and return a structured risk card that a human RM can act on. Use ONLY the data returned by `run_pipeline` — do not invent fields, do not pattern-match against memorized archetypes.

## The two tools you have

- `run_pipeline(glid)` — execute the full Python skill pipeline for this seller. Runs all 16 Python leaf skills (churn scoring, SHAP RCA, peer benchmark, demand index, messaging, etc.) and returns a `flow_state` JSON containing: computed signals in `derived`, skill outputs in `phases`, and `final_tier` (Critical / High / Moderate / Low) at the top level. Call this exactly once at the start of the assessment. Invoke as: `python skills/seller-churn-assessment/scripts/run_pipeline.py <glid>`
- `read_skill_reference(name)` — read a stage reference file from `references/`. Call this whenever the playbook routes you to a reference (e.g. `name: "decline-analysis"`, no `.md` suffix). You may call it multiple times in sequence inside a single turn to fetch several stages at once.

The reference files are the detailed how-to for each stage. They are deliberately not pre-loaded — read the ones you need, when you need them, so the system prompt stays focused on the playbook and the output contract.

## Playbook

Run these stages in order. Each stage produces a "carry-forward" value that the next stage consumes. The names below match the reference filenames you pass to `read_skill_reference`. Read `derived.*` fields from `flow_state.derived` and skill outputs from `flow_state.phases`.

1. **`decline-analysis`** — read `derived.recent_vs_baseline_activity`, `derived.bl_consumption_rate`, `derived.bl_reply_rate`. Carry forward: `decline_severity` (none / mild / moderate / sharp / unknown) and `decline_notes`.
2. **`engagement-health`** — read `derived.pns_pickup_ratio`, `derived.cqs_band`, `derived.blni_volume`, plus the reply rate already computed. Also read `flow_state.phases.phase2_churn.churn-scoring.data.score_breakdown` for signal-level detail. Carry forward: `engagement_verdict` (healthy / mixed / frustrated / collapsed) and `engagement_notes`.
3. **`root-cause-diagnosis`** — the most important stage. Read `flow_state.context.mcats`, `flow_state.context.city`, `flow_state.context.nob`, `flow_state.phases.phase0_benchmark.peer-benchmark.data`, `flow_state.phases.phase2_churn.shap-rca.data.rca_category`. Apply world knowledge of the seller's category and city. Carry forward: `root_cause`, `category_context`, `diagnosis_notes`.
4. **`risk-synthesis`** — combine the three carry-forwards above into a final `risk_tier`, numeric ordinal `churn_score`, and `confidence`. The diagnosis can downgrade (niche_false_positive) or upgrade (newbie_ramp_failure) the tier — trust the diagnosis over `final_tier` from the pipeline.
5. **`action-outreach`** — produce up to 3 prioritized actions tied to the `root_cause` (not just the tier), and draft outreach text for Critical and High only.

## Output contract

Return ONLY a single ```json fenced block matching this schema. No prose outside the fence, no extra fields, no commentary.

```json
{
  "glid": 0,
  "risk_tier": "Critical | High | Moderate | Low",
  "churn_score": 0,
  "score_type": "ordinal_risk_score",
  "confidence": "high | medium | low",
  "tenure_bucket": "newbie | early | mature",

  "risk_drivers": [],
  "protective_factors": [],

  "root_cause": "",
  "category_context": "",

  "evidence": [
    {"signal": "", "value": "", "interpretation": ""}
  ],

  "recommended_actions": [
    {"priority": 1, "action": "", "rationale": ""}
  ],
  "drafted_outreach": {
    "channel": "call_script | email",
    "subject": "",
    "body": ""
  },

  "data_gaps": []
}
```

Populate `drafted_outreach` ONLY when `risk_tier` is Critical or High. For Moderate / Low, omit the field entirely (do not include an empty object or empty strings).

Populate `recommended_actions` ONLY when `risk_tier` is Critical or High (1-3 actions, driven by `root_cause`). For Moderate / Low, return `recommended_actions` as an empty list `[]`.

## Output style — per-field word budgets

An RM reads this card in a queue. Every line must carry signal, not narration. Use fragments and concrete numbers; drop hedge words, throat-clearing, and explanatory paragraphs. The budgets below are limits, not targets — shorter is fine.

| Field | Budget | Style |
|---|---|---|
| `category_context` | 1 sentence, ≤25 words | One sentence naming category + city + scale |
| `risk_drivers[]` | ≤15 words each | Fragment style: `"Zero BL consumption (0/254)"` not `"Zero BL consumption — only 0 of 254 allocated leads consumed indicating disengagement"` |
| `protective_factors[]` | ≤15 words each | Same fragment style as drivers |
| `evidence[].signal` | ≤4 words | Field name or short label, e.g. `"BL consumption rate"` |
| `evidence[].value` | ≤8 words | The number or string, no narration |
| `evidence[].interpretation` | ≤12 words | Fragment: `"Below the 0.3 healthy threshold"` not full sentence |
| `recommended_actions[].action` | 1 sentence, ≤25 words | Concrete imperative |
| `recommended_actions[].rationale` | ≤15 words | One phrase naming the gating factor |
| `drafted_outreach.subject` | ≤10 words | |
| `drafted_outreach.body` | 3 sentences max, ≤80 words | |
| `data_gaps[]` | ≤12 words each | Name the field + brief reason: `"BLNI breakdown null — cannot confirm wrong_product share"` |

## Data quality fallback

If `run_pipeline` returns `_partial: true` or `_errors`, do the assessment on what you have, lower `confidence`, and list the missing pieces in `data_gaps`. Do not refuse — partial assessments are valuable as long as the gaps are surfaced honestly.

## Hard guardrails

- **NACH / payment-status fields are the churn LABEL, not predictors.** Never use `api_nach_*` to justify a risk tier — that's circular.
- **High BLNI is engagement, not churn.** A seller actively marking BLNI is frustrated, not gone.
- **Do not pattern-match this seller's curve onto "churned-shape" archetypes.** Anchor on the seller's *own* baseline ratio.
- **A human RM sends the outreach.** Draft text must fit a copy-paste workflow; never imply auto-send.
- **Product rank distribution is a weak signal.** Do NOT lead `risk_drivers` or `evidence` with rank counts. Buyer-outcome signals are far stronger.
```

- [ ] **Step 2: Copy references from `Skills_Ami/references/`**

```bash
cp Skills_Ami/references/decline-analysis.md     skills/seller-churn-assessment/references/
cp Skills_Ami/references/engagement-health.md    skills/seller-churn-assessment/references/
cp Skills_Ami/references/root-cause-diagnosis.md skills/seller-churn-assessment/references/
cp Skills_Ami/references/risk-synthesis.md       skills/seller-churn-assessment/references/
cp Skills_Ami/references/action-outreach.md      skills/seller-churn-assessment/references/
```

- [ ] **Step 3: Verify directory structure**

```bash
find skills/seller-churn-assessment -type f
```
Expected output:
```
skills/seller-churn-assessment/SKILL.md
skills/seller-churn-assessment/references/action-outreach.md
skills/seller-churn-assessment/references/decline-analysis.md
skills/seller-churn-assessment/references/engagement-health.md
skills/seller-churn-assessment/references/risk-synthesis.md
skills/seller-churn-assessment/references/root-cause-diagnosis.md
skills/seller-churn-assessment/scripts/run_pipeline.py
```

- [ ] **Step 4: Commit**

```bash
git add skills/seller-churn-assessment/
git commit -m "feat: add seller-churn-assessment orchestrator skill with references"
```

---

## Task 5: Migrate pilot leaf skill — `churn-scoring`

**Files:**
- Modify: `skills/churn-scoring/SKILL.md`
- Create: `skills/churn-scoring/scripts/skill.py` (content from `skills/churn-scoring/skill.py`)
- Delete: `skills/churn-scoring/meta.yaml`, `skills/churn-scoring/skill.py`

The `meta.yaml` for `churn-scoring` currently contains:
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
    - key: enq_30d
      ...  # (full list in file)
outputs:
  - key: churn_score
    type: int
  ...
```

- [ ] **Step 1: Create `scripts/` directory for `churn-scoring`**

```bash
mkdir -p skills/churn-scoring/scripts
```

- [ ] **Step 2: Move `skill.py` to `scripts/skill.py`**

```bash
cp skills/churn-scoring/skill.py skills/churn-scoring/scripts/skill.py
```

- [ ] **Step 3: Update `skills/churn-scoring/SKILL.md` — add `metadata:` block**

Read `skills/churn-scoring/meta.yaml` first to get the exact content, then prepend it into the `SKILL.md` frontmatter under `metadata:`.

The updated `SKILL.md` frontmatter should look like:
```yaml
---
name: churn-scoring
description: Score a seller's churn risk on a 0–100 scale using 14 severity-tiered behavioral signals, a compound multiplier for stacked Red flags, a trajectory adjustment from the conversion-point skill, and a final LLM second-opinion of ±10. Use this skill in Phase 2 of the churn pipeline as the canonical risk score that every downstream phase branches on (`flow.risk` ∈ Red/Amber/Green).
compatibility: Requires Python 3.11+, seller_survival package
metadata:
  version: "2.0"
  category: scoring
  python_class: churn-scoring
  inputs:
    required:
      - key: glid
        source: snapshot.glid
        type: int
    optional:
      - key: enq_30d
        source: behavioral.bl.received_30d
        type: int
        default: 0
      - key: replied_30d
        source: behavioral.bl.replied_90d
        type: int
        default: 0
      - key: active_days_30d
        source: behavioral.lms.lms_active_days_30d
        type: int
        default: 0
      - key: bl_velocity_pct
        source: derived.bl_velocity_pct
        type: float
      - key: pns_success_pct
        source: derived.pns_success_pct
        type: float
      - key: rag
        source: context.rag_category
        type: str
      - key: cqs
        source: behavioral.activity.cqs
        type: float
      - key: hotleads_count
        source: behavioral.bl.hotleads_count
        type: int
        default: 0
      - key: event_count
        source: behavioral.activity.event_count
        type: int
        default: 0
      - key: trajectory_type
        source: flow.trajectory_type
        type: str
      - key: trajectory_label
        source: flow.trajectory_label
        type: str
      - key: cliff_drop_pct
        source: flow.cliff_drop_pct
        type: float
  outputs:
    - key: churn_score
      type: int
    - key: risk
      type: str
    - key: churn_reasons
      type: list
    - key: reason_tags
      type: list
    - key: score_breakdown
      type: dict
    - key: reply_rate_30d
      type: float
    - key: base_score
      type: float
    - key: compound_multiplier
      type: float
    - key: trajectory_adjustment
      type: int
    - key: pre_llm_score
      type: int
    - key: llm_adjustment
      type: int
    - key: llm_justification
      type: str
    - key: llm_used
      type: bool
    - key: red_flag_count
      type: int
---
```

- [ ] **Step 4: Verify skill still loads and runs**

```bash
python -m churn_analysis skills | grep churn-scoring
```
Expected: `churn-scoring` listed with version `2.0`, category `scoring`

- [ ] **Step 5: Run all existing tests**

```bash
python -m pytest tests/ -v
```
Expected: all PASS

- [ ] **Step 6: Delete legacy files**

```bash
rm skills/churn-scoring/skill.py
rm skills/churn-scoring/meta.yaml
```

- [ ] **Step 7: Verify skill still loads after deletion**

```bash
python -m churn_analysis skills | grep churn-scoring
```
Expected: still listed correctly (now loading from `scripts/skill.py` + `SKILL.md` metadata)

- [ ] **Step 8: Run all tests again**

```bash
python -m pytest tests/ -v
```
Expected: all PASS

- [ ] **Step 9: Commit**

```bash
git add skills/churn-scoring/
git commit -m "feat: migrate churn-scoring to scripts/skill.py + metadata frontmatter"
```

---

## Task 6: Migrate remaining 15 leaf skills

Apply the exact same pattern as Task 5 for each skill below. For each skill:
1. `mkdir -p skills/<name>/scripts`
2. `cp skills/<name>/skill.py skills/<name>/scripts/skill.py`
3. Merge `meta.yaml` content into `SKILL.md` frontmatter under `metadata:`
4. `python -m churn_analysis skills | grep <name>` — verify still listed
5. `rm skills/<name>/skill.py && rm skills/<name>/meta.yaml`
6. Verify again + run `python -m pytest tests/ -v`
7. Commit per skill: `git commit -m "feat: migrate <name> to scripts/skill.py + metadata frontmatter"`

**Skills to migrate (in this order):**
1. `bl-card`
2. `bl-upgrade`
3. `call-summary`
4. `conversion-point`
5. `cross-platform-intelligence`
6. `demand-index`
7. `gifted-lead`
8. `llm-cohort-scorer`
9. `onboarding-health`
10. `peer-benchmark`
11. `pre-call-brief`
12. `script-generation`
13. `shap-rca`
14. `whatsapp-message`
15. `winback-priority`

After all 15 are done:

- [ ] **Final verification: all 16 skills load**

```bash
python -m churn_analysis skills
```
Expected: 16 skills listed, all with correct version + category, none loading from root `skill.py`

- [ ] **Run full test suite**

```bash
python -m pytest tests/ -v
```
Expected: all PASS

---

## Task 7: Delete `Skills_Ami/` and commit cleanup

- [ ] **Step 1: Verify `skills/seller-churn-assessment/` is complete**

```bash
find skills/seller-churn-assessment -type f
```
Expected: SKILL.md, 5 reference files, scripts/run_pipeline.py all present

- [ ] **Step 2: Delete `Skills_Ami/`**

```bash
rm -rf Skills_Ami/
```

- [ ] **Step 3: Verify nothing imports from `Skills_Ami/`**

```bash
grep -r "Skills_Ami" . --include="*.py" --include="*.md"
```
Expected: no results (or only this plan file)

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/ -v
```
Expected: all PASS

- [ ] **Step 5: Smoke-test CLI end-to-end**

```bash
python -m churn_analysis skills
```
Expected: 16 leaf skills listed. `seller-churn-assessment` is NOT in this list (it is the orchestrator skill in `skills/seller-churn-assessment/`, not a registered Python skill).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: remove Skills_Ami/ — replaced by skills/seller-churn-assessment/"
```

---

## Self-Review Notes

- **Spec coverage:** All 9 migration steps covered. Tier mapping in Task 3. `meta.yaml` merger in Task 2+5+6. Orchestrator skill in Task 4. Deletion in Task 7. ✓
- **No placeholders:** All code blocks are complete. All commands have expected output. ✓
- **Type consistency:** `map_tiers()` defined in Task 3 and referenced only within `run_pipeline.py`. `SkillSpec.version` / `.category` used consistently from Task 2 onward. ✓
- **Note on `call-summary`:** This skill has `SKILL.md` and `meta.yaml` but check if it has `skill.py` before running `cp` — if missing, skip the copy step and only do the frontmatter merge.
