"""
IndiaMART Churn Analysis Pipeline
Usage:  python pipeline.py path/to/glids.txt
Output: runs/run_YYYYMMDD_HHMMSS/
  data/<glid>/*.json          — raw API responses
  data/<glid>/dashboard.html  — per-seller churn dashboard
  index.html                  — seller index for this run
  master_dashboard.html       — aggregated churn analytics for this run
  analysis/churn_signals.json — raw signal data
"""
import json, os, sys, time, re, threading
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter, defaultdict
from datetime import datetime

# ── API credentials ───────────────────────────────────────────────────────────
EMPID          = "990151691"
JWT            = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJFTVBMT1lFRSIsInN1YiI6Ijk5MDE1MTY5MSIsImV4cCI6MTc4MDg5NzYzMCwiaWF0IjoxNzc1NzEzNjMwfQ.PLtn5DhM04_FNfywZhYdLOOH_GTf-lvfCIOrl7uS6W0"
INGESTION_KEY  = "1f082cadae2b715a37eec357d2c344d0e56b804c1933bb318ccb003f8c7e027b"
INGESTION_URL  = "https://ingestion-service-kntbneg73q-el.a.run.app"
DWH_URL        = "https://imdwh.intermesh.net/api/go"
MERP_URL       = "https://merp.intermesh.net"
METRICS_AS_OF  = "2026-01-01"

MAX_WORKERS = 5
TIMEOUT     = 25
SLEEP_BTW   = 0.15

print_lock = threading.Lock()
def log(msg):
    with print_lock: print(msg, flush=True)

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — FETCH ALL APIS
# ═══════════════════════════════════════════════════════════════════════════════
def get_apis(g):
    return [
        {"name":"scorecard_summary","method":"POST","url":f"{DWH_URL}/cust_wh_summary_api",
         "headers":{"Content-Type":"text/plain"},"body":json.dumps({"in_glusr_usr_id":g,"in_rpt_type":"1"})},
        {"name":"scorecard_6m","method":"POST","url":f"{DWH_URL}/cust_scorecard_api",
         "headers":{"Content-Type":"text/plain"},"body":json.dumps({"in_glusr_usr_id":g,"in_rpt_type":"1"})},
        {"name":"scorecard_12m","method":"POST","url":f"{DWH_URL}/cust_wh_apiv2",
         "headers":{"Content-Type":"text/plain"},"body":json.dumps({"in_glusr_usr_id":g,"in_rpt_type":"1"})},
        {"name":"competitors","method":"POST","url":f"{DWH_URL}/nsdprepplus?in_glusr_usr_id={g}&comp_flag=1",
         "headers":{"accept":"application/json","Content-Type":"application/json"},
         "body":json.dumps({"in_glusr_usr_id":g,"comp_flag":"1"})},
        {"name":"competitors_counts","method":"POST","url":f"{DWH_URL}/nsdprepplus?in_glusr_usr_id={g}&comp_flag=2",
         "headers":{"accept":"application/json","Content-Type":"application/json"},
         "body":json.dumps({"in_glusr_usr_id":g,"comp_flag":"2"})},
        {"name":"product_summary","method":"GET",
         "url":f"{MERP_URL}/go/api/csd/v1/qualityScoreDetails?glid={g}&empid={EMPID}&flag=summary&AK={JWT}",
         "headers":{},"body":None},
        {"name":"composite","method":"GET","url":f"{INGESTION_URL}/api/v1/sellers/{g}",
         "headers":{"accept":"application/json","x-api-key":INGESTION_KEY},"body":None},
        {"name":"hotleads","method":"GET","url":f"{INGESTION_URL}/api/v1/sellers/{g}/hotleads",
         "headers":{"accept":"application/json","x-api-key":INGESTION_KEY},"body":None},
        {"name":"metrics","method":"GET",
         "url":f"{INGESTION_URL}/api/v1/sellers/{g}/metrics?as_of={METRICS_AS_OF}",
         "headers":{"accept":"application/json","x-api-key":INGESTION_KEY},"body":None},
        {"name":"activity","method":"GET","url":f"{INGESTION_URL}/api/v1/sellers/{g}/activity",
         "headers":{"accept":"application/json","x-api-key":INGESTION_KEY},"body":None},
    ]

def call_api(api):
    body_b = api["body"].encode() if api["body"] else None
    req = urllib.request.Request(api["url"], data=body_b, headers=api["headers"], method=api["method"])
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            try:    parsed = json.loads(raw)
            except: parsed = {"_raw": raw.decode("utf-8", errors="replace")}
            return {"status": resp.status, "data": parsed, "error": None}
    except urllib.error.HTTPError as e:
        try:
            body_err = e.read().decode("utf-8", errors="replace")
            try:    pe = json.loads(body_err)
            except: pe = {"_raw": body_err}
        except:  pe = {}
        return {"status": e.code, "data": pe, "error": str(e)}
    except Exception as e:
        return {"status": None, "data": None, "error": str(e)}

def fetch_glid(glid, data_dir):
    g = str(glid)
    out_dir = os.path.join(data_dir, g)
    os.makedirs(out_dir, exist_ok=True)
    apis = get_apis(g)
    ok = 0
    statuses = {}
    for api in apis:
        name = api["name"]
        path = os.path.join(out_dir, f"{name}.json")
        if os.path.exists(path):
            try:
                ex = json.load(open(path, encoding="utf-8"))
                if ex.get("status") == 200:
                    statuses[name] = 200; ok += 1; continue
            except: pass
        result = call_api(api)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        statuses[name] = result.get("status")
        if result.get("status") == 200: ok += 1
        time.sleep(SLEEP_BTW)
    log(f"  [GLID {g:>12}] {ok}/{len(apis)} OK")
    return g, ok, len(apis)

def fetch_all(glids, data_dir):
    log(f"\n[1/4] Fetching APIs for {len(glids)} GLIDs x {len(get_apis('0'))} APIs...")
    log("-"*60)
    t0 = time.time()
    total_ok = total_calls = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_glid, g, data_dir): g for g in glids}
        for fut in as_completed(futures):
            g, ok, total = fut.result()
            total_ok += ok; total_calls += total
    log(f"  Done in {time.time()-t0:.1f}s | {total_ok}/{total_calls} successful")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — COMPUTE CHURN SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════
def safe_parse(val):
    if isinstance(val, str):
        val = val.strip()
        if val.startswith("{") or val.startswith("["):
            try: return safe_parse(json.loads(val))
            except: pass
    if isinstance(val, dict): return {k: safe_parse(v) for k,v in val.items()}
    if isinstance(val, list): return [safe_parse(i) for i in val]
    return val

def load_json(glid, name, data_dir):
    p = os.path.join(data_dir, str(glid), f"{name}.json")
    if not os.path.exists(p): return None
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except: return None

