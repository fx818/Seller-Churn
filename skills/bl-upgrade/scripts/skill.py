"""BL Upgrade Skill — identify sellers eligible for Buy Lead tier upgrade."""
from churn_analysis.skills.base_skill import Skill, SkillResult


class BLUpgradeSkill(Skill):
    name = "bl-upgrade"
    required_inputs = ["glid"]
    optional_inputs = [
        "churn_score",
        "days_to_renewal",
        "ctype",
        "account_age_days",
        "active_days_30d",
        "replied_30d",
        "enq_30d",
        "llm_risk_level",
    ]

    def invoke(self, inputs: dict) -> SkillResult:
        churn_score = inputs.get("churn_score") or 0
        days_to_renewal = inputs.get("days_to_renewal") or 999
        ctype = (inputs.get("ctype") or "").upper()
        account_age_days = inputs.get("account_age_days") or 0
        active_days_30d = inputs.get("active_days_30d") or 0
        replied_30d = inputs.get("replied_30d") or 0
        llm_risk_level = (inputs.get("llm_risk_level") or "").strip()

        # --- Mode detection ---
        mode_a = (
            float(churn_score) >= 70
            and int(days_to_renewal) <= 15
        )
        if llm_risk_level in ("Critical", "Very High"):
            mode_a = True

        mode_b = (
            ctype == "FREELIST"
            and 25 <= int(account_age_days) <= 35
            and int(active_days_30d) >= 10
            and int(replied_30d) > 0
        )

        # Mode A takes priority if both triggered
        if mode_a:
            return SkillResult(
                success=True,
                data={
                    "eligible": True,
                    "mode": "AT_RISK_RETENTION",
                    "upgrade_leads_count": 5,
                    "upgrade_message_hi": (
                        "Ramesh Bhai, renewal se pehle aapke liye 5 premium leads unlock ki hain "
                        "— yeh normal sellers ko nahi milti."
                    ),
                    "upgrade_message_en": (
                        "We've unlocked 5 premium leads for you before renewal "
                        "— these aren't available to regular sellers."
                    ),
                    "action": "OFFER_PREMIUM_LEADS",
                    "expected_conversion_uplift": 0.22,
                },
                confidence=0.90,
            )

        if mode_b:
            return SkillResult(
                success=True,
                data={
                    "eligible": True,
                    "mode": "MONTHLY_TO_ANNUAL",
                    "upgrade_leads_count": 3,
                    "upgrade_message_hi": (
                        "Aap monthly pe hain — in 3 premium leads tak access nahi hai. "
                        "Annual pe switch karte hain toh yeh leads seedha milenge."
                    ),
                    "upgrade_message_en": (
                        "You're on monthly — these 3 premium leads aren't accessible. "
                        "Switch to annual and get them directly."
                    ),
                    "action": "SEND_PREVIEW_LEADS",
                    "expected_conversion_uplift": 0.18,
                },
                confidence=0.85,
            )

        # Not eligible
        reason = (
            f"churn_score={churn_score}, days_to_renewal={days_to_renewal}"
            f" — no trigger criteria met"
        )
        return SkillResult(
            success=True,
            data={
                "eligible": False,
                "mode": None,
                "reason": reason,
            },
            confidence=0.95,
        )

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=False,
            data={
                "eligible": False,
                "mode": None,
                "used_fallback": True,
            },
            error=str(error),
            confidence=0.1,
            used_fallback=True,
        )
