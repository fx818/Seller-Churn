# delivery_cascade.py
# DeliveryCascade manages message delivery state per GLID across channels.
# Channels in order: WHATSAPP (primary), SMS (fallback after 48h unread),
#                    IVR (fallback after 72h), HUMAN_CALL (Red tier escalation)

import json
import os
from datetime import datetime

# ---------------------------------------------------------------------------
# Message templates (Hindi + English)
# ---------------------------------------------------------------------------

_TEMPLATES = {
    "WHATSAPP": {
        "Red": {
            "hi": (
                "नमस्ते {company}! आपके IndiaMart अकाउंट पर ध्यान देने की जरूरत है। "
                "आपकी लीड्स में गिरावट देखी गई है। हमारा विशेषज्ञ आज आपसे बात करेगा।"
            ),
            "en": (
                "Hello {company}! Your IndiaMart account needs immediate attention. "
                "We've noticed a drop in your leads. Our specialist will call you today."
            ),
        },
        "Amber": {
            "hi": (
                "नमस्ते {company}! आपके IndiaMart खाते को बेहतर बनाने के लिए हमारे पास "
                "कुछ सुझाव हैं। क्या आप अभी देखना चाहेंगे?"
            ),
            "en": (
                "Hello {company}! We have suggestions to improve your IndiaMart account "
                "performance. Would you like to review them now?"
            ),
        },
        "Green": {
            "hi": (
                "नमस्ते {company}! आप IndiaMart पर अच्छा कर रहे हैं। "
                "अपना कैटलॉग अपडेट करके और भी बेहतर परिणाम पाएं।"
            ),
            "en": (
                "Hello {company}! You're doing great on IndiaMart. "
                "Update your catalog to get even better results."
            ),
        },
    },
    "SMS": {
        "Red": {
            "hi": "IndiaMart: {company} - आपके अकाउंट पर तुरंत ध्यान दें। हमारा विशेषज्ञ संपर्क करेगा।",
            "en": "IndiaMart: {company} - Urgent account attention needed. Our specialist will contact you.",
        },
        "Amber": {
            "hi": "IndiaMart: {company} - आपके अकाउंट को बेहतर बनाने के सुझाव तैयार हैं।",
            "en": "IndiaMart: {company} - Improvement suggestions ready for your account.",
        },
    },
    "IVR": {
        "Red": {
            "hi": "IndiaMart की ओर से संदेश: {company}, आपके खाते में सुधार के लिए हम संपर्क कर रहे हैं।",
            "en": "Message from IndiaMart: {company}, we're reaching out to help improve your account.",
        },
    },
    "HUMAN_CALL": {
        "brief": (
            "Red-tier seller {company} (GLID {glid}). RCA: {rca}. "
            "Churn score: {churn_score}. Key issue: account health critical. "
            "Offer: gifted lead / catalog audit / BL upgrade as applicable."
        ),
    },
}