def compute_signals(glid, data_dir):
    g = str(glid)
    sig = {"glid": g}
    reasons = []
    score = 0

    # 1. scorecard_summary
    ss = load_json(g, "scorecard_summary", data_dir)
    if ss and ss.get("status") == 200:
        inner = safe_parse(ss.get("data", {}).get("response", "{}"))
        summ  = inner.get("summary", [{}])[0] if inner.get("summary") else {}
        tot_enq     = safe_parse(summ.get("tot_enq", "{}"))
        enq_replied = safe_parse(summ.get("enq_replied", "{}"))
        lms_days    = safe_parse(summ.get("lms_active_days", "{}"))
        bl_cons     = safe_parse(summ.get("bl_cons", "{}"))

        enq_30 = tot_enq.get("30d", 0) or 0 if isinstance(tot_enq, dict) else 0
        rep_30 = enq_replied.get("30d", 0) or 0 if isinstance(enq_replied, dict) else 0
        act_30 = lms_days.get("30d", 0) or 0 if isinstance(lms_days, dict) else 0
        bl_30  = bl_cons.get("30d", 0) or 0 if isinstance(bl_cons, dict) else 0

        sig.update({"enq_30d": enq_30, "replied_30d": rep_30,
                    "active_days_30d": act_30, "bl_cons_30d": bl_30,
                    "city": summ.get("gl_city_name", ""),
                    "enterprise": summ.get("enterprise_type", ""),
                    "client_since": summ.get("client_since", "")})

        reply_rate = round(rep_30/enq_30*100, 1) if enq_30 > 0 else 0
        sig["reply_rate_30d"] = reply_rate
        if reply_rate < 40 and enq_30 > 0:
            score += 20; reasons.append(f"Low reply rate: {reply_rate}% (threshold 40%)")
        if act_30 == 0:
            score += 18; reasons.append("Zero LMS active days in last 30d")
        elif act_30 <= 3:
            score += 10; reasons.append(f"Only {act_30} active days in last 30d")
        if enq_30 == 0:
            score += 15; reasons.append("Zero enquiries in last 30d — no lead flow")

    # 2. scorecard_6m
    s6 = load_json(g, "scorecard_6m", data_dir)
    if s6 and s6.get("status") == 200:
        inner  = safe_parse(s6.get("data", {}).get("response", "{}"))
        months = sorted(inner.get("summary", []), key=lambda x: x.get("year_month", 0))
        if len(months) >= 2:
            last_enq = months[-1].get("total_enq", 0) or 0
            prev_enq = months[-2].get("total_enq", 0) or 0
            if prev_enq > 0:
                velocity = round((last_enq - prev_enq)/prev_enq*100, 1)
                sig["bl_velocity_pct"] = velocity
                if velocity <= -30:
                    score += 22; reasons.append(f"BL velocity drop: {velocity}% MoM (critical)")
                elif velocity <= -10:
                    score += 10; reasons.append(f"BL velocity declining: {velocity}% MoM")

            last_pns = months[-1].get("pns_success_prcnt", 100) or 100
            sig["pns_success_pct"] = last_pns
            if last_pns < 60:
                score += 12; reasons.append(f"PNS answer rate {last_pns}% — below 60%")

            sig["monthly_enq"]        = [m.get("total_enq", 0) or 0 for m in months]
            sig["monthly_labels"]     = [f"{m.get('data_month','')} {m.get('data_year','')}" for m in months]
            sig["monthly_pns"]        = [m.get("pns_calls_recd", 0) or 0 for m in months]
            sig["monthly_pns_ans"]    = [m.get("pns_calls_ans", 0) or 0 for m in months]
            sig["monthly_replies"]    = [m.get("replies", 0) or 0 for m in months]
            sig["monthly_active_days"]= [m.get("lms_active_days", 0) or 0 for m in months]

    # 3. metrics
    mt = load_json(g, "metrics", data_dir)
    if mt and mt.get("status") == 200:
        d = mt.get("data", {}) or {}
        sig.update({
            "pns_received_90d":  d.get("pns_received_90d", 0) or 0,
            "pns_answered_90d":  d.get("pns_answered_90d", 0) or 0,
            "enq_received_90d":  d.get("enq_received_90d", 0) or 0,
            "enq_replies_90d":   d.get("enq_replies_90d", 0) or 0,
            "meetings_90d":      d.get("meetings_90d", 0) or 0,
            "pns_received_1yr":  d.get("pns_received_1yr", 0) or 0,
            "pns_answered_1yr":  d.get("pns_answered_1yr", 0) or 0,
            "enq_received_1yr":  d.get("enq_received_1yr", 0) or 0,
            "meetings_1yr":      d.get("meetings_1yr", 0) or 0,
        })
        pns_r = sig["pns_received_90d"]
        pns_a = sig["pns_answered_90d"]
        pns_rate = round(pns_a/pns_r*100, 1) if pns_r > 0 else None
        if pns_rate is not None and pns_rate < 60:
            score += 10; reasons.append(f"PNS answer rate 90d: {pns_rate}%")

    # 4. composite
    cp = load_json(g, "composite", data_dir)
    if cp and cp.get("status") == 200:
        d = cp.get("data", {}) or {}
        prof = d.get("profile", {}) or {}
        sig.update({
            "company":     prof.get("company_name", ""),
            "rag":         prof.get("rag_category", ""),
            "rag_score":   prof.get("rag_score", 0),
            "account_age": prof.get("account_age_days", 0),
            "paid_history":prof.get("paid_history", False),
            "ctype":       prof.get("customer_type", ""),
        })
        if sig["rag"] == "Red":
            score += 25; reasons.append("RAG category: Red — highest churn risk tier")
        elif sig["rag"] == "Amber":
            score += 12; reasons.append("RAG category: Amber — moderate churn risk")

    # 5. product_summary — CQS
    ps = load_json(g, "product_summary", data_dir)
    if ps and ps.get("status") == 200:
        d     = ps.get("data", {})
        inner = d.get("data", d) if isinstance(d, dict) else {}
        cqs   = inner.get("CQS", None)
        if cqs is not None:
            sig["cqs"] = cqs
            if cqs < 60:
                score += 15; reasons.append(f"CQS: {cqs} — below 60, poor product visibility")
            elif cqs < 75:
                score += 7;  reasons.append(f"CQS: {cqs} — below 75, room for improvement")

    # 6. hotleads
    hl = load_json(g, "hotleads", data_dir)
    if hl and hl.get("status") == 200:
        items = (hl.get("data", {}) or {}).get("items", [])
        sig["hotleads_count"] = len(items)
        if len(items) == 0:
            score += 8; reasons.append("No hotlead activity — no engagement events")

    # 7. activity
    ac = load_json(g, "activity", data_dir)
    if ac and ac.get("status") == 200:
        d = ac.get("data", {}) or {}
        ec = d.get("event_count", 0)
        sig["event_count"] = ec
        if ec == 0:
            score += 12; reasons.append("Zero clickstream events — no platform activity")
        elif ec < 10:
            score += 6;  reasons.append(f"Only {ec} clickstream events — very low activity")
        events = d.get("events", [])
        if events:
            dts = [str(e.get("datevalue", "")) for e in events if e.get("datevalue")]
            if dts:
                latest = max(dts)
                sig["last_seen"] = f"{latest[:4]}-{latest[4:6]}-{latest[6:8]}"

    # 8. competitors_counts
    cc = load_json(g, "competitors_counts", data_dir)
    if cc and cc.get("status") == 200:
        inner = safe_parse(cc.get("data", {}).get("response", "{}"))
        rows  = inner.get("mcat_data", [])
        if rows:
            sig["total_bl_market"]   = rows[0].get("total_bl", 0) or 0
            sig["total_paid_market"] = rows[0].get("total_paid_sellers", 0) or 0

    score = min(score, 100)
    sig["churn_score"]   = score
    sig["churn_reasons"] = reasons
    sig["risk"]          = "Red" if score >= 65 else ("Amber" if score >= 35 else "Green")
    return sig

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — SELLER DASHBOARDS
# ═══════════════════════════════════════════════════════════════════════════════
PALETTE = ["#6366f1","#8b5cf6","#06b6d4","#10b981","#f59e0b","#ef4444","#ec4899","#14b8a6","#f97316","#a855f7"]

def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')
def chart_cfg(type_, labels, datasets, opts=None):
    cfg = {"type":type_,"data":{"labels":labels,"datasets":datasets},"options":{
        "responsive":True,"maintainAspectRatio":False,
        "plugins":{"legend":{"labels":{"color":"#94a3b8"}}},
        "scales":{"x":{"ticks":{"color":"#94a3b8"},"grid":{"color":"#2e3350"}},
                  "y":{"ticks":{"color":"#94a3b8"},"grid":{"color":"#2e3350"}}
                 } if type_ not in ("doughnut","pie") else {}
    }}
    if opts: cfg["options"].update(opts)
    return json.dumps(cfg, ensure_ascii=False, default=str)

