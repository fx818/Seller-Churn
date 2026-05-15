"""Winback Priority Skill — score churned sellers for re-engagement prioritisation."""
from .base_skill import Skill, SkillResult

RECOVERABILITY = {
    "NO_LEADS": 90,
    "POOR_CATALOG": 75,
    "BL_DECLINE": 60,
    "LOW_ENGAGEMENT": 55,
    "LOW_PNS_RESPONSE": 50,
    "PEER_GAP": 50,
    "RAG_RISK": 40,
    "UNKNOWN": 30,
}

PITCH_TYPES = {
    "NO_LEADS": "DEMAND_IMPROVED",
    "POOR_CATALOG": "CATALOG_FIX",
    "BL_DECLINE": "PLATFORM_HEALTH",
    "LOW_ENGAGEMENT": "EASY_SETUP",
    "LOW_PNS_RESPONSE": "MISSED_CALLS_FIXED",
    "PEER_GAP": "COMPETITOR_INSIGHT",
    "RAG_RISK": "ACCOUNT_RESET",
}

OPENING_LINES = {
    "DEMAND_IMPROVED": (
        "Bhai, aap tab gaye the jab leads nahi aa rahi thi. "
        "Maine aaj check kiya — aapki category mein abhi {demand_index} active buyers hain."
    ),
    "CATALOG_FIX": (
        "Bhai, jis issue ki wajah se leads nahi aa rahi thi — "
        "woh fix ho sakta hai. 20 minute mein catalog update karte hain."
    ),
    "PLATFORM_HEALTH": (
        "Bhai, aapka previous account review kiya — "
        "platform pe aapke liye ab better results hain."
    ),
}
_DEFAULT_OPENING = "Bhai, aapka purana account dekha — aapki category mein ab accha demand hai."


class WinbackPrioritySkill(Skill):
    name = "winback_priority"
    required_inputs = ["glid"]
    optional_inputs = [
        "churn_reason", "rca_category",
        "churn_date", "account_age_days",
        "enterprise", "ctype",
        "historical_enq", "current_demand_index",
        "days_since_churn", "paid_history", "city",
        "churn_score", "enq_30d", "active_days_30d",
        "peer_delta_pct", "cqs", "trajectory_type", "demand_index",
    ]

    def invoke(self, inputs: dict) -> SkillResult:
        # Accept churn_reason or rca_category interchangeably
        churn_reason = (inputs.get("churn_reason") or inputs.get("rca_category") or "UNKNOWN").upper()
        ctype = (inputs.get("ctype") or "").upper()
        historical_enq = float(inputs.get("historical_enq") or 0)
        current_demand_index = inputs.get("current_demand_index")
        days_since_churn = inputs.get("days_since_churn")
        enterprise = bool(inputs.get("enterprise") or False)

        # --- Normalised sub-scores ---
        historical_lead_quality = min(historical_enq / 20.0, 1.0)
        demand_score = float(current_demand_index if current_demand_index is not None else 50) / 100.0
        recoverability_score = RECOVERABILITY.get(churn_reason, 30) / 100.0

        days_since = float(days_since_churn if days_since_churn is not None else 180)
        cool_off_req = 180 if ctype == "FREELIST" else 90
        cool_off_elapsed = days_since >= cool_off_req
        cool_off_days_remaining = max(0, int(cool_off_req - days_since))

        if days_since > cool_off_req:
            recency_bonus = max(0.0, 1.0 - (days_since - cool_off_req) / 365.0)
        else:
            recency_bonus = 0.0

        winback_score = round(
            100 * (
                historical_lead_quality * 0.30
                + demand_score * 0.35
                + recoverability_score * 0.25
                + recency_bonus * 0.10
            )
        )

        # --- Priority tier ---
        if winback_score >= 65:
            priority = "HIGH"
        elif winback_score >= 40:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        # --- Pitch type & opening line ---
        pitch_type = PITCH_TYPES.get(churn_reason, "GENERAL")
        template = OPENING_LINES.get(pitch_type, _DEFAULT_OPENING)
        demand_index_display = int(current_demand_index) if current_demand_index is not None else 50
        opening_line = template.format(demand_index=demand_index_display)

        # --- Gifted lead eligibility: HIGH or MEDIUM priority and cool-off elapsed ---
        gifted_lead_eligible = cool_off_elapsed and priority in ("HIGH", "MEDIUM")

        # --- Estimated conversion probability (simple heuristic) ---
        est_conv = round(winback_score / 100.0 * 0.40, 2)  # max ~40% at score=100

        # --- Recommended package ---
        recommended_package = "annual" if ctype != "FREELIST" or enterprise else "monthly"

        return SkillResult(
            success=True,
            data={
                "winback_score": winback_score,
                "priority": priority,
                "cool_off_elapsed": cool_off_elapsed,
                "cool_off_days_remaining": cool_off_days_remaining,
                "winback_pitch_type": pitch_type,
                "opening_line_hi": opening_line,
                "gifted_lead_eligible": gifted_lead_eligible,
                "estimated_conversion_probability": est_conv,
                "recommended_package": recommended_package,
            },
            confidence=0.85,
        )

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=False,
            data={
                "winback_score": 0,
                "priority": "LOW",
                "cool_off_elapsed": False,
                "cool_off_days_remaining": 0,
                "winback_pitch_type": "GENERAL",
                "opening_line_hi": _DEFAULT_OPENING,
                "gifted_lead_eligible": False,
                "estimated_conversion_probability": 0.0,
                "recommended_package": "monthly",
            },
            error=str(error),
            confidence=0.1,
            used_fallback=True,
        )
