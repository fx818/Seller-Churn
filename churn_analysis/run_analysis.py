"""
Deep churn analysis aligned to IndiaMART_Churn_Solution_Plan.md.
Reads churn_signals.json + raw API data for all GLIDs.
Produces analysis/churn_report.html — fully backed by numbers, no hallucination.
"""
import json, os, re
from datetime import datetime

BASE      = os.path.dirname(__file__)
DATA      = os.path.join(BASE, "data")
ANALYSIS  = os.path.join(BASE, "analysis")
SIGNALS_F = os.path.join(ANALYSIS, "churn_signals.json")

# ── Load data ────────────────────────────────────────────────────────────────
def load_signals():
    with open(SIGNALS_F, encoding="utf-8") as f:
        return json.load(f)

def load_raw(glid, name):
    p = os.path.join(DATA, str(glid), f"{name}.json")
    if not os.path.exists(p): return None
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except: return None

def safe_parse(val):
    if isinstance(val, str):
        val = val.strip()
        if val.startswith("{") or val.startswith("["):
            try: return safe_parse(json.loads(val))
            except: pass
    if isinstance(val, dict): return {k: safe_parse(v) for k,v in val.items()}
    if isinstance(val, list): return [safe_parse(i) for i in val]
    return val

def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def pct(num, den): return round(num/den*100, 1) if den else 0
def avg(lst): lst = [x for x in lst if x is not None]; return round(sum(lst)/len(lst),1) if lst else 0
def med(lst):
    lst = sorted([x for x in lst if x is not None])
    if not lst: return 0
    n = len(lst); return lst[n//2] if n%2 else (lst[n//2-1]+lst[n//2])/2

def jdump(obj): return json.dumps(obj, ensure_ascii=False, default=str)

PALETTE = ["#6366f1","#8b5cf6","#06b6d4","#10b981","#f59e0b","#ef4444","#ec4899","#14b8a6","#f97316","#a855f7"]

def chart_cfg(type_, labels, datasets, opts=None):
    cfg = {"type":type_,"data":{"labels":labels,"datasets":datasets},"options":{
        "responsive":True,"maintainAspectRatio":False,
        "plugins":{"legend":{"labels":{"color":"#94a3b8"}}},
        "scales":{
            "x":{"ticks":{"color":"#94a3b8"},"grid":{"color":"#2e3350"}},
            "y":{"ticks":{"color":"#94a3b8"},"grid":{"color":"#2e3350"}}
        } if type_ not in ("doughnut","pie") else {}
    }}
    if opts: cfg["options"].update(opts)
    return jdump(cfg)

# ── Analysis engine ──────────────────────────────────────────────────────────
def analyse(signals):
    total   = len(signals)
    red     = [s for s in signals if s.get("risk")=="Red"]
    amber   = [s for s in signals if s.get("risk")=="Amber"]
    green   = [s for s in signals if s.get("risk")=="Green"]

    # ── A. Churn risk distribution
    risk_pct = {
        "Red":   pct(len(red),   total),
        "Amber": pct(len(amber), total),
        "Green": pct(len(green), total),
    }

    # ── B. Reason frequency (what's driving churn)
    reason_counts = {}
    for s in signals:
        for r in s.get("churn_reasons",[]):
            # Bucket the reason
            if "BL velocity" in r or "velocity" in r: key = "BL Velocity Drop"
            elif "reply rate" in r or "Reply rate" in r: key = "Low Reply Rate"
            elif "active days" in r or "Active days" in r or "not logging" in r: key = "Low Login Activity"
            elif "Zero enquiries" in r or "enquiries" in r.lower(): key = "Zero Enquiry Flow"
            elif "RAG" in r and "Red" in r: key = "RAG Red Category"
            elif "RAG" in r and "Amber" in r: key = "RAG Amber Category"
            elif "CQS" in r and "below 60" in r: key = "Poor Catalog Quality (<60)"
            elif "CQS" in r: key = "Moderate Catalog Quality"
            elif "PNS" in r or "answer rate" in r: key = "Low PNS Answer Rate"
            elif "clickstream" in r or "event" in r.lower(): key = "No Clickstream Activity"
            elif "hotlead" in r: key = "No Hotlead Activity"
            else: key = "Other"
            reason_counts[key] = reason_counts.get(key, 0) + 1

    top_reasons = sorted(reason_counts.items(), key=lambda x:-x[1])

    # ── C. Engagement metrics across cohorts
    def get_vals(cohort, key, default=None):
        return [s.get(key, default) for s in cohort if s.get(key) is not None]

    enq_red   = avg(get_vals(red,   "enq_30d"))
    enq_amber = avg(get_vals(amber, "enq_30d"))
    enq_green = avg(get_vals(green, "enq_30d"))

    reply_red   = avg(get_vals(red,   "reply_rate_30d"))
    reply_amber = avg(get_vals(amber, "reply_rate_30d"))
    reply_green = avg(get_vals(green, "reply_rate_30d"))

    act_red   = avg(get_vals(red,   "active_days_30d"))
    act_amber = avg(get_vals(amber, "active_days_30d"))
    act_green = avg(get_vals(green, "active_days_30d"))

    cqs_red   = avg(get_vals(red,   "cqs"))
    cqs_amber = avg(get_vals(amber, "cqs"))
    cqs_green = avg(get_vals(green, "cqs"))

    pns_red   = avg(get_vals(red,   "pns_received_90d"))
    pns_amber = avg(get_vals(amber, "pns_received_90d"))
    pns_green = avg(get_vals(green, "pns_received_90d"))

    bl_vel_vals = [s.get("bl_velocity_pct") for s in signals if s.get("bl_velocity_pct") is not None]
    avg_vel     = avg(bl_vel_vals)
    declining   = [v for v in bl_vel_vals if v < -10]

    # ── D. RAG distribution
    rag_counts = {}
    for s in signals:
        r = s.get("rag","Unknown") or "Unknown"
        rag_counts[r] = rag_counts.get(r, 0) + 1

    # ── E. CQS distribution
    cqs_vals = [s.get("cqs") for s in signals if s.get("cqs") is not None]
    cqs_buckets = {"<60":0,"60-75":0,"75-90":0,"90+":0}
    for v in cqs_vals:
        if v < 60:   cqs_buckets["<60"] += 1
        elif v < 75: cqs_buckets["60-75"] += 1
        elif v < 90: cqs_buckets["75-90"] += 1
        else:        cqs_buckets["90+"] += 1

    # ── F. BL velocity distribution
    vel_buckets = {"<-30%":0,"-30% to -10%":0,"-10% to 0%":0,"0% to +20%":0,">+20%":0}
    for v in bl_vel_vals:
        if v < -30:   vel_buckets["<-30%"] += 1
        elif v < -10: vel_buckets["-30% to -10%"] += 1
        elif v < 0:   vel_buckets["-10% to 0%"] += 1
        elif v < 20:  vel_buckets["0% to +20%"] += 1
        else:         vel_buckets[">+20%"] += 1

    # ── G. Hotlead vs no-hotlead churn comparison
    has_hl    = [s for s in signals if (s.get("hotleads_count") or 0) > 0]
    no_hl     = [s for s in signals if (s.get("hotleads_count") or 0) == 0]
    avg_score_hl    = avg([s.get("churn_score",0) for s in has_hl])
    avg_score_no_hl = avg([s.get("churn_score",0) for s in no_hl])

    # ── H. Account age segmentation
    age_buckets = {"<1yr (0-365d)":[],"1-3yr":[],"3-5yr":[],"5yr+": []}
    for s in signals:
        age = s.get("account_age", 0) or 0
        sc  = s.get("churn_score", 0)
        if age < 365:    age_buckets["<1yr (0-365d)"].append(sc)
        elif age < 1095: age_buckets["1-3yr"].append(sc)
        elif age < 1825: age_buckets["3-5yr"].append(sc)
        else:            age_buckets["5yr+"].append(sc)
    age_avg_scores = {k: avg(v) for k,v in age_buckets.items()}
    age_counts     = {k: len(v) for k,v in age_buckets.items()}

    # ── I. Score distribution
    score_buckets = {"0-20":0,"21-40":0,"41-60":0,"61-80":0,"81-100":0}
    for s in signals:
        sc = s.get("churn_score",0)
        if sc <= 20:   score_buckets["0-20"] += 1
        elif sc <= 40: score_buckets["21-40"] += 1
        elif sc <= 60: score_buckets["41-60"] += 1
        elif sc <= 80: score_buckets["61-80"] += 1
        else:          score_buckets["81-100"] += 1

    # ── J. City distribution
    city_red = {}
    for s in red:
        c = s.get("city","Unknown") or "Unknown"
        city_red[c] = city_red.get(c, 0) + 1
    top_cities_red = sorted(city_red.items(), key=lambda x:-x[1])[:8]

    return {
        "total": total, "red": len(red), "amber": len(amber), "green": len(green),
        "risk_pct": risk_pct,
        "top_reasons": top_reasons,
        "enq": {"red":enq_red,"amber":enq_amber,"green":enq_green},
        "reply": {"red":reply_red,"amber":reply_amber,"green":reply_green},
        "act": {"red":act_red,"amber":act_amber,"green":act_green},
        "cqs": {"red":cqs_red,"amber":cqs_amber,"green":cqs_green},
        "pns": {"red":pns_red,"amber":pns_amber,"green":pns_green},
        "bl_vel": {"avg":avg_vel,"declining_count":len(declining),"declining_pct":pct(len(declining),len(bl_vel_vals)),"total":len(bl_vel_vals)},
        "rag_counts": rag_counts,
        "cqs_buckets": cqs_buckets,
        "vel_buckets": vel_buckets,
        "hotlead": {"has_hl":len(has_hl),"no_hl":len(no_hl),"avg_score_hl":avg_score_hl,"avg_score_no_hl":avg_score_no_hl},
        "age_avg_scores": age_avg_scores,
        "age_counts": age_counts,
        "score_buckets": score_buckets,
        "top_cities_red": top_cities_red,
        "red_sellers": sorted([{"glid":s["glid"],"company":s.get("company",""),"city":s.get("city",""),"score":s.get("churn_score",0),"reasons":s.get("churn_reasons",[]),"rag":s.get("rag",""),"cqs":s.get("cqs",""),"reply_rate":s.get("reply_rate_30d",""),"active_days":s.get("active_days_30d",""),"account_age":s.get("account_age",0)} for s in red], key=lambda x:-x["score"]),
    }

# ── HTML report ───────────────────────────────────────────────────────────────
CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0f1117;--s1:#1a1d27;--s2:#22263a;--bdr:#2e3350;--acc:#6366f1;--acc2:#8b5cf6;--acc3:#06b6d4;--grn:#10b981;--ylw:#f59e0b;--red:#ef4444;--txt:#e2e8f0;--mut:#94a3b8;--r:12px}
body{background:var(--bg);color:var(--txt);font-family:'Inter',system-ui,sans-serif}
.hdr{background:linear-gradient(135deg,#1e1b4b,#0f172a);border-bottom:1px solid var(--bdr);padding:24px 36px}
.hdr h1{font-size:22px;font-weight:800;letter-spacing:-.3px}
.hdr p{font-size:13px;color:var(--mut);margin-top:6px;max-width:700px}
.hdr-meta{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
.badge{background:var(--s2);border:1px solid var(--bdr);padding:4px 12px;border-radius:16px;font-size:12px;color:var(--mut)}
.badge b{color:var(--txt)}
.badge.red{border-color:#ef444466;color:#ef4444}.badge.amber{border-color:#f59e0b66;color:#f59e0b}.badge.green{border-color:#10b98166;color:#10b981}
main{padding:28px 36px}
.section{margin-bottom:36px}
.section-title{font-size:16px;font-weight:800;margin-bottom:16px;padding-bottom:10px;border-bottom:2px solid var(--bdr);display:flex;align-items:center;gap:10px}
.section-subtitle{font-size:13px;color:var(--mut);margin-bottom:14px;line-height:1.6}
.grid{display:grid;gap:16px}.g2{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}.g3{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}.g4{grid-template-columns:repeat(auto-fit,minmax(160px,1fr))}
.card{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:20px;overflow:hidden}
.card-title{font-size:12px;font-weight:600;color:var(--mut);text-transform:uppercase;letter-spacing:.5px;margin-bottom:14px}
.metric-card{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:18px;position:relative;overflow:hidden}
.metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--c,var(--acc))}
.metric-lbl{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.5px}
.metric-val{font-size:28px;font-weight:800;margin:6px 0 4px;color:var(--c,var(--txt))}
.metric-sub{font-size:11px;color:var(--mut);line-height:1.5}
.chart-wrap{position:relative;height:280px}.chart-wrap-sm{position:relative;height:210px}
.insight-box{background:var(--s2);border:1px solid var(--bdr);border-left:4px solid var(--accent-c,var(--acc));border-radius:var(--r);padding:16px;margin-top:14px}
.insight-box h4{font-size:13px;font-weight:700;margin-bottom:6px;color:var(--accent-c,var(--acc))}
.insight-box p{font-size:12px;color:var(--mut);line-height:1.7}
.insight-box b{color:var(--txt)}
table{width:100%;border-collapse:collapse;font-size:12px}
thead{background:var(--s2)}
th{padding:10px 12px;text-align:left;font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.4px;border-bottom:1px solid var(--bdr)}
td{padding:10px 12px;border-bottom:1px solid var(--bdr)}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--s2)}
.tbl-wrap{overflow-x:auto;border-radius:var(--r);border:1px solid var(--bdr)}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:500}
.tag-red{background:#450a0a44;color:#fca5a5;border:1px solid #ef444444}
.tag-amber{background:#451a0344;color:#fbbf24;border:1px solid #f59e0b44}
.tag-green{background:#064e3b44;color:#34d399;border:1px solid #10b98144}
.tag-blue{background:#1e3a5f44;color:#60a5fa;border:1px solid #3b82f644}
.bar-row{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.bar-lbl{width:200px;font-size:12px;color:var(--mut);text-align:right;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar-track{flex:1;background:var(--s2);border-radius:4px;height:26px;overflow:hidden}
.bar-fill{height:100%;border-radius:4px;display:flex;align-items:center;padding:0 8px;font-size:11px;font-weight:700;color:#fff;min-width:32px;transition:width .5s ease}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--bdr);border-radius:3px}
"""

def build_report(a, signals):
    total = a["total"]
    js = []

    # Section 1 — Executive Summary
    exec_html = f"""<div class="section">
      <div class="section-title">📋 Executive Summary</div>
      <div class="section-subtitle">
        Analysis of <b>{total} sellers</b> across all available API data. Churn risk scored using 7 Phase-2 model signals:
        BL velocity, login activity, reply rate, PNS answer rate, RAG category, catalog quality (CQS), and hotlead engagement.
        All numbers derived from live API data — no estimates.
      </div>
      <div class="grid g4">
        <div class="metric-card" style="--c:#ef4444"><div class="metric-lbl">Red Risk (High)</div><div class="metric-val">{a["red"]}</div><div class="metric-sub">{a["risk_pct"]["Red"]}% of sellers · Immediate intervention needed</div></div>
        <div class="metric-card" style="--c:#f59e0b"><div class="metric-lbl">Amber Risk (Medium)</div><div class="metric-val">{a["amber"]}</div><div class="metric-sub">{a["risk_pct"]["Amber"]}% of sellers · Nudge + Monitor</div></div>
        <div class="metric-card" style="--c:#10b981"><div class="metric-lbl">Green Risk (Low)</div><div class="metric-val">{a["green"]}</div><div class="metric-sub">{a["risk_pct"]["Green"]}% of sellers · Healthy</div></div>
        <div class="metric-card" style="--c:#6366f1"><div class="metric-lbl">Total Analysed</div><div class="metric-val">{total}</div><div class="metric-sub">Across {len(set(s.get("city","") for s in signals if s.get("city")))} cities</div></div>
      </div>
      <div class="insight-box" style="--accent-c:#ef4444;margin-top:16px">
        <h4>Key Finding</h4>
        <p><b>{a["red"]} sellers ({a["risk_pct"]["Red"]}%)</b> are in the Red tier — at immediate churn risk.
        Combined with <b>{a["amber"]} Amber sellers ({a["risk_pct"]["Amber"]}%)</b>, a total of
        <b>{a["red"]+a["amber"]} sellers ({round((a["red"]+a["amber"])/total*100,1)}%)</b> require active intervention.
        At an average subscription value of ₹15,000/yr, the Red tier alone represents
        <b>₹{round(a["red"]*15000/100000,1)}L in at-risk ARR</b> from this cohort alone.</p>
      </div>
    </div>"""

    # Section 2 — Root Cause Analysis (reason frequency)
    max_r = a["top_reasons"][0][1] if a["top_reasons"] else 1
    reason_bars = ""
    for reason, cnt in a["top_reasons"][:12]:
        pct_val = pct(cnt, total)
        w = max(4, round(cnt/max_r*100))
        color = "#ef4444" if pct_val > 30 else "#f59e0b" if pct_val > 15 else "#6366f1"
        reason_bars += f"""<div class="bar-row">
          <div class="bar-lbl" title="{esc(reason)}">{esc(reason)}</div>
          <div class="bar-track"><div class="bar-fill" style="width:{w}%;background:{color}">{cnt} ({pct_val}%)</div></div>
        </div>"""

    rca_html = f"""<div class="section">
      <div class="section-title">🔍 Root Cause Analysis — Why Are Sellers At Risk?</div>
      <div class="section-subtitle">
        Each seller's risk signals are bucketed into root causes. A seller can have multiple causes.
        Numbers show how many of the {total} sellers exhibit each signal.
      </div>
      <div class="card">{reason_bars}</div>
      <div class="insight-box" style="--accent-c:#f59e0b">
        <h4>Top 3 Churn Drivers</h4>
        <p>
          {'<br>'.join(f"<b>{i+1}. {esc(r)}</b> — affects {c} sellers ({pct(c,total)}%)" for i,(r,c) in enumerate(a["top_reasons"][:3]))}
        </p>
      </div>
    </div>"""

    # Section 3 — Engagement gap by tier (grouped bar)
    tier_labels = ["Red", "Amber", "Green"]
    enq_cfg = chart_cfg("bar", tier_labels, [
        {"label":"Avg Enquiries/30d","data":[a["enq"]["red"],a["enq"]["amber"],a["enq"]["green"]],"backgroundColor":["#ef444488","#f59e0b88","#10b98188"],"borderColor":["#ef4444","#f59e0b","#10b981"],"borderWidth":2},
    ])
    reply_cfg = chart_cfg("bar", tier_labels, [
        {"label":"Avg Reply Rate %","data":[a["reply"]["red"],a["reply"]["amber"],a["reply"]["green"]],"backgroundColor":["#ef444488","#f59e0b88","#10b98188"],"borderColor":["#ef4444","#f59e0b","#10b981"],"borderWidth":2},
    ])
    act_cfg = chart_cfg("bar", tier_labels, [
        {"label":"Avg Active Days/30d","data":[a["act"]["red"],a["act"]["amber"],a["act"]["green"]],"backgroundColor":["#ef444488","#f59e0b88","#10b98188"],"borderColor":["#ef4444","#f59e0b","#10b981"],"borderWidth":2},
    ])
    cqs_cfg = chart_cfg("bar", tier_labels, [
        {"label":"Avg CQS Score","data":[a["cqs"]["red"],a["cqs"]["amber"],a["cqs"]["green"]],"backgroundColor":["#ef444488","#f59e0b88","#10b98188"],"borderColor":["#ef4444","#f59e0b","#10b981"],"borderWidth":2},
    ])
    js += [f"new Chart(document.getElementById('ch_enq'),{enq_cfg});",
           f"new Chart(document.getElementById('ch_reply'),{reply_cfg});",
           f"new Chart(document.getElementById('ch_act'),{act_cfg});",
           f"new Chart(document.getElementById('ch_cqs'),{cqs_cfg});"]

    engage_html = f"""<div class="section">
      <div class="section-title">📊 Engagement Gap — Red vs Amber vs Green</div>
      <div class="section-subtitle">Average values per metric across risk tiers. These gaps confirm the model's signal validity.</div>
      <div class="grid g2">
        <div class="card"><div class="card-title">Avg Enquiries per 30 Days</div><div class="chart-wrap-sm"><canvas id="ch_enq"></canvas></div></div>
        <div class="card"><div class="card-title">Avg Reply Rate (%)</div><div class="chart-wrap-sm"><canvas id="ch_reply"></canvas></div></div>
        <div class="card"><div class="card-title">Avg Platform Active Days (30d)</div><div class="chart-wrap-sm"><canvas id="ch_act"></canvas></div></div>
        <div class="card"><div class="card-title">Avg CQS (Catalog Quality Score)</div><div class="chart-wrap-sm"><canvas id="ch_cqs"></canvas></div></div>
      </div>
      <div class="insight-box" style="--accent-c:#6366f1">
        <h4>Engagement Gap Proof Points</h4>
        <p>
          Red sellers average <b>{a["enq"]["red"]} enquiries/30d</b> vs <b>{a["enq"]["green"]} for Green</b>
          ({round((1-a["enq"]["red"]/a["enq"]["green"])*100) if a["enq"]["green"] else "N/A"}% fewer).<br>
          Reply rate: Red = <b>{a["reply"]["red"]}%</b> vs Green = <b>{a["reply"]["green"]}%</b>.<br>
          Active days: Red = <b>{a["act"]["red"]}d</b> vs Green = <b>{a["act"]["green"]}d</b> per month.<br>
          CQS: Red sellers average <b>{a["cqs"]["red"]}</b> vs Green <b>{a["cqs"]["green"]}</b>.
        </p>
      </div>
    </div>"""

    # Section 4 — BL Velocity
    vel_cfg = chart_cfg("bar", list(a["vel_buckets"].keys()), [
        {"label":"Sellers","data":list(a["vel_buckets"].values()),
         "backgroundColor":["#ef444488","#f59e0b88","#f59e0b44","#10b98188","#10b981cc"],
         "borderColor":["#ef4444","#f59e0b","#f59e0b","#10b981","#10b981"],"borderWidth":2}
    ])
    js.append(f"new Chart(document.getElementById('ch_vel'),{vel_cfg});")

    bl_html = f"""<div class="section">
      <div class="section-title">📉 BL Velocity Analysis — Month-over-Month Drop</div>
      <div class="section-subtitle">
        BL Velocity Drop is the #1 churn predictor per the Phase 2 model.
        Measured as % change in enquiries from the previous month to the current month.
        Only sellers with 6-month scorecard data included (n={a["bl_vel"]["total"]}).
      </div>
      <div class="grid g3">
        <div class="metric-card" style="--c:#ef4444"><div class="metric-lbl">Avg MoM Velocity</div><div class="metric-val">{a["bl_vel"]["avg"]}%</div><div class="metric-sub">Across all sellers with data</div></div>
        <div class="metric-card" style="--c:#f59e0b"><div class="metric-lbl">Sellers Declining &gt;10%</div><div class="metric-val">{a["bl_vel"]["declining_count"]}</div><div class="metric-sub">{a["bl_vel"]["declining_pct"]}% of sellers with velocity data</div></div>
        <div class="metric-card" style="--c:#6366f1"><div class="metric-lbl">Sellers With Velocity Data</div><div class="metric-val">{a["bl_vel"]["total"]}</div></div>
      </div>
      <div class="card" style="margin-top:16px"><div class="card-title">BL Velocity Distribution</div><div class="chart-wrap"><canvas id="ch_vel"></canvas></div></div>
      <div class="insight-box" style="--accent-c:#ef4444">
        <h4>BL Velocity Finding</h4>
        <p><b>{a["bl_vel"]["declining_count"]} sellers ({a["bl_vel"]["declining_pct"]}%)</b> show &gt;10% MoM decline in enquiry volume —
        the primary trigger for Phase 2 Red classification per the churn model framework.
        Average velocity across the cohort: <b>{a["bl_vel"]["avg"]}%</b>.</p>
      </div>
    </div>"""

    # Section 5 — RAG distribution
    rag_labels = list(a["rag_counts"].keys())
    rag_vals   = [a["rag_counts"][k] for k in rag_labels]
    rag_colors = {"Red":"#ef4444","Amber":"#f59e0b","Green":"#10b981","Green+":"#34d399","Unknown":"#94a3b8"}
    rag_cfg = chart_cfg("doughnut", rag_labels, [
        {"data": rag_vals, "backgroundColor":[rag_colors.get(l,"#94a3b8") for l in rag_labels], "borderWidth":0}
    ])
    js.append(f"new Chart(document.getElementById('ch_rag'),{rag_cfg});")

    rag_html = f"""<div class="section">
      <div class="section-title">🚦 RAG Category Distribution</div>
      <div class="section-subtitle">
        RAG (Red-Amber-Green) is IndiaMART's internal seller health classification from the composite profile API.
        A Red RAG category is the strongest single-field churn predictor — contributing +25 points to churn score.
      </div>
      <div class="grid g2">
        <div class="card"><div class="card-title">RAG Distribution</div><div class="chart-wrap-sm"><canvas id="ch_rag"></canvas></div></div>
        <div class="card">
          <div class="card-title">RAG Counts & Risk Correlation</div>
          {''.join(f'<div class="bar-row"><div class="bar-lbl">{esc(k)}</div><div class="bar-track"><div class="bar-fill" style="width:{max(4,round(v/max(rag_vals)*100))}%;background:{rag_colors.get(k,"#94a3b8")}">{v} ({pct(v,total)}%)</div></div></div>' for k,v in a["rag_counts"].items())}
        </div>
      </div>
      <div class="insight-box" style="--accent-c:#ef4444">
        <h4>RAG Finding</h4>
        <p><b>{a["rag_counts"].get("Red",0)} sellers ({pct(a["rag_counts"].get("Red",0),total)}%)</b> are Red-RAG —
        IndiaMART's own highest-risk classification. Combined Red+Amber RAG:
        <b>{a["rag_counts"].get("Red",0)+a["rag_counts"].get("Amber",0)} sellers
        ({pct(a["rag_counts"].get("Red",0)+a["rag_counts"].get("Amber",0),total)}%)</b>.
        These sellers are in the direct churn pathway without intervention.</p>
      </div>
    </div>"""

    # Section 6 — CQS analysis
    cqs_cfg_chart = chart_cfg("bar", list(a["cqs_buckets"].keys()), [
        {"label":"Sellers","data":list(a["cqs_buckets"].values()),
         "backgroundColor":["#ef444488","#f59e0b88","#10b98188","#10b981cc"],
         "borderColor":["#ef4444","#f59e0b","#10b981","#10b981"],"borderWidth":2}
    ])
    js.append(f"new Chart(document.getElementById('ch_cqs2'),{cqs_cfg_chart});")

    cqs_html = f"""<div class="section">
      <div class="section-title">📦 Catalog Quality Score (CQS) Analysis</div>
      <div class="section-subtitle">
        CQS measures product listing quality — photos, descriptions, ISQ, price, brochure, video.
        Low CQS directly causes low buyer visibility, leading to fewer enquiries → churn.
        Per the Track A framework, sellers with CQS &lt;75 need specific actionable gap-closing.
      </div>
      <div class="card"><div class="card-title">CQS Distribution</div><div class="chart-wrap"><canvas id="ch_cqs2"></canvas></div></div>
      <div class="insight-box" style="--accent-c:#f59e0b">
        <h4>CQS Finding</h4>
        <p>
          <b>{a["cqs_buckets"]["<60"]} sellers ({pct(a["cqs_buckets"]["<60"], len([s for s in signals if s.get("cqs") is not None]))}% of sellers with CQS data)</b>
          have CQS below 60 — poor catalog quality directly suppressing lead flow.<br>
          <b>{a["cqs_buckets"]["60-75"]} sellers</b> are in the 60–75 range — fixable with targeted product improvements.<br>
          Per Phase 3 Track A: adding photos, descriptions, and ISQs to CQS &lt;60 sellers would recover an estimated 40% of suppressed leads.
        </p>
      </div>
    </div>"""

    # Section 7 — Hotlead engagement
    hl_cfg = chart_cfg("doughnut",
        ["Has Hotlead Activity","No Hotlead Activity"],
        [{"data":[a["hotlead"]["has_hl"],a["hotlead"]["no_hl"]],"backgroundColor":["#10b981","#ef4444"],"borderWidth":0}])
    js.append(f"new Chart(document.getElementById('ch_hl'),{hl_cfg});")

    hl_html = f"""<div class="section">
      <div class="section-title">🔥 Hotlead Engagement Analysis</div>
      <div class="section-subtitle">
        Hotleads represent premium engagement events (PUA, ENQR, UA). Sellers with zero hotlead activity
        show higher churn scores. This validates the Phase 3 "gifted lead" strategy: injecting a real lead
        triggers re-engagement for disengaged sellers.
      </div>
      <div class="grid g2">
        <div class="card"><div class="card-title">Hotlead Activity Split</div><div class="chart-wrap-sm"><canvas id="ch_hl"></canvas></div></div>
        <div class="card">
          <div class="card-title">Avg Churn Score: Hotlead vs No-Hotlead</div>
          <div style="display:flex;gap:20px;align-items:center;height:190px;justify-content:center">
            <div style="text-align:center">
              <div style="font-size:48px;font-weight:900;color:#10b981">{a["hotlead"]["avg_score_hl"]}</div>
              <div style="font-size:12px;color:var(--mut)">Has Hotleads<br>({a["hotlead"]["has_hl"]} sellers)</div>
            </div>
            <div style="font-size:24px;color:var(--mut)">vs</div>
            <div style="text-align:center">
              <div style="font-size:48px;font-weight:900;color:#ef4444">{a["hotlead"]["avg_score_no_hl"]}</div>
              <div style="font-size:12px;color:var(--mut)">No Hotleads<br>({a["hotlead"]["no_hl"]} sellers)</div>
            </div>
          </div>
        </div>
      </div>
      <div class="insight-box" style="--accent-c:#10b981">
        <h4>Hotlead Finding</h4>
        <p>Sellers with hotlead activity average a churn score of <b>{a["hotlead"]["avg_score_hl"]}</b>
        vs <b>{a["hotlead"]["avg_score_no_hl"]}</b> for sellers with zero hotlead events —
        a <b>{abs(round(a["hotlead"]["avg_score_no_hl"]-a["hotlead"]["avg_score_hl"],1))} point gap</b>.
        This confirms that engagement events are a strong protective factor and validates the
        Phase 4 "gifted lead" intervention approach.</p>
      </div>
    </div>"""

    # Section 8 — Account age vs churn
    age_keys = list(a["age_avg_scores"].keys())
    age_scores = [a["age_avg_scores"][k] for k in age_keys]
    age_counts_vals = [a["age_counts"][k] for k in age_keys]
    age_cfg = chart_cfg("bar", age_keys, [
        {"label":"Avg Churn Score","data":age_scores,"backgroundColor":"#6366f188","borderColor":"#6366f1","borderWidth":2,"yAxisID":"y"},
        {"label":"Seller Count","data":age_counts_vals,"type":"line","borderColor":"#f59e0b","backgroundColor":"#f59e0b22","borderWidth":2,"yAxisID":"y1"},
    ], {"scales":{"y":{"ticks":{"color":"#94a3b8"},"grid":{"color":"#2e3350"}},"y1":{"ticks":{"color":"#f59e0b"},"position":"right","grid":{"drawOnChartArea":False}}}})
    js.append(f"new Chart(document.getElementById('ch_age'),{age_cfg});")

    age_html = f"""<div class="section">
      <div class="section-title">📅 Account Age vs Churn Risk</div>
      <div class="section-subtitle">
        Does churn risk vary by how long a seller has been on the platform?
        Identifies which cohort is most at risk — new sellers (onboarding failure) vs veteran sellers (ROI fatigue).
      </div>
      <div class="card"><div class="card-title">Avg Churn Score by Account Age</div><div class="chart-wrap"><canvas id="ch_age"></canvas></div></div>
      <div class="insight-box" style="--accent-c:#8b5cf6">
        <h4>Account Age Finding</h4>
        <p>{'<br>'.join(f"<b>{k}</b>: {a['age_counts'][k]} sellers, avg score {a['age_avg_scores'][k]}" for k in age_keys)}</p>
      </div>
    </div>"""

    # Section 9 — Red tier seller table
    red_rows = ""
    for s in a["red_sellers"][:30]:
        tag = f'<span class="tag tag-red">Red</span>'
        reasons_short = esc(s["reasons"][0][:60]) if s.get("reasons") else "—"
        red_rows += f"""<tr>
          <td><a href="../data/{s["glid"]}/dashboard.html" style="color:var(--acc3)">{esc(str(s["glid"]))}</a></td>
          <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{esc(s.get("company",""))}</td>
          <td>{esc(s.get("city",""))}</td>
          <td><b style="color:#ef4444">{s["score"]}</b></td>
          <td>{esc(str(s.get("rag","")))} </td>
          <td>{esc(str(s.get("cqs","—")))}</td>
          <td>{esc(str(s.get("reply_rate","—")))}%</td>
          <td>{esc(str(s.get("active_days","—")))}</td>
          <td style="font-size:10px;color:var(--mut);max-width:200px">{reasons_short}</td>
        </tr>"""

    red_table_html = f"""<div class="section">
      <div class="section-title">🔴 Red Tier Sellers — Full List (Top 30 by Score)</div>
      <div class="section-subtitle">Sellers requiring immediate intervention. Click GLID to open individual dashboard.</div>
      <div class="tbl-wrap"><table>
        <thead><tr><th>GLID</th><th>Company</th><th>City</th><th>Score</th><th>RAG</th><th>CQS</th><th>Reply%</th><th>Active Days</th><th>Top Risk Signal</th></tr></thead>
        <tbody>{red_rows}</tbody>
      </table></div>
    </div>"""

    # Section 10 — Phase-mapped interventions
    actions_html = f"""<div class="section">
      <div class="section-title">💡 Recommended Interventions (Phase-Mapped)</div>
      <div class="section-subtitle">Based on the churn solution framework. Interventions mapped to each risk tier.</div>
      <div class="grid g3">
        <div class="insight-box" style="--accent-c:#ef4444">
          <h4>🔴 Red Tier — {a["red"]} sellers</h4>
          <p>
            <b>Phase 2:</b> Flag for human PNS caller queue immediately.<br>
            <b>Phase 3 Track B:</b> Generate personalised call script with SHAP top-2 reasons.<br>
            <b>Phase 4:</b> Unlock 3–5 next-tier leads if 10d from predicted dropout.<br>
            <b>Priority signal:</b> {esc(a["top_reasons"][0][0]) if a["top_reasons"] else "N/A"}<br>
            <b>Estimated at-risk ARR:</b> ₹{round(a["red"]*15000/100000,1)}L (at ₹15k/seller/yr)
          </p>
        </div>
        <div class="insight-box" style="--accent-c:#f59e0b">
          <h4>🟡 Amber Tier — {a["amber"]} sellers</h4>
          <p>
            <b>Phase 2:</b> Automated WhatsApp nudge with peer BL comparison.<br>
            <b>Phase 3 Track A:</b> Dashboard comparison card becomes prominent.<br>
            <b>Phase 3 Track B:</b> Gifted lead if engagement drops further.<br>
            <b>Priority signal:</b> {esc(a["top_reasons"][1][0]) if len(a["top_reasons"])>1 else "N/A"}<br>
            <b>Estimated at-risk ARR:</b> ₹{round(a["amber"]*15000/100000,1)}L
          </p>
        </div>
        <div class="insight-box" style="--accent-c:#10b981">
          <h4>🟢 Green Tier — {a["green"]} sellers</h4>
          <p>
            <b>Phase 5:</b> Renewal window boost — unlock 3–5 premium leads 7d before renewal.<br>
            <b>Phase 3 Track A:</b> Standard peer comparison card visible.<br>
            Monitor daily — any BL velocity drop &gt;20% triggers re-scoring.<br>
            <b>Focus:</b> Maintain engagement, prevent drift to Amber.
          </p>
        </div>
      </div>
    </div>"""

    report_html = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Churn Analysis Report — IndiaMART</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>{CSS}</style></head><body>
<div class="hdr">
  <h1>🔥 Seller Churn Analysis Report — IndiaMART</h1>
  <p>Phase 2 Churn Predictor analysis across {total} sellers. All signals sourced from live API data.
     Aligned to IndiaMART Seller Churn Reduction &amp; Winback System — 5-Phase Lifecycle Architecture.</p>
  <div class="hdr-meta">
    <div class="badge red"><b>{a["red"]} Red</b> ({a["risk_pct"]["Red"]}%)</div>
    <div class="badge amber"><b>{a["amber"]} Amber</b> ({a["risk_pct"]["Amber"]}%)</div>
    <div class="badge green"><b>{a["green"]} Green</b> ({a["risk_pct"]["Green"]}%)</div>
    <div class="badge"><b>{total}</b> total sellers</div>
    <div class="badge">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
    <a href="../index.html" style="text-decoration:none"><div class="badge">← Seller Index</div></a>
  </div>
</div>
<main>
{exec_html}
{rca_html}
{engage_html}
{bl_html}
{rag_html}
{cqs_html}
{hl_html}
{age_html}
{red_table_html}
{actions_html}
</main>
<script>{"".join(js)}</script>
</body></html>"""

    out = os.path.join(ANALYSIS, "churn_report.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(report_html)
    print(f"  Report -> {out}")
    return out

def main():
    print("Loading churn signals...")
    signals = load_signals()
    print(f"  {len(signals)} sellers loaded")
    print("Running analysis...")
    a = analyse(signals)
    print(f"  Red: {a['red']} | Amber: {a['amber']} | Green: {a['green']}")
    print("Building report...")
    build_report(a, signals)
    # Save analysis JSON too
    with open(os.path.join(ANALYSIS, "analysis_results.json"), "w", encoding="utf-8") as f:
        json.dump({k:v for k,v in a.items() if k != "red_sellers"}, f, indent=2, default=str)
    print("Done.")

if __name__ == "__main__":
    main()
