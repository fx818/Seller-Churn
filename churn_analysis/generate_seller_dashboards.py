"""
Generates dashboard.html for each GLID in data/<glid>/
Generic but churn-analysis-aware: shows all API responses in one unified seller view.
"""
import json, os, re
from datetime import datetime

BASE   = os.path.dirname(__file__)
DATA   = os.path.join(BASE, "data")

PALETTE = ["#6366f1","#8b5cf6","#06b6d4","#10b981","#f59e0b","#ef4444","#ec4899","#14b8a6","#f97316","#a855f7"]

# ── Helpers ──────────────────────────────────────────────────────────────────
def load(glid, name):
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

def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')
def humanize(k): return re.sub(r'[_\-]+',' ',str(k)).title()
def jdump(obj): return json.dumps(obj, ensure_ascii=False, default=str)

def chart(type_, labels, datasets, opts=None):
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

CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0f1117;--s1:#1a1d27;--s2:#22263a;--bdr:#2e3350;--acc:#6366f1;--acc2:#8b5cf6;--acc3:#06b6d4;--grn:#10b981;--ylw:#f59e0b;--red:#ef4444;--txt:#e2e8f0;--mut:#94a3b8;--r:12px}
body{background:var(--bg);color:var(--txt);font-family:'Inter',system-ui,sans-serif;min-height:100vh}
.hdr{background:linear-gradient(135deg,#1e1b4b,#0f172a);border-bottom:1px solid var(--bdr);padding:18px 28px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.hdr-icon{width:40px;height:40px;background:linear-gradient(135deg,var(--acc),var(--acc2));border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0}
.hdr h1{font-size:17px;font-weight:700}.hdr p{font-size:11px;color:var(--mut);margin-top:2px}
.hdr-right{margin-left:auto;display:flex;gap:6px;flex-wrap:wrap}
.badge{background:var(--s2);border:1px solid var(--bdr);padding:3px 10px;border-radius:14px;font-size:11px;color:var(--mut)}
.badge b{color:var(--txt)}.badge.risk-red{border-color:#ef444466;color:#ef4444}.badge.risk-amber{border-color:#f59e0b66;color:#f59e0b}.badge.risk-green{border-color:#10b98166;color:#10b981}
main{padding:20px 28px}
.grid{display:grid;gap:14px}.g2{grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}.g3{grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}.g4{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.card{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:18px;overflow:hidden}
.card-title{font-size:12px;font-weight:600;color:var(--mut);text-transform:uppercase;letter-spacing:.5px;margin-bottom:14px}
.metric-card{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:16px;position:relative;overflow:hidden}
.metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--c,var(--acc))}
.metric-lbl{font-size:10px;color:var(--mut);text-transform:uppercase;letter-spacing:.5px}
.metric-val{font-size:22px;font-weight:800;margin:5px 0 3px;color:var(--c,var(--txt))}
.metric-sub{font-size:10px;color:var(--mut)}
.section{margin-bottom:24px}
.section-title{font-size:14px;font-weight:700;margin-bottom:12px;display:flex;align-items:center;gap:8px;border-bottom:1px solid var(--bdr);padding-bottom:8px}
table{width:100%;border-collapse:collapse;font-size:12px}
thead{background:var(--s2)}
th{padding:8px 10px;text-align:left;font-size:10px;color:var(--mut);text-transform:uppercase;letter-spacing:.4px;white-space:nowrap;border-bottom:1px solid var(--bdr)}
td{padding:9px 10px;border-bottom:1px solid var(--bdr);vertical-align:top}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--s2)}
.tbl-wrap{overflow-x:auto;border-radius:var(--r);border:1px solid var(--bdr)}
.tag{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:500}
.tag-green{background:#064e3b44;color:#34d399;border:1px solid #10b98144}
.tag-red{background:#450a0a44;color:#fca5a5;border:1px solid #ef444444}
.tag-blue{background:#1e3a5f44;color:#60a5fa;border:1px solid #3b82f644}
.tag-yellow{background:#451a0344;color:#fbbf24;border:1px solid #f59e0b44}
.tag-purple{background:#2d1b6944;color:#a78bfa;border:1px solid #8b5cf644}
.chart-wrap{position:relative;height:260px}.chart-wrap-sm{position:relative;height:190px}
.dual-bar{display:flex;align-items:center;gap:8px;margin-bottom:7px}
.dual-lbl{width:160px;font-size:11px;color:var(--mut);text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex-shrink:0}
.dual-track{flex:1;display:flex;gap:3px}
.dual-fill{height:20px;border-radius:4px;display:flex;align-items:center;padding:0 6px;font-size:10px;font-weight:600;color:#fff;min-width:24px}
.tl-item{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--bdr)}
.tl-item:last-child{border-bottom:none}
.tl-dot{width:8px;height:8px;border-radius:50%;background:var(--acc);flex-shrink:0;margin-top:4px}
.tl-title{font-size:12px;font-weight:600}
.tl-time{font-size:10px;color:var(--mut);margin-top:2px}
.tl-meta{display:flex;gap:4px;flex-wrap:wrap;margin-top:4px}
.no-data{background:var(--s2);border:1px solid var(--bdr);border-radius:var(--r);padding:24px;text-align:center;color:var(--mut);font-size:12px}
.churn-banner{border-radius:var(--r);padding:16px 20px;margin-bottom:20px;display:flex;align-items:center;gap:16px}
.churn-banner.red{background:#450a0a44;border:1px solid #ef444466}
.churn-banner.amber{background:#451a0344;border:1px solid #f59e0b66}
.churn-banner.green{background:#064e3b44;border:1px solid #10b98166}
.churn-score{font-size:36px;font-weight:900;flex-shrink:0}
.churn-reasons{font-size:12px;color:var(--mut);margin-top:4px}
.churn-reasons li{margin-top:3px}
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--bdr);border-radius:2px}
"""

def yn_tag(v):
    s = str(v).upper()
    if s == "YES": return '<span class="tag tag-green">YES</span>'
    if s == "NO":  return '<span class="tag tag-red">NO</span>'
    return esc(str(v))

# ── Churn score computer ─────────────────────────────────────────────────────
def compute_churn_signals(glid):
    signals = {}
    reasons = []
    score   = 0

    # 1. scorecard_summary — BL count, reply rate, active days
    ss = load(glid, "scorecard_summary")
    if ss and ss.get("status") == 200:
        inner = safe_parse(ss.get("data",{}).get("response","{}"))
        summ  = inner.get("summary", [{}])[0] if inner.get("summary") else {}
        tot_enq = safe_parse(summ.get("tot_enq","{}"))
        enq_replied = safe_parse(summ.get("enq_replied","{}"))
        lms_days = safe_parse(summ.get("lms_active_days","{}"))
        bl_cons  = safe_parse(summ.get("bl_cons","{}"))

        enq_30 = tot_enq.get("30d",0) or 0 if isinstance(tot_enq,dict) else 0
        rep_30 = enq_replied.get("30d",0) or 0 if isinstance(enq_replied,dict) else 0
        act_30 = lms_days.get("30d",0) or 0 if isinstance(lms_days,dict) else 0
        bl_30  = bl_cons.get("30d",0) or 0 if isinstance(bl_cons,dict) else 0

        signals["enq_30d"]    = enq_30
        signals["replied_30d"]= rep_30
        signals["active_days_30d"] = act_30
        signals["bl_cons_30d"]= bl_30
        signals["city"]       = summ.get("gl_city_name","")
        signals["enterprise"] = summ.get("enterprise_type","")
        signals["client_since"]= summ.get("client_since","")

        # Reply rate
        reply_rate = round(rep_30/enq_30*100,1) if enq_30 > 0 else 0
        signals["reply_rate_30d"] = reply_rate
        if reply_rate < 40 and enq_30 > 0:
            score += 20
            reasons.append(f"Low reply rate: {reply_rate}% (threshold 40%)")
        if act_30 == 0:
            score += 18
            reasons.append("Zero LMS active days in last 30d — seller not logging in")
        elif act_30 <= 3:
            score += 10
            reasons.append(f"Only {act_30} active days in last 30d — low engagement")
        if enq_30 == 0:
            score += 15
            reasons.append("Zero enquiries in last 30d — no lead flow")

    # 2. scorecard_6m — BL velocity, PNS success, monthly trend
    s6 = load(glid, "scorecard_6m")
    if s6 and s6.get("status") == 200:
        inner  = safe_parse(s6.get("data",{}).get("response","{}"))
        months = sorted(inner.get("summary",[]), key=lambda x: x.get("year_month",0))
        if len(months) >= 2:
            last_enq   = months[-1].get("total_enq",0) or 0
            prev_enq   = months[-2].get("total_enq",0) or 0
            if prev_enq > 0:
                velocity = round((last_enq - prev_enq)/prev_enq*100, 1)
                signals["bl_velocity_pct"] = velocity
                if velocity <= -30:
                    score += 22
                    reasons.append(f"BL velocity drop: {velocity}% MoM (critical threshold: -30%)")
                elif velocity <= -10:
                    score += 10
                    reasons.append(f"BL velocity declining: {velocity}% MoM")

            # PNS success trend
            last_pns   = months[-1].get("pns_success_prcnt",100) or 100
            signals["pns_success_pct"] = last_pns
            if last_pns < 60:
                score += 12
                reasons.append(f"PNS answer rate {last_pns}% — below 60% threshold")

            signals["monthly_enq"] = [m.get("total_enq",0) or 0 for m in months]
            signals["monthly_labels"] = [f"{m.get('data_month','')} {m.get('data_year','')}" for m in months]
            signals["monthly_pns"]  = [m.get("pns_calls_recd",0) or 0 for m in months]
            signals["monthly_pns_ans"] = [m.get("pns_calls_ans",0) or 0 for m in months]
            signals["monthly_replies"] = [m.get("replies",0) or 0 for m in months]
            signals["monthly_active_days"] = [m.get("lms_active_days",0) or 0 for m in months]

    # 3. metrics — PNS, calls, meetings
    mt = load(glid, "metrics")
    if mt and mt.get("status") == 200:
        d = mt.get("data", mt.get("data",{}))
        signals["pns_received_90d"]  = d.get("pns_received_90d",0) or 0
        signals["pns_answered_90d"]  = d.get("pns_answered_90d",0) or 0
        signals["enq_received_90d"]  = d.get("enq_received_90d",0) or 0
        signals["enq_replies_90d"]   = d.get("enq_replies_90d",0) or 0
        signals["meetings_90d"]      = d.get("meetings_90d",0) or 0
        signals["pns_received_1yr"]  = d.get("pns_received_1yr",0) or 0
        signals["pns_answered_1yr"]  = d.get("pns_answered_1yr",0) or 0
        signals["enq_received_1yr"]  = d.get("enq_received_1yr",0) or 0
        signals["meetings_1yr"]      = d.get("meetings_1yr",0) or 0
        pns_rate_90 = round(signals["pns_answered_90d"]/signals["pns_received_90d"]*100,1) if signals["pns_received_90d"] > 0 else None
        if pns_rate_90 is not None and pns_rate_90 < 60:
            score += 10
            reasons.append(f"PNS answer rate 90d: {pns_rate_90}%")

    # 4. composite — RAG score, profile
    cp = load(glid, "composite")
    if cp and cp.get("status") == 200:
        d = cp.get("data", {}) or {}
        prof = d.get("profile", {}) or {}
        signals["company"]    = prof.get("company_name","")
        signals["rag"]        = prof.get("rag_category","")
        signals["rag_score"]  = prof.get("rag_score",0)
        signals["account_age"]= prof.get("account_age_days",0)
        signals["paid_history"]= prof.get("paid_history",False)
        signals["ctype"]      = prof.get("customer_type","")
        if signals["rag"] == "Red":
            score += 25
            reasons.append("RAG category: Red — highest churn risk tier")
        elif signals["rag"] == "Amber":
            score += 12
            reasons.append("RAG category: Amber — moderate churn risk")

    # 5. product_summary — CQS
    ps = load(glid, "product_summary")
    if ps and ps.get("status") == 200:
        d = ps.get("data",{})
        inner = d.get("data",d) if isinstance(d,dict) else {}
        cqs = inner.get("CQS",None)
        if cqs is not None:
            signals["cqs"] = cqs
            if cqs < 60:
                score += 15
                reasons.append(f"CQS (Catalog Quality Score): {cqs} — below 60, poor product visibility")
            elif cqs < 75:
                score += 7
                reasons.append(f"CQS: {cqs} — below 75, room for improvement")

    # 6. hotleads — engagement
    hl = load(glid, "hotleads")
    if hl and hl.get("status") == 200:
        d = hl.get("data",{})
        items = d.get("items",[]) if isinstance(d,dict) else []
        signals["hotleads_count"] = len(items)
        if len(items) == 0:
            score += 8
            reasons.append("No hotlead activity — seller not generating engagement events")

    # 7. activity — last event, event count
    ac = load(glid, "activity")
    if ac and ac.get("status") == 200:
        d = ac.get("data",{}) or {}
        events = d.get("events",[])
        ec = d.get("event_count",0)
        signals["event_count"] = ec
        if ec == 0:
            score += 12
            reasons.append("Zero clickstream events — no platform activity recorded")
        elif ec < 10:
            score += 6
            reasons.append(f"Only {ec} clickstream events — very low activity")

        # Last seen
        if events:
            dts = [str(e.get("datevalue","")) for e in events if e.get("datevalue")]
            if dts:
                latest = max(dts)
                signals["last_seen"] = f"{latest[:4]}-{latest[4:6]}-{latest[6:8]}"

    # 8. competitors_counts — market context
    cc = load(glid, "competitors_counts")
    if cc and cc.get("status") == 200:
        inner = safe_parse(cc.get("data",{}).get("response","{}"))
        rows  = inner.get("mcat_data",[])
        if rows:
            r = rows[0]
            signals["total_bl_market"] = r.get("total_bl",0) or 0
            signals["total_paid_market"]= r.get("total_paid_sellers",0) or 0

    # Cap score
    score = min(score, 100)
    signals["churn_score"] = score
    signals["churn_reasons"] = reasons
    if score >= 65:   signals["risk"] = "Red"
    elif score >= 35: signals["risk"] = "Amber"
    else:             signals["risk"] = "Green"

    return signals

# ── Dashboard HTML builder ───────────────────────────────────────────────────
def build_dashboard(glid):
    g = str(glid)
    sig = compute_churn_signals(g)

    score = sig.get("churn_score", 0)
    risk  = sig.get("risk","Green")
    reasons = sig.get("churn_reasons",[])
    risk_color = {"Red":"#ef4444","Amber":"#f59e0b","Green":"#10b981"}[risk]

    all_js = []

    # ── Churn banner
    rl = sig.get("churn_reasons",[])
    reasons_html = "".join(f"<li>⚠ {esc(r)}</li>" for r in rl) if rl else "<li>No major risk signals detected</li>"
    banner = f"""<div class="churn-banner {risk.lower()}">
      <div>
        <div style="font-size:11px;color:{risk_color};font-weight:700;text-transform:uppercase;letter-spacing:1px">Churn Risk</div>
        <div class="churn-score" style="color:{risk_color}">{score}</div>
        <div style="font-size:11px;color:{risk_color}">{risk} Tier</div>
      </div>
      <div style="flex:1">
        <div style="font-size:13px;font-weight:600;margin-bottom:6px">Risk Signals</div>
        <ul class="churn-reasons">{reasons_html}</ul>
      </div>
    </div>"""

    # ── Profile cards
    profile_html = f"""<div class="section">
      <div class="section-title">👤 Seller Profile</div>
      <div class="grid g4">
        <div class="metric-card" style="--c:#6366f1"><div class="metric-lbl">Company</div><div class="metric-val" style="font-size:13px;margin-top:8px">{esc(sig.get("company","—"))}</div></div>
        <div class="metric-card" style="--c:#06b6d4"><div class="metric-lbl">City</div><div class="metric-val" style="font-size:15px">{esc(sig.get("city","—"))}</div></div>
        <div class="metric-card" style="--c:#8b5cf6"><div class="metric-lbl">Customer Type</div><div class="metric-val" style="font-size:12px;margin-top:8px">{esc(sig.get("ctype","—"))}</div></div>
        <div class="metric-card" style="--c:#f59e0b"><div class="metric-lbl">Account Age</div><div class="metric-val">{sig.get("account_age","—")}</div><div class="metric-sub">days</div></div>
        <div class="metric-card" style="--c:{risk_color}"><div class="metric-lbl">RAG Category</div><div class="metric-val" style="font-size:15px;color:{risk_color}">{esc(sig.get("rag","—"))}</div></div>
        <div class="metric-card" style="--c:#10b981"><div class="metric-lbl">Paid History</div><div class="metric-val" style="font-size:15px">{'Yes' if sig.get('paid_history') else 'No'}</div></div>
        <div class="metric-card" style="--c:#ec4899"><div class="metric-lbl">Client Since</div><div class="metric-val" style="font-size:15px">{esc(sig.get("client_since","—"))}</div></div>
        <div class="metric-card" style="--c:#14b8a6"><div class="metric-lbl">CQS Score</div><div class="metric-val">{sig.get("cqs","—")}</div></div>
      </div>
    </div>"""

    # ── Engagement KPIs
    eng_html = f"""<div class="section">
      <div class="section-title">📊 Engagement Signals</div>
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

    # ── Monthly trend charts
    charts_html = ""
    if sig.get("monthly_labels"):
        labels = sig["monthly_labels"]

        enq_cfg = chart("bar", labels, [
            {"label":"Enquiries","data":sig.get("monthly_enq",[]),"backgroundColor":"#6366f188","borderColor":"#6366f1","borderWidth":2},
            {"label":"Replies","data":sig.get("monthly_replies",[]),"backgroundColor":"#10b98188","borderColor":"#10b981","borderWidth":2},
        ])
        pns_cfg = chart("bar", labels, [
            {"label":"PNS Received","data":sig.get("monthly_pns",[]),"backgroundColor":"#06b6d488","borderColor":"#06b6d4","borderWidth":2},
            {"label":"PNS Answered","data":sig.get("monthly_pns_ans",[]),"backgroundColor":"#10b98188","borderColor":"#10b981","borderWidth":2},
        ])
        act_cfg = chart("line", labels, [
            {"label":"Active Days","data":sig.get("monthly_active_days",[]),"borderColor":"#f59e0b","backgroundColor":"#f59e0b22","borderWidth":2,"tension":0.4,"fill":True},
        ])
        all_js += [
            f"new Chart(document.getElementById('ch_enq'),{enq_cfg});",
            f"new Chart(document.getElementById('ch_pns'),{pns_cfg});",
            f"new Chart(document.getElementById('ch_act'),{act_cfg});",
        ]
        charts_html = f"""<div class="section">
          <div class="section-title">📈 Monthly Trends</div>
          <div class="grid g2">
            <div class="card"><div class="card-title">Enquiries vs Replies</div><div class="chart-wrap"><canvas id="ch_enq"></canvas></div></div>
            <div class="card"><div class="card-title">PNS Calls</div><div class="chart-wrap"><canvas id="ch_pns"></canvas></div></div>
          </div>
          <div class="card" style="margin-top:14px"><div class="card-title">Platform Active Days</div><div class="chart-wrap-sm"><canvas id="ch_act"></canvas></div></div>
        </div>"""

    # ── Competitors section
    comp_html = ""
    comp_data = load(g, "competitors")
    if comp_data and comp_data.get("status") == 200:
        inner = safe_parse(comp_data.get("data",{}).get("response","{}"))
        comps = inner.get("competitors",[])
        if comps:
            rows = "".join(f"""<tr>
              <td>{esc(c.get("competitor_company",""))}</td>
              <td><span class="tag tag-blue">{esc(c.get("custtype_name",""))}</span></td>
              <td>{esc(c.get("competitor_city",""))}</td>
              <td>{esc(c.get("competitor_membersince",""))}</td>
            </tr>""" for c in comps[:10])
            comp_html = f"""<div class="section">
              <div class="section-title">🏭 Top Competitors ({len(comps)} total)</div>
              <div class="tbl-wrap"><table>
                <thead><tr><th>Company</th><th>Type</th><th>City</th><th>Member Since</th></tr></thead>
                <tbody>{rows}</tbody>
              </table></div>
              <div style="margin-top:10px;font-size:11px;color:var(--mut)">Market: {sig.get("total_bl_market",0)} total BLs | {sig.get("total_paid_market",0)} paid sellers</div>
            </div>"""

    # ── Hotleads timeline
    hl_html = ""
    hl_data = load(g, "hotleads")
    if hl_data and hl_data.get("status") == 200:
        items = (hl_data.get("data",{}) or {}).get("items",[])
        if items:
            dc = {"PUA":"#6366f1","UA":"#10b981","ENQR":"#f59e0b","CALL":"#06b6d4"}
            tl = "".join(f"""<div class="tl-item">
              <div class="tl-dot" style="background:{dc.get(it.get('data_type',''),'#94a3b8')}"></div>
              <div><div class="tl-title">{esc(it.get("activity",""))}</div>
              <div class="tl-time">{esc(str(it.get("hotlead_date","")))} <span class="tag tag-purple">{esc(it.get("data_type",""))}</span></div></div>
            </div>""" for it in items[:10])
            hl_html = f"""<div class="section">
              <div class="section-title">🔥 Hotlead Activity ({len(items)} events)</div>
              <div class="card">{tl}</div>
            </div>"""

    body = banner + profile_html + eng_html + charts_html + comp_html + hl_html

    html = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GLID {g} — Seller Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>{CSS}</style></head><body>
<div class="hdr">
  <div class="hdr-icon">📊</div>
  <div><h1>Seller Dashboard — GLID {g}</h1><p>{esc(sig.get("company",""))}</p></div>
  <div class="hdr-right">
    <div class="badge risk-{risk.lower()}"><b>{risk} Risk · Score {score}</b></div>
    <div class="badge">{esc(sig.get("city",""))}</div>
    <div class="badge">Generated: {datetime.now().strftime("%Y-%m-%d")}</div>
    <a href="../index.html" style="text-decoration:none"><div class="badge">← All Sellers</div></a>
  </div>
</div>
<main>{body}</main>
<script>{"".join(all_js)}</script>
</body></html>"""

    out = os.path.join(DATA, g, "dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return sig

# ── Master index ─────────────────────────────────────────────────────────────
def build_index(all_sigs):
    risk_color = {"Red":"#ef4444","Amber":"#f59e0b","Green":"#10b981"}
    red   = [s for s in all_sigs if s.get("risk")=="Red"]
    amber = [s for s in all_sigs if s.get("risk")=="Amber"]
    green = [s for s in all_sigs if s.get("risk")=="Green"]

    def card(s):
        g = s["glid"]
        rc = risk_color.get(s.get("risk","Green"),"#10b981")
        return f"""<a href="data/{g}/dashboard.html" style="text-decoration:none">
          <div class="seller-card" style="--stripe:{rc}">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
              <div style="font-size:18px;font-weight:900;color:{rc}">{s.get("churn_score",0)}</div>
              <div>
                <div style="font-size:13px;font-weight:700;color:var(--txt)">{esc(s.get("company","GLID "+str(g)))}</div>
                <div style="font-size:11px;color:var(--mut)">{esc(s.get("city",""))} · {esc(s.get("ctype",""))}</div>
              </div>
              <div class="risk-dot" style="background:{rc};margin-left:auto"></div>
            </div>
            <div style="font-size:10px;color:var(--mut);display:flex;gap:8px;flex-wrap:wrap">
              <span>Enq: {s.get("enq_30d","—")}</span>
              <span>Reply: {s.get("reply_rate_30d","—")}%</span>
              <span>Active: {s.get("active_days_30d","—")}d</span>
              <span>CQS: {s.get("cqs","—")}</span>
              <span>RAG: {s.get("rag","—")}</span>
            </div>
            {('<div style="font-size:10px;color:'+rc+';margin-top:6px">⚠ '+esc(s["churn_reasons"][0])+'</div>') if s.get("churn_reasons") else ""}
          </div></a>"""

    def section(title, items, icon):
        if not items: return ""
        return f"""<div class="group-title">{icon} {title} ({len(items)})</div>
        <div class="seller-grid">{"".join(card(s) for s in sorted(items, key=lambda x:-x.get("churn_score",0)))}</div>"""

    html = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Churn Analysis — All Sellers</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#0f1117;--s1:#1a1d27;--s2:#22263a;--bdr:#2e3350;--acc:#6366f1;--txt:#e2e8f0;--mut:#94a3b8;--r:10px}}
body{{background:var(--bg);color:var(--txt);font-family:'Inter',system-ui,sans-serif}}
.hdr{{background:linear-gradient(135deg,#1e1b4b,#0f172a);border-bottom:1px solid var(--bdr);padding:20px 32px}}
.hdr h1{{font-size:20px;font-weight:800}}.hdr p{{font-size:12px;color:var(--mut);margin-top:4px}}
.stats{{display:flex;gap:12px;margin-top:14px;flex-wrap:wrap}}
.stat{{background:var(--s2);border:1px solid var(--bdr);padding:8px 16px;border-radius:20px;font-size:12px}}
.stat b{{font-size:18px;display:block;font-weight:800}}
.stat.red{{border-color:#ef444466;color:#ef4444}}.stat.amber{{border-color:#f59e0b66;color:#f59e0b}}.stat.green{{border-color:#10b98166;color:#10b981}}
main{{padding:24px 32px}}
.group-title{{font-size:11px;font-weight:700;color:var(--mut);text-transform:uppercase;letter-spacing:1px;margin:24px 0 12px;display:flex;align-items:center;gap:8px}}
.group-title::after{{content:'';flex:1;height:1px;background:var(--bdr)}}
.seller-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}}
.seller-card{{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:14px;cursor:pointer;transition:all .15s;position:relative;overflow:hidden}}
.seller-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--stripe,var(--acc))}}
.seller-card:hover{{border-color:var(--acc);transform:translateY(-2px)}}
.risk-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
::-webkit-scrollbar{{width:4px}}.hdr-right{{margin-left:auto}}
</style></head><body>
<div class="hdr">
  <h1>🔥 Churn Analysis Dashboard</h1>
  <p>IndiaMART Seller Churn Risk — All {len(all_sigs)} sellers analysed</p>
  <div class="stats">
    <div class="stat red"><b>{len(red)}</b>Red (High Risk)</div>
    <div class="stat amber"><b>{len(amber)}</b>Amber (Medium Risk)</div>
    <div class="stat green"><b>{len(green)}</b>Green (Low Risk)</div>
    <div class="stat"><b>{len(all_sigs)}</b>Total Sellers</div>
    <div class="stat"><b>{round(len(red)/len(all_sigs)*100,1) if all_sigs else 0}%</b>High Risk Rate</div>
  </div>
</div>
<main>
  {section("HIGH RISK — Immediate Intervention Required", red, "🔴")}
  {section("MEDIUM RISK — Monitor & Nudge", amber, "🟡")}
  {section("LOW RISK — Healthy", green, "🟢")}
</main>
</body></html>"""

    out = os.path.join(BASE, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Master index -> {out}")

# ── Run ───────────────────────────────────────────────────────────────────────
def main():
    glids = sorted(os.listdir(DATA))
    glids = [g for g in glids if g.isdigit() and os.path.isdir(os.path.join(DATA, g))]
    print(f"Generating dashboards for {len(glids)} sellers...")
    all_sigs = []
    for i, g in enumerate(glids):
        try:
            sig = build_dashboard(g)
            sig["glid"] = g
            all_sigs.append(sig)
            print(f"  [{i+1}/{len(glids)}] {g} — {sig.get('risk','?')} ({sig.get('churn_score',0)})")
        except Exception as e:
            print(f"  [FAIL] {g}: {e}")
            all_sigs.append({"glid":g,"churn_score":0,"risk":"Green","churn_reasons":[]})

    # Save signals JSON for analysis script
    with open(os.path.join(BASE, "analysis", "churn_signals.json"), "w", encoding="utf-8") as f:
        json.dump(all_sigs, f, indent=2, ensure_ascii=False, default=str)

    build_index(all_sigs)
    print(f"\nDone. {len(all_sigs)} dashboards generated.")

if __name__ == "__main__":
    main()