SELLER_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0f1117;--s1:#1a1d27;--s2:#22263a;--bdr:#2e3350;--acc:#6366f1;--txt:#e2e8f0;--mut:#94a3b8;--r:12px}
body{background:var(--bg);color:var(--txt);font-family:'Inter',system-ui,sans-serif;min-height:100vh}
.hdr{background:linear-gradient(135deg,#1e1b4b,#0f172a);border-bottom:1px solid var(--bdr);padding:18px 28px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.hdr-icon{width:40px;height:40px;background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:20px}
.hdr h1{font-size:17px;font-weight:700}.hdr p{font-size:11px;color:var(--mut);margin-top:2px}
.hdr-right{margin-left:auto;display:flex;gap:6px;flex-wrap:wrap}
.badge{background:var(--s2);border:1px solid var(--bdr);padding:3px 10px;border-radius:14px;font-size:11px;color:var(--mut)}
.badge.risk-red{border-color:#ef444466;color:#ef4444}.badge.risk-amber{border-color:#f59e0b66;color:#f59e0b}.badge.risk-green{border-color:#10b98166;color:#10b981}
main{padding:20px 28px}
.grid{display:grid;gap:14px}.g2{grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}.g4{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.card{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:18px}
.card-title{font-size:12px;font-weight:600;color:var(--mut);text-transform:uppercase;letter-spacing:.5px;margin-bottom:14px}
.metric-card{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:16px;position:relative;overflow:hidden}
.metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--c,#6366f1)}
.metric-lbl{font-size:10px;color:var(--mut);text-transform:uppercase;letter-spacing:.5px}
.metric-val{font-size:22px;font-weight:800;margin:5px 0 3px;color:var(--c,var(--txt))}
.metric-sub{font-size:10px;color:var(--mut)}
.section{margin-bottom:24px}
.section-title{font-size:14px;font-weight:700;margin-bottom:12px;display:flex;align-items:center;gap:8px;border-bottom:1px solid var(--bdr);padding-bottom:8px}
table{width:100%;border-collapse:collapse;font-size:12px}
thead{background:var(--s2)}
th{padding:8px 10px;text-align:left;font-size:10px;color:var(--mut);text-transform:uppercase;letter-spacing:.4px;border-bottom:1px solid var(--bdr)}
td{padding:9px 10px;border-bottom:1px solid var(--bdr);vertical-align:top}
tr:hover td{background:var(--s2)}
.tbl-wrap{overflow-x:auto;border-radius:var(--r);border:1px solid var(--bdr)}
.tag{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:500}
.tag-blue{background:#1e3a5f44;color:#60a5fa;border:1px solid #3b82f644}
.tag-purple{background:#2d1b6944;color:#a78bfa;border:1px solid #8b5cf644}
.chart-wrap{position:relative;height:260px}.chart-wrap-sm{position:relative;height:190px}
.tl-item{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--bdr)}
.tl-item:last-child{border-bottom:none}
.tl-dot{width:8px;height:8px;border-radius:50%;background:#6366f1;flex-shrink:0;margin-top:4px}
.tl-title{font-size:12px;font-weight:600}
.tl-time{font-size:10px;color:var(--mut);margin-top:2px}
.churn-banner{border-radius:var(--r);padding:16px 20px;margin-bottom:20px;display:flex;align-items:center;gap:16px}
.churn-banner.red{background:#450a0a44;border:1px solid #ef444466}
.churn-banner.amber{background:#451a0344;border:1px solid #f59e0b66}
.churn-banner.green{background:#064e3b44;border:1px solid #10b98166}
.churn-score{font-size:36px;font-weight:900}
.churn-reasons{font-size:12px;color:var(--mut);margin-top:4px}
.churn-reasons li{margin-top:3px}
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--bdr);border-radius:2px}
"""

def build_seller_dashboard(sig, data_dir, run_dir):
    g = str(sig["glid"])
    score = sig.get("churn_score", 0)
    risk  = sig.get("risk", "Green")
    risk_color = {"Red":"#ef4444","Amber":"#f59e0b","Green":"#10b981"}[risk]
    all_js = []

    reasons_html = "".join(f"<li>{esc(r)}</li>" for r in sig.get("churn_reasons", [])) or "<li>No major risk signals</li>"
    banner = f"""<div class="churn-banner {risk.lower()}">
      <div style="text-align:center;min-width:80px">
        <div style="font-size:11px;color:{risk_color};font-weight:700;text-transform:uppercase;letter-spacing:1px">Churn Risk</div>
        <div class="churn-score" style="color:{risk_color}">{score}</div>
        <div style="font-size:11px;color:{risk_color}">{risk} Tier</div>
      </div>
      <div style="flex:1">
        <div style="font-size:13px;font-weight:600;margin-bottom:6px">Risk Signals Detected</div>
        <ul class="churn-reasons">{reasons_html}</ul>
      </div>
    </div>"""

    profile_html = f"""<div class="section">
      <div class="section-title">Seller Profile</div>
      <div class="grid g4">
        <div class="metric-card" style="--c:#6366f1"><div class="metric-lbl">Company</div><div class="metric-val" style="font-size:12px;margin-top:8px">{esc(sig.get("company","—"))}</div></div>
        <div class="metric-card" style="--c:#06b6d4"><div class="metric-lbl">City</div><div class="metric-val" style="font-size:14px">{esc(sig.get("city","—"))}</div></div>
        <div class="metric-card" style="--c:#8b5cf6"><div class="metric-lbl">Segment</div><div class="metric-val" style="font-size:12px;margin-top:8px">{esc(sig.get("enterprise","—"))}</div></div>
        <div class="metric-card" style="--c:#f59e0b"><div class="metric-lbl">Account Age</div><div class="metric-val">{sig.get("account_age","—")}</div><div class="metric-sub">days</div></div>
        <div class="metric-card" style="--c:{risk_color}"><div class="metric-lbl">RAG</div><div class="metric-val" style="font-size:14px;color:{risk_color}">{esc(sig.get("rag","—"))}</div></div>
        <div class="metric-card" style="--c:#10b981"><div class="metric-lbl">Paid History</div><div class="metric-val" style="font-size:14px">{"Yes" if sig.get("paid_history") else "No"}</div></div>
        <div class="metric-card" style="--c:#ec4899"><div class="metric-lbl">Client Since</div><div class="metric-val" style="font-size:14px">{esc(sig.get("client_since","—"))}</div></div>
        <div class="metric-card" style="--c:#14b8a6"><div class="metric-lbl">CQS Score</div><div class="metric-val">{sig.get("cqs","—")}</div></div>
      </div>
    </div>"""

    eng_html = f"""<div class="section">
      <div class="section-title">Engagement Signals</div>
      <div class="grid g4">
        <div class="metric-card" style="--c:#6366f1"><div class="metric-lbl">Enquiries (30d)</div><div class="metric-val">{sig.get("enq_30d","—")}</div></div>
        <div class="metric-card" style="--c:#10b981"><div class="metric-lbl">Reply Rate (30d)</div><div class="metric-val">{sig.get("reply_rate_30d","—")}%</div></div>
        <div class="metric-card" style="--c:#06b6d4"><div class="metric-lbl">Active Days (30d)</div><div class="metric-val">{sig.get("active_days_30d","—")}</div></div>
        <div class="metric-card" style="--c:#f59e0b"><div class="metric-lbl">BL Cons (30d)</div><div class="metric-val">{sig.get("bl_cons_30d","—")}</div></div>
        <div class="metric-card" style="--c:#8b5cf6"><div class="metric-lbl">PNS Received (90d)</div><div class="metric-val">{sig.get("pns_received_90d","—")}</div></div>
        <div class="metric-card" style="--c:#ec4899"><div class="metric-lbl">PNS Answered (90d)</div><div class="metric-val">{sig.get("pns_answered_90d","—")}</div></div>
        <div class="metric-card" style="--c:#14b8a6"><div class="metric-lbl">Meetings (90d)</div><div class="metric-val">{sig.get("meetings_90d","—")}</div></div>
        <div class="metric-card" style="--c:#f97316"><div class="metric-lbl">Hotleads</div><div class="metric-val">{sig.get("hotleads_count","—")}</div></div>
      </div>
    </div>"""

    charts_html = ""
    if sig.get("monthly_labels"):
        lb = sig["monthly_labels"]
        enq_cfg = chart_cfg("bar", lb, [
            {"label":"Enquiries","data":sig.get("monthly_enq",[]),"backgroundColor":"#6366f188","borderColor":"#6366f1","borderWidth":2},
            {"label":"Replies","data":sig.get("monthly_replies",[]),"backgroundColor":"#10b98188","borderColor":"#10b981","borderWidth":2},
        ])
        pns_cfg = chart_cfg("bar", lb, [
            {"label":"PNS Received","data":sig.get("monthly_pns",[]),"backgroundColor":"#06b6d488","borderColor":"#06b6d4","borderWidth":2},
            {"label":"PNS Answered","data":sig.get("monthly_pns_ans",[]),"backgroundColor":"#10b98188","borderColor":"#10b981","borderWidth":2},
        ])
        act_cfg = chart_cfg("line", lb, [
            {"label":"Active Days","data":sig.get("monthly_active_days",[]),
             "borderColor":"#f59e0b","backgroundColor":"#f59e0b22","borderWidth":2,"tension":0.4,"fill":True},
        ])
        all_js += [f"new Chart(document.getElementById('ch_enq'),{enq_cfg});",
                   f"new Chart(document.getElementById('ch_pns'),{pns_cfg});",
                   f"new Chart(document.getElementById('ch_act'),{act_cfg});"]
        charts_html = f"""<div class="section">
          <div class="section-title">Monthly Trends</div>
          <div class="grid g2">
            <div class="card"><div class="card-title">Enquiries vs Replies</div><div class="chart-wrap"><canvas id="ch_enq"></canvas></div></div>
            <div class="card"><div class="card-title">PNS Calls</div><div class="chart-wrap"><canvas id="ch_pns"></canvas></div></div>
          </div>
          <div class="card" style="margin-top:14px"><div class="card-title">Platform Active Days</div><div class="chart-wrap-sm"><canvas id="ch_act"></canvas></div></div>
        </div>"""

    comp_html = ""
    comp_data = load_json(g, "competitors", data_dir)
    if comp_data and comp_data.get("status") == 200:
        inner = safe_parse(comp_data.get("data", {}).get("response", "{}"))
        comps = inner.get("competitors", [])
        if comps:
            rows = "".join(f"""<tr>
              <td>{esc(c.get("competitor_company",""))}</td>
              <td><span class="tag tag-blue">{esc(c.get("custtype_name",""))}</span></td>
              <td>{esc(c.get("competitor_city",""))}</td>
              <td>{esc(c.get("competitor_membersince",""))}</td>
            </tr>""" for c in comps[:10])
            comp_html = f"""<div class="section">
              <div class="section-title">Top Competitors ({len(comps)} total)</div>
              <div class="tbl-wrap"><table>
                <thead><tr><th>Company</th><th>Type</th><th>City</th><th>Member Since</th></tr></thead>
                <tbody>{rows}</tbody>
              </table></div>
              <div style="margin-top:8px;font-size:11px;color:var(--mut)">
                Market: {sig.get("total_bl_market",0)} total BLs | {sig.get("total_paid_market",0)} paid sellers
              </div>
            </div>"""

    hl_html = ""
    hl_data = load_json(g, "hotleads", data_dir)
    if hl_data and hl_data.get("status") == 200:
        items = (hl_data.get("data", {}) or {}).get("items", [])
        if items:
            dc = {"PUA":"#6366f1","UA":"#10b981","ENQR":"#f59e0b","CALL":"#06b6d4"}
            tl = "".join(f"""<div class="tl-item">
              <div class="tl-dot" style="background:{dc.get(it.get('data_type',''),'#94a3b8')}"></div>
              <div><div class="tl-title">{esc(it.get("activity",""))}</div>
              <div class="tl-time">{esc(str(it.get("hotlead_date","")))}
              <span class="tag tag-purple">{esc(it.get("data_type",""))}</span></div></div>
            </div>""" for it in items[:10])
            hl_html = f"""<div class="section">
              <div class="section-title">Hotlead Activity ({len(items)} events)</div>
              <div class="card">{tl}</div>
            </div>"""

    html = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GLID {g} — Seller Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>{SELLER_CSS}</style></head><body>
<div class="hdr">
  <div class="hdr-icon">S</div>
  <div><h1>Seller Dashboard — GLID {g}</h1><p>{esc(sig.get("company",""))}</p></div>
  <div class="hdr-right">
    <div class="badge risk-{risk.lower()}">{risk} Risk | Score {score}</div>
    <div class="badge">{esc(sig.get("city",""))}</div>
    <div class="badge">{datetime.now().strftime("%Y-%m-%d")}</div>
    <a href="../index.html" style="text-decoration:none"><div class="badge">All Sellers</div></a>
    <a href="../master_dashboard.html" style="text-decoration:none"><div class="badge">Master Dashboard</div></a>
  </div>
</div>
<main>{banner}{profile_html}{eng_html}{charts_html}{comp_html}{hl_html}</main>
<script>{"".join(all_js)}</script>
</body></html>"""

    out = os.path.join(data_dir, g, "dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

def build_index(all_sigs, run_dir):
    risk_color = {"Red":"#ef4444","Amber":"#f59e0b","Green":"#10b981"}
    red   = [s for s in all_sigs if s.get("risk") == "Red"]
    amber = [s for s in all_sigs if s.get("risk") == "Amber"]
    green = [s for s in all_sigs if s.get("risk") == "Green"]

    def card(s):
        g  = s["glid"]
        rc = risk_color.get(s.get("risk","Green"),"#10b981")
        top = esc(s["churn_reasons"][0]) if s.get("churn_reasons") else ""
        return f"""<a href="data/{g}/dashboard.html" style="text-decoration:none">
          <div class="seller-card" style="--stripe:{rc}">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
              <div style="font-size:20px;font-weight:900;color:{rc};min-width:32px">{s.get("churn_score",0)}</div>
              <div style="flex:1;min-width:0">
                <div style="font-size:13px;font-weight:700;color:#f1f5f9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{esc(s.get("company","GLID "+g))}</div>
                <div style="font-size:11px;color:#64748b">{esc(s.get("city",""))} | {esc(s.get("enterprise",""))}</div>
              </div>
              <div style="width:10px;height:10px;border-radius:50%;background:{rc};flex-shrink:0"></div>
            </div>
            <div style="font-size:10px;color:#64748b;display:flex;gap:8px;flex-wrap:wrap">
              <span>Enq: {s.get("enq_30d","—")}</span>
              <span>Reply: {s.get("reply_rate_30d","—")}%</span>
              <span>Active: {s.get("active_days_30d","—")}d</span>
              <span>CQS: {s.get("cqs","—")}</span>
              <span>RAG: {s.get("rag","—")}</span>
            </div>
            {f'<div style="font-size:10px;color:{rc};margin-top:6px">{top}</div>' if top else ""}
          </div></a>"""

    def section(title, items, icon, color):
        if not items: return ""
        cards = "".join(card(s) for s in sorted(items, key=lambda x: -x.get("churn_score",0)))
        return f"""<div class="group-title" style="color:{color}">{icon} {title} ({len(items)})</div>
        <div class="seller-grid">{cards}</div>"""

    html = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Churn Run — All Sellers</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f1117;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif}}
.hdr{{background:linear-gradient(135deg,#1e1b4b,#0f172a);border-bottom:1px solid #2e3350;padding:20px 32px}}
.hdr h1{{font-size:20px;font-weight:800}}.hdr p{{font-size:12px;color:#64748b;margin-top:4px}}
.stats{{display:flex;gap:12px;margin-top:14px;flex-wrap:wrap}}
.stat{{background:#1e293b;border:1px solid #2e3350;padding:8px 16px;border-radius:20px;font-size:12px}}
.stat b{{font-size:18px;display:block;font-weight:800}}
.stat.red{{border-color:#ef444466;color:#ef4444}}.stat.amber{{border-color:#f59e0b66;color:#f59e0b}}.stat.green{{border-color:#10b98166;color:#10b981}}
.hdr-links{{display:flex;gap:8px;margin-top:12px}}
.hdr-links a{{background:#1e293b;border:1px solid #334155;color:#94a3b8;padding:6px 14px;border-radius:8px;text-decoration:none;font-size:12px}}
main{{padding:24px 32px}}
.group-title{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:24px 0 12px;display:flex;align-items:center;gap:8px}}
.group-title::after{{content:'';flex:1;height:1px;background:#1e293b}}
.seller-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}}
.seller-card{{background:#1a1d27;border:1px solid #2e3350;border-radius:10px;padding:14px;position:relative;overflow:hidden;transition:all .15s}}
.seller-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--stripe)}}
.seller-card:hover{{border-color:#6366f1;transform:translateY(-2px)}}
</style></head><body>
<div class="hdr">
  <h1>Churn Analysis — All Sellers</h1>
  <p>Run: {os.path.basename(run_dir)} | {len(all_sigs)} sellers analysed</p>
  <div class="stats">
    <div class="stat red"><b>{len(red)}</b>Red — High Risk</div>
    <div class="stat amber"><b>{len(amber)}</b>Amber — Medium</div>
    <div class="stat green"><b>{len(green)}</b>Green — Healthy</div>
    <div class="stat"><b>{len(all_sigs)}</b>Total</div>
  </div>
  <div class="hdr-links">
    <a href="master_dashboard.html">Master Dashboard</a>
  </div>
</div>
<main>
  {section("HIGH RISK — Immediate Action", red, "&#x1F534;","#ef4444")}
  {section("MEDIUM RISK — Monitor & Nudge", amber, "&#x1F7E1;","#f59e0b")}
  {section("LOW RISK — Healthy", green, "&#x1F7E2;","#10b981")}
</main></body></html>"""

    out = os.path.join(run_dir, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"  Index -> {out}")

def build_seller_dashboards(all_sigs, data_dir, run_dir):
    log(f"\n[3/4] Building {len(all_sigs)} seller dashboards...")
    for i, sig in enumerate(all_sigs):
        try:
            build_seller_dashboard(sig, data_dir, run_dir)
        except Exception as e:
            log(f"  [WARN] GLID {sig['glid']}: {e}")
    build_index(all_sigs, run_dir)

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — MASTER DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
def bucket_reason(r):
    r = r.lower()
    if "reply rate" in r:       return "Low Reply Rate"
    if "bl" in r and any(k in r for k in ("declin","drop","velocity","negative")): return "BL Decline / Velocity Drop"
    if "pns" in r:              return "Low PNS Answer Rate"
    if "cqs" in r:              return "Low Catalog Quality (CQS)"
    if any(k in r for k in ("login","inactiv","active day","lms")): return "Inactivity / Low Login"
    if "hotlead" in r:          return "No Hotlead Engagement"
    if "rag" in r:              return "Poor RAG Rating"
    if "enquir" in r or "enq" in r: return "No Enquiry Flow"
    if "event" in r or "clickstream" in r: return "No Platform Activity"
    return r[:55].title()

def top_reasons(subset, n=10):
    c = Counter()
    for s in subset:
        for r in s.get("churn_reasons", []):
            c[bucket_reason(r)] += 1
    return c.most_common(n)

def avg_val(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals)/len(vals), 2) if vals else 0

def pct(n, total):
    return round(100*n/total, 1) if total else 0

def normalise_ent(e):
    e = (e or "").strip()
    if not e: return "Unknown"
    return {"ME":"ME (Mid-Enterprise)","BB":"BB (Big Business)"}.get(e, e)

def normalise_ct(ct):
    ct = (ct or "").strip().upper()
    if not ct or ct == "?": return "Unknown"
    if "CATALOG" in ct: return "CATALOG"
    if "FCP" in ct and "PNS" in ct: return "FCP+PNS"
    if "FREE" in ct: return "FREELIST"
    if "LEADER" in ct: return "LEADER"
    if "BL PAID" in ct: return "BL Paid"
    return "Other"

def seg_analysis(sigs, group_fn, n=10):
    groups = defaultdict(list)
    for s in sigs:
        groups[group_fn(s)].append(s)
    result = {}
    for name, subset in sorted(groups.items(), key=lambda x: -len(x[1])):
        if not subset: continue
        tr = top_reasons(subset, n)
        result[name] = {
            "count": len(subset),
            "red": sum(1 for s in subset if s["risk"]=="Red"),
            "amber": sum(1 for s in subset if s["risk"]=="Amber"),
            "green": sum(1 for s in subset if s["risk"]=="Green"),
            "avg_score": avg_val([s.get("churn_score") for s in subset]),
            "avg_reply": avg_val([s.get("reply_rate_30d") for s in subset]),
            "avg_cqs":   avg_val([s.get("cqs") for s in subset]),
            "top_reasons": [{"reason":r,"count":c,"pct":pct(c,len(subset))} for r,c in tr],
        }
    return result

def reason_bars_html(items, max_c):
    colors = ["#ef4444","#f97316","#f59e0b","#eab308","#84cc16",
              "#22c55e","#14b8a6","#3b82f6","#8b5cf6","#ec4899"]
    out = ""
    for i, item in enumerate(items):
        w = round(100*item["count"]/max_c) if max_c else 0
        out += f"""<div style="margin-bottom:10px">
          <div style="font-size:13px;color:#cbd5e1;font-weight:500;margin-bottom:4px">{i+1}. {item['reason']}</div>
          <div style="display:flex;align-items:center;gap:10px">
            <div style="flex:1;height:12px;background:#1e293b;border-radius:6px;overflow:hidden">
              <div style="width:{w}%;height:100%;background:{colors[i%len(colors)]};border-radius:6px"></div>
            </div>
            <span style="font-size:12px;color:#64748b;white-space:nowrap">{item['count']} sellers ({item['pct']}%)</span>
          </div>
        </div>"""
    return out

def seg_tabs_html(seg_dict, prefix):
    names = list(seg_dict.keys())
    tabs  = "".join(
        f'<button onclick="showTab(\'{prefix}\',{i})" id="{prefix}-t{i}" class="stab">'
        f'{n} ({seg_dict[n]["count"]})</button>'
        for i,n in enumerate(names)
    )
    panels = ""
    for i, name in enumerate(names):
        d = seg_dict[name]
        max_c = d["top_reasons"][0]["count"] if d["top_reasons"] else 1
        panels += f"""<div id="{prefix}-p{i}" class="spanel">
          <div style="margin-bottom:16px">
            <h3 style="font-size:16px;font-weight:600;color:#f1f5f9">{name}</h3>
            <div style="font-size:13px;color:#64748b;margin-top:4px">
              {d['count']} sellers &nbsp;|&nbsp; Avg Churn Score: <b style="color:#f1f5f9">{d['avg_score']}</b>
              &nbsp;|&nbsp; Avg Reply Rate: <b style="color:#f1f5f9">{round(d['avg_reply']*100,1)}%</b>
              &nbsp;|&nbsp; Avg CQS: <b style="color:#f1f5f9">{d['avg_cqs']}</b>
            </div>
            <div style="margin-top:6px">
              <span style="background:#7f1d1d;color:#fca5a5;padding:2px 8px;border-radius:4px;font-size:12px;margin-right:4px">{d['red']} Red</span>
              <span style="background:#78350f;color:#fcd34d;padding:2px 8px;border-radius:4px;font-size:12px;margin-right:4px">{d['amber']} Amber</span>
              <span style="background:#14532d;color:#86efac;padding:2px 8px;border-radius:4px;font-size:12px">{d['green']} Green</span>
            </div>
          </div>
          <h4 style="font-size:12px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px">Top {len(d['top_reasons'])} Churn Reasons</h4>
          {reason_bars_html(d['top_reasons'], max_c)}
        </div>"""

    js = f"""
    <script>
    (function(){{
      var p='{prefix}', n={json.dumps(names)};
      function show(i){{
        n.forEach(function(_,j){{
          var t=document.getElementById(p+'-t'+j), pn=document.getElementById(p+'-p'+j);
          t.style.background=j===i?'#4F46E5':'#1e293b';
          t.style.color=j===i?'#fff':'#94a3b8';
          t.style.borderColor=j===i?'#4F46E5':'#334155';
          pn.style.display=j===i?'block':'none';
        }});
      }}
      window['showTab'+(p)]=show;
      var oldST=window.showTab;
      window.showTab=function(px,i){{if(px===p)show(i);else if(oldST&&oldST!==window.showTab)oldST(px,i);}};
      show(0);
    }})();
    </script>"""

    return f"""<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px">{tabs}</div>
    <div>{panels}</div>{js}"""

def build_master_dashboard(all_sigs, run_dir):
    total = len(all_sigs)
    red   = [s for s in all_sigs if s["risk"]=="Red"]
    amber = [s for s in all_sigs if s["risk"]=="Amber"]
    green = [s for s in all_sigs if s["risk"]=="Green"]

    # Segments
    ent_data = seg_analysis(all_sigs, lambda s: normalise_ent(s.get("enterprise","")))
    ct_data  = seg_analysis(all_sigs, lambda s: normalise_ct(s.get("ctype","")))

    # Overall top 10
    o_top10 = top_reasons(all_sigs, 10)
    r_top10 = top_reasons(red, 10)

    # City distribution
    city_counts = Counter(s.get("city","Unknown") for s in red if s.get("city"))
    city_top = city_counts.most_common(10)

    # Tier metric averages
    def tm(subset):
        return {
            "reply": avg_val([s.get("reply_rate_30d",0) for s in subset]),
            "cqs":   avg_val([s.get("cqs") for s in subset]),
            "active":avg_val([s.get("active_days_30d") for s in subset]),
            "hotl":  avg_val([s.get("hotleads_count") for s in subset]),
        }

    # Score distribution
    buckets = {"0-19":0,"20-34":0,"35-49":0,"50-64":0,"65-79":0,"80+":0}
    for s in all_sigs:
        sc = s.get("churn_score",0)
        if sc<20: buckets["0-19"]+=1
        elif sc<35: buckets["20-34"]+=1
        elif sc<50: buckets["35-49"]+=1
        elif sc<65: buckets["50-64"]+=1
        elif sc<80: buckets["65-79"]+=1
        else: buckets["80+"]+=1

    est_arr = len(red)*15000
    run_name = os.path.basename(run_dir)

    def bar_chart_json(labels, values, label, color="#4F46E5", horizontal=False):
        return json.dumps({
            "type":"bar",
            "data":{"labels":labels,"datasets":[{"label":label,"data":values,"backgroundColor":color,"borderRadius":4}]},
            "options":{
                "indexAxis":"y" if horizontal else "x",
                "responsive":True,"maintainAspectRatio":False,
                "plugins":{"legend":{"display":False}},
                "scales":{
                    "x":{"beginAtZero":True,"ticks":{"color":"#94a3b8"},"grid":{"color":"#1e293b"}},
                    "y":{"ticks":{"color":"#cbd5e1","font":{"size":11}},"grid":{"display":False}}
                }
            }
        }, ensure_ascii=False, default=str)

    def donut_json(labels, values, colors):
        return json.dumps({
            "type":"doughnut",
            "data":{"labels":labels,"datasets":[{"data":values,"backgroundColor":colors,"borderWidth":2,"borderColor":"#0f172a"}]},
            "options":{"responsive":True,"maintainAspectRatio":False,
                       "plugins":{"legend":{"position":"right","labels":{"color":"#cbd5e1","font":{"size":11}}}}}
        }, ensure_ascii=False, default=str)

    trm = {k: tm(v) for k,v in [("Red",red),("Amber",amber),("Green",green)]}
    grouped_json = json.dumps({
        "type":"bar",
        "data":{
            "labels":["Reply Rate %","CQS Score","Active Days/30d","Hotleads"],
            "datasets":[
                {"label":"Red","data":[round(trm["Red"]["reply"]*100,1),trm["Red"]["cqs"],trm["Red"]["active"],trm["Red"]["hotl"]],"backgroundColor":"#ef4444","borderRadius":4},
                {"label":"Amber","data":[round(trm["Amber"]["reply"]*100,1),trm["Amber"]["cqs"],trm["Amber"]["active"],trm["Amber"]["hotl"]],"backgroundColor":"#f59e0b","borderRadius":4},
                {"label":"Green","data":[round(trm["Green"]["reply"]*100,1),trm["Green"]["cqs"],trm["Green"]["active"],trm["Green"]["hotl"]],"backgroundColor":"#22c55e","borderRadius":4},
            ]
        },
        "options":{"responsive":True,"maintainAspectRatio":False,
                   "plugins":{"legend":{"labels":{"color":"#cbd5e1"}}},
                   "scales":{"x":{"ticks":{"color":"#94a3b8"},"grid":{"color":"#1e293b"}},
                             "y":{"beginAtZero":True,"ticks":{"color":"#94a3b8"},"grid":{"color":"#1e293b"}}}}
    }, ensure_ascii=False, default=str)

    o_items = [{"reason":r,"count":c,"pct":pct(c,total)} for r,c in o_top10]
    r_items = [{"reason":r,"count":c,"pct":pct(c,len(red))} for r,c in r_top10]
    o_max = o_items[0]["count"] if o_items else 1
    r_max = r_items[0]["count"] if r_items else 1

    red_rows = "".join(f"""<tr>
      <td><a href="data/{s['glid']}/dashboard.html" target="_blank" style="color:#818cf8">{s['glid']}</a></td>
      <td>{esc(s.get('company','—'))[:28]}</td>
      <td>{esc(s.get('city','—'))}</td>
      <td>{esc(s.get('enterprise','—'))}</td>
      <td><span style="background:#7f1d1d;color:#fca5a5;padding:2px 8px;border-radius:6px;font-weight:700">{s.get('churn_score',0)}</span></td>
      <td>{round(s.get('reply_rate_30d',0)*100,1)}%</td>
      <td>{s.get('cqs','—')}</td>
      <td>{s.get('active_days_30d','—')}</td>
      <td>{s.get('enq_30d','—')}</td>
      <td style="font-size:11px;color:#94a3b8">{esc('; '.join(s.get('churn_reasons',[])[:2]))[:60]}</td>
    </tr>""" for s in sorted(red, key=lambda x: -x.get("churn_score",0)))

    ent_tabs = seg_tabs_html(ent_data, "ent")
    ct_tabs  = seg_tabs_html(ct_data, "ct")

    HTML = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Master Dashboard — {run_name}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f172a;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif;font-size:14px;line-height:1.5}}
.hdr{{background:linear-gradient(135deg,#1e1b4b,#0f172a);padding:24px 36px;border-bottom:1px solid #1e293b}}
.hdr h1{{font-size:22px;font-weight:700;color:#fff}}.hdr p{{color:#64748b;margin-top:4px;font-size:13px}}
.hdr-links{{display:flex;gap:8px;margin-top:12px}}
.hdr-links a{{background:#1e293b;border:1px solid #334155;color:#94a3b8;padding:6px 14px;border-radius:8px;text-decoration:none;font-size:12px}}
.container{{padding:28px 36px;max-width:1600px;margin:0 auto}}
.section{{margin-bottom:40px}}
.stitle{{font-size:16px;font-weight:600;color:#f1f5f9;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid #1e293b}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:16px;margin-bottom:32px}}
.kpi{{background:#1e293b;border-radius:12px;padding:20px;border:1px solid #334155}}
.kpi-val{{font-size:28px;font-weight:700;color:#f1f5f9}}.kpi.red .kpi-val{{color:#ef4444}}.kpi.amber .kpi-val{{color:#f59e0b}}.kpi.green .kpi-val{{color:#22c55e}}
.kpi-lbl{{font-size:11px;color:#64748b;margin-top:4px;text-transform:uppercase;letter-spacing:.05em}}
.kpi-sub{{font-size:11px;color:#475569;margin-top:2px}}
.cgrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(400px,1fr));gap:20px}}
.ccard{{background:#1e293b;border-radius:12px;padding:20px;border:1px solid #334155}}
.ccard h3{{font-size:13px;font-weight:600;color:#94a3b8;margin-bottom:14px}}
.cwrap{{position:relative;height:280px}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
@media(max-width:900px){{.two-col{{grid-template-columns:1fr}}}}
.stab{{background:#1e293b;border:1px solid #334155;color:#94a3b8;padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px}}
.spanel{{display:none;background:#1e293b;border-radius:12px;padding:24px;border:1px solid #334155}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#0f172a;color:#64748b;text-align:left;padding:10px 12px;border-bottom:1px solid #1e293b;font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:.05em}}
td{{padding:10px 12px;border-bottom:1px solid #1e293b;color:#cbd5e1}}
tr:hover td{{background:#1e293b}}
</style>
</head><body>
<div class="hdr">
  <h1>IndiaMART Churn — Master Analytics Dashboard</h1>
  <p>Run: {run_name} &nbsp;|&nbsp; {total} sellers &nbsp;|&nbsp; Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
  <div class="hdr-links">
    <a href="index.html">Seller Index</a>
  </div>
</div>
<div class="container">

<div class="section">
  <div class="kpis">
    <div class="kpi"><div class="kpi-val">{total}</div><div class="kpi-lbl">Total Sellers</div><div class="kpi-sub">This run</div></div>
    <div class="kpi red"><div class="kpi-val">{len(red)}</div><div class="kpi-lbl">Red — High Risk</div><div class="kpi-sub">{pct(len(red),total)}% of sellers</div></div>
    <div class="kpi amber"><div class="kpi-val">{len(amber)}</div><div class="kpi-lbl">Amber — Moderate</div><div class="kpi-sub">{pct(len(amber),total)}%</div></div>
    <div class="kpi green"><div class="kpi-val">{len(green)}</div><div class="kpi-lbl">Green — Healthy</div><div class="kpi-sub">{pct(len(green),total)}%</div></div>
    <div class="kpi"><div class="kpi-val">Rs {est_arr:,}</div><div class="kpi-lbl">Est. At-Risk ARR</div><div class="kpi-sub">Red x Rs 15k avg</div></div>
    <div class="kpi"><div class="kpi-val">{round(avg_val([s.get("churn_score") for s in all_sigs]),1)}</div><div class="kpi-lbl">Avg Churn Score</div><div class="kpi-sub">0 safe, 100 churned</div></div>
    <div class="kpi"><div class="kpi-val">{round(avg_val([s.get("reply_rate_30d",0) for s in all_sigs])*100,1)}%</div><div class="kpi-lbl">Avg Reply Rate</div><div class="kpi-sub">Last 30 days</div></div>
    <div class="kpi"><div class="kpi-val">{round(avg_val([s.get("cqs") for s in all_sigs if s.get("cqs")]),1)}</div><div class="kpi-lbl">Avg CQS</div><div class="kpi-sub">Catalog quality</div></div>
  </div>
</div>

<div class="section">
  <div class="stitle">Risk Distribution &amp; Score Spread</div>
  <div class="cgrid">
    <div class="ccard"><h3>Risk Tier Distribution</h3><div class="cwrap"><canvas id="riskDist"></canvas></div></div>
    <div class="ccard"><h3>Churn Score Distribution</h3><div class="cwrap"><canvas id="scoreDist"></canvas></div></div>
    <div class="ccard"><h3>Key Metrics by Risk Tier (Averages)</h3><div class="cwrap"><canvas id="tierM"></canvas></div></div>
    <div class="ccard"><h3>Top Cities — Red Tier</h3><div class="cwrap"><canvas id="cityChart"></canvas></div></div>
  </div>
</div>

<div class="section">
  <div class="stitle">Top 10 Churn Reasons — All {total} Sellers</div>
  <div class="two-col">
    <div class="ccard"><h3>All Sellers (n={total})</h3>{reason_bars_html(o_items,o_max)}</div>
    <div class="ccard"><h3>Red Tier Only (n={len(red)})</h3>{reason_bars_html(r_items,r_max)}</div>
  </div>
</div>

<div class="section">
  <div class="stitle">Churn Reasons by Enterprise Segment</div>
  {ent_tabs}
</div>

<div class="section">
  <div class="stitle">Churn Reasons by Subscription Type</div>
  {ct_tabs}
</div>

<div class="section">
  <div class="stitle">Red-Tier Sellers ({len(red)}) — Sorted by Score</div>
  <div style="overflow-x:auto;background:#1e293b;border-radius:12px;border:1px solid #334155">
    <table>
      <thead><tr><th>GLID</th><th>Company</th><th>City</th><th>Segment</th><th>Score</th>
        <th>Reply%</th><th>CQS</th><th>Active Days</th><th>Enq 30d</th><th>Top Reasons</th></tr></thead>
      <tbody>{red_rows}</tbody>
    </table>
  </div>
</div>

</div>
<script>
new Chart(document.getElementById('riskDist'), {donut_json(["Red","Amber","Green"],[len(red),len(amber),len(green)],["#ef4444","#f59e0b","#22c55e"])});
new Chart(document.getElementById('scoreDist'), {bar_chart_json(list(buckets.keys()),list(buckets.values()),"Sellers","#8b5cf6")});
new Chart(document.getElementById('tierM'), {grouped_json});
new Chart(document.getElementById('cityChart'), {bar_chart_json([c for c,_ in city_top],[n for _,n in city_top],"Red Sellers","#ef4444",True)});
</script>
</body></html>"""

    out = os.path.join(run_dir, "master_dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(HTML)
    log(f"  Master dashboard -> {out}")

# ═══════════════════════════════════════════════════════════════════════════════
# HOMEPAGE — lists all runs
# ═══════════════════════════════════════════════════════════════════════════════
def build_homepage(base_dir):
    runs_dir = os.path.join(base_dir, "runs")
    runs = []
    if os.path.isdir(runs_dir):
        for name in sorted(os.listdir(runs_dir), reverse=True):
            run_dir = os.path.join(runs_dir, name)
            if not os.path.isdir(run_dir): continue
            sigs_path = os.path.join(run_dir, "analysis", "churn_signals.json")
            has_master = os.path.exists(os.path.join(run_dir, "master_dashboard.html"))
            has_index  = os.path.exists(os.path.join(run_dir, "index.html"))
            stats = {"total":0,"red":0,"amber":0,"green":0,"avg_score":0}
            if os.path.exists(sigs_path):
                try:
                    sigs = json.load(open(sigs_path, encoding="utf-8"))
                    stats["total"] = len(sigs)
                    stats["red"]   = sum(1 for s in sigs if s.get("risk")=="Red")
                    stats["amber"] = sum(1 for s in sigs if s.get("risk")=="Amber")
                    stats["green"] = sum(1 for s in sigs if s.get("risk")=="Green")
                    scores = [s.get("churn_score",0) for s in sigs]
                    stats["avg_score"] = round(sum(scores)/len(scores), 1) if scores else 0
                except: pass
            # Parse run timestamp from folder name: run_YYYYMMDD_HHMMSS
            ts_str = name.replace("run_","")
            try:
                ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                display_ts = ts.strftime("%d %b %Y, %H:%M")
            except:
                display_ts = ts_str
            runs.append({
                "name": name,
                "ts": display_ts,
                "rel_path": f"runs/{name}",
                "has_master": has_master,
                "has_index": has_index,
                **stats,
            })

    def run_card(r):
        red_pct   = round(100*r["red"]/r["total"],1) if r["total"] else 0
        green_pct = round(100*r["green"]/r["total"],1) if r["total"] else 0
        master_btn = (f'<a href="{r["rel_path"]}/master_dashboard.html" class="btn btn-master">Master Dashboard</a>'
                      if r["has_master"] else '<span class="btn btn-disabled">No master dashboard</span>')
        index_btn  = (f'<a href="{r["rel_path"]}/index.html" class="btn btn-index">Seller Index</a>'
                      if r["has_index"] else '<span class="btn btn-disabled">No index</span>')
        return f"""<div class="run-card">
          <div class="run-header">
            <div>
              <div class="run-name">{r["name"]}</div>
              <div class="run-ts">{r["ts"]}</div>
            </div>
            <div class="run-total">{r["total"]}<span>sellers</span></div>
          </div>
          <div class="run-risk-bar">
            <div class="rb-red"   style="flex:{r['red']}"></div>
            <div class="rb-amber" style="flex:{r['amber']}"></div>
            <div class="rb-green" style="flex:{r['green']}"></div>
          </div>
          <div class="run-stats">
            <div class="rs red"><span>{r['red']}</span>Red ({red_pct}%)</div>
            <div class="rs amber"><span>{r['amber']}</span>Amber</div>
            <div class="rs green"><span>{r['green']}</span>Green ({green_pct}%)</div>
            <div class="rs neutral"><span>{r['avg_score']}</span>Avg Score</div>
          </div>
          <div class="run-actions">{master_btn}{index_btn}</div>
        </div>"""

    cards_html = "".join(run_card(r) for r in runs) if runs else \
        '<div class="empty">No runs yet. Run: <code>python pipeline.py glids.txt</code></div>'

    HTML = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>IndiaMART Churn — All Runs</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f172a;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif;min-height:100vh}}
.hdr{{background:linear-gradient(135deg,#1e1b4b,#0f172a);padding:28px 40px;border-bottom:1px solid #1e293b}}
.hdr h1{{font-size:24px;font-weight:800;color:#fff;letter-spacing:-.3px}}
.hdr p{{color:#64748b;margin-top:6px;font-size:13px}}
.hdr-meta{{display:flex;align-items:center;gap:16px;margin-top:14px;flex-wrap:wrap}}
.hdr-stat{{font-size:13px;color:#475569}}
.hdr-stat b{{color:#94a3b8}}
.container{{padding:32px 40px;max-width:1400px;margin:0 auto}}
.section-label{{font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.08em;margin-bottom:16px}}
.runs-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:20px}}
.run-card{{background:#1e293b;border:1px solid #334155;border-radius:14px;padding:22px;transition:border-color .15s}}
.run-card:hover{{border-color:#4F46E5}}
.run-header{{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:14px}}
.run-name{{font-size:13px;font-weight:600;color:#f1f5f9;font-family:monospace}}
.run-ts{{font-size:12px;color:#475569;margin-top:3px}}
.run-total{{text-align:right;font-size:28px;font-weight:800;color:#f1f5f9;line-height:1}}
.run-total span{{display:block;font-size:11px;font-weight:400;color:#64748b;margin-top:2px}}
.run-risk-bar{{display:flex;height:6px;border-radius:4px;overflow:hidden;margin-bottom:12px;gap:2px}}
.rb-red{{background:#ef4444;border-radius:3px}}.rb-amber{{background:#f59e0b;border-radius:3px}}.rb-green{{background:#22c55e;border-radius:3px}}
.run-stats{{display:flex;gap:16px;margin-bottom:16px;flex-wrap:wrap}}
.rs{{font-size:11px;color:#64748b}}.rs span{{display:block;font-size:18px;font-weight:700;line-height:1.2}}
.rs.red span{{color:#ef4444}}.rs.amber span{{color:#f59e0b}}.rs.green span{{color:#22c55e}}.rs.neutral span{{color:#94a3b8}}
.run-actions{{display:flex;gap:10px;flex-wrap:wrap}}
.btn{{display:inline-block;padding:8px 18px;border-radius:8px;font-size:13px;font-weight:600;text-decoration:none;transition:all .15s}}
.btn-master{{background:#4F46E5;color:#fff}}.btn-master:hover{{background:#4338CA}}
.btn-index{{background:#1e293b;color:#94a3b8;border:1px solid #334155}}.btn-index:hover{{border-color:#94a3b8;color:#f1f5f9}}
.btn-disabled{{background:#0f172a;color:#334155;border:1px solid #1e293b;display:inline-block;padding:8px 18px;border-radius:8px;font-size:13px}}
.empty{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:40px;text-align:center;color:#475569}}
.empty code{{background:#0f172a;padding:4px 10px;border-radius:6px;color:#94a3b8;font-size:13px}}
::-webkit-scrollbar{{width:4px}}.hdr-badge{{background:#1e293b;border:1px solid #334155;padding:4px 12px;border-radius:20px;font-size:12px;color:#64748b}}
</style>
</head><body>
<div class="hdr">
  <h1>IndiaMART Churn Analysis</h1>
  <p>All pipeline runs — each run is isolated with its own data, dashboards and analysis</p>
  <div class="hdr-meta">
    <div class="hdr-badge">{len(runs)} run{"s" if len(runs)!=1 else ""}</div>
    <div class="hdr-stat">Latest: <b>{runs[0]["ts"] if runs else "—"}</b></div>
    <div class="hdr-stat">To start a new run: <b>python pipeline.py glids.txt</b></div>
  </div>
</div>
<div class="container">
  <div class="section-label">All Runs — newest first</div>
  <div class="runs-grid">{cards_html}</div>
</div>
</body></html>"""

    out = os.path.join(base_dir, "home.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(HTML)
    log(f"  Homepage -> {out}")

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py path/to/glids.txt")
        sys.exit(1)

    glids_file = sys.argv[1]
    if not os.path.exists(glids_file):
        print(f"File not found: {glids_file}")
        sys.exit(1)

    with open(glids_file, encoding="utf-8") as f:
        glids = [line.strip() for line in f if line.strip()]

    if not glids:
        print("No GLIDs found in file.")
        sys.exit(1)

    # Create run directory
    run_id  = datetime.now().strftime("%Y%m%d_%H%M%S")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    run_dir  = os.path.join(BASE_DIR, "runs", f"run_{run_id}")
    data_dir = os.path.join(run_dir, "data")
    analysis_dir = os.path.join(run_dir, "analysis")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(analysis_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Churn Analysis Pipeline")
    print(f"  GLIDs   : {len(glids)}")
    print(f"  Run dir : {run_dir}")
    print(f"{'='*60}")

    # Step 1: Fetch
    fetch_all(glids, data_dir)

    # Step 2: Signals
    log(f"\n[2/4] Computing churn signals for {len(glids)} sellers...")
    all_sigs = []
    for i, g in enumerate(glids):
        try:
            sig = compute_signals(g, data_dir)
            all_sigs.append(sig)
        except Exception as e:
            log(f"  [WARN] GLID {g}: {e}")
            all_sigs.append({"glid":g,"churn_score":0,"risk":"Green","churn_reasons":[]})

    # Save signals
    sigs_path = os.path.join(analysis_dir, "churn_signals.json")
    with open(sigs_path, "w", encoding="utf-8") as f:
        json.dump(all_sigs, f, indent=2, ensure_ascii=False, default=str)
    log(f"  Signals saved -> {sigs_path}")

    risk_counts = Counter(s["risk"] for s in all_sigs)
    log(f"  Red: {risk_counts['Red']} | Amber: {risk_counts['Amber']} | Green: {risk_counts['Green']}")

    # Step 3: Seller dashboards + index
    build_seller_dashboards(all_sigs, data_dir, run_dir)

    # Step 4: Master dashboard
    log(f"\n[4/4] Building master dashboard...")
    build_master_dashboard(all_sigs, run_dir)

    # Homepage — regenerate after every run
    log(f"\n[+] Updating homepage...")
    build_homepage(BASE_DIR)

    print(f"\n{'='*60}")
    print(f"  DONE!")
    print(f"  Homepage : {BASE_DIR}\\home.html")
    print(f"  Master   : {run_dir}\\master_dashboard.html")
    print(f"  Index    : {run_dir}\\index.html")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
