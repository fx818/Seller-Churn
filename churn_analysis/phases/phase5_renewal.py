"""Phase 5 — Renewal Window Boost Engine.

Filters sellers with ctype in (CATALOG, FCP+PNS) and account_age_days > 90.
Generates PRE_RENEWAL_BOOST, RENEWAL_DAY_DELIVERY, or POST_RENEWAL_REINFORCE
messages in Hindi + English based on days_to_renewal.
"""
import os
import json
import sys
from datetime import datetime, timezone

from ..skills.registry import registry

_ELIGIBLE_CTYPES = {"CATALOG", "FCP+PNS", "FCP_PNS", "FCPPNS"}

# ---------------------------------------------------------------------------
# Message templates (Hindi + English)
# ---------------------------------------------------------------------------

_PRE_RENEWAL_BOOST_HI = (
    "आपकी सदस्यता जल्द नवीनीकृत होने वाली है! अभी रिन्यू करें और "
    "3-5 प्रीमियम लीड्स मुफ़्त पाएं। ऑफर सीमित समय के लिए है।"
)
_PRE_RENEWAL_BOOST_EN = (
    "Your subscription is renewing soon! Renew now and unlock 3-5 premium leads "
    "at no extra cost. Limited-time offer — act fast!"
)

_RENEWAL_DAY_HI = (
    "आज आपकी सदस्यता नवीनीकृत हो गई है। बधाई! तुरंत लीड डिलीवरी शुरू "
    "हो गई है — अपना डैशबोर्ड जांचें।"
)
_RENEWAL_DAY_EN = (
    "Your subscription has been renewed today — congratulations! "
    "Immediate lead delivery is now active. Check your dashboard."
)

_POST_RENEWAL_HI = (
    "नवीनीकरण के बाद आपको 7 दिनों तक उच्च-गुणवत्ता वाली लीड्स मिलेंगी। "
    "जल्दी जवाब दें और अपनी रैंकिंग बढ़ाएं।"
)
_POST_RENEWAL_EN = (
    "Welcome back! For the next 7 days you receive elevated-quality leads "
    "as part of our post-renewal programme. Reply quickly to maximise your rank."
)


def _compute_days_to_renewal(seller: dict) -> int:
    """Return days_to_renewal using 365 - (account_age_days % 365)."""
    age = int(seller.get("account_age_days", seller.get("account_age", 0)))
    days_to = 365 - (age % 365)
    # Edge case: exactly on anniversary -> 0
    if days_to == 365:
        days_to = 0
    return days_to


def _determine_sub_action(days_to_renewal: int, account_age_days: int) -> str | None:
    """Return the renewal sub-action key or None if no action applies."""
    if days_to_renewal == 0:
        return "RENEWAL_DAY_DELIVERY"
    if days_to_renewal <= 7:
        return "PRE_RENEWAL_BOOST"
    # POST_RENEWAL_REINFORCE: just renewed (account_age % 365 <= 7, i.e. within 7 days post-renewal)
    days_since_renewal = account_age_days % 365
    if days_since_renewal <= 7 and days_since_renewal > 0:
        return "POST_RENEWAL_REINFORCE"
    return None


