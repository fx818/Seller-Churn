"""SKILL 1 — ChurnScoringSkill: 14-signal weighted churn score 0-100."""
from .base_skill import Skill, SkillResult

RED_THRESHOLD   = 65
AMBER_THRESHOLD = 35


class ChurnScoringSkill(Skill):
    name = "churn_scoring"
    version = "1.0"
    required_inputs = ["glid"]
    optional_inputs = [
        "enq_30d", "replied_30d", "active_days_30d", "bl_velocity_pct",
        "pns_success_pct", "rag", "cqs", "hotleads_count", "event_count",
    ]

    def invoke(self, inputs: dict) -> SkillResult:
        score = 0
        reasons: list[str] = []
        tags: list[str] = []
        breakdown: dict[str, int] = {}

        def add(points: int, tag: str, reason: str, key: str):
            nonlocal score
            score += points
            tags.append(tag)
            reasons.append(reason)
            breakdown[key] = breakdown.get(key, 0) + points

        enq_30     = inputs.get("enq_30d") or 0
        replied_30 = inputs.get("replied_30d") or 0
        active_30  = inputs.get("active_days_30d") or 0
        bl_vel     = inputs.get("bl_velocity_pct")
        pns_pct    = inputs.get("pns_success_pct")
        rag        = (inputs.get("rag") or "").strip()
        cqs        = inputs.get("cqs")
        hotleads   = inputs.get("hotleads_count")
        events     = inputs.get("event_count") or 0

        # --- Reply rate
        if enq_30 > 0:
            reply_rate = round(replied_30 / enq_30 * 100, 1)
            if reply_rate < 40:
                add(20, "LOW_REPLY_RATE", f"Low reply rate: {reply_rate}% (threshold 40%)", "reply_rate")
        else:
            reply_rate = 0

        # --- Active days
        if active_30 == 0:
            add(18, "ZERO_ACTIVE_DAYS", "Zero LMS active days in last 30d", "active_days")
        elif active_30 <= 3:
            add(10, "LOW_ACTIVE_DAYS", f"Only {active_30} active days in last 30d", "active_days")

        # --- Enquiry flow
        if enq_30 == 0:
            add(15, "NO_ENQUIRY_FLOW", "Zero enquiries in last 30d — no lead flow", "enq")

        # --- BL velocity
        if bl_vel is not None:
            if bl_vel <= -30:
                add(22, "BL_VELOCITY_CRITICAL", f"BL velocity drop: {bl_vel}% MoM (critical)", "bl_velocity")
            elif bl_vel <= -10:
                add(10, "BL_VELOCITY_DECLINING", f"BL velocity declining: {bl_vel}% MoM", "bl_velocity")

        # --- PNS answer rate
        if pns_pct is not None and pns_pct < 60:
            add(12, "LOW_PNS_RATE", f"PNS answer rate {pns_pct}% — below 60%", "pns")

        # --- RAG
        if rag == "Red":
            add(25, "RAG_RED", "RAG category: Red — highest churn risk tier", "rag")
        elif rag == "Amber":
            add(12, "RAG_AMBER", "RAG category: Amber — moderate churn risk", "rag")

        # --- CQS
        if cqs is not None:
            if cqs < 60:
                add(15, "LOW_CQS_CRITICAL", f"CQS: {cqs} — below 60, poor product visibility", "cqs")
            elif cqs < 75:
                add(7, "LOW_CQS_MODERATE", f"CQS: {cqs} — below 75, room for improvement", "cqs")

        # --- Hotleads
        if hotleads is not None and hotleads == 0:
            add(8, "NO_HOTLEAD", "No hotlead activity — no engagement events", "hotleads")

        # --- Clickstream
        if events == 0:
            add(12, "NO_PLATFORM_ACTIVITY", "Zero clickstream events — no platform activity", "activity")
        elif events < 10:
            add(6, "LOW_PLATFORM_ACTIVITY", f"Only {events} clickstream events — very low activity", "activity")

        score = min(score, 100)
        risk  = "Red" if score >= RED_THRESHOLD else ("Amber" if score >= AMBER_THRESHOLD else "Green")

        # Check data coverage
        signals_available = sum(1 for v in [enq_30, replied_30, active_30, bl_vel, rag, cqs, events] if v is not None)
        confidence = 1.0 if signals_available >= 5 else max(0.2, signals_available / 7)

        return SkillResult(
            success=True,
            data={
                "churn_score":    score,
                "risk":           risk,
                "churn_reasons":  reasons,
                "reason_tags":    tags,
                "score_breakdown": breakdown,
                "reply_rate_30d": reply_rate,
                "signals_available": signals_available,
            },
            confidence=confidence,
            used_fallback=False,
        )

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=False,
            data={"churn_score": None, "risk": "Unknown", "reason_tags": [], "churn_reasons": []},
            error=str(error), confidence=0.2, used_fallback=True,
        )
