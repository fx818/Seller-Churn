"""SKILL 1 — ChurnScoringSkill: 14-signal weighted churn score 0-100.

v2.0 upgrades:
  1. **Data-aware** — uses `flow.trajectory_type` from conversion_point:
       TYPE_A (Sudden Cliff)      → +6 urgency bonus
       TYPE_B (Gradual Drift)     → +0
       TYPE_C (Never Engaged)     → resets baseline (different intervention)
  2. **Weighted normalization** — each signal scales by severity (not binary):
       reply_rate at 5% gets more pts than reply_rate at 35%
  3. **Compound penalty** — 3+ Red-severity flags → ×1.15 multiplier
  4. **LLM second opinion** — passes signals to LLM for sanity check (opt-in via
       LLM_API_KEY). LLM can adjust ±10 pts with justification.

Cross-platform adjustment happens in bl_card (cross_platform runs after churn_scoring).
"""
import json
import os
import re

import requests as _requests

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"), override=True)
except Exception:
    pass

from churn_analysis.skills.base_skill import Skill, SkillResult


RED_THRESHOLD   = 72
AMBER_THRESHOLD = 42


# ── LLM helpers ──────────────────────────────────────────────────────────────

_LLM_SYSTEM_REVIEW = (
    "You are an expert IndiaMART churn analyst. Given a seller's 14 behavioral signals "
    "and a deterministic churn score, give a calibrated second opinion. You can adjust "
    "the score by ±10 points based on signal interactions the rule-based model may have "
    "missed (e.g., compound effects, recency, severity nuances). Return STRICT JSON only."
)

_LLM_USER_REVIEW_TEMPLATE = """\
SELLER SIGNALS
--------------
Reply rate (30d):    {reply_rate}%  (BLs received: {enq_30}, replied: {replied_30})
Active days (30d):   {active_days}
Enquiry flow:        {enq_30} BLs in 30d
BL velocity (MoM):   {bl_velocity}%
PNS answer rate:     {pns}%
CQS:                 {cqs}
RAG category:        {rag}
Hotleads:            {hotleads}
Clickstream events:  {events}

Trajectory:          {trajectory_type} — {trajectory_label}

RULE-BASED CHURN SCORE
----------------------
Base score (rule sum): {base_score}/100
Compound multiplier:   {compound_multiplier}
Trajectory adjustment: {trajectory_adjustment:+d}
Pre-LLM score:         {pre_llm_score}/100  ({pre_llm_risk})

Top reasons:
{reasons_block}

INSTRUCTIONS
------------
1. Review the signals. Are there interactions the rule-based score missed?
2. Decide on an adjustment in range [-10, +10]:
   - Positive (riskier than score suggests) if you see compounding signals
   - Negative (less risky) if individual flags don't reinforce each other
3. Provide a short justification (1-2 sentences).

Return STRICT JSON:
{{
  "adjustment": 0,
  "justification": "...",
  "key_interactions": ["short list of signal interactions you noticed"]
}}
"""


