"""SKILL 5 — OnboardingHealthSkill: 7-check health for new sellers (account_age ≤ 90d).

Upgrades over v1.1:
  - Check 6: CQS gate (catalog quality from snapshot)
  - Check 7: Catalog completeness (product count vs days-since-signup expectation)
  - City-risk prior: high-risk cities get a flat -15 penalty
  - Category-risk prior: high-risk categories get a flat -10 penalty
  - LLM-personalized first-week activation plan (with template fallback)
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


# ── Constants ────────────────────────────────────────────────────────────────

_HIGH_RISK_CITIES = {
    "lucknow", "kanpur", "saharanpur", "surat", "jaipur",
    "agra", "varanasi", "meerut", "ghaziabad",
}

_HIGH_RISK_CATEGORIES = {
    "apparel", "textiles", "garments", "clothing", "fabric",
}


def _tier(score: float, high: float = 70, low: float = 40) -> str:
    return "Green" if score >= high else ("Amber" if score >= low else "Red")


# ── LLM helpers (re-use the pattern from script_generation) ─────────────────

_LLM_SYSTEM_ONBOARDING = (
    "You are an IndiaMART onboarding success coach. Generate a personalized "
    "first-week activation plan (3-5 concrete tasks) for a NEW seller, based on "
    "their actual signals. Output Hindi-primary (Devanagari Hindi in Latin script, "
    "code-mixed with English business terms like 'catalog', 'photos', 'notifications'). "
    "Reference the seller's real numbers. Each task should be doable in < 15 minutes. "
    "Return STRICT JSON only — no markdown."
)

_LLM_USER_ONBOARDING_TEMPLATE = """\
NEW SELLER ONBOARDING PROFILE
-----------------------------
Company:           {company}
City:              {city}  (high_risk_city={hrc})
Customer type:     {ctype}
Account age:       {age} days
Verified:          paid_history={paid_hist}, rag={rag}

CATALOG & QUALITY
-----------------
CQS:               {cqs}/100  (threshold for Green: >=70)
IM products:       {im_products}  (expected for age {age}d: ~{expected_products})
Approved products: {approved_products}

ENGAGEMENT (first 30d)
----------------------
BLs received:      {enq_30}
BLs replied:       {replied_30}
Reply rate:        {reply_rate}%

MARKET CONTEXT
--------------
Category demand tier: {demand_tier}
Demand explanation:   {demand_explanation}
Peer benchmark:       {peer_summary}
Enq percentile:       {enq_percentile}

ONBOARDING HEALTH ASSESSMENT
----------------------------
Composite score:   {health_score}/100  ({health_tier})
Red-tier checks:   {red_checks}

INSTRUCTIONS
------------
Write a 3-5 task activation plan for the first week. Each task:
  - title:        short Hindi (e.g. "Catalog mein 5 products add karein")
  - title_en:     English version
  - reason:       why this matters for THIS seller (use real data)
  - reason_en:    English version
  - effort_min:   estimated minutes to complete
  - priority:     "critical" | "high" | "medium"
  - rep_action:   what the rep does on the call to enable this

Also include:
  - opening_pitch_hi: first 2 sentences the rep should say on the activation call
  - opening_pitch_en: English version
  - tone:        "urgent" | "supportive" | "educational" (based on health_tier)

