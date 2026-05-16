"""Winback Priority Skill v2.0 — score churned/at-risk sellers for re-engagement.

Upgrades over v1:
  1. historical_quality uses enq_30d + reply_rate (recent activity), not lifetime enq.
  2. recoverability_score is multiplied by rca_confidence (low-confidence RCA hedges).
  3. paid_history_bonus rewards previously-paid sellers.
  4. trajectory_factor: TYPE_B drift > TYPE_A cliff > TYPE_C never-engaged.
  5. peer_recovery_signal: peer_delta_pct improving = small bonus.
  6. interaction_bonus: demand & recoverability both strong → x1.10 multiplier.
  7. cool_off is now a HARD GATE — no HIGH tier until elapsed.
  8. LLM second opinion: ±10 adjustment with one-line justification.
"""
from __future__ import annotations

import json
import os
import re

import requests as _requests

from churn_analysis.skills.base_skill import Skill, SkillResult


RECOVERABILITY = {
    "NO_LEADS":        90,
    "POOR_CATALOG":    75,
    "BL_DECLINE":      60,
    "LOW_ENGAGEMENT":  55,
    "LOW_PNS_RESPONSE":50,
    "PEER_GAP":        50,
    "RAG_RISK":        40,
    "UNKNOWN":         30,
}

