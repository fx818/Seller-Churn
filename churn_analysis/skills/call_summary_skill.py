"""Call summary skill — parses call transcript via LLM, returns 3-line summary + updated RCA + next action."""
import json, os, re
import requests as _requests

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"), override=True)

from .base_skill import Skill, SkillResult

_SYSTEM_PROMPT = (
    "You are a CRM assistant for IndiaMART sales reps. "
    "Extract key information from this call transcript. Return strict JSON only."
)

_USER_PROMPT_TEMPLATE = """\
Call Type: {call_type}
Pre-call RCA: {pre_call_rca}
Seller: {seller_name}

Transcript:
{transcript}

Extract and return:
{{
  "summary_lines": ["line1", "line2", "line3"],
  "sentiment": "positive" | "neutral" | "negative",
  "updated_rca": "NO_LEADS" | "LOW_ENGAGEMENT" | "POOR_CATALOG" | "LOW_PNS_RESPONSE" | "PEER_GAP" | "RAG_RISK" | "BL_DECLINE" | "UNKNOWN",
  "stated_concern": "seller's main stated concern in 1 sentence",
  "next_action": "FOLLOW_UP_48H" | "FOLLOW_UP_7D" | "ESCALATE" | "MONITOR" | "NO_ACTION",
  "next_action_detail": "specific follow-up instruction",
  "call_outcome": "ENGAGED" | "NOT_INTERESTED" | "CALLBACK_REQUESTED" | "ALREADY_CANCELLED" | "UNRESPONSIVE",
  "churn_risk_updated": "Red" | "Amber" | "Green"
}}"""

_NEXT_ACTION_LABELS = {
    "FOLLOW_UP_48H": "Follow up in 48h",
    "FOLLOW_UP_7D":  "Follow up in 7 days",
    "ESCALATE":      "Escalate to senior rep",
    "MONITOR":       "Monitor account",
    "NO_ACTION":     "No action required",
}


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
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    return json.loads(text)


def _build_confidence(parsed: dict) -> float:
    score = 0.6
    if parsed.get("updated_rca", "UNKNOWN") != "UNKNOWN":
        score += 0.1
    if parsed.get("call_outcome") and parsed["call_outcome"] != "UNRESPONSIVE":
        score += 0.1
    if parsed.get("stated_concern"):
        score += 0.1
    if len(parsed.get("summary_lines", [])) >= 2:
        score += 0.1
    return round(min(score, 1.0), 2)


class CallSummarySkill(Skill):
    name: str = "call_summary"
    required_inputs: list[str] = ["glid", "transcript", "call_type"]
    optional_inputs: list[str] = ["pre_call_rca", "call_date", "model", "seller_name", "company"]

    def invoke(self, inputs: dict) -> SkillResult:
        transcript   = inputs["transcript"]
        call_type    = inputs["call_type"]
        pre_call_rca = inputs.get("pre_call_rca") or "unknown"
        seller_name  = inputs.get("seller_name") or "unknown"
        model        = inputs.get("model") or os.getenv("LLM_MODEL", "gpt-4o-mini")

        user_prompt = _USER_PROMPT_TEMPLATE.format(
            call_type=call_type,
            pre_call_rca=pre_call_rca,
            seller_name=seller_name,
            transcript=transcript,
        )

        raw = _call_llm(_SYSTEM_PROMPT, user_prompt, model)
        parsed = _parse_llm_response(raw)

        summary_lines     = parsed.get("summary_lines", [])[:3]
        sentiment         = parsed.get("sentiment", "neutral")
        updated_rca       = parsed.get("updated_rca", "UNKNOWN")
        stated_concern    = parsed.get("stated_concern", "")
        next_action       = parsed.get("next_action", "FOLLOW_UP_48H")
        next_action_detail = parsed.get("next_action_detail", "")
        call_outcome      = parsed.get("call_outcome", "UNRESPONSIVE")
        churn_risk        = parsed.get("churn_risk_updated", "Amber")

        notes = "; ".join(summary_lines) if summary_lines else "Call completed."

        data = {
            "summary_lines": summary_lines,
            "sentiment": sentiment,
            "updated_rca": updated_rca,
            "stated_concern": stated_concern,
            "next_action": next_action,
            "next_action_detail": next_action_detail,
            "crm_entry": {
                "call_outcome": call_outcome,
                "next_step": _NEXT_ACTION_LABELS.get(next_action, next_action),
                "notes": notes,
            },
            "churn_risk_updated": churn_risk,
            "confidence": _build_confidence(parsed),
        }
        return SkillResult(success=True, data=data, confidence=_build_confidence(parsed))

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        data = {
            "summary_lines": ["Call completed. Details unavailable."],
            "sentiment": "neutral",
            "updated_rca": inputs.get("pre_call_rca") or "UNKNOWN",
            "stated_concern": "",
            "next_action": "FOLLOW_UP_48H",
            "next_action_detail": "Review call manually and follow up within 48 hours.",
            "crm_entry": {
                "call_outcome": "UNRESPONSIVE",
                "next_step": "Follow up in 48h",
                "notes": "Call completed. Details unavailable.",
            },
            "churn_risk_updated": "Amber",
            "confidence": 0.1,
        }
        return SkillResult(success=True, data=data, error=str(error), confidence=0.1, used_fallback=True)