Return STRICT JSON:
{{
  "tasks": [
    {{"title": "...", "title_en": "...", "reason": "...", "reason_en": "...",
      "effort_min": 5, "priority": "critical", "rep_action": "..."}}
  ],
  "opening_pitch_hi": "...",
  "opening_pitch_en": "...",
  "tone": "supportive",
  "personalization_signals_used": ["short list"]
}}
"""


def _call_llm(system: str, user: str, model: str, timeout: int = 60) -> str:
    base    = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        raise RuntimeError("LLM_API_KEY not set")
    url = f"{base}/chat/completions"
    resp = _requests.post(
        url,
        json={
            "model":      model,
            "max_tokens": 3500,    # plan can be verbose (Hindi + English per task)
            "temperature": 0.4,
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
    """Parse LLM JSON output, tolerant of common formatting issues."""
    text = (text or "").strip()
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)

    # First try as-is
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try removing trailing commas before } or ]
    fixed = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Try replacing single quotes around keys/strings with double
    fixed = re.sub(r"(?<=[\{\[,:\s])'([^']*?)'", r'"\1"', text)
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Last resort: try parsing just the "tasks" array and reconstruct
    raise json.JSONDecodeError("Could not parse LLM JSON", text, 0)


def _template_activation_plan(checks: dict, tier: str, company: str) -> dict:
    """Deterministic fallback activation plan."""
    seller = (company or "Bhai").split()[0]
    tasks = []

    # Always include a setup task
    if checks.get("first_bl_response", {}).get("tier") == "Red":
        tasks.append({
            "title":     "Mobile app pe notifications enable karein",
            "title_en":  "Enable notifications on the mobile app",
            "reason":    "Pichle 30 din mein BLs aayi lekin reply nahi hua — notification setup issue",
            "reason_en": "BLs received but no replies — likely notification setup issue",
            "effort_min": 5,
            "priority":  "critical",
            "rep_action": "Walk through mobile app notification settings live on the call",
        })

    if checks.get("verification", {}).get("tier") in ("Red", "Amber"):
        tasks.append({
            "title":     "Documentation upload karein (GST + business proof)",
            "title_en":  "Upload documentation (GST + business proof)",
            "reason":    "Verification pending — buyers verified sellers ko prefer karte hain",
            "reason_en": "Verification pending — verified sellers get more buyer trust",
            "effort_min": 10,
            "priority":  "high",
            "rep_action": "Share upload link via WhatsApp; remind in 48h if not done",
        })

    if checks.get("catalog_completeness", {}).get("tier") in ("Red", "Amber"):
        tasks.append({
            "title":     "5 products add karein, har product mein 3+ photos",
            "title_en":  "Add 5 products with at least 3 photos each",
            "reason":    "Buyers pehle photos dekhte hain — minimum 3 photos per product chahiye",
            "reason_en": "Buyers look at photos first — minimum 3 photos per product",
            "effort_min": 15,
            "priority":  "high",
            "rep_action": "Co-create one product live; seller does the rest",
        })

    if checks.get("cqs_quality", {}).get("tier") in ("Red", "Amber"):
        tasks.append({
            "title":     "Product titles + descriptions improve karein",
            "title_en":  "Improve product titles and descriptions",
            "reason":    "Catalog Quality Score (CQS) below threshold — search ranking pe affect ho raha hai",
            "reason_en": "Catalog Quality Score below threshold — affects search ranking",
            "effort_min": 12,
            "priority":  "medium",
            "rep_action": "Suggest 2-3 keyword improvements per product",
        })

    if not tasks:
        tasks.append({
            "title":     "Daily 5 min platform pe spend karein",
            "title_en":  "Spend 5 minutes daily on the platform",
            "reason":    "Account healthy hai — bas daily engagement maintain karna hai",
            "reason_en": "Account is healthy — just maintain daily engagement",
            "effort_min": 5,
            "priority":  "medium",
            "rep_action": "Recommend a daily 5-min check-in routine",
        })

    if tier == "Red":
        opening_hi = f"{seller} bhai, account dekha — kuch important cheezein setup karni hain, abhi 15-20 minute ke liye time mil sakta hai?"
        opening_en = f"{seller} ji, reviewed your account — there are a few critical setup items. Got 15-20 minutes right now?"
        tone = "urgent"
    elif tier == "Amber":
        opening_hi = f"{seller} bhai, setup almost complete hai — 2-3 small steps remaining, saath mein 10 minute mein finish kar dete hain?"
        opening_en = f"{seller} ji, your setup is almost complete — 2-3 quick steps remain. Can we finish them together in 10 minutes?"
        tone = "supportive"
    else:
        opening_hi = f"{seller} bhai, account healthy lag raha hai — bas ek check-in call hai, sab theek?"
        opening_en = f"{seller} ji, your account looks healthy — just a quick check-in call. Everything good?"
        tone = "educational"

    return {
        "tasks":            tasks,
        "opening_pitch_hi": opening_hi,
        "opening_pitch_en": opening_en,
        "tone":             tone,
        "personalization_signals_used": [],
    }


def _expected_products_for_age(age_days: int) -> int:
    """Heuristic: how many products should a seller have uploaded by day N."""
    if age_days <= 7:    return 3
    if age_days <= 30:   return 8
    if age_days <= 60:   return 15
    return 20


# ── Skill ────────────────────────────────────────────────────────────────────

class OnboardingHealthSkill(Skill):
    name = "onboarding-health"
    version = "2.0"
    required_inputs = ["glid"]
    optional_inputs = [
        # Identity
        "account_age_days", "city", "enterprise", "ctype", "company",
        "paid_history", "rag",
        # Quality + engagement
        "cqs", "enq_30d", "replied_30d",
        # Catalog
        "im_product_count", "approved_products",
        "mcats",
        # Nested result dicts (backward compatible)
        "demand_index_result", "peer_benchmark_result",
        # Flat flow keys from upstream phase0_benchmark
        "demand_tier", "demand_explanation", "demand_index",
        "enq_percentile", "peer_median_enq", "gap_severity",
        "peer_summary_line",
        # LLM controls
        "model", "force_template",
    ]

    def invoke(self, inputs: dict) -> SkillResult:
        age        = inputs.get("account_age_days") or 0
        city       = (inputs.get("city") or "").lower().strip()
        ctype      = (inputs.get("ctype") or inputs.get("enterprise") or "").upper()
        cqs        = inputs.get("cqs")
        enq_30     = inputs.get("enq_30d") or 0
        replied_30 = inputs.get("replied_30d") or 0
        paid_hist  = inputs.get("paid_history") or False
        rag        = (inputs.get("rag") or "").strip()
        company    = inputs.get("company") or ""
        mcats      = inputs.get("mcats") or []
        demand_res = inputs.get("demand_index_result") or {}
        peer_res   = inputs.get("peer_benchmark_result") or {}

        # Product count: prefer flow (cross_platform), fallback to snapshot
        im_products = (
            inputs.get("im_product_count")
            or inputs.get("approved_products")
            or 0
        )

        # Reply rate (used by LLM prompt)
        reply_rate = round(replied_30 / enq_30 * 100, 1) if enq_30 > 0 else 0

        checks = {}

        # ── Check 1: Category Demand (weight 25%) ─────────────────────────────
        demand_tier  = inputs.get("demand_tier") or demand_res.get("demand_tier") or "Amber"
        demand_msg   = (inputs.get("demand_explanation")
                        or demand_res.get("demand_explanation")
                        or "Demand data unavailable")
        demand_score = 100 if demand_tier == "Green" else (50 if demand_tier == "Amber" else 10)
        checks["demand"] = {
            "score":  demand_score,
            "weight": 0.25,
            "tier":   demand_tier,
            "note":   demand_msg,
        }

        # ── Check 2: Business Verification (weight 10%) ───────────────────────
        verified     = paid_hist and rag != "Red"
        verif_score  = 100 if verified else (50 if paid_hist else 0)
        verif_tier   = "Green" if verified else ("Amber" if paid_hist else "Red")
        checks["verification"] = {
            "score":  verif_score,
            "weight": 0.10,
            "tier":   verif_tier,
            "note":   ("Paid history + healthy RAG" if verified else
                       ("Paid history but RAG risk" if paid_hist else "No paid history — high early-churn risk")),
        }

        # ── Check 3: Peer Benchmark Gap (weight 10%) ──────────────────────────
        enq_pct = inputs.get("enq_percentile")
        if enq_pct is None:
            enq_pct = peer_res.get("enq_percentile", 50)
        peer_score   = max(0, min(100, enq_pct))
        peer_tier    = _tier(peer_score, 60, 30)
        peer_summary = (inputs.get("peer_summary_line")
                        or peer_res.get("peer_summary_line")
                        or "Peer data not available")
        checks["peer_gap"] = {
            "score":  peer_score,
            "weight": 0.10,
            "tier":   peer_tier,
            "note":   peer_summary,
        }

        # ── Check 4: First BL Response (weight 15%) ───────────────────────────
        if enq_30 == 0:
            first_bl_score, first_bl_tier = 40, "Amber"
            first_bl_note  = "No BLs received yet — too early to assess"
        elif replied_30 > 0:
            first_bl_score, first_bl_tier = 100, "Green"
            first_bl_note  = f"Responded to {replied_30} of {enq_30} BLs ({reply_rate}%)"
        else:
            first_bl_score, first_bl_tier = 0, "Red"
            first_bl_note  = f"Received {enq_30} BLs but replied to none — lead setup issue"
        checks["first_bl_response"] = {
            "score":  first_bl_score,
            "weight": 0.15,
            "tier":   first_bl_tier,
            "note":   first_bl_note,
        }

        # ── Check 5: Package Type (weight 10%) ────────────────────────────────
        if "CATALOG" in ctype or "FCP" in ctype or "PNS" in ctype:
            pkg_score, pkg_tier = 80, "Green"
            pkg_note = f"Package {ctype} — standard onboarding track"
        elif "FREE" in ctype or "FREELIST" in ctype:
            pkg_score, pkg_tier = 30, "Amber"
            pkg_note = "FREELIST — higher early-churn risk; upgrade conversation recommended"
        else:
            pkg_score, pkg_tier = 50, "Amber"
            pkg_note = f"Package type {ctype or 'unknown'} — standard monitoring"
        checks["package_type"] = {
            "score":  pkg_score,
            "weight": 0.10,
            "tier":   pkg_tier,
            "note":   pkg_note,
        }

        # ── Check 6: CQS Gate (weight 15%) ────────────────────────────────────
        # CQS = Catalog Quality Score from IndiaMART. Threshold: >=70 healthy.
        if cqs is None:
            cqs_score, cqs_tier = 50, "Amber"
            cqs_note = "CQS not available — flag for catalog quality check"
        elif cqs >= 70:
            cqs_score, cqs_tier = 100, "Green"
            cqs_note = f"CQS {cqs}/100 — healthy catalog quality"
        elif cqs >= 50:
            cqs_score, cqs_tier = 60, "Amber"
            cqs_note = f"CQS {cqs}/100 — below ideal, improve product titles + photos"
        else:
            cqs_score, cqs_tier = 15, "Red"
            cqs_note = f"CQS {cqs}/100 — critical, will hurt buyer visibility"
        checks["cqs_quality"] = {
            "score":  cqs_score,
            "weight": 0.15,
            "tier":   cqs_tier,
            "note":   cqs_note,
        }

        # ── Check 7: Catalog Completeness (weight 15%) ────────────────────────
        # Expected product count grows with seller age.
        expected = _expected_products_for_age(age)
        if im_products == 0:
            cat_score, cat_tier = 0, "Red"
            cat_note = "No products listed — critical onboarding gap"
        elif im_products >= expected:
            cat_score, cat_tier = 100, "Green"
            cat_note = f"{im_products} products listed (target by day {age}: {expected}) — on track"
        elif im_products >= expected * 0.5:
            cat_score, cat_tier = 60, "Amber"
            cat_note = f"{im_products} products listed (target: {expected}) — needs more catalog depth"
        else:
            cat_score, cat_tier = 25, "Red"
            cat_note = f"Only {im_products} products (target: {expected}) — significant catalog gap"
        checks["catalog_completeness"] = {
            "score":  cat_score,
            "weight": 0.15,
            "tier":   cat_tier,
            "note":   cat_note,
        }

        # ── Composite score ───────────────────────────────────────────────────
        base_score = sum(c["score"] * c["weight"] for c in checks.values())

        # ── Risk priors (flat penalties) ──────────────────────────────────────
        priors = []
        prior_penalty = 0
        if city and any(city.startswith(c) for c in _HIGH_RISK_CITIES):
            prior_penalty += 15
            priors.append({
                "type": "high_risk_city", "value": city,
                "penalty": 15,
                "note":   f"{city.title()} is a historically high-churn onboarding city",
            })
        mcat_text = " ".join(str(m) for m in mcats).lower() if mcats else ""
        if any(cat in mcat_text for cat in _HIGH_RISK_CATEGORIES):
            prior_penalty += 10
            matched = next(cat for cat in _HIGH_RISK_CATEGORIES if cat in mcat_text)
            priors.append({
                "type": "high_risk_category", "value": matched,
                "penalty": 10,
                "note":   f"{matched.title()} category has higher onboarding churn",
            })

        onboarding_score = round(max(0, min(100, base_score - prior_penalty)))
        onboarding_risk  = _tier(onboarding_score, 65, 35)

        # ── Trigger ───────────────────────────────────────────────────────────
        if onboarding_risk == "Red":
            trigger = "HUMAN_CALL_24H"
            hint = "Urgent setup call: lead management + notification setup. Frame as activation, not sales."
        elif onboarding_risk == "Amber":
            trigger = "WHATSAPP_SETUP_GUIDE"
            hint = "Send WhatsApp guide + follow up in 48h if no engagement."
        else:
            trigger = "MONITOR_7D"
            hint = "Healthy onboarding — automated nurture, check again at day 30."

        # ── LLM-personalized activation plan ──────────────────────────────────
        force_template = bool(inputs.get("force_template"))
        red_checks_str = ", ".join(k for k, c in checks.items() if c["tier"] == "Red") or "(none)"
        plan = None
        llm_used = False
        llm_error = None

        if not force_template and os.getenv("LLM_API_KEY"):
            try:
                model = inputs.get("model") or os.getenv("LLM_MODEL", "gpt-4o-mini")
                hrc = any(city.startswith(c) for c in _HIGH_RISK_CITIES)
                user_prompt = _LLM_USER_ONBOARDING_TEMPLATE.format(
                    company=company or "—",
                    city=city or "—",
                    hrc=hrc,
                    ctype=ctype or "—",
                    age=age,
                    paid_hist=paid_hist,
                    rag=rag or "—",
                    cqs=cqs if cqs is not None else "—",
                    im_products=im_products,
                    expected_products=expected,
                    approved_products=inputs.get("approved_products", "—"),
                    enq_30=enq_30,
                    replied_30=replied_30,
                    reply_rate=reply_rate,
                    demand_tier=demand_tier,
                    demand_explanation=demand_msg,
                    peer_summary=peer_summary,
                    enq_percentile=enq_pct,
                    health_score=onboarding_score,
                    health_tier=onboarding_risk,
                    red_checks=red_checks_str,
                )
                raw    = _call_llm(_LLM_SYSTEM_ONBOARDING, user_prompt, model)
                parsed = _parse_llm_json(raw)
                if parsed.get("tasks") and parsed.get("opening_pitch_hi"):
                    plan = parsed
                    llm_used = True
                else:
                    raise ValueError("LLM returned incomplete plan")
            except Exception as exc:
                llm_error = str(exc)[:200]

        if plan is None:
            plan = _template_activation_plan(checks, onboarding_risk, company)

        # ── Result ────────────────────────────────────────────────────────────
        data = {
            # Canonical keys
            "health_score":     onboarding_score,
            "health_tier":      onboarding_risk,
            "checks":           checks,
            "risk_priors":      priors,
            "prior_penalty":    prior_penalty,
            "base_score":       round(base_score, 1),
            # Activation plan
            "activation_plan":  plan,
            "plan_method":      "llm" if llm_used else "template",
            # Triggers + hints
            "trigger_action":   trigger,
            "call_script_hint": hint,
            "account_age_days": age,
            "is_new_seller":    age <= 90,
            "alerts":           [c["note"] for c in checks.values() if c["tier"] == "Red"],
            "recommendations":  [hint],
            "expected_products": expected,
            # Back-compat
            "onboarding_score": onboarding_score,
            "onboarding_risk":  onboarding_risk,
            "check_results":    checks,
        }
        if llm_error:
            data["llm_error"] = llm_error

        confidence = 0.88 if llm_used else 0.75
        return SkillResult(success=True, data=data, confidence=confidence)

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=False,
            data={"onboarding_score": None, "health_score": None,
                  "onboarding_risk": "Unknown", "health_tier": "Unknown",
                  "trigger_action": "DATA_INSUFFICIENT"},
            error=str(error), confidence=0.1, used_fallback=True,
        )
