"""SKILL — BLCardSkill: aggregate all pipeline outputs into a single seller briefing card."""
from .base_skill import Skill, SkillResult


def _band_emoji(b: str) -> str:
    return {"R": "🔴", "A": "🟡", "G": "🟢"}.get((b or "").upper(), "⚪")


def _verdict(churn_score, risk, llm_risk, winback_score=None, winback_priority=None):
    # ---- CRITICAL: high churn OR Red risk OR HIGH-priority winback ≥75 ----
    if risk == "Red" or (churn_score is not None and churn_score >= 70):
        return "CRITICAL — Immediate retention call"
    if winback_score is not None and winback_score >= 75 and winback_priority == "HIGH":
        return "CRITICAL — HIGH winback priority, call immediately"

    # ---- AT RISK: Amber, moderate churn, LLM flag, or winback ≥40 ----
    if risk == "Amber" or (churn_score is not None and churn_score >= 40):
        return "AT RISK — Schedule retention call within 7 days"
    if llm_risk in ("Critical", "High", "Very High"):
        return "AT RISK — LLM-flagged, prioritize"
    if winback_score is not None and winback_score >= 65:
        return "AT RISK — Recoverable churn (winback HIGH), prioritize"
    if winback_score is not None and winback_score >= 40:
        return "AT RISK — Winback opportunity (MEDIUM), schedule call"

    return "HEALTHY — Routine check-in"


def _priority_score(churn_score, risk, llm_risk, days_to_renewal,
                    winback_score=None, winback_priority=None):
    """0-100 priority score for queueing reps."""
    p = churn_score or 0
    if llm_risk == "Critical": p += 15
    elif llm_risk == "High":    p += 8
    if risk == "Red":           p += 10
    if days_to_renewal is not None and days_to_renewal <= 30:
        p += 15
    # Winback recoverable sellers also belong near the top of the queue
    if winback_priority == "HIGH":
        p += 12
    elif winback_priority == "MEDIUM":
        p += 6
    if winback_score is not None and winback_score >= 75:
        p += 5
    return min(100, p)


