"""SKILL 7 — PreCallBriefSkill: Rep-ready 30-second pre-call brief card for Red-tier sellers."""
from churn_analysis.skills.base_skill import Skill, SkillResult


def _severity(value, critical_thresh, high_thresh=None):
    if value is None:
        return "info"
    if isinstance(value, (int, float)):
        if value >= critical_thresh:
            return "critical"
        if high_thresh is not None and value >= high_thresh:
            return "high"
    return "medium"


class PreCallBriefSkill(Skill):
    name = "pre-call-brief"
    version = "1.0"
    required_inputs = ["glid"]
    optional_inputs = [
        "company", "city", "enterprise", "ctype",
        "churn_score", "risk", "rca_category", "rca_explanation_en",
        "peer_delta_pct", "enq_30d", "bl_velocity_pct",
        "pns_success_pct", "cqs", "active_days_30d",
        "account_age_days", "hotleads_count", "days_to_renewal",
        "llm_risk_level", "llm_bands", "llm_reasoning",
        "churned_lookalikes", "retained_lookalikes",
        "seller_name",
    ]

    def invoke(self, inputs: dict) -> SkillResult:
        company      = inputs.get("company") or "This Seller"
        city         = inputs.get("city") or "—"
        enterprise   = inputs.get("enterprise") or "—"
        ctype        = inputs.get("ctype") or "—"
        churn_score  = inputs.get("churn_score")
        risk         = inputs.get("risk") or "Unknown"
        rca          = inputs.get("rca_category") or "UNKNOWN"
        rca_en       = inputs.get("rca_explanation_en") or ""
        peer_delta   = inputs.get("peer_delta_pct")
        enq_30       = inputs.get("enq_30d", 0)
        bl_vel       = inputs.get("bl_velocity_pct")
        pns_pct      = inputs.get("pns_success_pct")
        cqs          = inputs.get("cqs")
        active_30    = inputs.get("active_days_30d", 0)
        age          = inputs.get("account_age_days", 0)
        hotleads     = inputs.get("hotleads_count", 0)
        renewal_days = inputs.get("days_to_renewal")
        llm_risk     = inputs.get("llm_risk_level")
        llm_bands    = inputs.get("llm_bands") or {}
        llm_reason   = inputs.get("llm_reasoning") or ""
        seller_name  = inputs.get("seller_name") or company.split()[0]

        # ── Key signals ───────────────────────────────────────────────────────
        key_signals = []

        if churn_score is not None:
            key_signals.append({
                "label": "Churn Score",
                "value": f"{churn_score}/100",
                "severity": "critical" if churn_score >= 65 else ("high" if churn_score >= 45 else "medium"),
            })

        if llm_risk:
            key_signals.append({
                "label": "AI Risk Level",
                "value": f"{llm_risk} (cohort-calibrated)",
                "severity": "critical" if llm_risk in ("Critical", "Very High") else "high",
            })

        if bl_vel is not None:
            key_signals.append({
                "label": "Lead Volume Trend",
                "value": f"{bl_vel:+.0f}% MoM",
                "severity": "critical" if bl_vel <= -30 else ("high" if bl_vel <= -10 else "medium"),
            })

        if peer_delta is not None:
            key_signals.append({
                "label": "vs Peer Sellers",
                "value": f"{peer_delta:+.0f}% vs peers",
                "severity": "high" if peer_delta < -40 else "medium",
            })

        if pns_pct is not None:
            key_signals.append({
                "label": "PNS Answer Rate",
                "value": f"{pns_pct}%",
                "severity": "high" if pns_pct < 60 else "medium",
            })

        if active_30 is not None:
            key_signals.append({
                "label": "Active Days (30d)",
                "value": str(active_30),
                "severity": "critical" if active_30 == 0 else ("high" if active_30 <= 3 else "medium"),
            })

        if cqs is not None:
            key_signals.append({
                "label": "Catalog Score (CQS)",
                "value": str(cqs),
                "severity": "high" if cqs < 60 else "medium",
            })

        if renewal_days is not None:
            key_signals.append({
                "label": "Days to Renewal",
                "value": str(renewal_days),
                "severity": "critical" if renewal_days <= 7 else ("high" if renewal_days <= 30 else "medium"),
            })

        # ── Opening lines ────────────────────────────────────────────────────
        if rca == "NO_LEADS" or rca == "BL_DECLINE":
            opening_hi = f"{seller_name} Bhai, maine aapka account dekha — last month leads {abs(bl_vel) if bl_vel else '—'}% kam ho gayi hain."
            opening_en = f"{seller_name} ji, leads dropped {abs(bl_vel) if bl_vel else '—'}% last month. There's a specific reason I can explain."
        elif rca == "LOW_ENGAGEMENT":
            opening_hi = f"{seller_name} Bhai, platform pe kuch din se activity nahi dikhte — sab theek hai?"
            opening_en = f"{seller_name} ji, haven't seen much platform activity recently. Everything okay?"
        elif rca == "POOR_CATALOG":
            opening_hi = f"{seller_name} Bhai, aapke product listing mein kuch quick improvements hain — leads badhenge."
            opening_en = f"{seller_name} ji, quick catalog improvements could significantly boost your leads."
        else:
            opening_hi = f"{seller_name} Bhai, maine aapka account review kiya — discuss karna chahta hoon."
            opening_en = f"{seller_name} ji, reviewed your account — want to discuss a few key things."

        # ── Suggested actions ────────────────────────────────────────────────
        action_map = {
            "NO_LEADS":        ["Discuss national geography expansion", "Show buyer demand data from Delhi/Mumbai"],
            "BL_DECLINE":      ["Diagnose lead volume drop cause", "Suggest category or geography adjustment"],
            "LOW_ENGAGEMENT":  ["Fix notification setup on mobile", "Enable LMS reply from app"],
            "POOR_CATALOG":    ["Walk through CQS improvement steps", "Add missing product photos/prices"],
            "LOW_PNS_RESPONSE": ["Check call forwarding settings", "Enable DND exceptions for IndiaMART"],
            "PEER_GAP":        ["Share peer comparison data", "Identify specific differentiator peers use"],
        }
        suggested_actions = action_map.get(rca, ["Conduct discovery call", "Identify main blocker"])
        if llm_risk in ("Critical", "Very High"):
            suggested_actions.insert(0, "⚠️ AI-flagged as high churn risk — prioritize this call")

        # ── LLM bands display ────────────────────────────────────────────────
        bands_display = None
        if llm_bands:
            band_labels = {"R": "🔴 Red", "A": "🟡 Amber", "G": "🟢 Green"}
            bands_display = {
                "BL Consumption": band_labels.get(llm_bands.get("bl", ""), "—"),
                "LMS Activity":   band_labels.get(llm_bands.get("lms", ""), "—"),
                "Activity Trend": band_labels.get(llm_bands.get("activity", ""), "—"),
            }

        brief_text = (
            f"SELLER: {company} | {city} | {enterprise}/{ctype} | Age: {age}d\n"
            f"CHURN SCORE: {churn_score}/100 | RISK: {risk}"
            + (f" | AI: {llm_risk}" if llm_risk else "") + "\n"
            f"MAIN ISSUE: {rca} — {rca_en}\n"
            f"OPENING: {opening_en}\n"
            f"ACTIONS: {'; '.join(suggested_actions[:3])}"
        )

        return SkillResult(
            success=True,
            data={
                "company":           company,
                "city":              city,
                "enterprise":        enterprise,
                "ctype":             ctype,
                "opening_line_hi":   opening_hi,
                "opening_line_en":   opening_en,
                "key_signals":       key_signals,
                "suggested_actions": suggested_actions,
                "do_not_mention":    ["renewal price", "subscription cost", "competitor pricing"],
                "call_type":         "RETENTION",
                "estimated_call_duration": "8-12 min",
                "rca_category":      rca,
                "llm_risk_level":    llm_risk,
                "llm_bands_display": bands_display,
                "llm_reasoning":     llm_reason,
                "churned_lookalikes":  inputs.get("churned_lookalikes") or [],
                "retained_lookalikes": inputs.get("retained_lookalikes") or [],
                "brief_text":        brief_text,
            },
            confidence=0.85,
        )

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=False,
            data={"brief_text": "Brief unavailable due to data error.", "call_type": "RETENTION"},
            error=str(error), confidence=0.1, used_fallback=True,
        )
