"""
SkillLoader — parses skills/*.md frontmatter and maps snapshot fields to skill inputs.

The MD file is the contract. SkillSpec tells the runner:
  - which Python registry key to call (python_class)
  - how to build inputs from snapshot / derived / flow state
"""
import os
import re
from dataclasses import dataclass, field
from typing import Any


# ── Frontmatter parser ────────────────────────────────────────────────────────

def _parse_frontmatter(path: str) -> dict:
    """Read YAML frontmatter between --- delimiters from an MD file."""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end == -1:
        return {}
    yaml_str = content[3:end].strip()
    import yaml
    return yaml.safe_load(yaml_str) or {}


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class InputSpec:
    key: str
    source: str          # e.g. "context.rag_category" or "flow.risk"
    type: str = "any"
    default: Any = None
    required: bool = False


@dataclass
class OutputSpec:
    key: str
    type: str = "any"


@dataclass
class SkillSpec:
    name: str
    version: str = "1.0"
    description: str = ""
    python_class: str = ""   # registry key (same as name by default)
    category: str = ""
    inputs_required: list = field(default_factory=list)
    inputs_optional: list = field(default_factory=list)
    outputs: list = field(default_factory=list)


# ── SkillLoader ───────────────────────────────────────────────────────────────

_SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "skills")


class SkillLoader:
    def __init__(self, skills_dir: str | None = None):
        self._dir = os.path.abspath(skills_dir or _SKILLS_DIR)
        self._specs: dict[str, SkillSpec] = {}
        self._load_all()

    # ── Loading ───────────────────────────────────────────────────────────────

    def _load_all(self):
        if not os.path.isdir(self._dir):
            return
        for fname in sorted(os.listdir(self._dir)):
            if not fname.endswith(".md") or fname in ("README.md", "pipeline.md"):
                continue
            path = os.path.join(self._dir, fname)
            try:
                fm = _parse_frontmatter(path)
            except Exception as exc:
                print(f"  [WARN] Could not parse {fname}: {exc}")
                continue
            if not fm.get("name"):
                continue
            spec = self._build_spec(fm)
            self._specs[spec.name] = spec

    def _build_spec(self, fm: dict) -> SkillSpec:
        def _inp_list(raw: list) -> list[InputSpec]:
            result = []
            for item in (raw or []):
                if not isinstance(item, dict):
                    continue
                result.append(InputSpec(
                    key=str(item.get("key", "")),
                    source=str(item.get("source", "")),
                    type=str(item.get("type", "any")),
                    default=item.get("default"),
                    required=bool(item.get("required", False)),
                ))
            return result

        inp = fm.get("inputs") or {}
        out_raw = fm.get("outputs") or []
        outputs = [
            OutputSpec(key=str(o.get("key", "")), type=str(o.get("type", "any")))
            for o in out_raw if isinstance(o, dict)
        ]
        return SkillSpec(
            name=str(fm.get("name", "")),
            version=str(fm.get("version", "1.0")),
            description=str(fm.get("description", "")),
            python_class=str(fm.get("python_class", fm.get("name", ""))),
            category=str(fm.get("category", "")),
            inputs_required=_inp_list(inp.get("required") if isinstance(inp, dict) else []),
            inputs_optional=_inp_list(inp.get("optional") if isinstance(inp, dict) else []),
            outputs=outputs,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, name: str) -> SkillSpec | None:
        return self._specs.get(name)

    def list_skills(self) -> list[SkillSpec]:
        return sorted(self._specs.values(), key=lambda s: s.name)

    def build_inputs(
        self,
        spec: SkillSpec,
        snap: dict,
        derived: dict,
        flow: dict,
    ) -> dict:
        """Resolve all input sources into a concrete inputs dict for the skill."""
        inputs: dict[str, Any] = {}
        for inp in spec.inputs_required + spec.inputs_optional:
            val = self._resolve(inp.source, snap, derived, flow)
            if val is None and inp.default is not None:
                val = inp.default
            if val is not None:
                inputs[inp.key] = val

        # glid always present
        if "glid" not in inputs:
            inputs["glid"] = snap.get("glid")

        # Pass full snapshot and api_responses when available
        inputs.setdefault("snapshot", snap)
        if "api_responses" in flow:
            inputs.setdefault("api_responses", flow["api_responses"])
        if "account_age_days" in flow:
            inputs.setdefault("account_age_days", flow["account_age_days"])

        return inputs

    def _resolve(self, source: str, snap: dict, derived: dict, flow: dict) -> Any:
        if not source:
            return None
        parts = source.split(".", 1)
        ns = parts[0]
        rest = parts[1] if len(parts) > 1 else ""

        if ns == "snapshot":
            return _nested_get(snap, rest) if rest else snap
        elif ns == "context":
            return _nested_get(snap.get("context", {}), rest)
        elif ns == "behavioral":
            return _nested_get(snap.get("behavioral", {}), rest)
        elif ns == "derived":
            return derived.get(rest)
        elif ns == "flow":
            return flow.get(rest)
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _nested_get(d: Any, path: str) -> Any:
    if not path:
        return d
    for key in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d


def compute_derived(snap: dict) -> dict:
    """Compute derived values that don't exist directly in the snapshot."""
    bl  = snap.get("behavioral", {}).get("bl", {})
    lms = snap.get("behavioral", {}).get("lms", {})
    act = snap.get("behavioral", {}).get("activity", {})

    trend = act.get("monthly_trend", [])
    bl_vel = None
    if len(trend) >= 2:
        m0 = trend[-1].get("bl_cons", 0) or 0
        m1 = trend[-2].get("bl_cons", 0) or 0
        if m1 > 0:
            bl_vel = round((m0 - m1) / m1 * 100, 1)

    pns_r = lms.get("pns_received_90d", 0) or 0
    pns_a = lms.get("call_answered_90d", 0) or 0
    pns_pct = round(pns_a / pns_r * 100, 1) if pns_r > 0 else None

    # monthly_enq list for ConversionPointSkill
    monthly_enq = [m.get("total_enq", 0) or 0 for m in trend]

    _snaps_path = os.path.join(
        os.path.dirname(__file__), "..", "seller_survival", "data", "snapshots.parquet"
    )

    return {
        "bl_velocity_pct":  bl_vel,
        "pns_success_pct":  pns_pct,
        "monthly_enq":      monthly_enq,
        "snapshots_exist":  os.path.isfile(_snaps_path),
    }
