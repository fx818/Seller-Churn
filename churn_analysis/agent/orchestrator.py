"""
Agent Orchestrator — chains skills per seller, computes final_tier, emits action plan.

Usage:
    from churn_analysis.agent.orchestrator import run_seller
    card = run_seller(glid, signals, api_responses, peer_benchmarks, progress_cb=print)
"""
import os, sys, json
from typing import Callable

# Add hackathon root to path for seller_survival imports
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ..skills.registry import registry

_RISK_ORDER = {"Red": 2, "Amber": 1, "Green": 0, "Unknown": 0}

def _max_risk(a: str, b: str) -> str:
    return a if _RISK_ORDER.get(a, 0) >= _RISK_ORDER.get(b, 0) else b


def run_seller(
    glid: int | str,
    signals: dict,
    api_responses: dict | None = None,
    peer_benchmarks: dict | None = None,
    model: str | None = None,
    progress_cb: Callable[[str, dict], None] | None = None,
) -> dict:
    """
    Run the full skill chain for one seller.

    signals        — output of compute_signals() from pipeline.py (or compatible dict)
    api_responses  — raw API responses dict from slim_loader.fetch_for_glid()
    peer_benchmarks — pre-computed peer_benchmarks.json dict
    model           — Claude model override for LLMCohortScorerSkill
    progress_cb     — callback(step_name, result_data) for streaming progress

    Returns: action_plan dict
    """
    api_responses   = api_responses or {}
    peer_benchmarks = peer_benchmarks or {}

    def emit(step: str, data: dict):
        if progress_cb:
            progress_cb(step, data)

    results = {}

    # ── STEP 1: ChurnScoringSkill ────────────────────────────────────────────
    emit("churn_scoring", {"status": "running"})
    r1 = registry.run("churn_scoring", {
        "glid":            glid,
        "enq_30d":         signals.get("enq_30d"),
        "replied_30d":     signals.get("replied_30d"),
        "active_days_30d": signals.get("active_days_30d"),
        "bl_velocity_pct": signals.get("bl_velocity_pct"),
        "pns_success_pct": signals.get("pns_success_pct"),
        "rag":             signals.get("rag"),
        "cqs":             signals.get("cqs"),
        "hotleads_count":  signals.get("hotleads_count"),
        "event_count":     signals.get("event_count"),
    })
    results["churn_scoring"] = r1.data
    emit("churn_scoring", {"status": "done", **r1.data})

    churn_score  = r1.data.get("churn_score", 0) or 0
    risk_tier    = r1.data.get("risk", "Green")
    reason_tags  = r1.data.get("reason_tags", [])
    score_break  = r1.data.get("score_breakdown", {})

    # ── STEP 2: SHAPRCASkill ────────────────────────────────────────────────
    emit("shap_rca", {"status": "running"})
    r2 = registry.run("shap_rca", {
        "glid":             glid,
        "reason_tags":      reason_tags,
        "score_breakdown":  score_break,
        "rag":              signals.get("rag"),
        "cqs":              signals.get("cqs"),
        "bl_velocity_pct":  signals.get("bl_velocity_pct"),
        "pns_success_pct":  signals.get("pns_success_pct"),
    })
    results["shap_rca"] = r2.data
    emit("shap_rca", {"status": "done", **r2.data})
    rca_category = r2.data.get("rca_category", "UNKNOWN")

    # ── STEP 3: PeerBenchmarkSkill ──────────────────────────────────────────
    emit("peer_benchmark", {"status": "running"})
    r3 = registry.run("peer_benchmark", {
        "glid":            glid,
        "enterprise":      signals.get("enterprise"),
        "ctype":           signals.get("ctype"),
        "enq_30d":         signals.get("enq_30d"),
        "active_days_30d": signals.get("active_days_30d"),
        "cqs":             signals.get("cqs"),
        "pns_success_pct": signals.get("pns_success_pct"),
        "peer_benchmarks": peer_benchmarks,
    })
    results["peer_benchmark"] = r3.data
    emit("peer_benchmark", {"status": "done", **r3.data})
    peer_delta = r3.data.get("peer_delta_pct")

    # ── STEP 3b: ConversionPointSkill (runs after peer_benchmark for TYPE_C accuracy) ─
    emit("conversion_point", {"status": "running"})
    r0 = registry.run("conversion_point", {
        "monthly_enq":      signals.get("monthly_enq", []),
        "account_age_days": signals.get("account_age"),
        "enq_30d":          signals.get("enq_30d"),
        "active_days_30d":  signals.get("active_days_30d"),
        "cqs":              signals.get("cqs"),
        "peer_median_enq":  r3.data.get("peer_median_enq"),
    })
    results["conversion_point"] = r0.data
    emit("conversion_point", {"status": "done", **r0.data})

    trajectory_type  = r0.data.get("trajectory_type", "UNKNOWN")
    force_onboarding = r0.data.get("run_onboarding", False)

    # ── STEP 4: DemandIndexSkill ────────────────────────────────────────────
    emit("demand_index", {"status": "running"})
    r4 = registry.run("demand_index", {
        "glid":              glid,
        "city":              signals.get("city"),
        "enterprise":        signals.get("enterprise"),
        "ctype":             signals.get("ctype"),
        "mcats":             signals.get("mcats", []),
        "total_bl_market":   signals.get("total_bl_market"),
        "total_paid_market": signals.get("total_paid_market"),
        "monthly_enq":       signals.get("monthly_enq", []),
    })
    results["demand_index"] = r4.data
    emit("demand_index", {"status": "done", **r4.data})

    account_age = signals.get("account_age") or 0

    # ── STEP 5: OnboardingHealth (new sellers OR TYPE_C trajectory) ──────────
    if account_age <= 90 or force_onboarding:
        emit("onboarding_health", {"status": "running"})
        r5 = registry.run("onboarding_health", {
            "glid":                 glid,
            "account_age_days":     account_age,
            "city":                 signals.get("city"),
            "enterprise":           signals.get("enterprise"),
            "ctype":                signals.get("ctype"),
            "cqs":                  signals.get("cqs"),
            "enq_30d":              signals.get("enq_30d"),
            "replied_30d":          signals.get("replied_30d"),
            "paid_history":         signals.get("paid_history"),
            "rag":                  signals.get("rag"),
            "demand_index_result":  r4.data,
            "peer_benchmark_result": r3.data,
        })
        results["onboarding_health"] = r5.data
        emit("onboarding_health", {"status": "done", **r5.data})
        # For new sellers, use onboarding risk to inform final tier
        ob_risk = r5.data.get("onboarding_risk", "Green")
        risk_tier = _max_risk(risk_tier, ob_risk)
    else:
        results["onboarding_health"] = {"is_new_seller": False, "skipped": True}
        emit("onboarding_health", {"status": "skipped", "reason": "established seller"})

    # ── STEP 6: LLMCohortScorerSkill (established sellers, if library built) ─
    llm_result = {}
    if account_age > 90:
        emit("llm_cohort_scorer", {"status": "running"})
        r13 = registry.run("llm_cohort_scorer", {
            "glid":             glid,
            "account_age_days": account_age,
            "api_responses":    api_responses,
            "model":            model,
        })
        results["llm_cohort_scorer"] = r13.data
        llm_result = r13.data
        emit("llm_cohort_scorer", {"status": "done", **r13.data})

        if not r13.data.get("skipped") and r13.data.get("pipeline_tier"):
            llm_tier  = r13.data["pipeline_tier"]
            risk_tier = _max_risk(risk_tier, llm_tier)
    else:
        results["llm_cohort_scorer"] = {"skipped": True, "reason": "new seller — no cohort comparison"}
        emit("llm_cohort_scorer", {"status": "skipped", "reason": "new seller"})

    # ── STEP 7: WhatsAppMessage ─────────────────────────────────────────────
    emit("whatsapp_message", {"status": "running"})
    r6 = registry.run("whatsapp_message", {
        "glid":              glid,
        "company":           signals.get("company"),
        "seller_name":       signals.get("company", "").split()[0] if signals.get("company") else "Seller",
        "city":              signals.get("city"),
        "enterprise":        signals.get("enterprise"),
        "rca_category":      rca_category,
        "peer_delta_pct":    peer_delta,
        "peer_median_enq":   r3.data.get("peer_median_enq"),
        "peer_benchmark_result": r3.data,
        "enq_30d":           signals.get("enq_30d"),
        "cqs":               signals.get("cqs"),
        "pns_success_pct":   signals.get("pns_success_pct"),
        "bl_velocity_pct":   signals.get("bl_velocity_pct"),
        "llm_reasoning":      llm_result.get("reasoning"),
        "message_type":       "retention_nudge",
        "trajectory_type":    trajectory_type,
        "trajectory_opening": r0.data.get("opening_line_hi", ""),
    })
    results["whatsapp_message"] = r6.data
    emit("whatsapp_message", {"status": "done"})

    # ── STEP 8: PreCallBrief (Red and Amber sellers) ────────────────────────
    if risk_tier in ("Red", "Amber"):
        emit("pre_call_brief", {"status": "running"})
        r7 = registry.run("pre_call_brief", {
            "glid":               glid,
            "company":            signals.get("company"),
            "seller_name":        signals.get("company", "").split()[0] if signals.get("company") else "Seller",
            "city":               signals.get("city"),
            "enterprise":         signals.get("enterprise"),
            "ctype":              signals.get("ctype"),
            "churn_score":        churn_score,
            "risk":               risk_tier,
            "rca_category":       rca_category,
            "rca_explanation_en": r2.data.get("rca_explanation_en"),
            "peer_delta_pct":     peer_delta,
            "enq_30d":            signals.get("enq_30d"),
            "bl_velocity_pct":    signals.get("bl_velocity_pct"),
            "pns_success_pct":    signals.get("pns_success_pct"),
            "cqs":                signals.get("cqs"),
            "active_days_30d":    signals.get("active_days_30d"),
            "account_age_days":   account_age,
            "hotleads_count":     signals.get("hotleads_count"),
            "llm_risk_level":     llm_result.get("risk_level"),
            "llm_bands":          llm_result.get("bands"),
            "llm_reasoning":      llm_result.get("reasoning"),
            "churned_lookalikes":  llm_result.get("churned_lookalikes"),
            "retained_lookalikes": llm_result.get("retained_lookalikes"),
            "trajectory_type":     trajectory_type,
            "trajectory_opening":  r0.data.get("opening_line_hi", ""),
            "trajectory_explanation": r0.data.get("explanation", ""),
        })
        results["pre_call_brief"] = r7.data
        emit("pre_call_brief", {"status": "done"})
    else:
        results["pre_call_brief"] = {"skipped": True, "reason": f"risk_tier={risk_tier}, brief only for Red/Amber"}
        emit("pre_call_brief", {"status": "skipped", "reason": f"tier={risk_tier}"})

    # ── STEP 9: CrossPlatformIntelligenceSkill (all Red/Amber sellers) ──────
    if risk_tier in ("Red", "Amber"):
        emit("cross_platform", {"status": "running"})
        # Extract IM product count from API responses
        im_product_count = _extract_im_product_count(api_responses)
        r_xp = registry.run("cross_platform_intelligence", {
            "glid":             glid,
            "company":          signals.get("company", ""),
            "city":             signals.get("city", ""),
            "mcats":            signals.get("mcats", []),
            "rca_category":     rca_category,
            "ctype":            signals.get("ctype", ""),
            "im_product_count": im_product_count,
        })
        results["cross_platform"] = r_xp.data
        emit("cross_platform", {"status": "done" if r_xp.success else "skipped", **r_xp.data})
    else:
        results["cross_platform"] = {"skipped": True, "reason": f"tier={risk_tier} (Green sellers not scanned)"}
        emit("cross_platform", {"status": "skipped", "reason": "Green tier"})

    # ── STEP 10: ScriptGenerationSkill ──────────────────────────────────────
    emit("script_generation", {"status": "running"})
    r_script = registry.run("script_generation", {
        "glid":              glid,
        "company":           signals.get("company", ""),
        "seller_name":       (signals.get("company") or "").split()[0] or "Seller",
        "city":              signals.get("city", ""),
        "rca_category":      rca_category,
        "risk_tier":         risk_tier,
        "trajectory_type":   trajectory_type,
        "opening_line_hi":   r0.data.get("opening_line_hi", ""),
        "churn_score":       churn_score,
        "enq_30d":           signals.get("enq_30d"),
        "peer_median_enq":   r3.data.get("peer_median_enq"),
        "peer_delta_pct":    peer_delta,
        "active_days_30d":   signals.get("active_days_30d"),
        "bl_velocity_pct":   signals.get("bl_velocity_pct"),
        "pns_success_pct":   signals.get("pns_success_pct"),
        "hotleads_count":    signals.get("hotleads_count"),
        "cqs":               signals.get("cqs"),
        "cross_platform":    results.get("cross_platform", {}),
        "llm_risk_level":    llm_result.get("risk_level"),
        "llm_reasoning":     llm_result.get("reasoning"),
        "rca_explanation_en": r2.data.get("rca_explanation_en", ""),
    })
    results["script_generation"] = r_script.data
    emit("script_generation", {"status": "done"})

    # ── STEP 11: GiftedLeadSkill ─────────────────────────────────────────────
    emit("gifted_lead", {"status": "running"})
    r_lead = registry.run("gifted_lead", {
        "glid":         glid,
        "hotleads":     (api_responses.get("gifted_lead_v2") or {}).get("data", {}).get("results", []),
        "rca_category": rca_category,
        "churn_score":  churn_score,
    })
    results["gifted_lead"] = r_lead.data
    emit("gifted_lead", {"status": "done" if r_lead.success else "skipped"})

    # ── STEP 12: WinbackPrioritySkill ────────────────────────────────────────
    emit("winback_priority", {"status": "running"})
    r_wb = registry.run("winback_priority", {
        "glid":           glid,
        "churn_score":    churn_score,
        "rca_category":   rca_category,
        "trajectory_type": trajectory_type,
        "enq_30d":        signals.get("enq_30d"),
        "active_days_30d": signals.get("active_days_30d"),
        "account_age_days": account_age,
        "paid_history":   signals.get("paid_history"),
        "demand_index":   r4.data.get("demand_index"),
        "peer_delta_pct": peer_delta,
        "cqs":            signals.get("cqs"),
        "enterprise":     signals.get("enterprise"),
    })
    results["winback_priority"] = r_wb.data
    emit("winback_priority", {"status": "done" if r_wb.success else "skipped"})

    # ── STEP 13: BLUpgradeSkill ──────────────────────────────────────────────
    emit("bl_upgrade", {"status": "running"})
    r_bl = registry.run("bl_upgrade", {
        "glid":            glid,
        "churn_score":     churn_score,
        "enterprise":      signals.get("enterprise"),
        "account_age_days": account_age,
        "enq_30d":         signals.get("enq_30d"),
        "active_days_30d": signals.get("active_days_30d"),
        "llm_risk_level":  llm_result.get("risk_level"),
        "days_to_renewal": signals.get("days_to_renewal"),
        "rag":             signals.get("rag"),
        "paid_history":    signals.get("paid_history"),
    })
    results["bl_upgrade"] = r_bl.data
    emit("bl_upgrade", {"status": "done" if r_bl.success else "skipped"})

    # ── Compile action plan ──────────────────────────────────────────────────
    actions = _decide_actions(risk_tier, rca_category, results)

    action_plan = {
        "glid":             str(glid),
        "company":          signals.get("company", ""),
        "city":             signals.get("city", ""),
        "final_tier":       risk_tier,
        "churn_score":      churn_score,
        "rca_category":     rca_category,
        "trajectory_type":  trajectory_type,
        "actions":          actions,
        "skill_outputs":    results,
    }

    emit("complete", {"status": "done", "final_tier": risk_tier, "rca": rca_category})
    return action_plan