PITCH_TYPES = {
    "NO_LEADS":        "DEMAND_IMPROVED",
    "POOR_CATALOG":    "CATALOG_FIX",
    "BL_DECLINE":      "PLATFORM_HEALTH",
    "LOW_ENGAGEMENT":  "EASY_SETUP",
    "LOW_PNS_RESPONSE":"MISSED_CALLS_FIXED",
    "PEER_GAP":        "COMPETITOR_INSIGHT",
    "RAG_RISK":        "ACCOUNT_RESET",
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


_LLM_SYSTEM_REVIEW = (
    "You are a winback-priority reviewer for a B2B marketplace sales team. "
    "Given a seller's quantitative winback sub-scores, decide whether the model is "
    "over- or under-confident about calling this seller back NOW. "
    "You may shift the score by at most ±10. "
    "Reply with strict JSON only:\n"
    "{\n"
    '  "adjustment": <int between -10 and 10>,\n'
    '  "justification": "one short sentence (<= 25 words)"\n'
    "}\n"
)

_LLM_USER_TEMPLATE = """Seller signals:
- RCA: {rca}  (confidence: {conf})
- Pre-LLM winback score: {pre}
- historical_quality: {hq:.2f}  (enq_30d={enq30}, reply_rate={reply}%)
- demand_score:       {ds:.2f}  (demand_index={di})
- recoverability:     {rs:.2f}
- paid_history_bonus: {ph:.2f}
- trajectory_factor:  {tf:.2f}  ({traj})
- peer_recovery:      {pr:.2f}  (peer_delta_pct={pd})
- recency_bonus:      {rec:.2f}  (days_since_churn={dsc}, cool_off_elapsed={coe})
- interaction_bonus:  {ib:.2f}

Should we call THIS seller now? Return JSON.
"""


def _call_llm(system: str, user: str, model: str, timeout: int = 30) -> str:
    base    = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        raise RuntimeError("LLM_API_KEY not set")
    resp = _requests.post(
        f"{base}/chat/completions",
        json={
            "model":       model,
            "max_tokens":  400,
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
        return json.loads(re.sub(r",\s*([}\]])", r"\1", text))


def _trajectory_factor(traj: str) -> float:
    # TYPE_B drift: most recoverable (had momentum, gradually faded)
    # TYPE_A cliff: shock-driven; recoverable if cause is reversible
    # TYPE_C never engaged: hardest to win back
    return {
        "TYPE_B":  1.00,
        "TYPE_A":  0.70,
        "TYPE_C":  0.20,
    }.get((traj or "").upper(), 0.50)


def _peer_recovery_signal(peer_delta_pct) -> float:
    if peer_delta_pct is None:
        return 0.5
    try:
        d = float(peer_delta_pct)
    except (TypeError, ValueError):
        return 0.5
    # peer_delta_pct closer to 0 (or positive) = recovering vs peers
    if d >= 0:    return 1.0
    if d >= -20:  return 0.7
    if d >= -50:  return 0.4
    return 0.1


class WinbackPrioritySkill(Skill):
    name = "winback-priority"
    version = "2.0"
    required_inputs = ["glid"]
    optional_inputs = [
        # RCA
        "churn_reason", "rca_category", "rca_confidence",
        # Recency / cool-off
        "churn_date", "days_since_churn", "account_age_days",
        # Account
        "enterprise", "ctype", "paid_history", "city",
        # Activity signals (last 30d)
        "historical_enq", "enq_30d", "replied_30d", "reply_rate_30d", "active_days_30d",
        # Demand / peer / trajectory
        "current_demand_index", "demand_index",
        "peer_delta_pct", "trajectory_type", "cqs",
        "churn_score",
        # LLM controls
        "model", "force_no_llm",
    ]

    def invoke(self, inputs: dict) -> SkillResult:
        # ---- Normalise inputs ----
        rca = (inputs.get("rca_category") or inputs.get("churn_reason") or "UNKNOWN").upper()
        try:
            rca_conf = float(inputs.get("rca_confidence") or 0.6)
        except (TypeError, ValueError):
            rca_conf = 0.6
        rca_conf = max(0.0, min(1.0, rca_conf))

        ctype = (inputs.get("ctype") or "").upper()
        enterprise = bool(inputs.get("enterprise") or False)
        paid_history = bool(inputs.get("paid_history") or False)

        # Demand
        cdi = inputs.get("current_demand_index")
        if cdi is None:
            cdi = inputs.get("demand_index")
        demand_provided = cdi is not None
        demand_index_val = float(cdi) if demand_provided else 50.0

        # Recent activity
        enq_30d = float(inputs.get("enq_30d") or 0)
        replied_30d = float(inputs.get("replied_30d") or 0)
        reply_rate = inputs.get("reply_rate_30d")
        if reply_rate is None:
            reply_rate = (replied_30d / enq_30d * 100.0) if enq_30d > 0 else 0.0
        reply_rate = float(reply_rate)

        # Trajectory & peer
        traj = (inputs.get("trajectory_type") or "").upper()
        peer_delta = inputs.get("peer_delta_pct")

        # Cool-off
        days_since = float(inputs.get("days_since_churn") if inputs.get("days_since_churn") is not None else 180)
        cool_off_req = 180 if ctype == "FREELIST" else 90
        cool_off_elapsed = days_since >= cool_off_req
        cool_off_days_remaining = max(0, int(cool_off_req - days_since))

        # ---- Sub-scores (0..1) ----
        # historical_quality: enq_30d up to 20 = 1.0, plus reply-rate kicker
        enq_part   = min(enq_30d / 20.0, 1.0)
        reply_part = min(reply_rate / 50.0, 1.0)   # 50% reply → full
        historical_quality = round(0.6 * enq_part + 0.4 * reply_part, 3)

        demand_score = round(demand_index_val / 100.0, 3)

        recoverability_score = round((RECOVERABILITY.get(rca, 30) / 100.0) * rca_conf, 3)

        paid_history_bonus = 1.0 if paid_history else 0.3

        trajectory_factor = round(_trajectory_factor(traj), 3)
        peer_recovery     = round(_peer_recovery_signal(peer_delta), 3)

        if cool_off_elapsed:
            recency_bonus = round(max(0.0, 1.0 - (days_since - cool_off_req) / 365.0), 3)
        else:
            recency_bonus = 0.0

        # ---- Weighted base (sums to 1.0) ----
        weights = {
            "historical_quality":  0.20,
            "demand_score":        0.25,
            "recoverability":      0.20,
            "paid_history":        0.10,
            "trajectory":          0.10,
            "peer_recovery":       0.05,
            "recency":             0.10,
        }

        # If demand wasn't provided, redistribute its weight to recoverability
        if not demand_provided:
            w_demand = weights.pop("demand_score")
            weights["recoverability"] += w_demand
            demand_score = 0.0

        base = (
            historical_quality   * weights.get("historical_quality", 0)
            + demand_score       * weights.get("demand_score", 0)
            + recoverability_score * weights.get("recoverability", 0)
            + paid_history_bonus * weights.get("paid_history", 0)
            + trajectory_factor  * weights.get("trajectory", 0)
            + peer_recovery      * weights.get("peer_recovery", 0)
            + recency_bonus      * weights.get("recency", 0)
        )

        # ---- Interaction bonus: strong demand AND strong recoverability ----
        interaction_bonus = 1.0
        if demand_score >= 0.7 and recoverability_score >= 0.7:
            interaction_bonus = 1.10
        elif demand_score >= 0.5 and recoverability_score >= 0.5:
            interaction_bonus = 1.05

        pre_llm_score = int(round(100 * base * interaction_bonus))
        pre_llm_score = max(0, min(100, pre_llm_score))

        # ---- LLM second opinion (±10) ----
        llm_used = False
        llm_adjustment = 0
        llm_justification = ""
        force_no_llm = bool(inputs.get("force_no_llm"))
        model = inputs.get("model") or os.getenv("LLM_MODEL", "gpt-4o-mini")

        if not force_no_llm and os.getenv("LLM_API_KEY"):
            try:
                user_prompt = _LLM_USER_TEMPLATE.format(
                    rca=rca, conf=round(rca_conf, 2), pre=pre_llm_score,
                    hq=historical_quality, enq30=int(enq_30d), reply=round(reply_rate, 1),
                    ds=demand_score, di=int(demand_index_val) if demand_provided else "n/a",
                    rs=recoverability_score,
                    ph=paid_history_bonus,
                    tf=trajectory_factor, traj=traj or "unknown",
                    pr=peer_recovery, pd=peer_delta if peer_delta is not None else "n/a",
                    rec=recency_bonus, dsc=int(days_since), coe=cool_off_elapsed,
                    ib=interaction_bonus,
                )
                raw = _call_llm(_LLM_SYSTEM_REVIEW, user_prompt, model)
                parsed = _parse_llm_json(raw)
                adj = int(parsed.get("adjustment", 0))
                llm_adjustment = max(-10, min(10, adj))
                llm_justification = str(parsed.get("justification", ""))[:300]
                llm_used = True
            except Exception as e:
                llm_justification = f"(LLM error: {e})"

        winback_score = max(0, min(100, pre_llm_score + llm_adjustment))

        # ---- Tier (cool-off HARD GATES the HIGH tier) ----
        if winback_score >= 65 and cool_off_elapsed:
            priority = "HIGH"
        elif winback_score >= 65 and not cool_off_elapsed:
            priority = "MEDIUM"  # forced down — too early
        elif winback_score >= 40:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        # ---- Pitch & opening line ----
        pitch_type = PITCH_TYPES.get(rca, "GENERAL")
        template   = OPENING_LINES.get(pitch_type, _DEFAULT_OPENING)
        demand_disp = int(demand_index_val) if demand_provided else 50
        opening_line = template.format(demand_index=demand_disp)

        gifted_lead_eligible = cool_off_elapsed and priority in ("HIGH", "MEDIUM")
        est_conv = round(winback_score / 100.0 * 0.40, 2)
        recommended_package = "annual" if ctype != "FREELIST" or enterprise else "monthly"

        sub_scores_dict = {
            "historical_quality":   historical_quality,
            "demand_score":         demand_score,
            "recoverability_score": recoverability_score,
            "paid_history_bonus":   paid_history_bonus,
            "trajectory_factor":    trajectory_factor,
            "peer_recovery":        peer_recovery,
            "recency_bonus":        recency_bonus,
        }

        return SkillResult(
            success=True,
            data={
                "winback_score":     winback_score,
                "priority":          priority,
                # Clean keys (standalone CLI + Phase 5 renderer)
                "pre_llm_score":     pre_llm_score,
                "llm_used":          llm_used,
                "llm_adjustment":    llm_adjustment,
                "llm_justification": llm_justification,
                "interaction_bonus": interaction_bonus,
                "sub_scores":        sub_scores_dict,
                "weights":           weights,
                # Namespaced aliases (BL Card — avoids flow-merge collision with churn)
                "winback_priority":          priority,
                "winback_pre_llm_score":     pre_llm_score,
                "winback_llm_used":          llm_used,
                "winback_llm_adjustment":    llm_adjustment,
                "winback_llm_justification": llm_justification,
                "winback_interaction_bonus": interaction_bonus,
                "winback_sub_scores":        sub_scores_dict,
                "winback_weights":           weights,
                "winback_cool_off_elapsed":          cool_off_elapsed,
                "winback_cool_off_days_remaining":   cool_off_days_remaining,
                "winback_demand_provided":           demand_provided,
                # Rest
                "rca_used":          rca,
                "rca_confidence":    rca_conf,
                "demand_provided":   demand_provided,
                "cool_off_required_days":   cool_off_req,
                "cool_off_elapsed":         cool_off_elapsed,
                "cool_off_days_remaining":  cool_off_days_remaining,
                "winback_pitch_type":       pitch_type,
                "opening_line_hi":          opening_line,
                "pitch":                    opening_line,
                "gifted_lead_eligible":     gifted_lead_eligible,
                "estimated_conversion_probability": est_conv,
                "recommended_package":      recommended_package,
            },
            confidence=0.85,
        )

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=False,
            data={
                "winback_score": 0,
                "priority": "LOW",
                "pre_llm_score": 0,
                "llm_used": False,
                "llm_adjustment": 0,
                "llm_justification": "",
                "interaction_bonus": 1.0,
                "sub_scores": {},
                "weights": {},
                "cool_off_elapsed": False,
                "cool_off_days_remaining": 0,
                "winback_pitch_type": "GENERAL",
                "opening_line_hi": _DEFAULT_OPENING,
                "pitch": _DEFAULT_OPENING,
                "gifted_lead_eligible": False,
                "estimated_conversion_probability": 0.0,
                "recommended_package": "monthly",
            },
            error=str(error),
            confidence=0.1,
            used_fallback=True,
        )