def _call_llm(system: str, user: str, model: str, timeout: int = 30) -> str:
    base    = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        raise RuntimeError("LLM_API_KEY not set")
    url = f"{base}/chat/completions"
    resp = _requests.post(
        url,
        json={
            "model":       model,
            "max_tokens":  500,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        },
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _parse_llm_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        fixed = re.sub(r",\s*([}\]])", r"\1", text)
        return json.loads(fixed)


# ── Skill ────────────────────────────────────────────────────────────────────

class ChurnScoringSkill(Skill):
    name = "churn-scoring"
    version = "2.0"
    required_inputs = ["glid"]
    optional_inputs = [
        "enq_30d", "replied_30d", "active_days_30d", "bl_velocity_pct",
        "pns_success_pct", "rag", "cqs", "hotleads_count", "event_count",
        # Trajectory (from Phase 0 conversion_point)
        "trajectory_type", "trajectory_label", "cliff_drop_pct",
        # LLM controls
        "model", "force_no_llm",
    ]

    def invoke(self, inputs: dict) -> SkillResult:
        reasons: list[str] = []
        tags: list[str] = []
        breakdown: dict[str, int] = {}
        red_flags: list[str] = []   # severity Red — used for compound penalty

        def add(points: int, tag: str, reason: str, key: str, severity: str = "amber"):
            tags.append(tag)
            reasons.append(reason)
            breakdown[key] = breakdown.get(key, 0) + points
            if severity == "red":
                red_flags.append(tag)

        enq_30     = inputs.get("enq_30d") or 0
        replied_30 = inputs.get("replied_30d") or 0
        active_30  = inputs.get("active_days_30d") or 0
        bl_vel     = inputs.get("bl_velocity_pct")
        pns_pct    = inputs.get("pns_success_pct")
        rag        = (inputs.get("rag") or "").strip()
        cqs        = inputs.get("cqs")
        hotleads   = inputs.get("hotleads_count")
        events     = inputs.get("event_count") or 0
        traj_type  = (inputs.get("trajectory_type") or "").upper()
        traj_label = inputs.get("trajectory_label") or ""
        cliff_drop = inputs.get("cliff_drop_pct")

        # ── 1. Reply rate — weighted by severity ─────────────────────────────
        reply_rate = round(replied_30 / enq_30 * 100, 1) if enq_30 > 0 else 0
        if enq_30 > 0:
            if reply_rate == 0:
                add(18, "ZERO_REPLY_RATE", f"Zero reply rate ({enq_30} BLs unanswered)", "reply_rate", "red")
            elif reply_rate < 15:
                add(14, "CRITICAL_REPLY_RATE", f"Critical reply rate: {reply_rate}%", "reply_rate", "red")
            elif reply_rate < 40:
                add(8, "LOW_REPLY_RATE", f"Low reply rate: {reply_rate}% (threshold 40%)", "reply_rate")

        # ── 2. Active days — weighted ────────────────────────────────────────
        if active_30 == 0:
            add(14, "ZERO_ACTIVE_DAYS", "Zero LMS active days in last 30d", "active_days", "red")
        elif active_30 <= 3:
            add(8, "LOW_ACTIVE_DAYS", f"Only {active_30} active days in last 30d", "active_days")
        elif active_30 <= 7:
            add(4, "INFREQUENT_ACTIVE", f"Only {active_30} active days in last 30d", "active_days")

        # ── 3. Enquiry flow ──────────────────────────────────────────────────
        if enq_30 == 0:
            add(10, "NO_ENQUIRY_FLOW", "Zero enquiries in last 30d — no lead flow", "enq", "red")
        elif enq_30 < 3:
            add(4, "LOW_ENQUIRY_FLOW", f"Only {enq_30} enquiries in 30d", "enq")

        # ── 4. BL velocity — weighted by drop severity ───────────────────────
        if bl_vel is not None:
            if bl_vel <= -50:
                add(18, "BL_VELOCITY_CATASTROPHIC", f"BL velocity collapse: {bl_vel}% MoM", "bl_velocity", "red")
            elif bl_vel <= -30:
                add(14, "BL_VELOCITY_CRITICAL", f"BL velocity drop: {bl_vel}% MoM (critical)", "bl_velocity", "red")
            elif bl_vel <= -10:
                add(7, "BL_VELOCITY_DECLINING", f"BL velocity declining: {bl_vel}% MoM", "bl_velocity")
            elif bl_vel <= 0:
                add(2, "BL_VELOCITY_FLAT", f"BL velocity flat/slow decline: {bl_vel}% MoM", "bl_velocity")

        # ── 5. PNS answer rate — weighted ────────────────────────────────────
        if pns_pct is not None:
            if pns_pct < 30:
                add(10, "CRITICAL_PNS_RATE", f"Critical PNS rate {pns_pct}% — buyers can't reach seller", "pns", "red")
            elif pns_pct < 60:
                add(6, "LOW_PNS_RATE", f"PNS answer rate {pns_pct}% — below 60%", "pns")

        # ── 6. RAG — categorical ─────────────────────────────────────────────
        if rag == "Red":
            add(15, "RAG_RED", "RAG category: Red — highest churn risk tier", "rag", "red")
        elif rag == "Amber":
            add(8, "RAG_AMBER", "RAG category: Amber — moderate churn risk", "rag")

        # ── 7. CQS — weighted ────────────────────────────────────────────────
        if cqs is not None:
            if cqs < 40:
                add(13, "CRITICAL_CQS", f"CQS: {cqs} — critical, buyers won't find seller", "cqs", "red")
            elif cqs < 60:
                add(8, "LOW_CQS_CRITICAL", f"CQS: {cqs} — below 60, poor visibility", "cqs")
            elif cqs < 75:
                add(3, "LOW_CQS_MODERATE", f"CQS: {cqs} — below 75, room for improvement", "cqs")

        # ── 8. Hotleads ──────────────────────────────────────────────────────
        if hotleads is not None and hotleads == 0:
            add(4, "NO_HOTLEAD", "No hotlead activity — no engagement events", "hotleads")

        # ── 9. Clickstream events — weighted ─────────────────────────────────
        if events == 0:
            add(8, "NO_PLATFORM_ACTIVITY", "Zero clickstream events — no platform activity", "activity", "red")
        elif events < 10:
            add(3, "LOW_PLATFORM_ACTIVITY", f"Only {events} clickstream events — very low activity", "activity")

        # ── Base score (sum of all penalties) ────────────────────────────────
        base_score = sum(breakdown.values())

        # ── Compound penalty: kicks in only when 4+ Red flags interact ───────
        if len(red_flags) >= 6:
            compound_multiplier = 1.15
        elif len(red_flags) >= 4:
            compound_multiplier = 1.08
        else:
            compound_multiplier = 1.0

        compounded = base_score * compound_multiplier

        # ── Trajectory adjustment (data-aware) ───────────────────────────────
        trajectory_adjustment = 0
        trajectory_note = ""
        if traj_type == "TYPE_A":
            # Sudden cliff — heightened urgency
            trajectory_adjustment = 5 if (cliff_drop and cliff_drop <= -50) else 3
            trajectory_note = f"TYPE_A Sudden Cliff (drop {cliff_drop}%) → +{trajectory_adjustment} urgency"
            if "TYPE_A_SUDDEN_CLIFF" not in tags:
                tags.append("TYPE_A_SUDDEN_CLIFF")
            reasons.append(f"Trajectory: sudden cliff (last few months) — emergency intervention window")
        elif traj_type == "TYPE_C":
            # Never engaged — reset baseline (different intervention; not high score, but Red flag)
            # We cap the score for these so the system routes to onboarding rather than retention.
            trajectory_adjustment = 0
            trajectory_note = "TYPE_C Never Engaged → score retained; route to onboarding reset"
            if "TYPE_C_NEVER_ENGAGED" not in tags:
                tags.append("TYPE_C_NEVER_ENGAGED")
        elif traj_type == "TYPE_B":
            trajectory_adjustment = 1
            trajectory_note = "TYPE_B Gradual Drift → +1 (proactive window)"
            if "TYPE_B_GRADUAL_DRIFT" not in tags:
                tags.append("TYPE_B_GRADUAL_DRIFT")

        pre_llm_score = round(min(100, compounded + trajectory_adjustment))
        pre_llm_risk  = "Red" if pre_llm_score >= RED_THRESHOLD else ("Amber" if pre_llm_score >= AMBER_THRESHOLD else "Green")

        # ── LLM second opinion (opt-out via force_no_llm=True) ───────────────
        llm_adjustment    = 0
        llm_justification = ""
        llm_interactions  = []
        llm_error         = None
        llm_used          = False

        force_no_llm = bool(inputs.get("force_no_llm"))
        if not force_no_llm and os.getenv("LLM_API_KEY"):
            try:
                model = inputs.get("model") or os.getenv("LLM_MODEL", "gpt-4o-mini")
                reasons_block = "\n".join(f"  - {r}" for r in reasons[:8]) or "  (none)"
                user_prompt = _LLM_USER_REVIEW_TEMPLATE.format(
                    reply_rate=reply_rate, enq_30=enq_30, replied_30=replied_30,
                    active_days=active_30, bl_velocity=bl_vel if bl_vel is not None else "—",
                    pns=pns_pct if pns_pct is not None else "—",
                    cqs=cqs if cqs is not None else "—",
                    rag=rag or "—",
                    hotleads=hotleads if hotleads is not None else "—",
                    events=events,
                    trajectory_type=traj_type or "UNKNOWN",
                    trajectory_label=traj_label or "—",
                    base_score=round(base_score, 1),
                    compound_multiplier=compound_multiplier,
                    trajectory_adjustment=trajectory_adjustment,
                    pre_llm_score=pre_llm_score,
                    pre_llm_risk=pre_llm_risk,
                    reasons_block=reasons_block,
                )
                raw    = _call_llm(_LLM_SYSTEM_REVIEW, user_prompt, model)
                parsed = _parse_llm_json(raw)
                adj = parsed.get("adjustment", 0)
                if isinstance(adj, (int, float)):
                    llm_adjustment = max(-10, min(10, int(adj)))
                    llm_justification = parsed.get("justification", "")
                    llm_interactions  = parsed.get("key_interactions") or []
                    llm_used = True
            except Exception as exc:
                llm_error = str(exc)[:200]

        # ── Final score ──────────────────────────────────────────────────────
        final_score = max(0, min(100, pre_llm_score + llm_adjustment))
        risk = "Red" if final_score >= RED_THRESHOLD else ("Amber" if final_score >= AMBER_THRESHOLD else "Green")

        # ── Confidence ───────────────────────────────────────────────────────
        signals_available = sum(
            1 for v in [enq_30, replied_30, active_30, bl_vel, rag, cqs, events]
            if v is not None and v != 0  # truthy signals
        )
        # account for trajectory + LLM data
        if traj_type:
            signals_available += 1
        if llm_used:
            signals_available += 1
        base_conf = 1.0 if signals_available >= 5 else max(0.2, signals_available / 7)
        confidence = min(1.0, base_conf + (0.05 if llm_used else 0))

        return SkillResult(
            success=True,
            data={
                "churn_score":          final_score,
                "risk":                 risk,
                "churn_reasons":        reasons,
                "reason_tags":          tags,
                "score_breakdown":      breakdown,
                "red_flag_count":       len(red_flags),
                "red_flags":            red_flags,
                "reply_rate_30d":       reply_rate,
                "signals_available":    signals_available,
                # New: components
                "base_score":           round(base_score, 1),
                "compound_multiplier":  compound_multiplier,
                "compounded_score":     round(compounded, 1),
                "trajectory_adjustment": trajectory_adjustment,
                "trajectory_note":      trajectory_note,
                "pre_llm_score":        pre_llm_score,
                "pre_llm_risk":         pre_llm_risk,
                "llm_adjustment":       llm_adjustment,
                "llm_justification":    llm_justification,
                "llm_interactions":     llm_interactions,
                "llm_used":             llm_used,
                "llm_error":            llm_error,
            },
            confidence=confidence,
            used_fallback=False,
        )

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=False,
            data={"churn_score": None, "risk": "Unknown",
                  "reason_tags": [], "churn_reasons": []},
            error=str(error), confidence=0.2, used_fallback=True,
        )
