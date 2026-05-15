"""Script generation skill — routes by RCA category, generates Hindi-primary call scripts."""
from .base_skill import Skill, SkillResult


def _fmt(template: str, **kwargs) -> str:
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


_RCA_SCRIPTS: dict[str, dict] = {
    "NO_LEADS": {
        "opening_default": "Ramesh Bhai, main aapke account dekh raha tha — kuch interesting chal raha hai. Ek minute hai?",
        "diagnostic": "Maine dekha leads kum aa rahi hain. Aap Delhi/Mumbai ke buyers tak reach kar sakte ho — kya try kiya?",
        "value_demo": "Aapke jaise ek seller ne geography expand ki — {enq_30d} se {peer_median_enq} leads ho gayi.",
        "value_demo_default": "Aapke jaise ek seller ne geography expand ki — leads significantly badh gayi.",
        "action": "Main abhi geography setting change kar deta hoon — 2 minute.",
        "close": "Renewal ke baare mein pressure nahi hai. Pehle yeh lead pursue karo.",
        "opening_en": "Ramesh bhai, I was reviewing your account and noticed something interesting. Do you have a minute?",
        "diagnostic_en": "I see leads have been lower than expected. Have you tried reaching buyers in Delhi or Mumbai?",
        "value_demo_en": "A seller like you expanded their geography and went from {enq_30d} to {peer_median_enq} leads.",
        "value_demo_en_default": "A seller like you expanded their geography and significantly increased leads.",
        "action_en": "Let me change the geography setting right now — 2 minutes.",
        "close_en": "No pressure on renewal. First let's go after these leads.",
    },
    "LOW_ENGAGEMENT": {
        "opening_default": "Ramesh Bhai, aapke {enq_30d} leads last period respond nahi hue — koi notification issue toh nahi?",
        "diagnostic": "Kab last time IM pe login kiya tha? Mobile pe setup hai?",
        "value_demo": "Sellers jo daily 5 minute dete hain unka reply rate 3x hota hai.",
        "action": "Mobile app pe notifications on karte hain saath mein — 3 minute.",
        "close": "Chhota step, bada difference.",
        "opening_en": "Ramesh bhai, looks like {enq_30d} leads from last period didn't get a response — any notification issue?",
        "diagnostic_en": "When did you last log in to IndiaMART? Is the mobile app set up?",
        "value_demo_en": "Sellers who spend just 5 minutes daily see 3x higher reply rates.",
        "action_en": "Let's turn on mobile notifications together right now — 3 minutes.",
        "close_en": "Small step, big difference.",
    },
    "POOR_CATALOG": {
        "opening_default": "Ramesh Bhai, aapke competitors jo zyada leads le rahe hain unka ek simple difference hai.",
        "diagnostic": "Aapke products mein photos kitni hain abhi? Buyers pehle photo dekhte hain.",
        "value_demo_default": "7 extra photos = ~30% more leads in your category.",
        "action": "5 products pe photos upload karte hain abhi saath mein — 15 minute.",
        "close": "Koi extra cost nahi — sirf content update.",
        "opening_en": "Ramesh bhai, your competitors getting more leads have one simple difference.",
        "diagnostic_en": "How many photos do your products have right now? Buyers look at photos first.",
        "value_demo_en_default": "7 extra photos = ~30% more leads in your category.",
        "action_en": "Let's upload photos for 5 products together right now — 15 minutes.",
        "close_en": "No extra cost — just a content update.",
    },
    "PEER_GAP": {
        "opening_default": "Ramesh Bhai, same category mein ek seller last month {peer_median_enq} leads le gaya. Aapko {enq_30d} mili.",
        "diagnostic": "Woh ek specific cheez kar raha hai — kya main bataaun?",
        "value_demo": "Uski geography setting alag hai — national buyers include ki hain.",
        "action": "Yeh setting aapke account pe bhi on kar sakte hain — 2 minute.",
        "close": "Try karo — 30 din mein results visible hote hain.",
        "opening_en": "Ramesh bhai, a seller in your category got {peer_median_enq} leads last month. You got {enq_30d}.",
        "diagnostic_en": "They're doing one specific thing — want me to tell you what?",
        "value_demo_en": "Their geography setting is different — they've included national buyers.",
        "action_en": "We can turn on that setting for your account too — 2 minutes.",
        "close_en": "Try it — results are visible within 30 days.",
    },
}

