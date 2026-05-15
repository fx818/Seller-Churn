"""
LLM scoring: builds prompt → Claude API → parses 3-band JSON → composite risk_level + confidence.
"""
import json, os, re
import requests as _requests

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

# ── 27-cell deterministic composite rubric ─────────────────────────────────────
COMPOSITE_RUBRIC: dict[tuple[str, str, str], str] = {
    # 3 Reds
    ("R", "R", "R"): "Critical",
    # 2 Reds + 1 Amber
    ("R", "R", "A"): "Very High",
    ("R", "A", "R"): "Very High",
    ("A", "R", "R"): "Very High",
    # 2 Reds + 1 Green
    ("R", "R", "G"): "High",
    ("R", "G", "R"): "High",
    ("G", "R", "R"): "High",
    # 1 Red + 2 Ambers
    ("R", "A", "A"): "High",
    ("A", "R", "A"): "High",
    ("A", "A", "R"): "High",
    # 1 of each (R+A+G)
    ("R", "A", "G"): "Moderate",
    ("R", "G", "A"): "Moderate",
    ("A", "R", "G"): "Moderate",
    ("A", "G", "R"): "Moderate",
    ("G", "R", "A"): "Moderate",
    ("G", "A", "R"): "Moderate",
    # 3 Ambers
    ("A", "A", "A"): "Moderate",
    # 1 Red + 2 Greens
    ("R", "G", "G"): "Moderate",
    ("G", "R", "G"): "Moderate",
    ("G", "G", "R"): "Moderate",
    # 2 Ambers + 1 Green
    ("A", "A", "G"): "Low",
    ("A", "G", "A"): "Low",
    ("G", "A", "A"): "Low",
    # 1 Amber + 2 Greens
    ("A", "G", "G"): "Low",
    ("G", "A", "G"): "Low",
    ("G", "G", "A"): "Low",
    # 3 Greens
    ("G", "G", "G"): "Very Low",
}

RISK_TIER_ORDER = {"Critical": 5, "Very High": 4, "High": 3, "Moderate": 2, "Low": 1, "Very Low": 0}


def _build_system_prompt() -> str:
    return (
        "You are a seller-survival analyst at IndiaMART. Score the target seller on three "
        "behavioral dimensions using Red / Amber / Green bands, by comparing their metrics against "
        "the provided cohort of historically churned and retained sellers. "
        "Calibrate bands from the cohort data — there are no hard-coded thresholds. "
        "Return ONLY valid JSON, no other text."
    )


def _slim_snap(s: dict) -> dict:
    """Keep only the key behavioral signals needed for LLM scoring."""
    beh = s.get("behavioral", {})
    bl  = beh.get("bl", {})
    lms = beh.get("lms", {})
    act = beh.get("activity", {})
    monthly = act.get("monthly_trend", [])
    recent = monthly[-3:] if monthly else []
    return {
        "glid":               s.get("glid") or s.get("context", {}).get("glid"),
        "bl_consumption_rate": bl.get("consumption_rate"),
        "reply_rate":          bl.get("reply_rate"),
        "received_30d":        bl.get("received_30d"),
        "consumed_30d":        bl.get("consumed_30d"),
        "lms_active_days_30d": lms.get("lms_active_days_30d"),
        "call_pickup_ratio":   lms.get("call_pickup_ratio_90d"),
        "call_attempts_90d":   lms.get("call_attempts_90d"),
        "activity_30d":        act.get("activity_30d"),
        "event_count":         act.get("event_count"),
        "cqs":                 act.get("cqs"),
        "recent_enq_trend":    [m.get("total_enq") for m in recent],
    }