def run_phase5(run_dir: str, sellers: list, phase2_results: dict = None) -> dict:
    """Generate renewal boost flags and messages for eligible sellers.

    Args:
        run_dir: Path like 'runs/run_20260515_120000/'
        sellers: List of seller dicts
        phase2_results: Raw skill outputs per GLID from phase2 '_phase2_results'

    Returns:
        Renewal boost flags dict (also written to disk)
    """
    phase2_results = phase2_results or {}

    action_dir = os.path.join(run_dir, "action_plans")
    os.makedirs(action_dir, exist_ok=True)

    flags = {}
    total_eligible = 0
    sub_action_counts = {
        "PRE_RENEWAL_BOOST": 0,
        "RENEWAL_DAY_DELIVERY": 0,
        "POST_RENEWAL_REINFORCE": 0,
    }

    for seller in sellers:
        glid = str(seller.get("glid", ""))
        try:
            ctype = str(seller.get("ctype", "")).upper().replace("+", "_").replace(" ", "")
            age = int(seller.get("account_age_days", seller.get("account_age", 0)))

            # Filter: eligible ctypes + established (> 90 days)
            if ctype not in _ELIGIBLE_CTYPES or age <= 90:
                continue

            days_to_renewal = _compute_days_to_renewal(seller)
            sub_action = _determine_sub_action(days_to_renewal, age)

            if sub_action is None:
                continue  # No renewal window action for this seller right now

            total_eligible += 1
            sub_action_counts[sub_action] = sub_action_counts.get(sub_action, 0) + 1

            # Select message templates
            if sub_action == "PRE_RENEWAL_BOOST":
                msg_hi = _PRE_RENEWAL_BOOST_HI
                msg_en = _PRE_RENEWAL_BOOST_EN
            elif sub_action == "RENEWAL_DAY_DELIVERY":
                msg_hi = _RENEWAL_DAY_HI
                msg_en = _RENEWAL_DAY_EN
            else:  # POST_RENEWAL_REINFORCE
                msg_hi = _POST_RENEWAL_HI
                msg_en = _POST_RENEWAL_EN

            # Enrich with gifted_lead if appropriate
            p2 = phase2_results.get(glid, {})
            churn_score = p2.get("final_score") or p2.get("churn_scoring", {}).get("churn_score", 50)

            gifted_lead_data = None
            if sub_action in ("PRE_RENEWAL_BOOST", "RENEWAL_DAY_DELIVERY"):
                gl_result = registry.run("gifted_lead", {
                    "glid": glid,
                    "company": seller.get("company", ""),
                    "city": seller.get("city", ""),
                    "ctype": seller.get("ctype", ""),
                    "account_age_days": age,
                    "enq_30d": seller.get("enq_30d", 0),
                    "churn_score": churn_score,
                    "sub_action": sub_action,
                })
                gifted_lead_data = gl_result.data if gl_result.success else {"error": gl_result.error}

            flags[glid] = {
                "glid": glid,
                "company": seller.get("company", ""),
                "city": seller.get("city", ""),
                "ctype": seller.get("ctype", ""),
                "account_age_days": age,
                "days_to_renewal": days_to_renewal,
                "sub_action": sub_action,
                "renewal_message_hi": msg_hi,
                "renewal_message_en": msg_en,
                "gifted_lead": gifted_lead_data,
            }

        except Exception as exc:
            print(f"[phase5] ERROR for glid={glid}: {exc}", file=sys.stderr)
            flags[glid] = {
                "glid": glid,
                "company": seller.get("company", ""),
                "error": str(exc),
            }

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_eligible": total_eligible,
        "sub_action_counts": sub_action_counts,
        "flags": flags,
    }

    out_path = os.path.join(action_dir, "renewal_boost_flags.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(result, ensure_ascii=False, default=str, indent=2))

    print(f"[phase5] Written {out_path}  (eligible={total_eligible}, counts={sub_action_counts})")
    return result


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    _sample_sellers = [
        {
            "glid": "9999003", "company": "Sunrise Exports", "city": "Ahmedabad",
            "ctype": "CATALOG", "rag": "Amber",
            "account_age": 358, "account_age_days": 358,  # 7 days to renewal
            "paid_history": True, "mcats": ["Handicrafts"], "cqs": 60,
            "enq_30d": 5, "replied_30d": 4, "active_days_30d": 15,
            "bl_velocity_pct": 2.0, "pns_success_pct": 70.0,
            "hotleads_count": 1, "event_count": 3, "monthly_enq": 6,
        },
        {
            "glid": "9999004", "company": "Global Spices", "city": "Kochi",
            "ctype": "FCP+PNS", "rag": "Green",
            "account_age": 365, "account_age_days": 365,  # Renewal day
            "paid_history": True, "mcats": ["Spices"], "cqs": 75,
            "enq_30d": 20, "replied_30d": 18, "active_days_30d": 28,
            "bl_velocity_pct": 8.0, "pns_success_pct": 90.0,
            "hotleads_count": 5, "event_count": 10, "monthly_enq": 22,
        },
    ]
    _run_dir = os.path.join(os.path.dirname(__file__), "..", "..", "runs", "sample_run")
    out = run_phase5(_run_dir, _sample_sellers)
    print(json.dumps(out, indent=2, default=str))
