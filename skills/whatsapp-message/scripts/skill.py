"""SKILL 6 — WhatsAppMessageSkill: Personalized Hindi+English WhatsApp message by RCA."""
from churn_analysis.skills.base_skill import Skill, SkillResult

_TEMPLATES = {
    "NO_LEADS": {
        "hi": (
            "{name} Bhai, aapka account review kiya maine —\n"
            "aapki category mein national buyers (Delhi, Mumbai) actively\n"
            "search kar rahe hain abhi. Local se zyada reach milegi.\n"
            "Ek setting change 2 min mein kar dete hain? 📱"
        ),
        "en": (
            "Hi {name}, reviewed your account —\n"
            "Buyers from Delhi/Mumbai are actively searching your category.\n"
            "A quick geography setting change could get you more leads.\n"
            "Can we do this together? Takes 2 min. 📱"
        ),
        "cta": "Reply YES for a quick setup call",
    },
    "LOW_ENGAGEMENT": {
        "hi": (
            "{name} Bhai, aapke {enq_30d} leads last week respond nahi hue —\n"
            "koi notification issue toh nahi aaya?\n"
            "Mobile pe setup karein saath mein, 5 minute mein ho jaata hai. 🔔"
        ),
        "en": (
            "Hi {name}, your {enq_30d} leads went unanswered last week —\n"
            "Seems like a notification issue.\n"
            "Let's fix it together — 5 minutes on mobile. 🔔"
        ),
        "cta": "Reply YES to fix notification setup",
    },
    "POOR_CATALOG": {
        "hi": (
            "{name} Bhai, aapke peer sellers jo zyada leads le rahe hain\n"
            "unka ek simple difference hai — zyada product photos aur description.\n"
            "Aapka CQS {cqs} hai, {peer_cqs} tak laane se leads ~30% badhti hain. 📸"
        ),
        "en": (
            "Hi {name}, sellers getting more leads have one simple edge —\n"
            "more product photos & descriptions.\n"
            "Your CQS is {cqs}. Getting it to {peer_cqs} can increase leads by ~30%. 📸"
        ),
        "cta": "Reply YES for a catalog quality walkthrough",
    },
    "PEER_GAP": {
        "hi": (
            "{name} Bhai, aapki city mein ek seller same category mein\n"
            "last month {peer_median_enq} leads le gaya. Aapko {enq_30d} mili.\n"
            "Woh ek specific cheez kar raha hai — bataaun? 👇"
        ),
        "en": (
            "Hi {name}, a seller in your city & category got {peer_median_enq} leads last month.\n"
            "You got {enq_30d}.\n"
            "There's one specific thing they're doing differently — want me to share? 👇"
        ),
        "cta": "Reply YES to see what's working for peers",
    },
    "LOW_PNS_RESPONSE": {
        "hi": (
            "{name} Bhai, kaafi incoming buyer calls miss ho rahi hain aapki.\n"
            "PNS answer rate sirf {pns_success_pct}% hai — normally 60%+ hoti hai.\n"
            "Phone setting check karein — ek step mein fix ho jaata hai. 📞"
        ),
        "en": (
            "Hi {name}, you're missing a lot of incoming buyer calls.\n"
            "PNS answer rate is {pns_success_pct}% (should be 60%+).\n"
            "One quick phone setting fixes this. 📞"
        ),
        "cta": "Reply YES to fix missed calls",
    },
    "BL_DECLINE": {
        "hi": (
            "{name} Bhai, maine aapka account dekha — leads {bl_velocity_pct_abs}% kam ho gayi hain.\n"
            "Iska ek specific reason hai, aur solve bhi ho sakta hai.\n"
            "Kya ek minute baat kar sakte hain? 🤝"
        ),
        "en": (
            "Hi {name}, your leads dropped {bl_velocity_pct_abs}% last month.\n"
            "There's a specific reason — and a fix.\n"
            "Can we connect for a quick call? 🤝"
        ),
        "cta": "Reply YES for a 5-min call",
    },
    "RAG_RISK": {
        "hi": (
            "{name} Bhai, aapka account review kiya maine.\n"
            "Kuch areas hain jahan saath mein kaam kar sakte hain leads improve karne ke liye.\n"
            "Ek quick call schedule karein? 📊"
        ),
        "en": (
            "Hi {name}, reviewed your account.\n"
            "There are a few areas we can work on together to improve your lead flow.\n"
            "Can we schedule a quick call? 📊"
        ),
        "cta": "Reply YES to schedule a review call",
    },
}

