"""Singleton skill registry — auto-discovers skills/*/skill.py modules.

Each Anthropic-format skill folder under <repo>/skills/<name>/ contains a `skill.py`
module that defines a subclass of `Skill`. This registry walks that directory,
imports each module by file path via importlib, locates the Skill subclass, and
registers an instance under its `name` attribute.

The advantage over hard-coded imports: adding a new skill = drop a folder, no
Python edit required.
"""
import importlib.util
import inspect
import os
import sys

from .base_skill import Skill


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill):
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def run(self, name: str, inputs: dict):
        skill = self.get(name)
        if skill is None:
            from .base_skill import SkillResult
            return SkillResult(success=False, data={}, error=f"Skill '{name}' not found")
        return skill.run(inputs)

    def names(self) -> list[str]:
        return list(self._skills.keys())


registry = SkillRegistry()


# ── Auto-discovery ──────────────────────────────────────────────────────────

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_SKILLS_DIR = os.path.join(_REPO_ROOT, "skills")


def _discover_and_register():
    """Walk skills/<name>/skill.py, import each via importlib, register Skill subclasses."""
    if not os.path.isdir(_SKILLS_DIR):
        return

    # Ensure the repo root is on sys.path so `from churn_analysis.skills.base_skill import ...`
    # works inside each skill.py.
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)

    for entry in sorted(os.listdir(_SKILLS_DIR)):
        folder = os.path.join(_SKILLS_DIR, entry)
        if not os.path.isdir(folder):
            continue
        skill_py = os.path.join(folder, "skill.py")
        scripts_py = os.path.join(folder, "scripts", "skill.py")
        if os.path.isfile(scripts_py):
            skill_py = scripts_py
        elif not os.path.isfile(skill_py):
            continue
        mod_name = f"_skill_{entry.replace('-', '_')}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, skill_py)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
        except Exception as exc:
            print(f"  [WARN] Could not import skill {entry}: {exc}")
            continue

        # Find the Skill subclass defined in this module (not imported from base).
        for _attr_name, obj in inspect.getmembers(module, inspect.isclass):
            if obj is Skill:
                continue
            if not issubclass(obj, Skill):
                continue
            if obj.__module__ != mod_name:
                # Skip Skill imported from base; we only want the subclass defined here.
                continue
            try:
                instance = obj()
            except Exception as exc:
                print(f"  [WARN] Could not instantiate {obj.__name__}: {exc}")
                continue
            registry.register(instance)
            break


_discover_and_register()