def _msg(channel: str, tier: str, company: str, glid: str,
         churn_score: int = 0, rca: str = "") -> dict:
    """Render message strings for a given channel / tier."""
    tpl = _TEMPLATES.get(channel, {})
    tier_tpl = tpl.get(tier, tpl.get("Red", {}))

    if channel == "HUMAN_CALL":
        brief = _TEMPLATES["HUMAN_CALL"]["brief"].format(
            company=company, glid=glid, rca=rca, churn_score=churn_score
        )
        return {"brief_hint": brief}

    hi = tier_tpl.get("hi", "").format(company=company)
    en = tier_tpl.get("en", "").format(company=company)
    return {"message_hi": hi, "message_en": en}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_cascade_plan(glid: str, risk_tier: str, action_plan: dict) -> dict:
    """
    Build a full delivery cascade plan for a single seller.

    Parameters
    ----------
    glid        : seller GLID string
    risk_tier   : "Red" | "Amber" | "Green"
    action_plan : dict with keys: company, rca, churn_score, city (all optional)

    Returns
    -------
    dict matching the cascade plan schema
    """
    company = action_plan.get("company", glid)
    rca = action_plan.get("rca", "UNKNOWN")
    churn_score = int(action_plan.get("churn_score", 0))

    steps = []

    # Step 1 — WhatsApp (all tiers)
    step1 = {
        "step": 1,
        "channel": "WHATSAPP",
        "timing": "NOW",
        "delay_hours": 0,
        "trigger": "immediate",
    }
    step1.update(_msg("WHATSAPP", risk_tier, company, glid, churn_score, rca))
    steps.append(step1)

    if risk_tier in ("Red", "Amber"):
        # Step 2 — SMS fallback after 48 h
        step2 = {
            "step": 2,
            "channel": "SMS",
            "timing": "48h",
            "delay_hours": 48,
            "trigger": "if_unread_48h",
        }
        step2.update(_msg("SMS", risk_tier, company, glid, churn_score, rca))
        steps.append(step2)

    if risk_tier == "Red":
        # Step 3 — IVR fallback after 72 h
        step3 = {
            "step": 3,
            "channel": "IVR",
            "timing": "72h",
            "delay_hours": 72,
            "trigger": "if_unread_72h",
        }
        step3.update(_msg("IVR", risk_tier, company, glid, churn_score, rca))
        steps.append(step3)

        # Step 4 — Human call (Red mandatory, triggered 24 h after IVR = 96 h total)
        step4 = {
            "step": 4,
            "channel": "HUMAN_CALL",
            "timing": "24h",
            "delay_hours": 24,
            "trigger": "red_tier_mandatory",
        }
        step4.update(_msg("HUMAN_CALL", risk_tier, company, glid, churn_score, rca))
        steps.append(step4)

    return {
        "glid": glid,
        "company": company,
        "city": action_plan.get("city", ""),
        "risk_tier": risk_tier,
        "churn_score": churn_score,
        "rca": rca,
        "steps": steps,
    }


def export_cascade_queue(cascade_plans: dict) -> list:
    """
    Flatten all cascade plans into a sorted queue of pending actions.

    Sorted by:
      1. Priority: Red=1, Amber=2, Green=3
      2. Timing: soonest delay_hours first

    Parameters
    ----------
    cascade_plans : dict mapping glid -> cascade_plan dict

    Returns
    -------
    list of action dicts
    """
    _tier_priority = {"Red": 1, "Amber": 2, "Green": 3}

    queue = []
    for glid, plan in cascade_plans.items():
        tier = plan.get("risk_tier", "Green")
        priority = _tier_priority.get(tier, 3)
        company = plan.get("company", glid)
        city = plan.get("city", "")
        churn_score = plan.get("churn_score", 0)

        for step in plan.get("steps", []):
            item = {
                "glid": glid,
                "company": company,
                "city": city,
                "risk_tier": tier,
                "priority": priority,
                "step": step.get("step"),
                "channel": step.get("channel"),
                "timing": step.get("timing"),
                "delay_hours": step.get("delay_hours", 0),
                "trigger": step.get("trigger"),
                "churn_score": churn_score,
                "scheduled_at": step.get("timing", "NOW"),
            }
            # attach message fields if present
            for field in ("message_hi", "message_en", "brief_hint"):
                if field in step:
                    item[field] = step[field]
            queue.append(item)

    queue.sort(key=lambda x: (x["priority"], x["delay_hours"]))
    return queue


def write_cascade_queue(run_dir: str, cascade_plans: dict) -> str:
    """
    Write delivery_cascade.json to {run_dir}/action_plans/.

    Returns the output file path.
    """
    out_dir = os.path.join(run_dir, "action_plans")
    os.makedirs(out_dir, exist_ok=True)

    out_path = os.path.join(out_dir, "delivery_cascade.json")

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_plans": len(cascade_plans),
        "cascade_plans": list(cascade_plans.values()),
        "queue": export_cascade_queue(cascade_plans),
    }

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, default=str, indent=2)

    return out_path