_DEFAULT_SCRIPT = {
    "opening_default": "Ramesh Bhai, maine aapka account review kiya — kuch important hai.",
    "diagnostic": "Aapke leads {bl_velocity_pct}% kam ho gaye hain. Koi specific reason aaya mind mein?",
    "diagnostic_default": "Aapke leads recently kam ho gaye hain. Koi specific reason aaya mind mein?",
    "value_demo": "Maine ek specific fix identify ki hai jo aapke jaise sellers ke kaam aayi.",
    "action": "Ek setting check karte hain — 5 minute.",
    "close": "Aapke account mein potential hai — bas ek adjustment chahiye.",
    "opening_en": "Ramesh bhai, I reviewed your account — there's something important.",
    "diagnostic_en": "Your leads have dropped by {bl_velocity_pct}%. Any specific reason come to mind?",
    "diagnostic_en_default": "Your leads have dropped recently. Any specific reason come to mind?",
    "value_demo_en": "I've identified a specific fix that has worked for sellers like you.",
    "action_en": "Let's check one setting — 5 minutes.",
    "close_en": "Your account has potential — just needs one adjustment.",
}

_TYPE_C_OVERRIDE = {
    "opening": "Bhai, aapka account setup hona baaki laga — chaliye saath mein 10 minute mein properly set up karte hain.",
    "diagnostic": "Products add kiye hain? City setting dekhi?",
    "value_demo": "Ek properly setup account pe average 8 leads/month aati hain.",
    "action": "Abhi profile complete karte hain — 10 minute.",
    "opening_en": "Bhai, your account setup seems incomplete — let's properly set it up together in 10 minutes.",
    "diagnostic_en": "Have you added products? Have you checked the city setting?",
    "value_demo_en": "A properly set up account gets an average of 8 leads per month.",
    "action_en": "Let's complete the profile right now — 10 minutes.",
}

_OBJECTION_HANDLERS = {
    "competitor_platform": (
        "Samajh sakta hoon — doosre platforms bhi kaam karte hain. "
        "Lekin IndiaMART pe B2B buyers specifically aate hain jo bulk order dene ka intent rakhte hain. "
        "Ek baar compare karte hain — aapke last 3 mahine ke leads ka source kya raha?"
    ),
    "price_too_high": (
        "Bilkul valid point hai. Lekin aise socho — agar sirf 2 orders extra aaye subscription se, "
        "toh ROI positive ho jaata hai. Main aapke category ke average order value se calculate kar sakta hoon."
    ),
    "no_time": (
        "Koi baat nahi — main ek quick summary WhatsApp pe bhej deta hoon. "
        "Aap apne time pe dekh lena, aur jo bhi question ho directly reply karna."
    ),
}

_OBJECTION_HANDLERS_EN = {
    "competitor_platform": (
        "I understand — other platforms work too. "
        "But IndiaMART specifically attracts B2B buyers who intend to place bulk orders. "
        "Let's compare — what was the source of your leads over the last 3 months?"
    ),
    "price_too_high": (
        "Completely valid point. But think of it this way — if just 2 extra orders come through the subscription, "
        "the ROI turns positive. I can calculate that using your category's average order value."
    ),
    "no_time": (
        "No problem — I'll send you a quick summary on WhatsApp. "
        "Check it at your convenience, and just reply directly with any questions."
    ),
}


