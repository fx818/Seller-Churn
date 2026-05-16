# tests/test_registry_discovery.py
import os, sys, textwrap, pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

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
    # churn_analysis/skills/__init__.py re-exports `registry` (the SkillRegistry instance)
    # which shadows the submodule on the package object; use sys.modules to get the real module.
    import churn_analysis.skills.registry  # ensure module is loaded
    reg_module = sys.modules["churn_analysis.skills.registry"]

    original_dir = reg_module._SKILLS_DIR
    original_skills = dict(reg_module.registry._skills)
    reg_module._SKILLS_DIR = str(tmp_path)
    try:
        reg_module.registry._skills.clear()
        reg_module._discover_and_register()
        result = reg_module.registry.run("test-scripts-skill", {})
        assert result.success is True, f"Expected success, got error: {result.error}"
    finally:
        reg_module._SKILLS_DIR = original_dir
        reg_module.registry._skills = original_skills
