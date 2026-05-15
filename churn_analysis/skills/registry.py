"""Singleton skill registry — maps name → Skill instance."""
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


def _auto_register():
    from .churn_scoring_skill import ChurnScoringSkill
    from .shap_rca_skill import SHAPRCASkill
    from .peer_benchmark_skill import PeerBenchmarkSkill
    from .demand_index_skill import DemandIndexSkill
    from .onboarding_health_skill import OnboardingHealthSkill
    from .whatsapp_message_skill import WhatsAppMessageSkill
    from .pre_call_brief_skill import PreCallBriefSkill
    from .llm_cohort_scorer_skill import LLMCohortScorerSkill
    from .gifted_lead_skill import GiftedLeadSkill
    from .winback_priority_skill import WinbackPrioritySkill
    from .bl_upgrade_skill import BLUpgradeSkill
    from .script_generation_skill import ScriptGenerationSkill
    from .call_summary_skill import CallSummarySkill
    from .cross_platform_intelligence_skill import CrossPlatformIntelligenceSkill
    from .conversion_point_skill import ConversionPointSkill
    for cls in [
        ChurnScoringSkill, SHAPRCASkill, PeerBenchmarkSkill,
        DemandIndexSkill, OnboardingHealthSkill, WhatsAppMessageSkill,
        PreCallBriefSkill, LLMCohortScorerSkill,
        GiftedLeadSkill, WinbackPrioritySkill, BLUpgradeSkill,
        ScriptGenerationSkill, CallSummarySkill,
        CrossPlatformIntelligenceSkill, ConversionPointSkill,
    ]:
        registry.register(cls())


_auto_register()
