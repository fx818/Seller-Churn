"""SKILL 2 — SHAPRCASkill: Map reason_tags → primary RCA category + Hinglish explanation."""
from .base_skill import Skill, SkillResult

# Priority order: check these RCA categories in order, pick first that matches
_RCA_RULES = [
    {
        "category": "BL_DECLINE",
        "trigger_tags": {"BL_VELOCITY_CRITICAL"},
        "en": "Enquiry volume dropped sharply ({bl_velocity_pct}% MoM). Seller's lead pipeline is drying up.",
        "hi": "Aapke leads last month se {bl_velocity_pct_abs}% kam ho gaye hain. Yeh ek serious signal hai.",
        "hint": "Diagnose why BL volume dropped — geography expansion or category demand discussion.",
    },
    {
        "category": "NO_LEADS",
        "trigger_tags": {"NO_ENQUIRY_FLOW", "BL_VELOCITY_DECLINING"},
        "en": "Platform not delivering adequate lead volume. Local buyer demand may be saturated.",
        "hi": "Aapki current city/category mein leads kum aa rahi hain. National buyers explore karne chahiye.",
        "hint": "Suggest national buyer expansion or geography change.",
    },
    {
        "category": "LOW_ENGAGEMENT",
        "trigger_tags": {"ZERO_ACTIVE_DAYS", "NO_PLATFORM_ACTIVITY", "LOW_ACTIVE_DAYS", "LOW_PLATFORM_ACTIVITY"},
        "en": "Seller is not using the platform actively. Low login frequency, few clickstream events.",
        "hi": "Aapne platform pe login nahi kiya last few weeks. Notifications miss ho rahi hain.",
        "hint": "Mobile app setup + notification activation call within 24h.",
    },
    {
        "category": "POOR_CATALOG",
        "trigger_tags": {"LOW_CQS_CRITICAL", "LOW_CQS_MODERATE"},
        "en": "Profile and product listing quality is below peer average. CQS {cqs} limits buyer visibility.",
        "hi": "Aapki product listing mein kuch gaps hain. 7 extra photos aur description se leads ~30% badhti hain.",
        "hint": "Catalog quality improvement session — specific CQS gaps.",
    },
    {
        "category": "LOW_PNS_RESPONSE",
        "trigger_tags": {"LOW_PNS_RATE"},
        "en": "Seller is missing incoming buyer calls. PNS answer rate {pns_success_pct}% is below 60% threshold.",
        "hi": "Kaafi incoming calls miss ho rahi hain. PNS answer rate {pns_success_pct}% hai, 60% hona chahiye.",
        "hint": "Check if DND/phone issues. Offer callback setup assistance.",
    },
    {
        "category": "RAG_RISK",
        "trigger_tags": {"RAG_RED"},
        "en": "Platform health score flagged Red. Account shows systemic risk indicators.",
        "hi": "Aapka account health score kuch warning signals show kar raha hai. Saath mein dekhte hain.",
        "hint": "Sensitive — do not open with RAG score. Focus on account review framing.",
    },
    {
        "category": "PEER_GAP",
        "trigger_tags": set(),   # triggered by peer_delta_pct threshold, not tags
        "en": "Seller is getting leads but significantly below peers in the same category+city.",
        "hi": "Aapke competitors same area mein zyada leads le rahe hain. Ek specific cheez alag kar rahe hain.",
        "hint": "Show specific peer comparison data. Offer gifted lead from peer's geography.",
    },
]

_DEFAULT = {
    "category": "NO_LEADS",
    "en": "No specific root cause identified. General engagement improvement recommended.",
    "hi": "Aapka account review kiya maine — kuch areas hain jahan help kar sakta hoon.",
    "hint": "Generic retention call — discovery-first approach.",
}


def _format(template: str, **kw) -> str:
    try:
        return template.format(**kw)
    except Exception:
        return template


class SHAPRCASkill(Skill):
    name = "shap_rca"
    version = "1.0"
    required_inputs = ["glid", "reason_tags"]
    optional_inputs = [
        "score_breakdown", "rag", "cqs", "bl_velocity_pct",
        "peer_delta_pct", "pns_success_pct",
    ]

    def invoke(self, inputs: dict) -> SkillResult:
        tags      = set(inputs.get("reason_tags") or [])
        breakdown = inputs.get("score_breakdown") or {}
        bl_vel    = inputs.get("bl_velocity_pct")
        peer_d    = inputs.get("peer_delta_pct")
        cqs       = inputs.get("cqs", "—")
        pns_pct   = inputs.get("pns_success_pct", "—")
        rag       = inputs.get("rag", "")

        fmt_kw = {
            "bl_velocity_pct": f"{bl_vel}%" if bl_vel is not None else "—",
            "bl_velocity_pct_abs": f"{abs(bl_vel)}" if bl_vel is not None else "—",
            "cqs": cqs,
            "pns_success_pct": pns_pct,
        }

        matched_rule = None
        max_contrib  = -1

        for rule in _RCA_RULES:
            # Peer gap triggered by threshold
            if rule["category"] == "PEER_GAP":
                if peer_d is not None and peer_d < -40:
                    contrib = abs(peer_d)
                    if contrib > max_contrib:
                        matched_rule = rule
                        max_contrib  = contrib
                continue

            overlap = tags & rule["trigger_tags"]
            if not overlap:
                continue
            contrib = sum(breakdown.get(t.lower(), 5) for t in overlap)
            if contrib > max_contrib:
                matched_rule = rule
                max_contrib  = contrib

        if matched_rule is None:
            rca_cat  = _DEFAULT["category"]
            en_text  = _DEFAULT["en"]
            hi_text  = _DEFAULT["hi"]
            hint     = _DEFAULT["hint"]
            conf     = 0.3
        else:
            rca_cat = matched_rule["category"]
            en_text = _format(matched_rule["en"], **fmt_kw)
            hi_text = _format(matched_rule["hi"], **fmt_kw)
            hint    = matched_rule["hint"]
            conf    = min(0.95, 0.5 + max_contrib / 100)

        # Top feature = key with highest score contribution
        top_feature = max(breakdown, key=breakdown.get) if breakdown else None
        shap_list = sorted(
            [{"feature": k, "contribution": v, "direction": "negative"} for k, v in breakdown.items()],
            key=lambda x: x["contribution"], reverse=True,
        )

        return SkillResult(
            success=True,
            data={
                "rca_category":       rca_cat,
                "rca_confidence":     round(conf, 2),
                "rca_explanation_en": en_text,
                "rca_explanation_hi": hi_text,
                "intervention_hint":  hint,
                "top_feature":        top_feature,
                "top_feature_value":  breakdown.get(top_feature) if top_feature else None,
                "top_feature_contribution": breakdown.get(top_feature, 0) if top_feature else 0,
                "shap_breakdown":     shap_list,
            },
            confidence=conf,
        )

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=False,
            data={"rca_category": "UNKNOWN", "rca_confidence": 0.1, "shap_breakdown": []},
            error=str(error), confidence=0.1, used_fallback=True,
        )
