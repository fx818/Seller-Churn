"""SKILL 15 — ConversionPointSkill: Detect seller journey inflection point.

Three trajectory types:
  TYPE_A — sudden cliff  (peak → 60%+ drop in ≤2 months)
  TYPE_B — gradual drift (3+ consecutive declining months)
  TYPE_C — never engaged (never exceeded 10% of peer median from start)
"""
from churn_analysis.skills.base_skill import Skill, SkillResult


class ConversionPointSkill(Skill):
    name = "conversion-point"
    version = "1.0"
    required_inputs = ["monthly_enq"]
    optional_inputs = [
        "account_age_days", "peer_median_enq", "enq_30d",
        "active_days_30d", "cqs", "churn_score",
    ]

    # Labels shown in UI / action plan
    _TYPE_LABELS = {
        "TYPE_A": "Sudden Cliff",
        "TYPE_B": "Gradual Drift",
        "TYPE_C": "Never Engaged",
        "UNKNOWN": "Unknown",
    }

    def invoke(self, inputs: dict) -> SkillResult:
        monthly_enq: list = inputs.get("monthly_enq") or []
        peer_median: float = inputs.get("peer_median_enq") or 0
        account_age: int   = inputs.get("account_age_days") or 0
        enq_30d: int       = inputs.get("enq_30d") or 0

        # Need ≥2 data points for any meaningful detection
        if len(monthly_enq) < 2:
            return SkillResult(
                success=True,
                data=self._build(
                    "UNKNOWN", None, None,
                    note="Insufficient monthly data (<2 points)",
                    monthly_enq=monthly_enq,
                    peer_median=peer_median,
                ),
                confidence=0.3,
            )

        traj, cliff_month, cliff_pct = self._detect(monthly_enq, peer_median)

        return SkillResult(
            success=True,
            data=self._build(
                traj, cliff_month, cliff_pct,
                monthly_enq=monthly_enq,
                peer_median=peer_median,
                account_age=account_age,
            ),
            confidence=0.85,
        )

    # ── Detection Logic ───────────────────────────────────────────────────────

    def _detect(
        self,
        monthly: list,
        peer_median: float,
    ) -> tuple[str, int | None, float | None]:
        """Return (trajectory_type, cliff_month_index, cliff_drop_pct)."""

        # TYPE_C: never engaged — all values below 10% of peer median
        # If peer_median unknown, use absolute threshold of ≤2 enquiries ever
        never_threshold = max(peer_median * 0.10, 2) if peer_median > 0 else 2
        if all((v or 0) <= never_threshold for v in monthly):
            return "TYPE_C", None, None

        # TYPE_A: sudden cliff — find peak, then check next 1-2 months for ≥60% drop
        peak_val  = max((v or 0) for v in monthly)
        peak_idx  = next(i for i, v in enumerate(monthly) if (v or 0) == peak_val)

        if peak_idx < len(monthly) - 1 and peak_val > 0:
            # Check drop over next 1 month
            drop1 = ((peak_val - (monthly[peak_idx + 1] or 0)) / peak_val) * 100
            if drop1 >= 60:
                return "TYPE_A", peak_idx + 1, round(drop1, 1)

            # Check cumulative drop over next 2 months
            if peak_idx + 2 < len(monthly):
                val2 = (monthly[peak_idx + 2] or 0)
                drop2 = ((peak_val - val2) / peak_val) * 100
                if drop2 >= 60:
                    return "TYPE_A", peak_idx + 2, round(drop2, 1)

        # TYPE_B: gradual drift — 3+ consecutive declining months anywhere
        streak = 1
        streak_start = None
        for i in range(1, len(monthly)):
            curr = monthly[i] or 0
            prev = monthly[i - 1] or 0
            if curr < prev:
                if streak == 1:
                    streak_start = i - 1
                streak += 1
                if streak >= 3:
                    return "TYPE_B", streak_start, None
            else:
                streak = 1
                streak_start = None

        # Fallback — data exists but no clear pattern
        return "UNKNOWN", None, None

    # ── Result builder ────────────────────────────────────────────────────────

    def _build(
        self,
        traj: str,
        cliff_month: int | None,
        cliff_pct: float | None,
        monthly_enq: list | None = None,
        peer_median: float = 0,
        account_age: int = 0,
        note: str = "",
    ) -> dict:
        label = self._TYPE_LABELS.get(traj, "Unknown")

        # Human-readable explanation
        if traj == "TYPE_A":
            explanation = (
                f"Seller had strong activity then dropped ~{cliff_pct}% "
                f"around month {cliff_month + 1} — sudden disengagement."
            )
            opening_line_hi = (
                "Aapka business pehle bahut achha chal raha tha, "
                "phir achanak activity kam ho gayi — aaj iske baare mein baat karte hain."
            )
        elif traj == "TYPE_B":
            explanation = (
                "Seller showed 3+ months of continuous decline — gradual drift away from platform."
            )
            opening_line_hi = (
                "Pichle kuch mahino mein aapki IndiaMart activity dheere-dheere kam hui hai — "
                "kya koi specific issue hai jisme hum help kar sakte hain?"
            )
        elif traj == "TYPE_C":
            explanation = (
                "Seller never meaningfully engaged with the platform from onboarding — "
                "likely setup issues or expectation mismatch."
            )
            opening_line_hi = (
                "Aapne IndiaMart join kiya lekin platform ka poora faayda nahi uthaya — "
                "aaj aapko setup mein personally help karte hain."
            )
        else:
            explanation = note or "Could not determine a clear conversion pattern."
            opening_line_hi = (
                "Aapke account ki performance mein sudhar ke liye kuch points discuss karte hain."
            )

        return {
            "trajectory_type":   traj,
            "trajectory_label":  label,
            "explanation":       explanation,
            "opening_line_hi":   opening_line_hi,
            "cliff_month_index": cliff_month,
            "cliff_drop_pct":    cliff_pct,
            "monthly_enq":       monthly_enq or [],
            "peer_median_enq":   peer_median,
            "account_age_days":  account_age,
            # Flags for downstream orchestrator routing
            "is_type_c":         traj == "TYPE_C",
            "run_onboarding":    traj == "TYPE_C",
        }

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=False,
            data={
                "trajectory_type":  "UNKNOWN",
                "trajectory_label": "Unknown",
                "explanation":      "Conversion point detection failed.",
                "opening_line_hi":  "",
                "cliff_month_index": None,
                "cliff_drop_pct":   None,
                "is_type_c":        False,
                "run_onboarding":   False,
            },
            error=str(error),
            confidence=0.1,
            used_fallback=True,
        )