_DEFAULT_TEMPLATE = {
    "hi": (
        "{name} Bhai, aapka IndiaMART account review kiya.\n"
        "Kuch quick improvements hain jo leads badha sakti hain.\n"
        "Ek call karein? 📞"
    ),
    "en": (
        "Hi {name}, reviewed your IndiaMART account.\n"
        "There are a few quick improvements that could boost your leads.\n"
        "Can we connect? 📞"
    ),
    "cta": "Reply YES for a quick review call",
}


def _fmt(template: str, **kw) -> str:
    try:
        return template.format(**kw)
    except Exception:
        return template


class WhatsAppMessageSkill(Skill):
    name = "whatsapp-message"
    version = "1.0"
    required_inputs = ["glid"]
    optional_inputs = [
        "company", "seller_name", "city", "enterprise", "rca_category",
        "rca_explanation_hi", "peer_delta_pct", "peer_median_enq",
        "enq_30d", "cqs", "days_to_renewal", "message_type",
        "pns_success_pct", "bl_velocity_pct", "llm_reasoning",
    ]

    def invoke(self, inputs: dict) -> SkillResult:
        name         = inputs.get("seller_name") or inputs.get("company") or "Bhai"
        rca          = (inputs.get("rca_category") or "").strip()
        enq_30       = inputs.get("enq_30d") or 0
        cqs          = inputs.get("cqs") or "—"
        peer_median  = inputs.get("peer_median_enq") or "—"
        peer_cqs     = inputs.get("peer_benchmark_result", {}).get("peer_median_cqs") or "—"
        pns_pct      = inputs.get("pns_success_pct") or "—"
        bl_vel       = inputs.get("bl_velocity_pct")
        msg_type     = inputs.get("message_type") or "retention_nudge"

        bl_vel_abs = f"{abs(bl_vel)}" if bl_vel is not None else "—"

        fmt_kw = {
            "name":             name,
            "enq_30d":          enq_30,
            "cqs":              cqs,
            "peer_cqs":         peer_cqs,
            "peer_median_enq":  peer_median,
            "pns_success_pct":  pns_pct,
            "bl_velocity_pct_abs": bl_vel_abs,
        }

        tmpl = _TEMPLATES.get(rca, _DEFAULT_TEMPLATE)
        msg_hi = _fmt(tmpl["hi"], **fmt_kw)
        msg_en = _fmt(tmpl["en"], **fmt_kw)
        cta    = tmpl.get("cta", "Reply YES for assistance")

        return SkillResult(
            success=True,
            data={
                "message_hi":          msg_hi,
                "message_en":          msg_en,
                "message_type":        msg_type,
                "rca_used":            rca or "DEFAULT",
                "cta":                 cta,
                "personalization_vars": [k for k, v in fmt_kw.items() if str(v) != "—"],
                "estimated_open_rate": 0.72,
            },
            confidence=0.9,
        )

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        name = inputs.get("seller_name") or inputs.get("company") or "Seller"
        return SkillResult(
            success=True,
            data={
                "message_hi": f"{name} Bhai, aapka account review kiya. Kuch quick improvements hain — ek call karein?",
                "message_en": f"Hi {name}, reviewed your account. Quick call to improve leads?",
                "message_type": "retention_nudge",
                "rca_used": "FALLBACK",
                "cta": "Reply YES",
                "estimated_open_rate": 0.60,
            },
            confidence=0.4, used_fallback=True,
        )