def _extract_im_product_count(api_responses: dict) -> int:
    """Extract IndiaMART product count from cached API responses."""
    # Try product_details first
    pd = api_responses.get("product_details") or {}
    data = pd.get("data") or {}
    if isinstance(data, dict):
        items = data.get("data") or data.get("products") or data.get("items") or []
        if isinstance(items, list):
            return len(items)
        total = data.get("total_count") or data.get("count")
        if total:
            return int(total)
    # Try product_summary
    ps = api_responses.get("product_summary") or {}
    ps_data = ps.get("data") or {}
    if isinstance(ps_data, dict):
        count = ps_data.get("total_products") or ps_data.get("product_count")
        if count:
            return int(count)
    return 0


def _decide_actions(tier: str, rca: str, results: dict) -> list[dict]:
    actions = []
    if tier == "Red":
        actions.append({"type": "HUMAN_CALL", "priority": "HIGH", "timing": "24h",
                        "brief": results.get("pre_call_brief", {}).get("brief_text", "")})
        actions.append({"type": "WHATSAPP", "priority": "MEDIUM", "timing": "NOW",
                        "message_hi": results.get("whatsapp_message", {}).get("message_hi", ""),
                        "message_en": results.get("whatsapp_message", {}).get("message_en", "")})
    elif tier == "Amber":
        actions.append({"type": "WHATSAPP", "priority": "HIGH", "timing": "NOW",
                        "message_hi": results.get("whatsapp_message", {}).get("message_hi", ""),
                        "message_en": results.get("whatsapp_message", {}).get("message_en", "")})
        actions.append({"type": "MONITOR", "priority": "LOW", "timing": "7d",
                        "note": "Re-score in 7 days"})
    else:
        actions.append({"type": "MONITOR", "priority": "LOW", "timing": "30d",
                        "note": "Green tier — automated nurture track"})
    return actions