class BLCardSkill(Skill):
    name = "bl_card"
    version = "1.0"
    required_inputs = ["glid"]
    optional_inputs = [
        # Context
        "company", "city", "state", "custtype", "rag_category",
        "account_age_days", "turnover", "paid_history",
        # Churn scoring
        "churn_score", "risk", "churn_reasons", "reason_tags", "score_breakdown",
        "reply_rate_30d", "signals_available",
        # Churn v2.0 breakdown
        "base_score", "compound_multiplier", "compounded_score",
        "trajectory_adjustment", "trajectory_note",
        "pre_llm_score", "pre_llm_risk",
        "llm_adjustment", "llm_justification", "llm_interactions",
        "llm_used", "red_flag_count", "red_flags",
        # RCA
        "rca_category", "rca_confidence", "rca_explanation_en", "rca_explanation_hi",
        "intervention_hint",
        # LLM
        "llm_risk_level", "risk_level", "pipeline_tier", "confidence_score",
        "bands", "reasoning", "churned_lookalikes", "retained_lookalikes",
        # Onboarding
        "onboarding_score", "onboarding_status", "onboarding_issues",
        # Peer
        "peer_group", "peer_n", "peer_summary_line", "gap_severity",
        # Demand
        "demand_index", "demand_tier", "market_bl_per_seller", "trend",
        "demand_explanation", "recommended_action",
        # Conversion
        "trajectory_type", "trajectory_label", "explanation",
        # Pre-call brief
        "opening_line_en", "opening_line_hi", "key_signals",
        "suggested_actions", "brief_text",
        # WhatsApp
        "message_hi", "message_en",
        # Script
        "script_parts", "script_parts_en", "rca_used",
        # Gifted lead
        "lead_found", "fallback",
        # BL upgrade
        "eligible", "mode", "reason",
        # Winback (v2.0 derivation)
        "winback_score", "pitch", "days_to_renewal",
        "winback_priority", "winback_pre_llm", "winback_llm_used",
        "winback_llm_adjustment", "winback_llm_justification",
        "winback_interaction_bonus", "winback_sub_scores", "winback_weights",
        "winback_cool_off_elapsed", "winback_cool_off_days_remaining",
        "winback_demand_provided",
        # IM product count (snapshot + flow fallback)
        "im_approved_products", "im_product_count",
        # Cross-platform intelligence
        "platforms_found", "platform_data", "im_catalog_gap",
        "call_card", "competitive_positioning",
        # Onboarding (extended)
        "health_score", "health_tier", "onboarding_checks", "trigger_action",
    ]

    def invoke(self, inputs: dict) -> SkillResult:
        # ── Context ──────────────────────────────────────────────────────────
        company = inputs.get("company") or "—"
        city    = inputs.get("city") or "—"
        state   = inputs.get("state") or ""
        ctype   = inputs.get("custtype") or "—"
        rag     = inputs.get("rag_category") or "—"
        age     = inputs.get("account_age_days") or 0
        glid    = inputs.get("glid")

        # ── Scores ───────────────────────────────────────────────────────────
        churn_score = inputs.get("churn_score")
        risk        = inputs.get("risk") or "Unknown"
        llm_risk    = inputs.get("llm_risk_level") or inputs.get("risk_level")
        llm_tier    = inputs.get("pipeline_tier")
        llm_conf    = inputs.get("confidence_score")
        bands       = inputs.get("bands") or {}
        renewal     = inputs.get("days_to_renewal")

        # ── Cross-platform churn adjustment ──────────────────────────────────
        # Applied here because cross_platform runs AFTER churn_scoring.
        cp_adjustment = 0
        cp_adjustment_note = ""
        positioning = (inputs.get("competitive_positioning") or "").strip()
        cp_gap_for_adj = inputs.get("im_catalog_gap") or {}
        if positioning == "seller_stronger_elsewhere":
            gap_pct = cp_gap_for_adj.get("gap_pct", 0)
            if gap_pct < -40:
                cp_adjustment = 10
                cp_adjustment_note = f"Seller has {abs(gap_pct):.0f}% larger catalog elsewhere — catalog neglect on IM"
            elif gap_pct < -20:
                cp_adjustment = 5
                cp_adjustment_note = f"Seller has moderate catalog gap ({gap_pct:.0f}%) vs other platforms"

        # Compute final churn score with cross-platform adjustment
        if churn_score is not None and cp_adjustment > 0:
            final_churn_score = min(100, churn_score + cp_adjustment)
            if final_churn_score >= 65:
                final_risk = "Red"
            elif final_churn_score >= 35:
                final_risk = "Amber"
            else:
                final_risk = "Green"
        else:
            final_churn_score = churn_score
            final_risk = risk

        # Pull winback fields early so verdict + priority can use them
        winback_score    = inputs.get("winback_score")
        winback_priority = inputs.get("winback_priority")

        priority = _priority_score(
            final_churn_score, final_risk, llm_risk, renewal,
            winback_score=winback_score,
            winback_priority=winback_priority,
        )
        verdict  = _verdict(
            final_churn_score, final_risk, llm_risk,
            winback_score=winback_score,
            winback_priority=winback_priority,
        )

        # ── RCA ──────────────────────────────────────────────────────────────
        rca       = inputs.get("rca_category") or "UNKNOWN"
        rca_en    = inputs.get("rca_explanation_en") or ""
        rca_hi    = inputs.get("rca_explanation_hi") or ""
        hint      = inputs.get("intervention_hint") or ""

        # ── Trajectory + Demand ──────────────────────────────────────────────
        traj_label = inputs.get("trajectory_label") or inputs.get("trajectory_type") or "—"
        traj_expl  = inputs.get("explanation") or ""
        demand     = inputs.get("demand_tier") or "—"
        demand_idx = inputs.get("demand_index")
        demand_msg = inputs.get("demand_explanation") or ""

        # ── Peer ─────────────────────────────────────────────────────────────
        peer_line  = inputs.get("peer_summary_line") or ""
        peer_n     = inputs.get("peer_n")

        # ── Action ───────────────────────────────────────────────────────────
        actions    = inputs.get("suggested_actions") or []
        opening_en = inputs.get("opening_line_en") or ""
        opening_hi = inputs.get("opening_line_hi") or ""

        # ── Messaging ────────────────────────────────────────────────────────
        wa_hi      = inputs.get("message_hi") or ""
        wa_en      = inputs.get("message_en") or ""
        script_hi  = inputs.get("script_parts") or {}
        script_en  = inputs.get("script_parts_en") or {}

        # ── BL upgrade + Winback ─────────────────────────────────────────────
        upgrade_eligible = inputs.get("eligible")
        upgrade_reason   = inputs.get("reason") or ""
        winback_pitch    = inputs.get("pitch") or ""

        # ── IM product count (always available) ──────────────────────────────
        im_product_count = (
            inputs.get("im_product_count")
            or inputs.get("im_approved_products")
            or 0
        )

        # ── Cross-platform intelligence ──────────────────────────────────────
        cp_platforms = inputs.get("platforms_found") or []
        cp_data      = inputs.get("platform_data") or {}
        cp_gap       = inputs.get("im_catalog_gap") or {}
        cp_card      = inputs.get("call_card") or {}
        cp_position  = inputs.get("competitive_positioning") or ""

        # If cross_platform didn't run, im_catalog_gap is empty — backfill with snapshot count
        if not cp_gap and im_product_count:
            cp_gap = {
                "im_products":          im_product_count,
                "other_total_products": 0,
                "other_combination":    "none",
                "other_avg_products":   0,  # back-compat
                "gap_pct":              0,
                "severity":             "no_data",
            }

        # ── Onboarding ────────────────────────────────────────────────────────
        onboarding_score   = inputs.get("health_score")
        onboarding_tier    = inputs.get("health_tier")
        onboarding_checks  = inputs.get("onboarding_checks") or {}
        onboarding_trigger = inputs.get("trigger_action") or ""
        onboarding_priors  = inputs.get("risk_priors") or []
        onboarding_plan    = inputs.get("activation_plan") or {}
        onboarding_plan_method = inputs.get("plan_method") or ""

        # ── Build structured card ────────────────────────────────────────────
        card = {
            "header": {
                "glid":       glid,
                "company":    company,
                "location":   f"{city}, {state}".strip(", "),
                "customer_type": ctype,
                "rag":        rag,
                "account_age_days": age,
                "verdict":    verdict,
                "priority":   priority,
                "im_product_count": im_product_count,
            },
            "scores": {
                "churn_score":         final_churn_score,
                "risk_tier":           final_risk,
                "base_churn_score":    churn_score,
                "cp_adjustment":       cp_adjustment,
                "cp_adjustment_note":  cp_adjustment_note,
                "llm_risk":            llm_risk,
                "llm_tier":            llm_tier,
                "llm_confidence":      llm_conf,
                "bands": {
                    "bl":       f"{_band_emoji(bands.get('bl', ''))} {bands.get('bl', '—')}",
                    "lms":      f"{_band_emoji(bands.get('lms', ''))} {bands.get('lms', '—')}",
                    "activity": f"{_band_emoji(bands.get('activity', ''))} {bands.get('activity', '—')}",
                },
                # New: churn breakdown from churn_scoring v2.0
                "churn_breakdown": {
                    "base_score":           inputs.get("base_score"),
                    "compound_multiplier":  inputs.get("compound_multiplier"),
                    "trajectory_adjustment": inputs.get("trajectory_adjustment"),
                    "trajectory_note":      inputs.get("trajectory_note"),
                    "pre_llm_score":        inputs.get("pre_llm_score"),
                    "llm_adjustment":       inputs.get("llm_adjustment"),
                    "llm_justification":    inputs.get("llm_justification"),
                    "llm_used":             inputs.get("llm_used"),
                    "red_flag_count":       inputs.get("red_flag_count"),
                },
            },
            "root_cause": {
                "category":    rca,
                "confidence":  inputs.get("rca_confidence"),
                "english":     rca_en,
                "hindi":       rca_hi,
                "intervention": hint,
            },
            "signals": {
                "churn_reasons": inputs.get("churn_reasons") or [],
                "reason_tags":   inputs.get("reason_tags") or [],
                "reply_rate_30d": inputs.get("reply_rate_30d"),
                "trajectory":    traj_label,
                "trajectory_explanation": traj_expl,
                "demand_tier":   demand,
                "demand_index":  demand_idx,
                "demand_message": demand_msg,
                "peer_comparison": peer_line,
                "peer_n":        peer_n,
            },
            "action_plan": {
                "opening_en":  opening_en,
                "opening_hi":  opening_hi,
                "suggested_actions": actions,
                "do_not_mention":    ["renewal price", "subscription cost", "competitor pricing"],
                "estimated_duration": "8-12 min",
            },
            "messaging": {
                "whatsapp_hi":  wa_hi,
                "whatsapp_en":  wa_en,
                "call_script_hi": script_hi,
                "call_script_en": script_en,
            },
            "interventions": {
                "bl_upgrade_eligible":  upgrade_eligible,
                "bl_upgrade_reason":    upgrade_reason,
                "winback_score":        winback_score,
                "winback_pitch":        winback_pitch,
                "winback_priority":     inputs.get("winback_priority"),
                "winback_pre_llm":      inputs.get("winback_pre_llm"),
                "winback_llm_used":     inputs.get("winback_llm_used"),
                "winback_llm_adjustment":    inputs.get("winback_llm_adjustment"),
                "winback_llm_justification": inputs.get("winback_llm_justification"),
                "winback_interaction_bonus": inputs.get("winback_interaction_bonus"),
                "winback_sub_scores":   inputs.get("winback_sub_scores") or {},
                "winback_weights":      inputs.get("winback_weights") or {},
                "winback_cool_off_elapsed":       inputs.get("winback_cool_off_elapsed"),
                "winback_cool_off_days_remaining":inputs.get("winback_cool_off_days_remaining"),
                "winback_demand_provided":        inputs.get("winback_demand_provided"),
            },
            "lookalikes": {
                "churned":  inputs.get("churned_lookalikes") or [],
                "retained": inputs.get("retained_lookalikes") or [],
            },
            "cross_platform": {
                "platforms_found":        cp_platforms,
                "platform_data":          cp_data,
                "im_catalog_gap":         cp_gap,
                "headline_hi":            cp_card.get("headline_hi", ""),
                "headline_en":            cp_card.get("headline_en", ""),
                "data_points":            cp_card.get("data_points", []),
                "suggested_action":       cp_card.get("suggested_action", ""),
                "urgency":                cp_card.get("urgency", ""),
                "competitive_positioning": cp_position,
            },
            "onboarding": {
                "health_score":    onboarding_score,
                "health_tier":     onboarding_tier,
                "checks":          onboarding_checks,
                "trigger_action":  onboarding_trigger,
                "risk_priors":     onboarding_priors,
                "activation_plan": onboarding_plan,
                "plan_method":     onboarding_plan_method,
                "ran":             onboarding_score is not None,
            },
        }

        # ── Plain-text rep summary (for printing / CRM paste) ────────────────
        actions_str = " | ".join(actions[:3]) if actions else "Discovery call"
        summary_text = (
            f"╔═══════════════════════════════════════════════════════════════════╗\n"
            f"║ SELLER BL CARD — GLID {glid}\n"
            f"║ {company} | {city}, {state} | {ctype} | Age: {age}d\n"
            f"╠═══════════════════════════════════════════════════════════════════╣\n"
            f"║ VERDICT:  {verdict}\n"
            f"║ PRIORITY: {priority}/100\n"
            f"║ CHURN:    {churn_score}/100 ({risk})  |  LLM: {llm_risk or '—'}\n"
            f"║ RCA:      {rca} — {rca_en[:60]}\n"
            f"║ DEMAND:   {demand}  |  TRAJECTORY: {traj_label}\n"
        )
        if cp_platforms:
            combo = cp_gap.get("other_combination", "n/a")
            cp_line = (
                f"║ CROSS-PLATFORM: {','.join(cp_platforms)}  "
                f"IM={cp_gap.get('im_products','?')}p  "
                f"OTHER={cp_gap.get('other_total_products', cp_gap.get('other_avg_products','?'))}p"
                f" ({combo})  "
                f"GAP={cp_gap.get('gap_pct','?')}%\n"
            )
            summary_text += cp_line
        if onboarding_tier:
            summary_text += f"║ ONBOARDING: {onboarding_tier} (score={onboarding_score}) → {onboarding_trigger}\n"
        summary_text += (
            f"╠═══════════════════════════════════════════════════════════════════╣\n"
            f"║ OPENING:  {opening_en[:80]}\n"
            f"║ ACTIONS:  {actions_str[:80]}\n"
            f"╚═══════════════════════════════════════════════════════════════════╝"
        )
        card["summary_text"] = summary_text

        return SkillResult(success=True, data=card, confidence=0.95)

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=False,
            data={"summary_text": f"BL Card unavailable: {error}"},
            error=str(error), confidence=0.1, used_fallback=True,
        )