def _build_script(inputs: dict) -> tuple[dict, dict]:
    rca = inputs.get("rca_category", "").upper()
    seller = inputs.get("seller_name", "Bhai")
    enq_30d = inputs.get("enq_30d", "")
    peer_median = inputs.get("peer_median_enq", "")
    bl_vel = inputs.get("bl_velocity_pct", "")
    call_frame_hi = inputs.get("call_frame_hi", "")
    call_frame_en = inputs.get("call_frame_en", "")
    cross_platform = inputs.get("cross_platform_data")
    trajectory = inputs.get("trajectory_type", "")

    fmt_kwargs = {
        "seller": seller,
        "enq_30d": enq_30d,
        "peer_median_enq": peer_median,
        "bl_velocity_pct": bl_vel,
    }

    # TYPE_C override
    if trajectory == "TYPE_C":
        hi = {
            "opening": _TYPE_C_OVERRIDE["opening"],
            "diagnostic": _TYPE_C_OVERRIDE["diagnostic"],
            "value_demo": _TYPE_C_OVERRIDE["value_demo"],
            "action": _TYPE_C_OVERRIDE["action"],
            "close": "Aaj setup kar lete hain — 10 minute mein done.",
        }
        en = {
            "opening": _TYPE_C_OVERRIDE["opening_en"],
            "diagnostic": _TYPE_C_OVERRIDE["diagnostic_en"],
            "value_demo": _TYPE_C_OVERRIDE["value_demo_en"],
            "action": _TYPE_C_OVERRIDE["action_en"],
            "close": "Let's set it up today — done in 10 minutes.",
        }
        return hi, en

    tmpl = _RCA_SCRIPTS.get(rca)

    if rca == "NO_LEADS":
        opening_hi = call_frame_hi if call_frame_hi else tmpl["opening_default"]
        if enq_30d and peer_median:
            vd_hi = _fmt(tmpl["value_demo"], **fmt_kwargs)
            vd_en = _fmt(tmpl["value_demo_en"], **fmt_kwargs)
        else:
            vd_hi = tmpl["value_demo_default"]
            vd_en = tmpl["value_demo_en_default"]
        hi = {
            "opening": opening_hi,
            "diagnostic": tmpl["diagnostic"],
            "value_demo": vd_hi,
            "action": tmpl["action"],
            "close": tmpl["close"],
        }
        opening_en = call_frame_en if call_frame_en else tmpl["opening_en"]
        en = {
            "opening": opening_en,
            "diagnostic": tmpl["diagnostic_en"],
            "value_demo": vd_en,
            "action": tmpl["action_en"],
            "close": tmpl["close_en"],
        }

    elif rca == "LOW_ENGAGEMENT":
        opening_hi = call_frame_hi if call_frame_hi else _fmt(tmpl["opening_default"], **fmt_kwargs)
        opening_en = call_frame_en if call_frame_en else _fmt(tmpl["opening_en"], **fmt_kwargs)
        hi = {
            "opening": opening_hi,
            "diagnostic": tmpl["diagnostic"],
            "value_demo": tmpl["value_demo"],
            "action": tmpl["action"],
            "close": tmpl["close"],
        }
        en = {
            "opening": opening_en,
            "diagnostic": tmpl["diagnostic_en"],
            "value_demo": tmpl["value_demo_en"],
            "action": tmpl["action_en"],
            "close": tmpl["close_en"],
        }

    elif rca == "POOR_CATALOG":
        opening_hi = call_frame_hi if call_frame_hi else tmpl["opening_default"]
        opening_en = call_frame_en if call_frame_en else tmpl["opening_en"]
        if cross_platform:
            cp = cross_platform if isinstance(cross_platform, str) else str(cross_platform)
            vd_hi = cp
            vd_en = cp
        else:
            vd_hi = tmpl["value_demo_default"]
            vd_en = tmpl["value_demo_en_default"]
        hi = {
            "opening": opening_hi,
            "diagnostic": tmpl["diagnostic"],
            "value_demo": vd_hi,
            "action": tmpl["action"],
            "close": tmpl["close"],
        }
        en = {
            "opening": opening_en,
            "diagnostic": tmpl["diagnostic_en"],
            "value_demo": vd_en,
            "action": tmpl["action_en"],
            "close": tmpl["close_en"],
        }

    elif rca == "PEER_GAP":
        opening_hi = call_frame_hi if call_frame_hi else _fmt(tmpl["opening_default"], **fmt_kwargs)
        opening_en = call_frame_en if call_frame_en else _fmt(tmpl["opening_en"], **fmt_kwargs)
        hi = {
            "opening": opening_hi,
            "diagnostic": tmpl["diagnostic"],
            "value_demo": tmpl["value_demo"],
            "action": tmpl["action"],
            "close": tmpl["close"],
        }
        en = {
            "opening": opening_en,
            "diagnostic": tmpl["diagnostic_en"],
            "value_demo": tmpl["value_demo_en"],
            "action": tmpl["action_en"],
            "close": tmpl["close_en"],
        }

    else:
        # BL_DECLINE / RAG_RISK / LOW_PNS_RESPONSE / default
        opening_hi = call_frame_hi if call_frame_hi else _DEFAULT_SCRIPT["opening_default"]
        opening_en = call_frame_en if call_frame_en else _DEFAULT_SCRIPT["opening_en"]
        if bl_vel:
            diag_hi = _fmt(_DEFAULT_SCRIPT["diagnostic"], **fmt_kwargs)
            diag_en = _fmt(_DEFAULT_SCRIPT["diagnostic_en"], **fmt_kwargs)
        else:
            diag_hi = _DEFAULT_SCRIPT["diagnostic_default"]
            diag_en = _DEFAULT_SCRIPT["diagnostic_en_default"]
        hi = {
            "opening": opening_hi,
            "diagnostic": diag_hi,
            "value_demo": _DEFAULT_SCRIPT["value_demo"],
            "action": _DEFAULT_SCRIPT["action"],
            "close": _DEFAULT_SCRIPT["close"],
        }
        en = {
            "opening": opening_en,
            "diagnostic": diag_en,
            "value_demo": _DEFAULT_SCRIPT["value_demo_en"],
            "action": _DEFAULT_SCRIPT["action_en"],
            "close": _DEFAULT_SCRIPT["close_en"],
        }

    return hi, en