def _build_user_prompt(target: dict, churned: list[dict], retained: list[dict]) -> str:
    ctx = target.get("context", {})
    beh = target.get("behavioral", {})
    bl  = beh.get("bl", {})
    lms = beh.get("lms", {})
    act = beh.get("activity", {})
    monthly = act.get("monthly_trend", [])
    recent = monthly[-3:] if monthly else []

    target_slim = {
        "bl_consumption_rate": bl.get("consumption_rate"),
        "reply_rate":          bl.get("reply_rate"),
        "received_30d":        bl.get("received_30d"),
        "consumed_30d":        bl.get("consumed_30d"),
        "lms_active_days_30d": lms.get("lms_active_days_30d"),
        "call_pickup_ratio":   lms.get("call_pickup_ratio_90d"),
        "call_attempts_90d":   lms.get("call_attempts_90d"),
        "activity_30d":        act.get("activity_30d"),
        "event_count":         act.get("event_count"),
        "cqs":                 act.get("cqs"),
        "recent_enq_trend":    [m.get("total_enq") for m in recent],
    }

    churned_slim  = [_slim_snap(s) for s in churned]
    retained_slim = [_slim_snap(s) for s in retained]

    prompt = f"""Target seller:
{json.dumps(target_slim, default=str)}

Profile: custtype={ctx.get('custtype')} mcats={ctx.get('mcats',[])}

{len(churned_slim)} churned sellers: {json.dumps(churned_slim, default=str)}

{len(retained_slim)} retained sellers: {json.dumps(retained_slim, default=str)}

Score target on 3 dimensions vs cohort:
1. BL consumption (consumption_rate, reply_rate, consumed_30d)
2. LMS activity (call_pickup_ratio, call_attempts_90d, lms_active_days_30d)
3. Activity trend (recent_enq_trend direction, activity_30d, event_count)

Return ONLY JSON (use actual glid integers from the data above, not null):
{{"bl_band":"R|A|G","lms_band":"R|A|G","activity_band":"R|A|G","reasoning":"2-3 sentences","churned_lookalikes":[<pick up to 3 glid integers from churned list>],"retained_lookalikes":[<pick up to 3 glid integers from retained list>]}}"""
    return prompt


def _call_llm(system: str, user: str, model: str) -> str:
    base    = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key = os.getenv("LLM_API_KEY", "")
    url     = f"{base}/chat/completions"
    resp = _requests.post(
        url,
        json={
            "model":      model,
            "max_tokens": 1024,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        },
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _parse_llm_response(text: str) -> dict:
    text = text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    # Extract first JSON object
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    return json.loads(text)


def _confidence(
    mean_match_score: float,
    n_filtered: int,
    target_snapshot: dict,
) -> int:
    cohort_match_score = mean_match_score
    cohort_size_score  = min(n_filtered / 20.0, 1.0)

    beh = target_snapshot.get("behavioral", {})
    all_fields = (
        list(beh.get("bl", {}).values()) +
        list(beh.get("lms", {}).values()) +
        list(beh.get("activity", {}).items())
    )
    non_null = sum(1 for v in all_fields if v is not None and v != [] and v != {})
    data_completeness_score = non_null / max(len(all_fields), 1)

    raw = (
        0.5 * cohort_match_score +
        0.3 * cohort_size_score +
        0.2 * data_completeness_score
    )
    return round(100 * raw)


def score(
    target_snapshot: dict,
    churned_examples: list[dict],
    retained_examples: list[dict],
    mean_match_score: float = 0.0,
    n_filtered: int = 0,
    model: str | None = None,
) -> dict:
    """
    Runs LLM scoring, applies composite rubric, computes confidence.
    Returns full scored card dict.
    """
    model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
    system_prompt = _build_system_prompt()
    user_prompt   = _build_user_prompt(target_snapshot, churned_examples, retained_examples)

    raw_text = _call_llm(system_prompt, user_prompt, model)
    parsed   = _parse_llm_response(raw_text)

    bl_band       = parsed.get("bl_band", "A")
    lms_band      = parsed.get("lms_band", "A")
    activity_band = parsed.get("activity_band", "A")

    for band in (bl_band, lms_band, activity_band):
        if band not in ("R", "A", "G"):
            raise ValueError(f"Invalid band value from LLM: {band!r}")

    risk_level = COMPOSITE_RUBRIC.get((bl_band, lms_band, activity_band), "Moderate")
    confidence = _confidence(mean_match_score, n_filtered, target_snapshot)

    def _glid(snap):
        return snap.get("glid") or (snap.get("context") or {}).get("glid")

    churned_glids  = [g for g in (_glid(s) for s in churned_examples)  if g]
    retained_glids = [g for g in (_glid(s) for s in retained_examples) if g]

    def _clean_lookalikes(raw_list, fallback_glids):
        cleaned = [g for g in (raw_list or []) if g is not None]
        return cleaned if cleaned else fallback_glids[:3]

    return {
        "bands": {
            "bl":       bl_band,
            "lms":      lms_band,
            "activity": activity_band,
        },
        "risk_level":       risk_level,
        "confidence_score": confidence,
        "llm_output": {
            "reasoning":           parsed.get("reasoning", ""),
            "churned_lookalikes":  _clean_lookalikes(parsed.get("churned_lookalikes"), churned_glids),
            "retained_lookalikes": _clean_lookalikes(parsed.get("retained_lookalikes"), retained_glids),
        },
        "_llm_raw": raw_text,
    }


def risk_tier_value(risk_level: str) -> int:
    return RISK_TIER_ORDER.get(risk_level, 2)
