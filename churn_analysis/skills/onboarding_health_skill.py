"""SKILL 5 — OnboardingHealthSkill: 5-check health for new sellers (account_age ≤ 90d)."""
from .base_skill import Skill, SkillResult


def _tier(score: float, high: float = 70, low: float = 40) -> str:
    return "Green" if score >= high else ("Amber" if score >= low else "Red")


class OnboardingHealthSkill(Skill):
    name = "onboarding_health"
    version = "1.0"
    required_inputs = ["glid"]
    optional_inputs = [
        "account_age_days", "city", "enterprise", "ctype",
        "cqs", "enq_30d", "replied_30d", "paid_history", "rag",
        "demand_index_result", "peer_benchmark_result",
    ]

    def invoke(self, inputs: dict) -> SkillResult:
        age        = inputs.get("account_age_days") or 0
        ctype      = (inputs.get("ctype") or "").upper()
        cqs        = inputs.get("cqs")
        enq_30     = inputs.get("enq_30d") or 0
        replied_30 = inputs.get("replied_30d") or 0
        paid_hist  = inputs.get("paid_history") or False
        rag        = (inputs.get("rag") or "").strip()
        demand_res = inputs.get("demand_index_result") or {}
        peer_res   = inputs.get("peer_benchmark_result") or {}

        checks = {}

        # ── Check 1: Category Demand (weight 30%) ────────────────────────────
        demand_tier  = demand_res.get("demand_tier", "Amber")
        demand_score = 100 if demand_tier == "Green" else (50 if demand_tier == "Amber" else 10)
        checks["demand"] = {
            "score":  demand_score,
            "weight": 0.30,
            "tier":   demand_tier,
            "note":   demand_res.get("demand_explanation", "Demand data unavailable"),
        }

        # ── Check 2: Business Verification (weight 15%) ──────────────────────
        verified     = paid_hist and rag != "Red"
        verif_score  = 100 if verified else (50 if paid_hist else 0)
        verif_tier   = "Green" if verified else ("Amber" if paid_hist else "Red")
        checks["verification"] = {
            "score":  verif_score,
            "weight": 0.15,
            "tier":   verif_tier,
            "note":   ("Paid history + healthy RAG" if verified else
                       ("Paid history but RAG risk" if paid_hist else "No paid history — high early-churn risk")),
        }

        # ── Check 3: Peer Benchmark Gap (weight 15%) ─────────────────────────
        enq_pct     = peer_res.get("enq_percentile", 50)
        peer_score  = max(0, min(100, enq_pct))
        peer_tier   = _tier(peer_score, 60, 30)
        checks["peer_gap"] = {
            "score":  peer_score,
            "weight": 0.15,
            "tier":   peer_tier,
            "note":   peer_res.get("peer_summary_line", "Peer data not available"),
        }

        # ── Check 4: First BL Response (weight 20%) ──────────────────────────
        if enq_30 == 0:
            first_bl_score = 40
            first_bl_tier  = "Amber"
            first_bl_note  = "No BLs received yet — too early to assess"
        elif replied_30 > 0:
            first_bl_score = 100
            first_bl_tier  = "Green"
            first_bl_note  = f"Responded to {replied_30} of {enq_30} BLs"
        else:
            first_bl_score = 0
            first_bl_tier  = "Red"
            first_bl_note  = f"Received {enq_30} BLs but replied to none — lead setup issue"
        checks["first_bl_response"] = {
            "score":  first_bl_score,
            "weight": 0.20,
            "tier":   first_bl_tier,
            "note":   first_bl_note,
        }

        # ── Check 5: Package Type (weight 20%) ───────────────────────────────
        if "CATALOG" in ctype or "FCP" in ctype or "PNS" in ctype:
            pkg_score = 80
            pkg_tier  = "Green"
            pkg_note  = f"Package {ctype} — standard onboarding track"
        elif "FREE" in ctype or "FREELIST" in ctype:
            pkg_score = 30
            pkg_tier  = "Amber"
            pkg_note  = "FREELIST — higher early-churn risk; upgrade conversation recommended"
        else:
            pkg_score = 50
            pkg_tier  = "Amber"
            pkg_note  = f"Package type {ctype or 'unknown'} — standard monitoring"
        checks["package_type"] = {
            "score":  pkg_score,
            "weight": 0.20,
            "tier":   pkg_tier,
            "note":   pkg_note,
        }

        # ── Composite score ───────────────────────────────────────────────────
        onboarding_score = round(sum(
            c["score"] * c["weight"] for c in checks.values()
        ))
        onboarding_risk = _tier(onboarding_score, 65, 35)

        # Trigger action
        if onboarding_risk == "Red":
            trigger  = "HUMAN_CALL_24H"
            hint     = "Urgent setup call: lead management + notification setup. Frame as activation, not sales."
        elif onboarding_risk == "Amber":
            trigger  = "WHATSAPP_SETUP_GUIDE"
            hint     = "Send WhatsApp guide + follow up in 48h if no engagement."
        else:
            trigger  = "MONITOR_7D"
            hint     = "Healthy onboarding — automated nurture, check again at day 30."

        return SkillResult(
            success=True,
            data={
                "onboarding_score": onboarding_score,
                "onboarding_risk":  onboarding_risk,
                "check_results":    checks,
                "trigger_action":   trigger,
                "call_script_hint": hint,
                "account_age_days": age,
                "is_new_seller":    age <= 90,
            },
            confidence=0.80,
        )

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=False,
            data={"onboarding_score": None, "onboarding_risk": "Unknown", "trigger_action": "DATA_INSUFFICIENT"},
            error=str(error), confidence=0.1, used_fallback=True,
        )
