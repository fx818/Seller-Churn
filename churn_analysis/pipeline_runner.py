"""
PipelineRunner — reads skills/pipeline.md and runs all phases using the skills registry.

Each phase's condition is evaluated against context / derived / flow state.
Skill inputs are built by SkillLoader from MD specs.
"""
import json
import os
import sys
import time
from datetime import datetime

from .skill_loader import SkillLoader, compute_derived, _parse_frontmatter, _nested_get

_SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "skills")
_RUNS_DIR   = os.path.join(os.path.dirname(__file__), "..", "churn_analysis", "runs")
_HACKATHON  = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class PipelineRunner:
    def __init__(self, skills_dir: str | None = None):
        self._skills_dir = os.path.abspath(skills_dir or _SKILLS_DIR)
        self.loader = SkillLoader(self._skills_dir)
        self._phases = self._load_pipeline()

        # Import registry (skills are auto-registered on import)
        from .skills.registry import registry
        self._registry = registry

    # ── Pipeline MD loading ───────────────────────────────────────────────────

    def _load_pipeline(self) -> list[dict]:
        path = os.path.join(self._skills_dir, "pipeline.md")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"pipeline.md not found at {path}")
        fm = _parse_frontmatter(path)
        return fm.get("phases") or []

    # ── Public API ────────────────────────────────────────────────────────────

    def run_seller(self, glid: int, no_llm: bool = False, verbose: bool = True) -> dict:
        """Fetch → extract → run all pipeline phases. Returns full result dict."""
        if _HACKATHON not in sys.path:
            sys.path.insert(0, _HACKATHON)

        from seller_survival.slim_loader import fetch_for_glid
        from seller_survival.feature_schema import extract_snapshot

        if verbose:
            print(f"\n  [pipeline] Fetching APIs for GLID {glid}...")
        api_resp = fetch_for_glid(glid, verbose=False)

        if verbose:
            print(f"  [pipeline] Extracting snapshot...")
        snap = extract_snapshot(glid, "target", api_resp)

        derived = compute_derived(snap)

        # flow carries outputs from all previous skills (grows during pipeline)
        flow: dict = {
            "api_responses":    api_resp,
            "account_age_days": snap["context"].get("account_age_days", 0) or 0,
        }

        result = {
            "glid":    glid,
            "run_at":  datetime.now().isoformat(),
            "context": snap["context"],
            "phases":  {},
        }

        for phase in self._phases:
            phase_id   = phase.get("id", "unknown")
            phase_name = phase.get("name", phase_id)
            cond       = phase.get("condition")
            skill_names = phase.get("skills") or []

            if not _eval_condition(cond, snap, derived, flow, no_llm):
                if verbose:
                    print(f"  [pipeline] Skipped: {phase_name}")
                result["phases"][phase_id] = {"skipped": True, "reason": f"condition false: {cond}"}
                continue

            if verbose:
                print(f"  [pipeline] Running: {phase_name}")

            phase_results: dict[str, dict] = {}
            for skill_name in skill_names:
                spec = self.loader.get(skill_name)
                if spec is None:
                    if verbose:
                        print(f"    [WARN] No MD spec found for '{skill_name}' — skipping")
                    phase_results[skill_name] = {"skipped": True, "reason": "MD spec not found"}
                    continue

                inputs = self.loader.build_inputs(spec, snap, derived, flow)
                t0 = time.monotonic()
                sr = self._registry.run(spec.python_class, inputs)
                ms = int((time.monotonic() - t0) * 1000)

                phase_results[skill_name] = {
                    "success":    sr.success,
                    "confidence": sr.confidence,
                    "latency_ms": ms,
                    "data":       sr.data,
                    "error":      sr.error,
                }

                if sr.success and sr.data:
                    flow.update(sr.data)

                if verbose:
                    status = "OK" if sr.success else "FAIL"
                    print(f"    [{status}] {skill_name} ({ms}ms) confidence={sr.confidence:.2f}")

            result["phases"][phase_id] = phase_results

        return result

    def run_batch(
        self,
        glids: list[int],
        no_llm: bool = False,
        out_dir: str | None = None,
        verbose: bool = True,
    ) -> dict:
        """Run pipeline for a list of GLIDs. Saves JSON to runs/run_<timestamp>/."""
        run_id  = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = out_dir or os.path.join(_HACKATHON, "churn_analysis", "runs", f"run_{run_id}")
        os.makedirs(out_dir, exist_ok=True)

        results = {}
        total = len(glids)
        risk_counts = {"Red": 0, "Amber": 0, "Green": 0}

        print(f"\n[pipeline] Batch run: {total} sellers → {out_dir}")
        t0 = time.time()

        for i, glid in enumerate(glids, 1):
            try:
                res = self.run_seller(glid, no_llm=no_llm, verbose=verbose)
                results[str(glid)] = res

                # Track risk from churn_scoring
                risk = _deep_get(res, "phases.phase2_churn.churn_scoring.data.risk") or "Unknown"
                if risk in risk_counts:
                    risk_counts[risk] += 1

                # Per-seller file
                seller_path = os.path.join(out_dir, f"seller_{glid}.json")
                with open(seller_path, "w", encoding="utf-8") as f:
                    json.dump(res, f, indent=2, ensure_ascii=False, default=str)

                print(f"  [{i}/{total}] GLID {glid} → {risk}")
            except Exception as exc:
                print(f"  [{i}/{total}] GLID {glid} ERROR: {exc}")
                results[str(glid)] = {"glid": glid, "error": str(exc)}

        elapsed = time.time() - t0

        # Summary
        summary = {
            "run_id":  run_id,
            "total":   total,
            "elapsed": round(elapsed, 1),
            "risk":    risk_counts,
            "glids":   [str(g) for g in glids],
        }
        summary_path = os.path.join(out_dir, "summary.json")
        report_path  = os.path.join(out_dir, "report.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)

        print(f"\n[pipeline] Done in {elapsed:.1f}s")
        print(f"  Red: {risk_counts['Red']} | Amber: {risk_counts['Amber']} | Green: {risk_counts['Green']}")
        print(f"  Report -> {report_path}")
        print(f"  Summary -> {summary_path}")

        return results


# ── Condition evaluator (no eval()) ──────────────────────────────────────────

def _eval_condition(
    cond: str | None,
    snap: dict,
    derived: dict,
    flow: dict,
    no_llm: bool = False,
) -> bool:
    if cond is None:
        return True

    cond = cond.strip()

    # AND: split and evaluate each part
    if " AND " in cond:
        parts = [p.strip() for p in cond.split(" AND ")]
        return all(_eval_condition(p, snap, derived, flow, no_llm) for p in parts)

    # NOT
    if cond.startswith("NOT "):
        return not _eval_condition(cond[4:].strip(), snap, derived, flow, no_llm)

    # no_llm override
    if "llm" in cond.lower() and no_llm:
        return False

    # `field in [val, val, ...]`
    m = _re_in.match(cond)
    if m:
        lhs = _resolve_cond(m.group(1).strip(), snap, derived, flow)
        rhs_raw = m.group(2).strip()
        rhs_vals = [v.strip() for v in rhs_raw.split(",")]
        return str(lhs) in rhs_vals

    # `field == val`
    m = _re_eq.match(cond)
    if m:
        lhs = _resolve_cond(m.group(1).strip(), snap, derived, flow)
        rhs = _cast_cond(m.group(2).strip())
        return lhs == rhs

    # `field != val`
    m = _re_neq.match(cond)
    if m:
        lhs = _resolve_cond(m.group(1).strip(), snap, derived, flow)
        rhs = _cast_cond(m.group(2).strip())
        return lhs != rhs

    # `field <= val`
    m = _re_lte.match(cond)
    if m:
        lhs = _resolve_cond(m.group(1).strip(), snap, derived, flow)
        rhs = _cast_cond(m.group(2).strip())
        try:
            return float(lhs or 0) <= float(rhs)
        except (TypeError, ValueError):
            return False

    # `field >= val`
    m = _re_gte.match(cond)
    if m:
        lhs = _resolve_cond(m.group(1).strip(), snap, derived, flow)
        rhs = _cast_cond(m.group(2).strip())
        try:
            return float(lhs or 0) >= float(rhs)
        except (TypeError, ValueError):
            return False

    # `field < val`
    m = _re_lt.match(cond)
    if m:
        lhs = _resolve_cond(m.group(1).strip(), snap, derived, flow)
        rhs = _cast_cond(m.group(2).strip())
        try:
            return float(lhs or 0) < float(rhs)
        except (TypeError, ValueError):
            return False

    # `field > val`
    m = _re_gt.match(cond)
    if m:
        lhs = _resolve_cond(m.group(1).strip(), snap, derived, flow)
        rhs = _cast_cond(m.group(2).strip())
        try:
            return float(lhs or 0) > float(rhs)
        except (TypeError, ValueError):
            return False

    # Bare field (truthy check): e.g. "derived.snapshots_exist"
    val = _resolve_cond(cond, snap, derived, flow)
    return bool(val)


import re as _re_mod

_re_in  = _re_mod.compile(r"^(.+?)\s+in\s+\[(.+?)\]$")
_re_eq  = _re_mod.compile(r"^(.+?)\s+==\s+(.+)$")
_re_neq = _re_mod.compile(r"^(.+?)\s+!=\s+(.+)$")
_re_lte = _re_mod.compile(r"^(.+?)\s+<=\s+(.+)$")
_re_gte = _re_mod.compile(r"^(.+?)\s+>=\s+(.+)$")
_re_lt  = _re_mod.compile(r"^(.+?)\s+<\s+(.+)$")
_re_gt  = _re_mod.compile(r"^(.+?)\s+>\s+(.+)$")


def _resolve_cond(path: str, snap: dict, derived: dict, flow: dict) -> Any:
    """Resolve a dotted path like 'context.account_age_days' into a value."""
    parts = path.split(".", 1)
    ns = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    if ns == "context":
        return _nested_get(snap.get("context", {}), rest)
    elif ns == "behavioral":
        return _nested_get(snap.get("behavioral", {}), rest)
    elif ns == "derived":
        return derived.get(rest)
    elif ns == "flow":
        return flow.get(rest)
    elif ns == "snapshot":
        return _nested_get(snap, rest) if rest else snap
    return None


def _cast_cond(val: str) -> Any:
    val = val.strip().strip('"').strip("'")
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def _deep_get(d: dict, path: str) -> Any:
    """Navigate a dotted path through nested dicts."""
    for key in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d


from typing import Any
