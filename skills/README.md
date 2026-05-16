# Skills — MD-Driven Skill Definitions

Each `.md` file in this directory is both a **human-readable spec** and a **machine-parseable
definition**. The `SkillLoader` reads the YAML frontmatter to know what Python skill to run,
what inputs it needs, and where to get them from the seller snapshot.

---

## Quick Start

```bash
# List all available skills
python -m churn_analysis skills
python run_skill.py --list

# Run a single skill
python -m churn_analysis skill churn_scoring 11282573 --pretty
python run_skill.py churn_scoring 11282573 --pretty

# Full pipeline (all phases, from pipeline.md)
python -m churn_analysis pipeline --glid 11282573
python -m churn_analysis pipeline --glids-file glids.txt --no-llm

# Build reference library (required for LLM scoring)
python -m seller_survival build
```

---

## Skills Index

### Scoring
| Skill | Description | CLI |
|-------|-------------|-----|
| `churn_scoring` | 14-signal churn score 0-100 | `skill churn_scoring <GLID>` |
| `llm_cohort_scorer` | LLM cohort comparison (needs snapshots.parquet) | `skill llm_cohort_scorer <GLID>` |
| `onboarding_health` | Early-life health check (age <= 90d) | `skill onboarding_health <GLID>` |

### Analysis
| Skill | Description | CLI |
|-------|-------------|-----|
| `shap_rca` | Root cause analysis from reason tags | `skill shap_rca <GLID>` |
| `peer_benchmark` | Compare vs same-segment peers | `skill peer_benchmark <GLID>` |
| `demand_index` | Buyer demand health in city+category | `skill demand_index <GLID>` |
| `conversion_point` | Journey inflection type (cliff/drift/never) | `skill conversion_point <GLID>` |
| `call_summary` | LLM-powered call transcript analysis | See skill MD |

### Messaging
| Skill | Description | CLI |
|-------|-------------|-----|
| `pre_call_brief` | Rep-ready call brief card | `skill pre_call_brief <GLID>` |
| `whatsapp_message` | Hindi+English WhatsApp by RCA | `skill whatsapp_message <GLID>` |
| `script_generation` | 5-part call script by RCA | `skill script_generation <GLID>` |

### Action
| Skill | Description | CLI |
|-------|-------------|-----|
| `gifted_lead` | Best lead to gift at-risk seller | `skill gifted_lead <GLID>` |
| `winback_priority` | Red-tier winback score + pitch | `skill winback_priority <GLID>` |
| `bl_upgrade` | BL tier upgrade eligibility | `skill bl_upgrade <GLID>` |

### Library
| Skill | Description | CLI |
|-------|-------------|-----|
| `build_library` | Build reference snapshots.parquet | `python -m seller_survival build` |
| `score_seller` | Full score via seller_survival | `python -m seller_survival score <GLID>` |

### Pipeline
| File | Description |
|------|-------------|
| `pipeline.md` | Full pipeline definition — all phases, conditions, skill order |

---

## MD File Format

```yaml
---
name: skill_name              # registry key
version: "1.0"
category: scoring             # scoring | analysis | messaging | action | library
description: Short description
python_class: skill_name      # churn_analysis.skills.registry key

inputs:
  required:
    - key: glid
      source: snapshot.glid   # dotted path into snapshot / derived / flow
      type: int
  optional:
    - key: rag
      source: context.rag_category
      type: str

outputs:
  - key: churn_score
    type: int
---
# Human-readable docs below
```

### Source Path Namespaces
| Namespace | Maps to |
|-----------|---------|
| `snapshot.*` | `snap[...]` |
| `context.*` | `snap["context"][...]` |
| `behavioral.bl.*` | `snap["behavioral"]["bl"][...]` |
| `behavioral.lms.*` | `snap["behavioral"]["lms"][...]` |
| `behavioral.activity.*` | `snap["behavioral"]["activity"][...]` |
| `derived.*` | Computed: `bl_velocity_pct`, `pns_success_pct`, `monthly_enq`, `snapshots_exist` |
| `flow.*` | Output from a previous skill in the pipeline |

---

## Pipeline

The **`pipeline.md`** file defines the full execution graph:
- Which phases run
- Under what conditions (age, risk tier, snapshots availability)
- Which skills run in each phase
- How outputs flow between phases

To modify the pipeline order or add conditions — just edit `pipeline.md`.
No Python code changes needed.
