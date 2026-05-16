"""Churn Analysis UI — MD-driven skills pipeline with BL Card + per-skill panels."""
import sys
import os
import json

_ROOT = os.path.dirname(__file__)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st

st.set_page_config(
    page_title="Churn Analysis — BL Card",
    page_icon="📊",
    layout="wide",
)

st.markdown("""
<style>
.risk-red    { background:#fee2e2; color:#991b1b; padding:6px 16px; border-radius:8px; font-weight:700; font-size:1.1rem; display:inline-block; }
.risk-amber  { background:#fef3c7; color:#92400e; padding:6px 16px; border-radius:8px; font-weight:700; font-size:1.1rem; display:inline-block; }
.risk-green  { background:#d1fae5; color:#065f46; padding:6px 16px; border-radius:8px; font-weight:700; font-size:1.1rem; display:inline-block; }
.verdict-critical { background:linear-gradient(90deg,#dc2626,#991b1b); color:white; padding:14px 22px; border-radius:10px; font-weight:700; font-size:1.25rem; }
.verdict-risk     { background:linear-gradient(90deg,#f59e0b,#d97706); color:white; padding:14px 22px; border-radius:10px; font-weight:700; font-size:1.25rem; }
.verdict-healthy  { background:linear-gradient(90deg,#10b981,#059669); color:white; padding:14px 22px; border-radius:10px; font-weight:700; font-size:1.25rem; }
.score-big   { font-size:3rem; font-weight:800; line-height:1; }
.ok    { color:#16a34a; font-weight:600; }
.fail  { color:#dc2626; font-weight:600; }
.skip  { color:#6b7280; font-style:italic; }
.card-section { background:#f9fafb; border-left:4px solid #6366f1; padding:14px 18px; margin:10px 0; border-radius:6px; }
.card-h      { color:#4338ca; font-weight:700; font-size:1.05rem; margin-bottom:6px; }
.metric-pill { background:#e0e7ff; color:#3730a3; padding:4px 12px; border-radius:14px; font-size:0.85rem; font-weight:600; margin:2px; display:inline-block; }
.platform-pill-found { background:#d1fae5; color:#065f46; padding:6px 14px; border-radius:16px; font-weight:700; margin:4px; display:inline-block; }
.platform-pill-miss  { background:#f3f4f6; color:#6b7280; padding:6px 14px; border-radius:16px; margin:4px; display:inline-block; }
.priority-bar { background:#e5e7eb; height:10px; border-radius:5px; overflow:hidden; }
.priority-fill { height:100%; background:linear-gradient(90deg,#10b981,#f59e0b,#dc2626); }
.traj-typea { background:#dc2626; color:white; padding:8px 18px; border-radius:8px; font-weight:700; }
.traj-typeb { background:#f59e0b; color:white; padding:8px 18px; border-radius:8px; font-weight:700; }
.traj-typec { background:#6366f1; color:white; padding:8px 18px; border-radius:8px; font-weight:700; }
.sev-critical { background:#fee2e2; color:#991b1b; padding:3px 10px; border-radius:4px; font-weight:600; font-size:0.85rem; }
.sev-high     { background:#fed7aa; color:#9a3412; padding:3px 10px; border-radius:4px; font-weight:600; font-size:0.85rem; }
.sev-medium   { background:#fef3c7; color:#92400e; padding:3px 10px; border-radius:4px; font-weight:600; font-size:0.85rem; }
.sev-info     { background:#dbeafe; color:#1e40af; padding:3px 10px; border-radius:4px; font-weight:600; font-size:0.85rem; }
.phone-msg    { background:#dcfce7; color:#14532d; padding:14px 16px; border-radius:14px 14px 14px 4px; max-width:480px; font-family:'Segoe UI',sans-serif; white-space:pre-wrap; }
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════
def risk_badge(risk):
    css = {"Red": "risk-red", "Amber": "risk-amber", "Green": "risk-green"}.get(risk, "risk-amber")
    return f'<span class="{css}">{risk}</span>'

def verdict_class(verdict_str):
    v = (verdict_str or "").upper()
    if "CRITICAL" in v: return "verdict-critical"
    if "AT RISK" in v:  return "verdict-risk"
    return "verdict-healthy"

def score_color(score):
    if score is None: return "#6b7280"
    if score >= 70: return "#dc2626"
    if score >= 40: return "#d97706"
    return "#16a34a"

def sev_class(sev):
    return f"sev-{sev}" if sev in ("critical", "high", "medium", "info") else "sev-info"

def tier_badge(tier):
    return {"Green": "🟢", "Amber": "🟡", "Red": "🔴"}.get(tier, "⚪")

# ════════════════════════════════════════════════════════════════════════════
# PER-SKILL RENDERERS
# ════════════════════════════════════════════════════════════════════════════

def render_churn_scoring(d):
    if not d: return
    score = d.get("churn_score")
    risk  = d.get("risk", "Unknown")
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        st.markdown(f'<div class="score-big" style="color:{score_color(score)}">{score if score is not None else "—"}</div>', unsafe_allow_html=True)
        st.caption("Final Churn Score / 100")
    with c2:
        st.markdown(risk_badge(risk), unsafe_allow_html=True)
        st.caption("Risk Tier")
    with c3:
        sb = d.get("score_breakdown") or {}
        if sb:
            st.markdown("**Per-signal points:**")
            for k, v in sb.items():
                st.markdown(f"- {k.replace('_',' ').title()}: `+{v}`")

    # v2.0 derivation breakdown
    base    = d.get("base_score")
    cmult   = d.get("compound_multiplier", 1.0)
    tadj    = d.get("trajectory_adjustment", 0)
    tnote   = d.get("trajectory_note") or ""
    pre_llm = d.get("pre_llm_score")
    llm_adj = d.get("llm_adjustment", 0)
    llm_just= d.get("llm_justification") or ""
    llm_used = d.get("llm_used", False)
    red_count = d.get("red_flag_count", 0)

    if base is not None:
        with st.expander("📊 How the churn score was calculated", expanded=False):
            st.markdown("**Step-by-step derivation:**")
            st.markdown(f"  1. **Base score** (sum of per-signal penalties): `{base}`")
            if cmult and cmult > 1.0:
                st.markdown(f"  2. **Compound penalty** ({red_count} Red-severity flags): `×{cmult}` → `{round(base * cmult, 1)}`")
            else:
                st.markdown(f"  2. Compound penalty: not triggered ({red_count} Red flags, need ≥3)")
            if tadj:
                st.markdown(f"  3. **Trajectory adjustment**: `{tadj:+d}` — {tnote}")
            else:
                st.markdown(f"  3. Trajectory adjustment: `0`")
            if pre_llm is not None:
                st.markdown(f"  4. **Pre-LLM score**: `{pre_llm}`")
            if llm_used:
                st.markdown(f"  5. **🤖 LLM second-opinion adjustment**: `{llm_adj:+d}`")
                if llm_just:
                    st.info(f'**LLM rationale:** {llm_just}')
                interactions = d.get("llm_interactions") or []
                if interactions:
                    st.markdown("**Key signal interactions noticed by LLM:**")
                    for i in interactions:
                        st.markdown(f"  • {i}")
            else:
                st.markdown(f"  5. LLM second opinion: not run")
            st.divider()
            st.markdown(f"### Final: **{score}/100**  ({risk})")

            # Per-signal breakdown
            sb = d.get("score_breakdown") or {}
            if sb:
                st.markdown("**Per-signal points contributing to the base:**")
                for k, v in sb.items():
                    st.markdown(f"  - {k.replace('_',' ').title()}: `+{v}`")

            st.caption(
                "Tiers: ≥72 = Red, 42–71 = Amber, <42 = Green. "
                "Note: cross-platform adjustment (if any) is applied separately in the BL Card."
            )

    reasons = d.get("churn_reasons") or []
    if reasons:
        st.markdown("**Churn signals detected:**")
        for r in reasons:
            st.warning(r, icon="⚠️")

    tags = d.get("reason_tags") or []
    if tags:
        pills = " ".join(f'<span class="metric-pill">{t}</span>' for t in tags)
        st.markdown(pills, unsafe_allow_html=True)

    rep = d.get("reply_rate_30d")
    if rep is not None:
        st.caption(f"Reply rate (30d): {rep}%  |  Signals available: {d.get('signals_available','?')}  |  Red flags: {red_count}")


def render_shap_rca(d):
    if not d: return
    rca  = d.get("rca_category", "—")
    conf = d.get("rca_confidence")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown(f"### `{rca}`")
        if conf is not None:
            st.progress(min(1.0, float(conf)), text=f"Confidence: {conf:.2f}")
    with c2:
        st.info(d.get("rca_explanation_en", ""))
        st.caption(d.get("rca_explanation_hi", ""))
    if d.get("intervention_hint"):
        st.success(f"🔧 {d['intervention_hint']}")
    breakdown = d.get("shap_breakdown") or []
    if breakdown:
        with st.expander("SHAP contributions"):
            st.json(breakdown)


def render_llm_cohort(d):
    if not d: return
    if d.get("skipped"):
        st.info(f"Skipped — {d.get('reason','')}")
        return

    risk = d.get("risk_level", "—")
    tier = d.get("pipeline_tier", "—")
    conf = d.get("confidence_score")

    c1, c2, c3 = st.columns(3)
    c1.metric("LLM Risk Level", risk)
    c2.metric("Pipeline Tier", tier)
    c3.metric("Confidence", f"{conf}/100" if conf is not None else "—")

    bands = d.get("bands") or {}
    if bands:
        st.markdown("**Cohort bands:**")
        b1, b2, b3 = st.columns(3)
        b1.markdown(f"### {tier_badge(bands.get('bl','').upper()=='G' and 'Green' or bands.get('bl','').upper()=='A' and 'Amber' or 'Red')} BL: `{bands.get('bl','?')}`")
        b2.markdown(f"### {tier_badge(bands.get('lms','').upper()=='G' and 'Green' or bands.get('lms','').upper()=='A' and 'Amber' or 'Red')} LMS: `{bands.get('lms','?')}`")
        b3.markdown(f"### {tier_badge(bands.get('activity','').upper()=='G' and 'Green' or bands.get('activity','').upper()=='A' and 'Amber' or 'Red')} Activity: `{bands.get('activity','?')}`")

    if d.get("reasoning"):
        with st.expander("📖 LLM Reasoning"):
            st.write(d["reasoning"])

    l1, l2 = st.columns(2)
    with l1:
        st.markdown("**Churned lookalikes (similar sellers that churned):**")
        for g in (d.get("churned_lookalikes") or [])[:8]:
            st.markdown(f'<span class="metric-pill" style="background:#fee2e2;color:#991b1b">GLID {g}</span>', unsafe_allow_html=True)
    with l2:
        st.markdown("**Retained lookalikes (similar sellers that stayed):**")
        for g in (d.get("retained_lookalikes") or [])[:8]:
            st.markdown(f'<span class="metric-pill" style="background:#d1fae5;color:#065f46">GLID {g}</span>', unsafe_allow_html=True)

    cm = d.get("cohort_match") or {}
    if cm:
        st.caption(f"Cohort match: n_filtered={cm.get('n_filtered','?')}, tier={cm.get('tier','?')}, shown_to_llm={cm.get('shown_to_llm','?')}")


def render_peer_benchmark(d):
    if not d: return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Peer group", d.get("peer_group", "—"))
    c2.metric("n (peers)", d.get("peer_n", 0))
    pct = d.get("enq_percentile")
    if pct is not None:
        c3.metric("Enq percentile", f"{pct:.0f}")
        st.progress(min(1.0, pct / 100.0))
    c4.metric("Gap severity", d.get("gap_severity", "—"))
    if d.get("peer_summary_line"):
        st.info(d["peer_summary_line"])
    if d.get("peer_median_enq") is not None:
        st.caption(f"Peer median enq: {d['peer_median_enq']}")


def render_demand_index(d):
    if not d: return
    c1, c2, c3 = st.columns(3)
    c1.metric("Demand index", d.get("demand_index", "—"))
    c2.markdown(risk_badge(d.get("demand_tier", "—")), unsafe_allow_html=True)
    c2.caption("Demand tier")
    c3.metric("Trend", d.get("trend", "—"))

    mbs = d.get("market_bl_per_seller")
    if mbs is not None:
        st.caption(f"Market BLs per paid seller: {mbs}")

    if d.get("demand_explanation"):
        st.info(d["demand_explanation"])
    if d.get("recommended_action"):
        st.success(f"📌 {d['recommended_action']}")

    flags = []
    if d.get("is_high_risk_category"):
        flags.append("🚨 High-risk category")
    if d.get("city_risk_prior", 0):
        flags.append(f"⚠️ City risk prior: {d['city_risk_prior']}")
    if flags:
        st.warning(" | ".join(flags))


def render_conversion_point(d):
    if not d: return
    traj  = d.get("trajectory_type", "UNKNOWN")
    label = d.get("trajectory_label", "Unknown")

    urgency_map = {
        "TYPE_A": ("🚨 EMERGENCY — intervene within 24h", "traj-typea"),
        "TYPE_B": ("⚠️ PROACTIVE — 7-day window", "traj-typeb"),
        "TYPE_C": ("🆘 ONBOARDING RESET — never engaged", "traj-typec"),
    }
    urgency_text, css = urgency_map.get(traj, ("Unknown trajectory", "traj-typec"))
    st.markdown(f'<span class="{css}">{traj} — {label}</span>', unsafe_allow_html=True)
    st.write("")
    st.caption(urgency_text)

    if d.get("explanation"):
        st.info(d["explanation"])

    me = d.get("monthly_enq") or []
    if me and len(me) >= 2:
        st.markdown("**Monthly enquiry trend:**")
        st.line_chart(me, height=200)
        cliff = d.get("cliff_month_index")
        drop  = d.get("cliff_drop_pct")
        if cliff is not None:
            st.caption(f"Inflection: month {cliff + 1} of {len(me)}  |  drop: {drop}%")

    pm = d.get("peer_median_enq")
    if pm:
        st.caption(f"Peer median enq: {pm}")


def render_onboarding_health(d):
    if not d: return
    score = d.get("health_score") or d.get("onboarding_score")
    tier  = d.get("health_tier")  or d.get("onboarding_risk")
    base_score    = d.get("base_score")
    prior_penalty = d.get("prior_penalty", 0)
    priors        = d.get("risk_priors") or []

    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown(f'<div class="score-big" style="color:{score_color(100 - (score or 0))}">{score if score is not None else "—"}</div>', unsafe_allow_html=True)
        st.caption("Onboarding Health Score")
        st.markdown(risk_badge(tier or "—"), unsafe_allow_html=True)
        if base_score is not None and prior_penalty:
            st.caption(f"Base: {base_score} | Priors: −{prior_penalty}")
    with c2:
        trigger = d.get("trigger_action", "—")
        st.markdown(f"**Trigger action:** `{trigger}`")
        if d.get("call_script_hint"):
            st.success(f"💡 {d['call_script_hint']}")

    # Risk priors
    if priors:
        st.markdown("**⚠️ Risk Priors (flat penalties):**")
        for p in priors:
            st.warning(f"−{p.get('penalty')} pts: {p.get('note')}")

    # 7-Check breakdown
    checks = d.get("checks") or d.get("check_results") or {}
    if checks:
        st.markdown(f"**{len(checks)}-Check Breakdown:**")
        for cname, cdata in checks.items():
            tname = cdata.get("tier", "—")
            score_v = cdata.get("score", 0)
            weight = cdata.get("weight", 0)
            note = cdata.get("note", "")
            st.markdown(
                f"{tier_badge(tname)} **{cname.replace('_',' ').title()}** — "
                f"score `{score_v}/100`  · weight `{int(weight*100)}%`  · `{tname}`"
            )
            st.caption(f"  {note}")
            st.progress(min(1.0, score_v / 100.0))

    # Activation plan
    plan = d.get("activation_plan") or {}
    if plan:
        st.divider()
        plan_method = d.get("plan_method", "template")
        if plan_method == "llm":
            st.success(f"🤖 **LLM-personalized Activation Plan** (tone: {plan.get('tone','—')})")
            sigs = plan.get("personalization_signals_used") or []
            if sigs:
                st.caption("Signals used: " + ", ".join(f"`{s}`" for s in sigs))
        else:
            st.info(f"📋 **Template Activation Plan** (tone: {plan.get('tone','—')})")
            if d.get("llm_error"):
                st.caption(f"LLM unavailable: {d['llm_error']}")

        if plan.get("opening_pitch_hi"):
            st.markdown(f"**Opening pitch (HI):** _{plan['opening_pitch_hi']}_")
        if plan.get("opening_pitch_en"):
            st.caption(f"Opening pitch (EN): {plan['opening_pitch_en']}")

        tasks = plan.get("tasks") or []
        if tasks:
            st.markdown(f"**Tasks ({len(tasks)}):**")
            priority_emoji = {"critical": "🚨", "high": "⚠️", "medium": "ℹ️"}
            for i, t in enumerate(tasks, 1):
                pri = t.get("priority", "medium")
                with st.container(border=True):
                    st.markdown(
                        f"**{i}. {priority_emoji.get(pri, '•')} {t.get('title','—')}**  "
                        f"(`{pri}`, ~{t.get('effort_min','?')} min)"
                    )
                    if t.get("title_en"):
                        st.caption(f"EN: {t['title_en']}")
                    if t.get("reason"):
                        st.markdown(f"**Why:** {t['reason']}")
                    if t.get("rep_action"):
                        st.success(f"🎯 **Rep action:** {t['rep_action']}")


def render_pre_call_brief(d):
    if not d: return
    if d.get("opening_line_en"):
        st.info(f'**Opening (EN):** _{d["opening_line_en"]}_')
    if d.get("opening_line_hi"):
        st.caption(f'Opening (HI): {d["opening_line_hi"]}')

    signals = d.get("key_signals") or []
    if signals:
        st.markdown("**Key signals:**")
        for s in signals:
            sev = s.get("severity", "info")
            st.markdown(
                f'<span class="{sev_class(sev)}">{s.get("label","?")}: {s.get("value","?")}</span>',
                unsafe_allow_html=True
            )

    actions = d.get("suggested_actions") or []
    if actions:
        st.markdown("**Suggested actions:**")
        for a in actions:
            st.markdown(f"  ✓ {a}")

    if d.get("do_not_mention"):
        st.warning("**Do not mention:** " + ", ".join(d["do_not_mention"]))

    bands = d.get("llm_bands_display") or {}
    if bands:
        st.markdown("**LLM bands:**")
        bc = st.columns(len(bands))
        for i, (k, v) in enumerate(bands.items()):
            bc[i].metric(k, v)


def render_whatsapp(d):
    if not d: return
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Hindi 🇮🇳**")
        st.markdown(f'<div class="phone-msg">{d.get("message_hi","—")}</div>', unsafe_allow_html=True)
    with c2:
        st.markdown("**English**")
        st.markdown(f'<div class="phone-msg">{d.get("message_en","—")}</div>', unsafe_allow_html=True)
    if d.get("cta"):
        st.caption(f"CTA: {d['cta']}")
    if d.get("rca_used"):
        st.caption(f"RCA template used: `{d['rca_used']}`")


def render_script_generation(d):
    if not d: return
    parts_hi = d.get("script_parts") or {}
    parts_en = d.get("script_parts_en") or {}
    duration = d.get("estimated_duration_min", "?")
    rca_used = d.get("rca_used", "—")
    method   = d.get("generation_method", "template")
    signals  = d.get("personalization_signals_used") or []

    # Method badge
    if method == "llm":
        st.success(f"🤖 **LLM-personalized** (estimated duration: {duration} min)")
        if signals:
            st.caption("Signals used: " + ", ".join(f"`{s}`" for s in signals))
    else:
        st.info(f"📋 **Template-based** (RCA: `{rca_used}`, duration: {duration} min)")
        if d.get("llm_error"):
            st.caption(f"LLM unavailable — fell back to template. Error: {d['llm_error']}")
    st.divider()

    tab_hi, tab_en = st.tabs(["Hindi", "English"])
    steps = ["opening", "diagnostic", "value_demo", "action", "close"]
    with tab_hi:
        for i, s in enumerate(steps, 1):
            st.markdown(f"**{i}. {s.replace('_',' ').title()}**")
            st.markdown(f"> {parts_hi.get(s, '—')}")
    with tab_en:
        for i, s in enumerate(steps, 1):
            st.markdown(f"**{i}. {s.replace('_',' ').title()}**")
            st.markdown(f"> {parts_en.get(s, '—')}")

    obj_hi = d.get("objection_handlers") or {}
    if obj_hi:
        with st.expander("Objection Handlers"):
            for k, v in obj_hi.items():
                st.markdown(f"**{k.replace('_',' ').title()}:** {v}")


def render_gifted_lead(d):
    if not d: return
    if d.get("lead_found"):
        lead = d.get("lead") or {}
        st.success("🎁 Lead available to gift!")
        if lead:
            st.json(lead)
    else:
        st.info(f"No lead available. {d.get('reason','')}")
        if d.get("fallback"):
            st.caption(f"Fallback: {d['fallback']}")
        if d.get("total_qualifying"):
            st.caption(f"Total qualifying leads in pool: {d['total_qualifying']}")


def render_cross_platform(d):
    if not d: return
    if d.get("skipped"):
        st.warning(f"Skipped — {d.get('reason','')}")
        return

    platforms = d.get("platforms_found") or []
    pdata     = d.get("platform_data") or {}
    gap       = d.get("im_catalog_gap") or {}
    card      = d.get("call_card") or {}

    st.markdown("**Platforms scanned:**")
    all_known = ["justdial", "tradeindia", "shopify", "own_website"]
    pill_html = ""
    for p in all_known:
        if p in platforms or pdata.get(p, {}).get("found"):
            pill_html += f'<span class="platform-pill-found">✓ {p.title().replace("_"," ")}</span>'
        else:
            pill_html += f'<span class="platform-pill-miss">— {p.title().replace("_"," ")}</span>'
    st.markdown(pill_html, unsafe_allow_html=True)
    st.write("")

    # IndiaMART card (always first, as the baseline for comparison)
    im_count = d.get("im_product_count") or (gap.get("im_products") if gap else 0) or 0
    with st.container(border=True):
        cols = st.columns([2, 1, 1, 1])
        cols[0].markdown("**🏠 IndiaMART (this seller)**")
        cols[0].caption(f"Company: {d.get('company_name_used','—')}")
        cols[1].metric("Products", im_count)
        if d.get("own_website_domain"):
            cols[2].metric("Email domain", d["own_website_domain"][:15])
        if d.get("gst"):
            cols[3].metric("GST", "✓")

    # Per-platform cards
    for pname, pdetail in pdata.items():
        if not pdetail.get("found"):
            continue
        with st.container(border=True):
            cols = st.columns([2, 1, 1, 1])
            cols[0].markdown(f"**{pname.title().replace('_',' ')}**")
            if pdetail.get("url"):
                cols[0].caption(pdetail["url"])
            cols[1].metric("Products", pdetail.get("product_count", "?"))
            cols[2].metric("Photos/prod", pdetail.get("photos_avg", "?"))
            if pdetail.get("rating") is not None:
                cols[3].metric("Rating", pdetail.get("rating", "?"))
            elif pdetail.get("reviews") is not None:
                cols[3].metric("Reviews", pdetail.get("reviews", "?"))

    # Gap
    if gap:
        st.markdown("**IM vs Other Platforms — Product Gap:**")
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("IM products", gap.get("im_products", 0))
        g2.metric("Other avg", gap.get("other_avg_products", 0))
        g3.metric("Gap %", f"{gap.get('gap_pct', 0)}%")
        sev = gap.get("severity", "—")
        g4.markdown(f'<span class="{sev_class(sev)}">{sev}</span>', unsafe_allow_html=True)
        g4.caption("Severity")

    # Pitch card
    if card.get("headline_en") or card.get("headline_hi"):
        st.markdown("**Retention pitch:**")
        if card.get("headline_en"):
            st.info(f'EN: {card["headline_en"]}')
        if card.get("headline_hi"):
            st.caption(f'HI: {card["headline_hi"]}')

        dpts = card.get("data_points") or []
        if dpts:
            st.markdown("**Data points to mention:**")
            for dp in dpts:
                st.markdown(f"  • {dp}")

        if card.get("suggested_action"):
            st.success(f"🎯 {card['suggested_action']}  ({card.get('effort_estimate','')})")

    pos = d.get("competitive_positioning")
    if pos:
        st.caption(f"Competitive positioning: `{pos}`")


def render_bl_upgrade(d):
    if not d: return
    eligible = d.get("eligible")
    if eligible:
        st.success(f"✅ Eligible — mode: `{d.get('mode','?')}`")
    else:
        st.info("Not eligible at this time")
    if d.get("reason"):
        st.caption(d["reason"])


def render_winback(d):
    if not d: return
    ws = d.get("winback_score")
    pri = d.get("priority", "—")

    # Top-line metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Winback Score", ws if ws is not None else "—")
    with c2: st.metric("Priority", pri)
    with c3:
        cool_elapsed = d.get("cool_off_elapsed")
        st.metric("Cool-off",
                  "✓ elapsed" if cool_elapsed else f"✗ {d.get('cool_off_days_remaining','?')}d left")
    with c4:
        ec = d.get("estimated_conversion_probability")
        st.metric("Est. conv.", f"{int(ec*100)}%" if ec is not None else "—")

    if ws is not None:
        st.progress(min(1.0, ws / 100.0))

    if d.get("pitch") or d.get("opening_line_hi"):
        st.info(d.get("pitch") or d.get("opening_line_hi"))

    if d.get("gifted_lead_eligible"):
        st.success("✅ Gifted lead eligible")
    if d.get("recommended_package"):
        st.caption(f"Recommended package: **{d['recommended_package']}**  |  "
                   f"Pitch type: **{d.get('winback_pitch_type','—')}**")

    # ---- Derivation dropdown ----
    sub = d.get("sub_scores") or {}
    weights = d.get("weights") or {}
    if sub and weights:
        with st.expander("📊 How the winback score was calculated", expanded=False):
            st.markdown("**Step 1 — Weighted base from 7 sub-scores:**")

            rows = []
            for key, label in [
                ("historical_quality",   "Historical Quality  (enq_30d + reply_rate)"),
                ("demand_score",         "Demand Score        (current_demand_index/100)"),
                ("recoverability_score", "Recoverability      (RCA × rca_confidence)"),
                ("paid_history_bonus",   "Paid History Bonus  (1.0 paid / 0.3 freelist)"),
                ("trajectory_factor",    "Trajectory Factor   (B>A>C)"),
                ("peer_recovery",        "Peer Recovery       (peer_delta_pct trend)"),
                ("recency_bonus",        "Recency Bonus       (post cool-off decay)"),
            ]:
                w_key = key.replace("_score", "").replace("_bonus", "").replace("_factor", "")
                # Map back to weights dict keys
                wmap = {
                    "historical_quality":   "historical_quality",
                    "demand_score":         "demand_score",
                    "recoverability_score": "recoverability",
                    "paid_history_bonus":   "paid_history",
                    "trajectory_factor":    "trajectory",
                    "peer_recovery":        "peer_recovery",
                    "recency_bonus":        "recency",
                }
                w = weights.get(wmap[key], 0.0)
                v = sub.get(key, 0.0)
                contrib = round(100 * w * v, 2)
                rows.append({
                    "Sub-score":  label,
                    "Value":      f"{v:.2f}",
                    "Weight":     f"{w*100:.0f}%",
                    "Contribution (pts)": contrib,
                })
            st.table(rows)

            ib = d.get("interaction_bonus", 1.0)
            pre = d.get("pre_llm_score", 0)
            base_sum = sum(r["Contribution (pts)"] for r in rows)
            st.markdown(f"**Step 2 — Weighted base sum:** `{base_sum:.1f} pts`")
            if ib and ib > 1.0:
                st.markdown(f"**Step 3 — Interaction bonus:** `×{ib}` "
                            f"(demand & recoverability both strong)")
            else:
                st.markdown(f"**Step 3 — Interaction bonus:** `×1.0` (no compounding)")
            st.markdown(f"**Step 4 — Pre-LLM score:** `{pre}/100`")

            if d.get("llm_used"):
                ladj = d.get("llm_adjustment", 0)
                sign = "+" if ladj >= 0 else ""
                st.markdown(f"**Step 5 — LLM second-opinion adjustment:** `{sign}{ladj}`")
                if d.get("llm_justification"):
                    st.info(f"💬 LLM: {d['llm_justification']}")
            else:
                st.markdown(f"**Step 5 — LLM second opinion:** _not run_")

            st.markdown(f"**Step 6 — Final winback score:** **{ws}/100  →  {pri}**")

            if not d.get("cool_off_elapsed") and ws is not None and ws >= 65:
                st.warning(f"⚠️ Score would be HIGH but cool-off not elapsed "
                           f"({d.get('cool_off_days_remaining',0)}d remaining) — forced to MEDIUM.")

            if not d.get("demand_provided"):
                st.caption("ℹ️ Demand index not provided — its weight was redistributed to Recoverability.")

            st.caption(
                "Tiers: ≥65 + cool-off elapsed = HIGH  |  40-64 or pre-cool-off = MEDIUM  |  <40 = LOW"
            )


def render_bl_card_skill(d):
    """When phase6_card runs, just say so — the rich render is at the top."""
    if not d: return
    verdict = d.get("header", {}).get("verdict", "—")
    pri     = d.get("header", {}).get("priority", "?")
    st.success(f"BL Card aggregated → Verdict: **{verdict}**  |  Priority: **{pri}/100**")
    st.caption("Full rendered card is at the top of this page.")


SKILL_RENDERERS = {
    "churn_scoring":              render_churn_scoring,
    "shap_rca":                   render_shap_rca,
    "llm_cohort_scorer":          render_llm_cohort,
    "peer_benchmark":             render_peer_benchmark,
    "demand_index":               render_demand_index,
    "conversion_point":           render_conversion_point,
    "onboarding_health":          render_onboarding_health,
    "pre_call_brief":             render_pre_call_brief,
    "whatsapp_message":           render_whatsapp,
    "script_generation":          render_script_generation,
    "gifted_lead":                render_gifted_lead,
    "cross_platform_intelligence": render_cross_platform,
    "bl_upgrade":                 render_bl_upgrade,
    "winback_priority":           render_winback,
    "bl_card":                    render_bl_card_skill,
}


def render_phase(phase_id, phase_data, phase_label):
    if phase_data.get("skipped"):
        st.markdown(f"### {phase_label}  <span class='skip'>(Skipped)</span>", unsafe_allow_html=True)
        st.caption(f"Reason: {phase_data.get('reason','')}")
        return

    st.markdown(f"### {phase_label}")
    for skill_name, sr in phase_data.items():
        if not isinstance(sr, dict) or "success" not in sr:
            continue
        ok = sr.get("success", False)
        conf = sr.get("confidence", 0)
        ms   = sr.get("latency_ms", 0)
        cls  = "ok" if ok else "fail"
        label = "OK" if ok else "FAIL"
        with st.container(border=True):
            st.markdown(
                f'<span class="{cls}">[{label}]</span> **`{skill_name}`** — '
                f'confidence={conf:.2f} | {ms}ms',
                unsafe_allow_html=True
            )
            if sr.get("error"):
                st.error(sr["error"])
            data = sr.get("data") or {}
            renderer = SKILL_RENDERERS.get(skill_name)
            if renderer:
                renderer(data)
            else:
                # Fallback generic render
                with st.expander("Raw output"):
                    st.json(data)


# ════════════════════════════════════════════════════════════════════════════
# BL CARD RENDERER
# ════════════════════════════════════════════════════════════════════════════
def render_bl_card(card):
    if not card:
        st.warning("BL Card not generated.")
        return

    header = card.get("header", {})
    scores = card.get("scores", {})
    rc     = card.get("root_cause", {})
    sig    = card.get("signals", {})
    ap     = card.get("action_plan", {})
    msg    = card.get("messaging", {})
    intv   = card.get("interventions", {})
    look   = card.get("lookalikes", {})
    cp     = card.get("cross_platform", {})
    onb    = card.get("onboarding", {})

    # ── Seller header banner (company + GLID badge) ──
    _company  = header.get("company", "—") or "—"
    _location = header.get("location", "—") or "—"
    _ctype    = header.get("customer_type", "—") or "—"
    _glid     = header.get("glid", "")
    _initial  = _company.strip()[:1].upper() if _company and _company != "—" else "·"
    st.markdown(
        f"""
        <div style="background:linear-gradient(90deg,#1e293b 0%,#334155 100%);
                    border-radius:12px;padding:14px 20px;margin-bottom:14px;
                    display:flex;align-items:center;gap:16px;color:#fff">
          <div style="width:48px;height:48px;border-radius:50%;background:#3b82f6;
                      color:#fff;font-weight:700;font-size:22px;
                      display:flex;align-items:center;justify-content:center">{_initial}</div>
          <div style="flex:1">
            <div style="font-size:20px;font-weight:700;line-height:1.1">{_company}</div>
            <div style="font-size:12px;color:#cbd5e1;margin-top:4px">
              GLID <code style="background:rgba(255,255,255,.1);padding:1px 6px;border-radius:4px;color:#fff">{_glid}</code>
              &nbsp;·&nbsp; {_location} &nbsp;·&nbsp; {_ctype}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    verdict = header.get("verdict", "—")
    st.markdown(f'<div class="{verdict_class(verdict)}">⚡ VERDICT: {verdict}</div>', unsafe_allow_html=True)
    st.write("")

    h1, h2, h3, h4, h5 = st.columns(5)
    h1.markdown(f"**Company:** {header.get('company','—')}")
    h1.markdown(f"**GLID:** `{header.get('glid','')}`")
    h2.markdown(f"**Location:** {header.get('location','—')}")
    h2.markdown(f"**Account age:** {header.get('account_age_days',0)}d")
    h3.markdown(f"**Customer Type:** {header.get('customer_type','—')}")
    h3.markdown(f"**RAG:** {header.get('rag','—')}")

    # IM product count — always visible, sourced from header (snapshot fallback)
    im_products_count = (
        header.get("im_product_count")
        or (cp.get("im_catalog_gap") or {}).get("im_products")
        or 0
    )
    h4.metric("🏠 IM Products", im_products_count)
    h4.caption("from IndiaMART API")

    priority = header.get("priority", 0)
    h5.markdown(f"**Priority:** `{priority}/100`")
    h5.markdown(
        f'<div class="priority-bar"><div class="priority-fill" style="width:{priority}%"></div></div>',
        unsafe_allow_html=True
    )

    st.divider()

    # Scores
    st.markdown('<div class="card-section"><div class="card-h">📊 SCORES</div>', unsafe_allow_html=True)
    s1, s2, s3, s4 = st.columns(4)
    cs       = scores.get("churn_score")
    base_cs  = scores.get("base_churn_score")
    cp_adj   = scores.get("cp_adjustment", 0)
    cp_note  = scores.get("cp_adjustment_note", "")
    with s1:
        st.markdown(f'<div class="score-big" style="color:{score_color(cs)}">{cs if cs is not None else "—"}</div>', unsafe_allow_html=True)
        st.caption("Final Churn Score / 100")
        if cp_adj and base_cs is not None:
            st.caption(f"Base: {base_cs} + Cross-platform: +{cp_adj}")
    with s2:
        st.markdown(risk_badge(scores.get("risk_tier", "—")), unsafe_allow_html=True)
        st.caption("Risk Tier")
    with s3:
        llm = scores.get("llm_risk", "—")
        st.markdown(f"**{llm}**")
        if scores.get("llm_confidence") is not None:
            st.caption(f"LLM confidence: {scores.get('llm_confidence')}/100")
    with s4:
        bands = scores.get("bands", {})
        st.markdown(f"BL: {bands.get('bl','—')}")
        st.markdown(f"LMS: {bands.get('lms','—')}")
        st.markdown(f"Activity: {bands.get('activity','—')}")
    if cp_note:
        st.info(f"🌐 Cross-platform impact: {cp_note}")

    # Churn breakdown sub-section
    cb = scores.get("churn_breakdown") or {}
    if cb.get("base_score") is not None:
        with st.expander("📊 How the churn score was calculated", expanded=False):
            st.markdown("**Step-by-step derivation:**")
            st.markdown(f"  1. **Base** (sum of per-signal penalties): `{cb['base_score']}`")
            cmult = cb.get("compound_multiplier", 1.0)
            red_count = cb.get("red_flag_count", 0)
            if cmult and cmult > 1.0:
                st.markdown(f"  2. **Compound penalty** ({red_count} Red flags): `×{cmult}` → `{round(cb['base_score'] * cmult, 1)}`")
            else:
                st.markdown(f"  2. Compound penalty: not triggered ({red_count} Red flags, need ≥3)")
            tadj = cb.get("trajectory_adjustment", 0)
            if tadj:
                st.markdown(f"  3. **Trajectory adjustment**: `{tadj:+d}` — {cb.get('trajectory_note','')}")
            else:
                st.markdown(f"  3. Trajectory adjustment: `0`")
            if cb.get("pre_llm_score") is not None:
                st.markdown(f"  4. **Pre-LLM score**: `{cb['pre_llm_score']}`")
            if cb.get("llm_used"):
                st.markdown(f"  5. **🤖 LLM second-opinion adjustment**: `{cb.get('llm_adjustment', 0):+d}`")
                if cb.get("llm_justification"):
                    st.info(f'**LLM rationale:** {cb["llm_justification"]}')
            else:
                st.markdown(f"  5. LLM second opinion: not run")
            if cp_adj:
                st.markdown(f"  6. **🌐 Cross-platform adjustment**: `+{cp_adj}` — {cp_note}")
            else:
                st.markdown(f"  6. Cross-platform adjustment: `0` (no catalog gap)")
            st.divider()
            st.markdown(f"### Final: **{cs}/100**  ({scores.get('risk_tier','—')})")
            st.caption("Tiers: ≥72 = Red, 42–71 = Amber, <42 = Green")
    st.markdown('</div>', unsafe_allow_html=True)

    # RCA + signals
    rc_col, sig_col = st.columns(2)
    with rc_col:
        st.markdown('<div class="card-section"><div class="card-h">🎯 ROOT CAUSE</div>', unsafe_allow_html=True)
        st.markdown(f"**Category:** `{rc.get('category','—')}`")
        if rc.get("confidence") is not None:
            st.caption(f"Confidence: {rc.get('confidence'):.2f}")
        st.write(rc.get("english", ""))
        st.caption(rc.get("hindi", ""))
        if rc.get("intervention"):
            st.success(f"🔧 {rc['intervention']}")
        st.markdown('</div>', unsafe_allow_html=True)
    with sig_col:
        st.markdown('<div class="card-section"><div class="card-h">📡 SIGNALS</div>', unsafe_allow_html=True)
        for r in (sig.get("churn_reasons") or [])[:5]:
            st.markdown(f"• {r}")
        st.markdown("")
        if sig.get("trajectory"):
            st.markdown(f"**Trajectory:** {sig['trajectory']}")
        if sig.get("demand_tier"):
            st.markdown(f"**Demand:** {sig['demand_tier']} (idx={sig.get('demand_index','—')})")
        if sig.get("peer_comparison"):
            st.markdown(f"**Peers:** {sig['peer_comparison']}")
        st.markdown('</div>', unsafe_allow_html=True)

    # Onboarding (if ran)
    if onb.get("ran"):
        st.markdown('<div class="card-section"><div class="card-h">🌱 ONBOARDING HEALTH (new seller)</div>', unsafe_allow_html=True)
        o1, o2, o3 = st.columns([1, 1, 2])
        o1.metric("Health Score", onb.get("health_score", "—"))
        o2.markdown(risk_badge(onb.get("health_tier", "—")), unsafe_allow_html=True)
        o3.markdown(f"**Trigger:** `{onb.get('trigger_action','—')}`")

        checks = onb.get("checks") or {}
        if checks:
            st.markdown(f"**{len(checks)}-check breakdown:**")
            for cname, cdata in checks.items():
                st.markdown(
                    f"{tier_badge(cdata.get('tier','—'))} "
                    f"**{cname.replace('_',' ').title()}** "
                    f"({cdata.get('score',0)}/100): {cdata.get('note','')}"
                )

        # Risk priors
        priors = onb.get("risk_priors") or []
        if priors:
            st.markdown("**Risk priors applied:**")
            for p in priors:
                st.markdown(f"  ⚠️ −{p.get('penalty')} pts: {p.get('note')}")

        # Activation plan summary
        plan = onb.get("activation_plan") or {}
        if plan and plan.get("tasks"):
            st.markdown(f"**Activation plan ({onb.get('plan_method','template')}):**")
            if plan.get("opening_pitch_hi"):
                st.info(f"_{plan['opening_pitch_hi']}_")
            for i, t in enumerate(plan["tasks"][:5], 1):
                st.markdown(
                    f"  {i}. **{t.get('title','—')}** "
                    f"(`{t.get('priority','medium')}`, ~{t.get('effort_min','?')} min)"
                )
        st.markdown('</div>', unsafe_allow_html=True)

    # Cross-platform
    if cp.get("platforms_found") or cp.get("platform_data"):
        st.markdown('<div class="card-section"><div class="card-h">🌐 CROSS-PLATFORM INTELLIGENCE (Playwright)</div>', unsafe_allow_html=True)

        pdata = cp.get("platform_data") or {}
        gap   = cp.get("im_catalog_gap") or {}
        im_count = header.get("im_product_count") or gap.get("im_products", 0)

        # All 4 known competitor platforms — show as pills (found/missed)
        all_known = ["justdial", "tradeindia", "own_website", "shopify"]
        pill_html = ""
        for p in all_known:
            det = pdata.get(p) or {}
            if det.get("found"):
                pill_html += f'<span class="platform-pill-found">✓ {p.title().replace("_"," ")}</span>'
            else:
                pill_html += f'<span class="platform-pill-miss">— {p.title().replace("_"," ")}</span>'
        st.markdown("**Platforms scanned:** " + pill_html, unsafe_allow_html=True)
        st.write("")

        # Per-platform cards — IM first, then each found competitor (incl. own_website)
        found_platforms = [(p, pdata.get(p) or {}) for p in all_known if (pdata.get(p) or {}).get("found")]
        # Include any extra platforms that aren't in our known list (future-proof)
        for p, det in pdata.items():
            if p not in all_known and det.get("found"):
                found_platforms.append((p, det))

        all_cards = [("IndiaMART", {"product_count": im_count, "is_im": True})] + found_platforms
        cols = st.columns(len(all_cards))
        for i, (pname, pd_) in enumerate(all_cards):
            with cols[i]:
                is_im = pd_.get("is_im", False)
                if is_im:
                    label = "🏠 IndiaMART (this seller)"
                elif pname == "own_website":
                    label = f"🌐 {pd_.get('domain', 'Own Website')}"
                else:
                    label = pname.title().replace("_", " ")
                st.markdown(f"**{label}**")
                pc = pd_.get("product_count", 0)
                st.metric("Products", pc if pc > 0 else "—")
                if not is_im:
                    if pd_.get("rating", 0):
                        st.caption(f"⭐ {pd_['rating']}/5  |  {pd_.get('reviews', 0)} reviews")
                    if pd_.get("url"):
                        st.caption(f"[View profile]({pd_['url']})")

        gap = cp.get("im_catalog_gap", {})
        if gap:
            st.markdown("**IM vs Others — Catalog Gap:**")
            g1, g2, g3, g4 = st.columns(4)
            g1.metric("IM products", gap.get("im_products", 0))
            combo = gap.get("other_combination", "")
            other_label = {
                "sum_distinct":          "Other total (Σ)",
                "max_overlap":           "Other (max)",
                "single":                "Other",
                "name_dedupe_overlap":   "Other (name-dedup ◇)",
                "name_dedupe_distinct":  "Other (name-distinct)",
                "name_dedupe":           "Other (name-dedup)",
            }.get(combo, "Other total")
            g2.metric(other_label, gap.get("other_total_products", gap.get("other_avg_products", 0)))
            g3.metric("Gap %", f"{gap.get('gap_pct', 0)}%")
            sev = gap.get("severity", "—")
            g4.markdown(f'<span class="{sev_class(sev)}">{sev}</span>', unsafe_allow_html=True)
            g4.caption("Severity")

            match_method = gap.get("match_method", "counts")
            if match_method == "names":
                st.caption(
                    f"🔬 **Robust match:** product names matched across platforms "
                    f"(unique={gap.get('unique_via_names', 0)}, "
                    f"max raw count={gap.get('other_max_products', 0)})"
                )
                overlap_pairs = gap.get("overlap_pairs") or []
                if overlap_pairs:
                    pair_lines = [
                        f"  • {pp['platforms'][0]} ↔ {pp['platforms'][1]}: {pp['shared']} shared products"
                        for pp in overlap_pairs
                    ]
                    with st.expander("🔗 Cross-platform overlap detail", expanded=False):
                        for ln in pair_lines:
                            st.markdown(ln)
                        per_plat = gap.get("per_platform_unique") or {}
                        if per_plat:
                            st.markdown("**Platform-exclusive products (not on others):**")
                            for p, n in per_plat.items():
                                if n > 0:
                                    st.markdown(f"  • `{p}`: {n} unique")
                        ts = gap.get("titles_sampled") or {}
                        if ts:
                            st.markdown("**Sample scraped titles:**")
                            for p, titles in ts.items():
                                if titles:
                                    st.markdown(f"_{p}:_ " + ", ".join(f"`{t}`" for t in titles[:6]))
            else:
                st.caption(f"ℹ️ Combined via count heuristic ({combo}) — no product titles scraped")

        if cp.get("headline_en"):
            st.info(f"**Pitch (EN):** {cp['headline_en']}")
        if cp.get("headline_hi"):
            st.caption(f"Pitch (HI): {cp['headline_hi']}")
        if cp.get("data_points"):
            for dp in cp["data_points"][:4]:
                st.markdown(f"  • {dp}")
        if cp.get("suggested_action"):
            st.success(f"🎯 {cp['suggested_action']}")
        st.markdown('</div>', unsafe_allow_html=True)

    # Action plan
    st.markdown('<div class="card-section"><div class="card-h">🎬 ACTION PLAN</div>', unsafe_allow_html=True)
    if ap.get("opening_en"):
        st.markdown(f"**Opening (EN):** _{ap['opening_en']}_")
    if ap.get("opening_hi"):
        st.caption(f"Opening (HI): {ap['opening_hi']}")
    actions = ap.get("suggested_actions") or []
    if actions:
        st.markdown("**Suggested actions:**")
        for a in actions:
            st.markdown(f"  ✓ {a}")
    if ap.get("do_not_mention"):
        st.warning("**Do not mention:** " + ", ".join(ap["do_not_mention"]))
    st.markdown('</div>', unsafe_allow_html=True)

    # Messaging
    st.markdown('<div class="card-section"><div class="card-h">💬 MESSAGING</div>', unsafe_allow_html=True)
    tab_script, tab_wa = st.tabs(["📞 Call Script", "💚 WhatsApp"])
    with tab_script:
        sub_hi, sub_en = st.tabs(["Hindi", "English"])
        steps = ["opening", "diagnostic", "value_demo", "action", "close"]
        with sub_hi:
            for i, s in enumerate(steps, 1):
                v = msg.get("call_script_hi", {}).get(s, "—")
                st.markdown(f"**{i}. {s.replace('_',' ').title()}**")
                st.markdown(f"> {v}")
        with sub_en:
            for i, s in enumerate(steps, 1):
                v = msg.get("call_script_en", {}).get(s, "—")
                st.markdown(f"**{i}. {s.replace('_',' ').title()}**")
                st.markdown(f"> {v}")
    with tab_wa:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Hindi**")
            st.markdown(f'<div class="phone-msg">{msg.get("whatsapp_hi","—")}</div>', unsafe_allow_html=True)
        with c2:
            st.markdown("**English**")
            st.markdown(f'<div class="phone-msg">{msg.get("whatsapp_en","—")}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Interventions
    st.markdown('<div class="card-section"><div class="card-h">🔄 INTERVENTIONS</div>', unsafe_allow_html=True)
    i1, i2 = st.columns(2)
    with i1:
        st.markdown("**BL Upgrade**")
        if intv.get("bl_upgrade_eligible"):
            st.success(f"Eligible ({intv.get('bl_upgrade_reason','')})")
        else:
            st.info(f"Not eligible — {intv.get('bl_upgrade_reason','')}")
    with i2:
        st.markdown("**Winback**")
        ws = intv.get("winback_score")
        if ws is not None:
            wpri = intv.get("winback_priority") or "—"
            st.markdown(f"Score: `{ws}/100`  |  Priority: **{wpri}**")
            if intv.get("winback_pitch"):
                st.caption(intv["winback_pitch"])

            wsub = intv.get("winback_sub_scores") or {}
            wwts = intv.get("winback_weights") or {}
            if wsub and wwts:
                with st.expander("📊 How the winback score was calculated", expanded=False):
                    wmap = {
                        "historical_quality":   ("Historical Quality",   "historical_quality"),
                        "demand_score":         ("Demand Score",         "demand_score"),
                        "recoverability_score": ("Recoverability",       "recoverability"),
                        "paid_history_bonus":   ("Paid History Bonus",   "paid_history"),
                        "trajectory_factor":    ("Trajectory Factor",    "trajectory"),
                        "peer_recovery":        ("Peer Recovery",        "peer_recovery"),
                        "recency_bonus":        ("Recency Bonus",        "recency"),
                    }
                    rows = []
                    base_sum = 0.0
                    for k, (label, wkey) in wmap.items():
                        v = float(wsub.get(k, 0) or 0)
                        w = float(wwts.get(wkey, 0) or 0)
                        contrib = round(100 * v * w, 2)
                        base_sum += contrib
                        rows.append({
                            "Sub-score":  label,
                            "Value":      f"{v:.2f}",
                            "Weight":     f"{w*100:.0f}%",
                            "Contribution (pts)": contrib,
                        })
                    st.markdown("**Step 1 — Weighted base from 7 sub-scores:**")
                    st.table(rows)

                    ib = intv.get("winback_interaction_bonus", 1.0) or 1.0
                    pre = intv.get("winback_pre_llm", 0)
                    st.markdown(f"**Step 2 — Weighted base sum:** `{base_sum:.1f} pts`")
                    if ib > 1.0:
                        st.markdown(f"**Step 3 — Interaction bonus:** `×{ib}`  "
                                    f"(demand & recoverability both strong)")
                    else:
                        st.markdown("**Step 3 — Interaction bonus:** `×1.0`  (no compounding)")
                    st.markdown(f"**Step 4 — Pre-LLM score:** `{pre}/100`")

                    if intv.get("winback_llm_used"):
                        ladj = intv.get("winback_llm_adjustment", 0) or 0
                        sign = "+" if ladj >= 0 else ""
                        st.markdown(f"**Step 5 — LLM second-opinion adjustment:** `{sign}{ladj}`")
                        just = intv.get("winback_llm_justification")
                        if just:
                            st.info(f"💬 LLM: {just}")
                    else:
                        st.markdown("**Step 5 — LLM second opinion:** _not run_")

                    st.markdown(f"**Step 6 — Final winback score:** **{ws}/100  →  {wpri}**")

                    coe = intv.get("winback_cool_off_elapsed")
                    cdr = intv.get("winback_cool_off_days_remaining")
                    if coe is False and ws >= 65:
                        st.warning(f"⚠️ Score ≥65 but cool-off not elapsed "
                                   f"({cdr}d remaining) — tier forced to MEDIUM.")
                    if intv.get("winback_demand_provided") is False:
                        st.caption("ℹ️ Demand index not provided — weight redistributed to Recoverability.")
                    st.caption("Tiers: ≥65 + cool-off elapsed = HIGH  |  40-64 = MEDIUM  |  <40 = LOW")
        else:
            st.info("Not applicable (only Red risk)")
    st.markdown('</div>', unsafe_allow_html=True)

    # Lookalikes
    if look.get("churned") or look.get("retained"):
        st.markdown('<div class="card-section"><div class="card-h">👥 LOOKALIKES</div>', unsafe_allow_html=True)
        l1, l2 = st.columns(2)
        with l1:
            st.markdown("**Churned (similar):**")
            for g in look.get("churned", [])[:5]:
                st.markdown(f'<span class="metric-pill" style="background:#fee2e2;color:#991b1b">GLID {g}</span>', unsafe_allow_html=True)
        with l2:
            st.markdown("**Retained (similar):**")
            for g in look.get("retained", [])[:5]:
                st.markdown(f'<span class="metric-pill" style="background:#d1fae5;color:#065f46">GLID {g}</span>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    if card.get("summary_text"):
        with st.expander("📋 Plain-text BL Card (copy/paste to CRM)"):
            st.code(card["summary_text"], language=None)


# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR — page switcher
# ════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("Churn Suite")
    page = st.radio(
        "Mode",
        ["🔬 Pipeline Analysis", "📞 Post-Call Summary"],
        label_visibility="collapsed",
    )
    st.divider()


# ════════════════════════════════════════════════════════════════════════════
# PAGE 1 — Pipeline Analysis
# ════════════════════════════════════════════════════════════════════════════
if page == "🔬 Pipeline Analysis":
    st.title("Seller Churn Analysis")
    st.caption("MD-driven skills pipeline • SkillLoader + PipelineRunner • BL Card aggregator")

    with st.sidebar:
        st.header("Run Pipeline")
        glid = st.number_input("GLID", min_value=1, value=11282573, step=1)
        no_llm = st.checkbox("Skip LLM (faster)", value=False)
        run_btn = st.button("Run Analysis", type="primary", use_container_width=True)
        st.divider()
        st.caption("Phases (from `skills/pipeline.md`):")
        for p in [
            "0. Benchmarks (Peer + Demand + Trajectory)",
            "1. Onboarding Health",
            "2. Churn Scoring + RCA",
            "2b. LLM Cohort Scoring",
            "3. Action Skills",
            "3c. **Cross-Platform (Playwright)**",
            "4. BL Upgrade",
            "5. Winback Priority",
            "6. **BL Card (aggregated)**",
        ]:
            st.markdown(f"- {p}")

    if run_btn:
        with st.spinner(f"Running pipeline for GLID {glid}... (may take 20-30s if Playwright runs)"):
            try:
                from churn_analysis.pipeline_runner import PipelineRunner
                runner = PipelineRunner(os.path.join(_ROOT, "skills"))
                result = runner.run_seller(int(glid), no_llm=no_llm, verbose=False)
            except Exception as exc:
                st.error(f"Pipeline error: {exc}")
                import traceback
                st.code(traceback.format_exc())
                st.stop()

        ctx    = result.get("context", {})
        phases = result.get("phases", {})

        st.divider()
        st.subheader(f"📦 {ctx.get('company', f'GLID {glid}')} (GLID {glid})")
        st.caption(
            f"{ctx.get('city','')}, {ctx.get('state','')} | "
            f"{ctx.get('custtype','')} | Age: {ctx.get('account_age_days',0)}d | "
            f"RAG: {ctx.get('rag_category','—')} | Run: {result.get('run_at','')[:19]}"
        )

        # ── BL Card (top) ────────────────────────────────────────────────────
        st.markdown("## 💼 BL CARD — Aggregated Briefing")
        bl_card_data = phases.get("phase6_card", {}).get("bl_card", {}).get("data", {})
        render_bl_card(bl_card_data)

        st.divider()

        # ── Phase details ────────────────────────────────────────────────────
        st.markdown("## 🔬 Full Phase-by-Phase Analysis")
        phase_map = [
            ("phase0_benchmark",        "Phase 0 — Benchmarks (Peer + Demand + Trajectory)"),
            ("phase1_onboarding",       "Phase 1 — Onboarding Health"),
            ("phase2_churn",            "Phase 2 — Churn Scoring + RCA"),
            ("phase2_llm",              "Phase 2b — LLM Cohort Scoring"),
            ("phase3_actions",          "Phase 3 — Action Skills"),
            ("phase3c_cross_platform",  "Phase 3c — Cross-Platform Intelligence (Playwright)"),
            ("phase4",                  "Phase 4 — BL Upgrade"),
            ("phase5",                  "Phase 5 — Winback Priority"),
            ("phase6_card",             "Phase 6 — BL Card (Aggregator)"),
        ]
        for pid, label in phase_map:
            pdata = phases.get(pid, {})
            with st.expander(label, expanded=False):
                render_phase(pid, pdata, label)

        st.divider()

        # ── Summary ──────────────────────────────────────────────────────────
        st.markdown("## 📈 Run Summary")
        summary_rows = []
        for pid, label in phase_map:
            pdata = phases.get(pid, {})
            if pdata.get("skipped"):
                summary_rows.append({"Phase": label, "Status": "Skipped",
                                     "Skills": 0, "OK": 0, "FAIL": 0, "Latency (ms)": 0})
                continue
            ok = sum(1 for v in pdata.values() if isinstance(v, dict) and v.get("success"))
            fail = sum(1 for v in pdata.values() if isinstance(v, dict) and v.get("success") is False)
            total_ms = sum(v.get("latency_ms", 0) for v in pdata.values() if isinstance(v, dict))
            summary_rows.append({
                "Phase": label, "Status": "Ran",
                "Skills": ok + fail, "OK": ok, "FAIL": fail,
                "Latency (ms)": total_ms,
            })
        st.dataframe(summary_rows, use_container_width=True, hide_index=True)

        total_skills = sum(r["Skills"] for r in summary_rows)
        total_ok     = sum(r["OK"]     for r in summary_rows)
        total_fail   = sum(r["FAIL"]   for r in summary_rows)
        total_ms     = sum(r["Latency (ms)"] for r in summary_rows)
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Total skills", total_skills)
        t2.metric("OK", total_ok)
        t3.metric("FAIL", total_fail)
        t4.metric("Total latency", f"{total_ms} ms")

        with st.expander("🗂️ Raw pipeline JSON"):
            st.json(result)
        st.download_button(
            "⬇️ Download full JSON",
            data=json.dumps(result, indent=2, default=str, ensure_ascii=False),
            file_name=f"churn_analysis_{glid}.json",
            mime="application/json",
        )

    else:
        st.info("👉 Enter a GLID in the sidebar and click **Run Analysis**.")
        st.markdown("""
        ### What this shows
        1. **BL Card** — Verdict, scores, RCA, action plan, messaging, interventions, lookalikes, **cross-platform intelligence**, onboarding health (when applicable)
        2. **Phase-by-Phase Analysis** — Each skill renders with its own tailored panel:
           - Churn scoring → score breakdown + severity-colored signals
           - LLM cohort → reasoning + churned/retained lookalikes
           - Conversion point → **trajectory badge + sparkline chart**
           - Peer benchmark, Demand index, Onboarding health → dedicated panels
           - **Cross-Platform (Playwright)** → per-platform cards (JustDial / TradeIndia / OwnSite), gap analysis, retention pitch
           - WhatsApp → phone-style mockup, Call Script → 5-step tabs
        3. **Run Summary** — Status table of all phases
        4. **Raw JSON** — Downloadable
        """)


# ════════════════════════════════════════════════════════════════════════════
# PAGE 2 — Post-Call Summary
# ════════════════════════════════════════════════════════════════════════════
else:
    st.title("📞 Post-Call Summary")
    st.caption("Paste a call transcript → get sentiment, updated RCA, next action via `call_summary` skill")

    with st.sidebar:
        st.header("Post-Call Input")
        pcs_glid = st.number_input("GLID", min_value=1, value=11282573, step=1, key="pcs_glid")
        pcs_call_type = st.selectbox(
            "Call type",
            ["RETENTION", "RENEWAL", "WELCOME", "WINBACK", "ONBOARDING"],
        )
        pcs_pre_rca = st.selectbox(
            "Pre-call RCA",
            ["UNKNOWN", "NO_LEADS", "LOW_ENGAGEMENT", "POOR_CATALOG",
             "LOW_PNS_RESPONSE", "PEER_GAP", "RAG_RISK", "BL_DECLINE"],
        )
        pcs_seller_name = st.text_input("Seller name (optional)", value="")

    transcript = st.text_area(
        "Call transcript",
        height=280,
        placeholder="Paste the full call transcript here...",
    )
    pcs_run = st.button("Analyze Call", type="primary")

    if pcs_run:
        if not transcript.strip():
            st.error("Please paste a transcript first.")
            st.stop()

        with st.spinner("Analyzing call transcript..."):
            try:
                from churn_analysis.skills.registry import registry
                sr = registry.run("call_summary", {
                    "glid":          pcs_glid,
                    "transcript":    transcript,
                    "call_type":     pcs_call_type,
                    "pre_call_rca":  pcs_pre_rca,
                    "seller_name":   pcs_seller_name or "Seller",
                })
            except Exception as exc:
                st.error(f"Skill error: {exc}")
                import traceback
                st.code(traceback.format_exc())
                st.stop()

        if not sr.success:
            st.error(f"Failed: {sr.error}")
            st.stop()

        d = sr.data or {}
        st.divider()

        c1, c2, c3, c4 = st.columns(4)
        sentiment = d.get("sentiment", "—")
        sent_color = {"positive": "🟢", "neutral": "🟡", "negative": "🔴"}.get(sentiment, "⚪")
        c1.metric("Sentiment", f"{sent_color} {sentiment}")
        c2.metric("Updated RCA", d.get("updated_rca", "—"))
        c3.metric("Outcome", d.get("call_outcome", "—"))
        risk_upd = d.get("churn_risk_updated", "—")
        c4.markdown(risk_badge(risk_upd), unsafe_allow_html=True)
        c4.caption("Updated risk")

        st.divider()

        st.markdown("### 📝 3-Line Summary")
        for line in d.get("summary_lines", []):
            st.markdown(f"- {line}")

        if d.get("stated_concern"):
            st.markdown("### 🗣️ Seller's stated concern")
            st.info(d["stated_concern"])

        st.markdown("### ➡️ Next Action")
        na  = d.get("next_action", "—")
        nad = d.get("next_action_detail", "")
        st.success(f"**{na}** — {nad}")

        with st.expander("Raw skill output"):
            st.json(d)

    else:
        st.info("👉 Paste a transcript on the left and click **Analyze Call**.")
        st.markdown("""
        The `call_summary` skill uses an LLM to extract:
        - 3-line summary
        - Sentiment (positive / neutral / negative)
        - Updated RCA category (may differ from pre-call)
        - Stated concern in 1 sentence
        - Next action (FOLLOW_UP_48H / FOLLOW_UP_7D / ESCALATE / MONITOR / NO_ACTION)
        - Call outcome (ENGAGED / NOT_INTERESTED / CALLBACK_REQUESTED / etc.)
        - Updated churn risk tier
        """)