class ScriptGenerationSkill(Skill):
    name: str = "script_generation"
    required_inputs: list[str] = ["glid", "rca_category", "seller_name", "company", "city"]
    optional_inputs: list[str] = [
        "enterprise", "peer_median_enq", "enq_30d", "bl_velocity_pct",
        "gifted_lead", "days_to_renewal", "language", "llm_reasoning",
        "llm_risk_level", "trajectory_type", "trajectory_description",
        "call_frame_hi", "call_frame_en", "cross_platform_data",
    ]

    def invoke(self, inputs: dict) -> SkillResult:
        rca = inputs.get("rca_category", "").upper()
        language = inputs.get("language", "hi")
        trajectory = inputs.get("trajectory_type", "")

        hi_parts, en_parts = _build_script(inputs)

        data = {
            "script_parts": hi_parts,
            "script_parts_en": en_parts,
            "objection_handlers": _OBJECTION_HANDLERS,
            "objection_handlers_en": _OBJECTION_HANDLERS_EN,
            "language": language,
            "rca_used": rca if rca else "DEFAULT",
            "trajectory_type": trajectory,
            "estimated_duration_min": 10 if trajectory == "TYPE_C" else 7,
            "call_type": "RETENTION",
        }
        return SkillResult(success=True, data=data, confidence=1.0)

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        seller = inputs.get("seller_name", "Bhai")
        generic_hi = {
            "opening": f"{seller}, aapka account check kiya — ek important update hai.",
            "diagnostic": "Aapke account mein kya chal raha hai recently?",
            "value_demo": "Main aapko kuch useful data share karna chahta hoon.",
            "action": "5 minute baat karte hain — kab suitable hoga?",
            "close": "Aapka success hamara priority hai.",
        }
        generic_en = {
            "opening": f"{seller}, I checked your account — there's an important update.",
            "diagnostic": "What's been happening with your account recently?",
            "value_demo": "I want to share some useful data with you.",
            "action": "Let's talk for 5 minutes — when would suit you?",
            "close": "Your success is our priority.",
        }
        data = {
            "script_parts": generic_hi,
            "script_parts_en": generic_en,
            "objection_handlers": _OBJECTION_HANDLERS,
            "objection_handlers_en": _OBJECTION_HANDLERS_EN,
            "language": inputs.get("language", "hi"),
            "rca_used": "GENERIC_FALLBACK",
            "trajectory_type": inputs.get("trajectory_type", ""),
            "estimated_duration_min": 7,
            "call_type": "RETENTION",
        }
        return SkillResult(success=True, data=data, error=str(error), confidence=0.5, used_fallback=True)
