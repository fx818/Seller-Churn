"""
Extracts a structured Snapshot from raw slim_loader API responses.
All field extraction is defensive — missing fields yield None/[].
"""
import json
from collections import Counter
from datetime import datetime, timedelta


def _safe_parse(val):
    if isinstance(val, str):
        val = val.strip()
        if val.startswith("{") or val.startswith("["):
            try:
                return _safe_parse(json.loads(val))
            except Exception:
                pass
    if isinstance(val, dict):
        return {k: _safe_parse(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_safe_parse(i) for i in val]
    return val


def _g(d, *keys, default=None):
    """Safe nested get."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
        if cur is None:
            return default
    return cur


def extract_snapshot(glid: int | str, label: str, api_responses: dict) -> dict:
    """
    glid        — seller GLID
    label       — 'retained' | 'churned' | 'target'
    api_responses — dict returned by slim_loader.fetch_for_glid()

    Returns Snapshot dict with context + behavioral sub-dicts.
    """
    g = str(glid)

    # ── scorecard_summary ───────────────────────────────────────────────────────
    ss_raw = api_responses.get("scorecard_summary", {})
    ss_inner = _safe_parse(_g(ss_raw, "data", "response", default="{}"))
    ss = (ss_inner.get("summary") or [{}])[0] if isinstance(ss_inner, dict) else {}

    def _period(field, period):
        d = _safe_parse(ss.get(field, "{}"))
        if isinstance(d, dict):
            return d.get(period) or 0
        return 0

    city         = ss.get("gl_city_name") or ""
    state_code   = ss.get("gl_state_code") or ""
    enterprise   = ss.get("enterprise_type") or ""
    last_succ_call = ss.get("last_succ_call_dt")
    last_succ_call_summary = ss.get("last_succ_call_dt_1m_plus")

    # BL from scorecard_summary (received = tot_enq, consumed = bl_all_cons)
    bl_received_90d  = _period("tot_enq", "90d")
    bl_consumed_90d  = _period("bl_all_cons", "90d")
    bl_received_30d  = _period("tot_enq", "30d")
    bl_consumed_30d  = _period("bl_all_cons", "30d")
    pns_recd_90d     = _period("pns_calls_recd", "90d")
    pns_recd_30d     = _period("pns_calls_recd", "30d")
    call_attempted_90d  = _period("call_attempted", "90d")
    call_answered_90d   = _period("call_answered", "90d")
    calls_1min_90d      = _period("call_answered_1m_plus", "90d")
    lms_days_90d        = _period("lms_active_days", "90d")
    lms_days_30d        = _period("lms_active_days", "30d")
    enq_replied_90d     = _period("buyers_responded", "90d")

    # weekly BL active (last 5 weeks, w0=most recent)
    weekly_bl_raw = _safe_parse(ss.get("weekly_bl_active_days", "{}"))
    weekly_bl = []
    if isinstance(weekly_bl_raw, dict):
        for i in range(5):
            weekly_bl.append(weekly_bl_raw.get(f"w{i}") or 0)

    # ── scorecard_12m ──────────────────────────────────────────────────────────
    s12_raw  = api_responses.get("scorecard_12m", {})
    s12_inner = _safe_parse(_g(s12_raw, "data", "response", default="{}"))
    s12_months = []
    if isinstance(s12_inner, dict):
        s12_months = sorted(
            s12_inner.get("summary") or [],
            key=lambda x: x.get("year_month", 0)
        )

    monthly_trend = [
        {
            "year_month":    m.get("year_month"),
            "data_month":    m.get("data_month"),
            "bl_cons":       m.get("bl_cons") or 0,
            "total_enq":     m.get("total_enq") or 0,
            "lms_active_days": m.get("lms_active_days") or 0,
            "replies":       m.get("replies") or 0,
            "pns_calls_recd": m.get("pns_calls_recd") or 0,
            "pns_calls_ans": m.get("pns_calls_ans") or 0,
            "pns_success_prcnt": m.get("pns_success_prcnt"),
        }
        for m in s12_months
    ]

    # ── composite (ingestion) ──────────────────────────────────────────────────
    cp_raw = api_responses.get("composite", {})
    cp_d   = _g(cp_raw, "data") or {}
    prof   = cp_d.get("profile") or {}
    gst_d  = cp_d.get("gst") or {}
    eng    = cp_d.get("engagement") or {}

    company_name  = prof.get("company_name") or ""
    custtype      = prof.get("customer_type") or enterprise or ""
    account_age   = prof.get("account_age_days") or 0
    rag_category  = prof.get("rag_category") or ""
    paid_history  = prof.get("paid_history") or False
    turnover_slab = gst_d.get("annual_turnover_slab") or ""
    activity_30d  = eng.get("activity_30d") or 0
    cqs           = eng.get("cqs")

    # Normalise turnover slab → short label
    turnover = _normalise_turnover(turnover_slab)

    # ── product_details → mcats ────────────────────────────────────────────────
    pd_raw   = api_responses.get("product_details", {})
    pd_items = _g(pd_raw, "data", "data") or []
    mcats = list(dict.fromkeys(
        item["glcat_mcat_name"]
        for item in pd_items
        if isinstance(item, dict) and item.get("glcat_mcat_name")
    ))

    # ── metrics (ingestion) ───────────────────────────────────────────────────
    mt_raw = api_responses.get("metrics", {})
    mt_d   = _g(mt_raw, "data") or {}
    blni_count_1yr    = mt_d.get("blni_count_1yr") or 0
    enq_received_90d  = mt_d.get("enq_received_90d") or bl_received_90d
    enq_replies_90d   = mt_d.get("enq_replies_90d") or enq_replied_90d
    active_bl         = mt_d.get("active_bl")

    # ── activity (ingestion) ──────────────────────────────────────────────────
    ac_raw    = api_responses.get("activity", {})
    ac_d      = _g(ac_raw, "data") or {}
    event_count   = ac_d.get("event_count") or 0
    events        = ac_d.get("events") or []

    # Build daily_activity map: {YYYYMMDD: count}
    daily_activity: dict[str, int] = {}
    for ev in events:
        dv = str(ev.get("datevalue", ""))[:8]
        if dv:
            daily_activity[dv] = daily_activity.get(dv, 0) + 1

    # Weekly/monthly activity from daily_activity
    weekly_activity  = _aggregate_weekly(daily_activity, weeks=4)
    monthly_activity = _aggregate_monthly(daily_activity, months=3)

    # ── hotleads / blni counts ────────────────────────────────────────────────
    hl_raw = api_responses.get("hotleads", {})
    hl_items = _g(hl_raw, "data", "items") or []
    hotleads_count = len(hl_items)

    blni_raw = api_responses.get("blni", {})
    blni_items = _g(blni_raw, "data", "items") or []
    blni_count_90d = len(blni_items)

    # ── derived BL metrics ────────────────────────────────────────────────────
    consumption_rate = round(bl_consumed_90d / bl_received_90d, 4) if bl_received_90d > 0 else None
    reply_rate       = round(enq_replies_90d / enq_received_90d, 4) if enq_received_90d > 0 else None
    pickup_ratio_90d = round(call_answered_90d / call_attempted_90d, 4) if call_attempted_90d > 0 else None

    return {
        "glid":  int(g),
        "label": label,
        "context": {
            "company":   company_name,
            "turnover":  turnover,
            "turnover_raw": turnover_slab,
            "city":      city,
            "state":     state_code,
            "mcats":     mcats,
            "custtype":  custtype,
            "account_age_days": account_age,
            "rag_category":     rag_category,
            "paid_history":     paid_history,
        },
        "behavioral": {
            "bl": {
                "received_90d":    bl_received_90d,
                "consumed_90d":    bl_consumed_90d,
                "received_30d":    bl_received_30d,
                "consumed_30d":    bl_consumed_30d,
                "replied_90d":     enq_replies_90d,
                "consumption_rate": consumption_rate,
                "reply_rate":      reply_rate,
                "active_bl":       active_bl,
                "blni_count_1yr":  blni_count_1yr,
                "blni_count_90d":  blni_count_90d,
                "weekly_bl_active": weekly_bl,
                "hotleads_count":  hotleads_count,
            },
            "lms": {
                "call_attempts_90d":  call_attempted_90d,
                "call_answered_90d":  call_answered_90d,
                "call_pickup_ratio_90d": pickup_ratio_90d,
                "calls_1min_plus_90d": calls_1min_90d,
                "pns_received_90d":   pns_recd_90d,
                "lms_active_days_90d": lms_days_90d,
                "lms_active_days_30d": lms_days_30d,
                "last_succ_call_dt":  last_succ_call,
                "last_call_summary":  last_succ_call_summary,
            },
            "activity": {
                "activity_30d":    activity_30d,
                "event_count":     event_count,
                "cqs":             cqs,
                "weekly_activity": weekly_activity,
                "monthly_activity": monthly_activity,
                "monthly_trend":   monthly_trend,
                "daily_activity":  daily_activity,
            },
        },
    }


def _normalise_turnover(slab: str) -> str:
    """Map raw turnover slab string to a short canonical label."""
    if not slab:
        return "Unknown"
    s = slab.lower()
    if "40 l" in s or "40l" in s or "upto 40" in s:
        return "0 - 40 L"
    if "1.5 cr" in s or "40 l to 1.5" in s or "40l to 1.5" in s:
        return "40 L - 1.5 Cr"
    if "5 cr" in s or "1.5 cr to 5" in s:
        return "1.5 Cr - 5 Cr"
    if "25 cr" in s or "5 cr to 25" in s:
        return "5 Cr - 25 Cr"
    if "100 cr" in s or "25 cr to 100" in s:
        return "25 Cr - 100 Cr"
    if "100 cr" in s or "above 100" in s or "500 cr" in s:
        return "100 Cr+"
    return slab.strip()


def _aggregate_weekly(daily: dict, weeks: int = 4) -> list[int]:
    """Aggregate daily_activity into per-week totals (most recent week first)."""
    today = datetime.today()
    result = []
    for w in range(weeks):
        end   = today - timedelta(days=w * 7)
        start = end - timedelta(days=7)
        count = sum(
            v for k, v in daily.items()
            if start.strftime("%Y%m%d") <= k[:8] < end.strftime("%Y%m%d")
        )
        result.append(count)
    return result


def _aggregate_monthly(daily: dict, months: int = 3) -> list[int]:
    """Aggregate daily_activity into per-month totals (most recent month first)."""
    today = datetime.today()
    result = []
    for m in range(months):
        target_month = (today.month - m - 1) % 12 + 1
        target_year  = today.year - ((today.month - m - 1) // 12)
        prefix = f"{target_year}{target_month:02d}"
        count = sum(v for k, v in daily.items() if k.startswith(prefix))
        result.append(count)
    return result
