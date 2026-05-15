"""
Generates master_dashboard.html — comprehensive churn analytics.
- Overall top 10 churn reasons
- Top 10 reasons per enterprise segment (Proprietor / ME / Partnership / BB)
- Top 10 reasons per subscription type (CATALOG / FCP+PNS / FREELIST / etc.)
- Full numeric stats across all dimensions
"""
import json, os, re
from collections import Counter, defaultdict

BASE_DIR = os.path.dirname(__file__)
SIGNALS_FILE = os.path.join(BASE_DIR, "analysis", "churn_signals.json")
OUT_FILE = os.path.join(BASE_DIR, "master_dashboard.html")

# ── Load signals ─────────────────────────────────────────────────────────────
with open(SIGNALS_FILE, encoding="utf-8") as f:
    sigs = json.load(f)

total = len(sigs)

# ── Helpers ───────────────────────────────────────────────────────────────────
def bucket_reason(r):
    """Normalise a free-text reason into a short category label."""
    r = r.lower()
    if "reply rate" in r:      return "Low Reply Rate"
    if "bl" in r and ("declin" in r or "drop" in r or "velocity" in r or "negative" in r):
        return "BL Decline / Negative Velocity"
    if "pns" in r:             return "Low PNS Answer Rate"
    if "cqs" in r or "catalog quality" in r: return "Low Catalog Quality (CQS)"
    if "login" in r or "inactiv" in r or "active day" in r: return "Inactivity / Low Login"
    if "hotlead" in r or "hot lead" in r:    return "No Hotlead Engagement"
    if "rag" in r:             return "Poor RAG Rating"
    if "activity" in r:       return "Low Platform Activity"
    if "event" in r:          return "Low Activity Events"
    return r[:60].title()

def top_reasons(subset, n=10):
    c = Counter()
    for s in subset:
        for r in s.get("churn_reasons", []):
            c[bucket_reason(r)] += 1
    return c.most_common(n)

def avg(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else 0

def pct(n, total):
    return round(100 * n / total, 1) if total else 0

# ── Segment helpers ───────────────────────────────────────────────────────────
def normalise_ctype(ct):
    ct = (ct or "").strip()
    if not ct or ct == "?": return "Unknown"
    if "CATALOG" in ct.upper() or "TSCATALOG" in ct.upper(): return "CATALOG"
    if "FCP" in ct.upper() and "PNS" in ct.upper(): return "FCP+PNS"
    if "FREE" in ct.upper(): return "FREELIST"
    if "LEADER" in ct.upper(): return "LEADER"
    if "BL PAID" in ct.upper(): return "BL Paid"
    return "Other"

def normalise_enterprise(e):
    e = (e or "").strip()
    if not e: return "Unknown"
    if e in ("ME",): return "ME (Mid Enterprise)"
    if e in ("BB",): return "BB (Big Business)"
    return e  # Proprietor, Partnership, etc.

# ── Compute global stats ──────────────────────────────────────────────────────
red    = [s for s in sigs if s["risk"] == "Red"]
amber  = [s for s in sigs if s["risk"] == "Amber"]
green  = [s for s in sigs if s["risk"] == "Green"]

overall_top10 = top_reasons(sigs, 10)
red_top10     = top_reasons(red, 10)

# Per enterprise segment
ent_groups = defaultdict(list)
for s in sigs:
    ent_groups[normalise_enterprise(s.get("enterprise", ""))].append(s)

# Per subscription type
ct_groups = defaultdict(list)
for s in sigs:
    ct_groups[normalise_ctype(s.get("ctype", ""))].append(s)

# City distribution (Red tier)
city_red = Counter(s.get("city","Unknown") for s in red if s.get("city"))

# Score distribution
score_dist = Counter()
for s in sigs:
    sc = s.get("churn_score", 0)
    if sc < 20:   score_dist["0-19"] += 1
    elif sc < 35: score_dist["20-34"] += 1
    elif sc < 50: score_dist["35-49"] += 1
    elif sc < 65: score_dist["50-64"] += 1
    elif sc < 80: score_dist["65-79"] += 1
    else:         score_dist["80+"] += 1

# Metric avgs per risk tier
def tier_stats(subset):
    return {
        "count":       len(subset),
        "avg_score":   avg([s.get("churn_score") for s in subset]),
        "avg_reply":   avg([s.get("reply_rate_30d") for s in subset]),
        "avg_cqs":     avg([s.get("cqs") for s in subset]),
        "avg_active":  avg([s.get("active_days_30d") for s in subset]),
        "avg_pns":     avg([s.get("pns_success_pct") for s in subset]),
        "avg_enq":     avg([s.get("enq_30d") for s in subset]),
        "avg_hotl":    avg([s.get("hotleads_count") for s in subset]),
    }

# ── JS data payloads ──────────────────────────────────────────────────────────
def bar_cfg(labels, values, label, color="#4F46E5", horizontal=True):
    axis = "indexAxis" if horizontal else ""
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{"label": label, "data": values,
                          "backgroundColor": color, "borderRadius": 4}]
        },
        "options": {
            "indexAxis": "y" if horizontal else "x",
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {"legend": {"display": False}},
            "scales": {
                "x": {"beginAtZero": True,
                      "ticks": {"color": "#94a3b8"},
                      "grid": {"color": "#1e293b"}},
                "y": {"ticks": {"color": "#cbd5e1", "font": {"size": 11}},
                      "grid": {"display": False}}
            }
        }
    }

def doughnut_cfg(labels, values, colors=None):
    colors = colors or ["#ef4444","#f59e0b","#22c55e","#3b82f6","#8b5cf6","#ec4899","#14b8a6","#f97316"]
    return {
        "type": "doughnut",
        "data": {"labels": labels, "datasets": [{"data": values,
            "backgroundColor": colors[:len(labels)],
            "borderWidth": 2, "borderColor": "#0f172a"}]},
        "options": {"responsive": True, "maintainAspectRatio": False,
                    "plugins": {"legend": {"position": "right",
                        "labels": {"color": "#cbd5e1", "font": {"size": 11}}}}}
    }

def grouped_bar_cfg(labels, datasets):
    return {
        "type": "bar",
        "data": {"labels": labels, "datasets": datasets},
        "options": {
            "responsive": True, "maintainAspectRatio": False,
            "plugins": {"legend": {"labels": {"color": "#cbd5e1"}}},
            "scales": {
                "x": {"ticks": {"color": "#94a3b8"}, "grid": {"color": "#1e293b"}},
                "y": {"beginAtZero": True, "ticks": {"color": "#94a3b8"},
                      "grid": {"color": "#1e293b"}}
            }
        }
    }

# ── Build segment reason cards data ──────────────────────────────────────────
def seg_data(groups, n=10):
    out = {}
    for name, subset in sorted(groups.items(), key=lambda x: -len(x[1])):
        if not subset: continue
        reasons = top_reasons(subset, n)
        ts = tier_stats(subset)
        out[name] = {
            "count": len(subset),
            "red": sum(1 for s in subset if s["risk"]=="Red"),
            "amber": sum(1 for s in subset if s["risk"]=="Amber"),
            "green": sum(1 for s in subset if s["risk"]=="Green"),
            "avg_score": ts["avg_score"],
            "avg_reply": ts["avg_reply"],
            "avg_cqs": ts["avg_cqs"],
            "top_reasons": [{"reason": r, "count": c, "pct": pct(c, len(subset))}
                            for r, c in reasons],
        }
    return out

ent_data = seg_data(ent_groups)
ct_data  = seg_data(ct_groups)

# ── Precompute chart JSONs ─────────────────────────────────────────────────────
overall_labels = [r for r, _ in overall_top10]
overall_vals   = [c for _, c in overall_top10]

red_labels = [r for r, _ in red_top10]
red_vals   = [c for _, c in red_top10]

risk_dist_cfg = doughnut_cfg(
    ["Red","Amber","Green"],
    [len(red), len(amber), len(green)],
    ["#ef4444","#f59e0b","#22c55e"]
)

score_labels = ["0-19","20-34","35-49","50-64","65-79","80+"]
score_vals   = [score_dist.get(l,0) for l in score_labels]

city_top = city_red.most_common(10)
city_labels = [c for c,_ in city_top]
city_vals   = [n for _,n in city_top]

tier_metrics_cfg = grouped_bar_cfg(
    ["Reply Rate %", "CQS Score", "Active Days/30d", "Hotleads"],
    [
        {"label":"Red","data":[
            tier_stats(red)["avg_reply"]*100,
            tier_stats(red)["avg_cqs"],
            tier_stats(red)["avg_active"],
            tier_stats(red)["avg_hotl"]],
         "backgroundColor":"#ef4444","borderRadius":4},
        {"label":"Amber","data":[
            tier_stats(amber)["avg_reply"]*100,
            tier_stats(amber)["avg_cqs"],
            tier_stats(amber)["avg_active"],
            tier_stats(amber)["avg_hotl"]],
         "backgroundColor":"#f59e0b","borderRadius":4},
        {"label":"Green","data":[
            tier_stats(green)["avg_reply"]*100,
            tier_stats(green)["avg_cqs"],
            tier_stats(green)["avg_active"],
            tier_stats(green)["avg_hotl"]],
         "backgroundColor":"#22c55e","borderRadius":4},
    ]
)

est_arr = len(red) * 15000
at_risk_pct = pct(len(red), total)

# ── Red seller table ──────────────────────────────────────────────────────────
red_sorted = sorted(red, key=lambda s: -s.get("churn_score",0))

# ── HTML ──────────────────────────────────────────────────────────────────────
def reason_bars_html(top_reasons_list, max_count):
    rows = ""
    colors = ["#ef4444","#f97316","#f59e0b","#eab308","#84cc16",
              "#22c55e","#14b8a6","#3b82f6","#8b5cf6","#ec4899"]
    for i, item in enumerate(top_reasons_list):
        w = round(100 * item["count"] / max_count) if max_count else 0
        c = colors[i % len(colors)]
        rows += f"""
        <div class="reason-row">
          <div class="reason-label">{i+1}. {item['reason']}</div>
          <div class="reason-bar-wrap">
            <div class="reason-bar" style="width:{w}%;background:{c}"></div>
            <span class="reason-num">{item['count']} sellers ({item['pct']}%)</span>
          </div>
        </div>"""
    return rows

def seg_tabs_html(seg_data_dict, tab_prefix):
    if not seg_data_dict: return "<p>No data.</p>"
    names = list(seg_data_dict.keys())
    tabs_html = "".join(
        f'<button class="seg-tab" onclick="showSeg(\'{tab_prefix}\',\'{n}\')" id="{tab_prefix}-tab-{i}">{n} ({seg_data_dict[n]["count"]})</button>'
        for i, n in enumerate(names)
    )
    panels_html = ""
    for i, name in enumerate(names):
        d = seg_data_dict[name]
        max_c = d["top_reasons"][0]["count"] if d["top_reasons"] else 1
        risk_badges = (
            f'<span class="badge-red">{d["red"]} Red</span> '
            f'<span class="badge-amber">{d["amber"]} Amber</span> '
            f'<span class="badge-green">{d["green"]} Green</span>'
        )
        panels_html += f"""
        <div class="seg-panel" id="{tab_prefix}-panel-{i}">
          <div class="seg-header">
            <div>
              <h3>{name}</h3>
              <div class="seg-meta">{d['count']} sellers &nbsp;|&nbsp; Avg Churn Score: <b>{d['avg_score']}</b>
              &nbsp;|&nbsp; Avg Reply Rate: <b>{round(d['avg_reply']*100,1)}%</b>
              &nbsp;|&nbsp; Avg CQS: <b>{d['avg_cqs']}</b></div>
              <div class="seg-meta mt4">{risk_badges}</div>
            </div>
          </div>
          <h4>Top {len(d['top_reasons'])} Churn Reasons</h4>
          <div class="reason-list">{reason_bars_html(d['top_reasons'], max_c)}</div>
        </div>"""
    # activate first tab by default
    return f"""
    <div class="seg-tabs">{tabs_html}</div>
    <div class="seg-panels">{panels_html}</div>
    <script>
    (function(){{
      var prefix='{tab_prefix}';
      var names={json.dumps(names)};
      function activate(idx){{
        names.forEach(function(n,i){{
          var tb=document.getElementById(prefix+'-tab-'+i);
          var pn=document.getElementById(prefix+'-panel-'+i);
          if(i===idx){{tb.classList.add('active');pn.style.display='block';}}
          else{{tb.classList.remove('active');pn.style.display='none';}}
        }});
      }}
      window.showSeg=window.showSeg||function(p,n){{
        var idx=names.indexOf(n);
        if(prefix===p) activate(idx);
      }};
      // override for this prefix
      var oldShow=window.showSeg;
      window.showSeg=function(p,n){{
        if(p===prefix){{activate(names.indexOf(n));}}
        else{{oldShow(p,n);}}
      }};
      activate(0);
    }})();
    </script>"""

ent_tabs  = seg_tabs_html(ent_data, "ent")
ct_tabs   = seg_tabs_html(ct_data,  "ct")

overall_max = overall_vals[0] if overall_vals else 1
overall_bars = reason_bars_html(
    [{"reason": r, "count": c, "pct": pct(c, total)} for r, c in overall_top10],
    overall_max
)
red_bars = reason_bars_html(
    [{"reason": r, "count": c, "pct": pct(c, len(red))} for r, c in red_top10],
    red_vals[0] if red_vals else 1
)

red_rows_html = "".join(f"""
<tr>
  <td><a href="data/{s['glid']}/dashboard.html" target="_blank">{s['glid']}</a></td>
  <td>{s.get('company','—')[:30]}</td>
  <td>{s.get('city','—')}</td>
  <td>{s.get('enterprise','—')}</td>
  <td><span class="score-badge score-red">{s.get('churn_score',0)}</span></td>
  <td>{round(s.get('reply_rate_30d',0)*100,1)}%</td>
  <td>{s.get('cqs',0)}</td>
  <td>{s.get('active_days_30d',0)}</td>
  <td>{s.get('enq_30d',0)}</td>
  <td>{'; '.join(s.get('churn_reasons',[])[:2])[:60]}</td>
</tr>""" for s in red_sorted)

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>IndiaMART — Churn Master Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f172a;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif;font-size:14px;line-height:1.5}}
.header{{background:linear-gradient(135deg,#1e1b4b,#0f172a);padding:28px 36px;border-bottom:1px solid #1e293b}}
.header h1{{font-size:24px;font-weight:700;color:#fff}}
.header p{{color:#94a3b8;margin-top:4px}}
.container{{padding:28px 36px;max-width:1600px;margin:0 auto}}
.section{{margin-bottom:40px}}
.section-title{{font-size:17px;font-weight:600;color:#f1f5f9;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid #1e293b;display:flex;align-items:center;gap:8px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:16px;margin-bottom:32px}}
.kpi{{background:#1e293b;border-radius:12px;padding:20px;border:1px solid #334155}}
.kpi-val{{font-size:28px;font-weight:700;color:#f1f5f9}}
.kpi-lbl{{font-size:12px;color:#64748b;margin-top:4px;text-transform:uppercase;letter-spacing:.05em}}
.kpi-sub{{font-size:12px;color:#94a3b8;margin-top:2px}}
.kpi.red .kpi-val{{color:#ef4444}} .kpi.amber .kpi-val{{color:#f59e0b}} .kpi.green .kpi-val{{color:#22c55e}}
.charts-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:20px}}
.chart-card{{background:#1e293b;border-radius:12px;padding:20px;border:1px solid #334155}}
.chart-card h3{{font-size:14px;font-weight:600;color:#cbd5e1;margin-bottom:16px}}
.chart-wrap{{position:relative;height:280px}}
.chart-wrap.tall{{height:360px}}
.chart-wrap.short{{height:220px}}
.reason-list{{display:flex;flex-direction:column;gap:10px}}
.reason-row{{display:flex;flex-direction:column;gap:4px}}
.reason-label{{font-size:13px;color:#cbd5e1;font-weight:500}}
.reason-bar-wrap{{display:flex;align-items:center;gap:10px}}
.reason-bar{{height:12px;border-radius:6px;min-width:4px;transition:width .3s}}
.reason-num{{font-size:12px;color:#64748b;white-space:nowrap}}
.seg-tabs{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}}
.seg-tab{{background:#1e293b;border:1px solid #334155;color:#94a3b8;padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px;transition:all .2s}}
.seg-tab:hover,.seg-tab.active{{background:#4F46E5;border-color:#4F46E5;color:#fff}}
.seg-panel{{display:none;background:#1e293b;border-radius:12px;padding:24px;border:1px solid #334155}}
.seg-header{{margin-bottom:16px}}
.seg-header h3{{font-size:16px;font-weight:600;color:#f1f5f9;margin-bottom:6px}}
.seg-meta{{font-size:13px;color:#64748b}} .seg-meta.mt4{{margin-top:4px}}
.seg-panel h4{{font-size:13px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin:16px 0 12px}}
.badge-red{{background:#7f1d1d;color:#fca5a5;padding:2px 8px;border-radius:4px;font-size:12px}}
.badge-amber{{background:#78350f;color:#fcd34d;padding:2px 8px;border-radius:4px;font-size:12px}}
.badge-green{{background:#14532d;color:#86efac;padding:2px 8px;border-radius:4px;font-size:12px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#0f172a;color:#64748b;text-align:left;padding:10px 12px;border-bottom:1px solid #1e293b;font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:.05em}}
td{{padding:10px 12px;border-bottom:1px solid #1e293b;color:#cbd5e1}}
tr:hover td{{background:#1e293b}}
td a{{color:#818cf8;text-decoration:none}} td a:hover{{text-decoration:underline}}
.score-badge{{display:inline-block;padding:2px 8px;border-radius:6px;font-weight:700;font-size:13px}}
.score-red{{background:#7f1d1d;color:#fca5a5}}
.score-amber{{background:#78350f;color:#fcd34d}}
.score-green{{background:#14532d;color:#86efac}}
.full-width{{grid-column:1/-1}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
@media(max-width:900px){{.two-col{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="header">
  <h1>IndiaMART Churn — Master Analytics Dashboard</h1>
  <p>228 sellers analysed &nbsp;|&nbsp; Data as of 2026-05-15 &nbsp;|&nbsp; Signals: Reply Rate, BL Velocity, PNS, CQS, RAG, Hotleads, Activity</p>
</div>
<div class="container">

<!-- KPIs -->
<div class="section">
  <div class="kpis">
    <div class="kpi"><div class="kpi-val">{total}</div><div class="kpi-lbl">Total Sellers</div><div class="kpi-sub">Analysed</div></div>
    <div class="kpi red"><div class="kpi-val">{len(red)}</div><div class="kpi-lbl">Red — High Risk</div><div class="kpi-sub">{pct(len(red),total)}% of sellers</div></div>
    <div class="kpi amber"><div class="kpi-val">{len(amber)}</div><div class="kpi-lbl">Amber — Moderate</div><div class="kpi-sub">{pct(len(amber),total)}% of sellers</div></div>
    <div class="kpi green"><div class="kpi-val">{len(green)}</div><div class="kpi-lbl">Green — Low Risk</div><div class="kpi-sub">{pct(len(green),total)}% of sellers</div></div>
    <div class="kpi"><div class="kpi-val">Rs {est_arr:,}</div><div class="kpi-lbl">Est. At-Risk ARR</div><div class="kpi-sub">Red x Rs 15k avg</div></div>
    <div class="kpi"><div class="kpi-val">{round(avg([s.get('churn_score') for s in sigs]),1)}</div><div class="kpi-lbl">Avg Churn Score</div><div class="kpi-sub">0 = Safe, 100 = Churned</div></div>
    <div class="kpi"><div class="kpi-val">{round(avg([s.get('reply_rate_30d',0) for s in sigs])*100,1)}%</div><div class="kpi-lbl">Avg Reply Rate</div><div class="kpi-sub">Last 30 days</div></div>
    <div class="kpi"><div class="kpi-val">{round(avg([s.get('cqs') for s in sigs if s.get('cqs')]),1)}</div><div class="kpi-lbl">Avg CQS</div><div class="kpi-sub">Catalog Quality Score</div></div>
  </div>
</div>

<!-- Charts row 1 -->
<div class="section">
  <div class="section-title">Risk Distribution &amp; Score Spread</div>
  <div class="charts-grid">
    <div class="chart-card">
      <h3>Risk Tier Distribution</h3>
      <div class="chart-wrap"><canvas id="riskDist"></canvas></div>
    </div>
    <div class="chart-card">
      <h3>Churn Score Distribution</h3>
      <div class="chart-wrap"><canvas id="scoreDist"></canvas></div>
    </div>
    <div class="chart-card">
      <h3>Key Metrics by Risk Tier (Averages)</h3>
      <div class="chart-wrap"><canvas id="tierMetrics"></canvas></div>
    </div>
    <div class="chart-card">
      <h3>Top Cities — Red Tier Sellers</h3>
      <div class="chart-wrap"><canvas id="citiesRed"></canvas></div>
    </div>
  </div>
</div>

<!-- Overall top 10 reasons -->
<div class="section">
  <div class="section-title">Top 10 Churn Reasons — All {total} Sellers</div>
  <div class="two-col">
    <div class="chart-card">
      <h3>All Sellers (n={total})</h3>
      <div class="reason-list">{overall_bars}</div>
    </div>
    <div class="chart-card">
      <h3>Red Tier Only (n={len(red)})</h3>
      <div class="reason-list">{red_bars}</div>
    </div>
  </div>
</div>

<!-- By enterprise segment -->
<div class="section">
  <div class="section-title">Churn Reasons by Enterprise Segment — Top 10 per Segment</div>
  {ent_tabs}
</div>

<!-- By subscription type -->
<div class="section">
  <div class="section-title">Churn Reasons by Subscription Type — Top 10 per Type</div>
  {ct_tabs}
</div>

<!-- Red sellers table -->
<div class="section">
  <div class="section-title">Red-Tier Sellers ({len(red)}) — Sorted by Churn Score</div>
  <div style="overflow-x:auto;background:#1e293b;border-radius:12px;border:1px solid #334155;padding:4px">
    <table>
      <thead>
        <tr>
          <th>GLID</th><th>Company</th><th>City</th><th>Segment</th>
          <th>Score</th><th>Reply%</th><th>CQS</th><th>Active Days</th>
          <th>Enq 30d</th><th>Top Reasons</th>
        </tr>
      </thead>
      <tbody>{red_rows_html}</tbody>
    </table>
  </div>
</div>

</div>
<script>
var riskCfg={json.dumps(risk_dist_cfg)};
var scoreCfg={json.dumps(bar_cfg(score_labels,score_vals,"Sellers","#8b5cf6",False))};
var tierCfg={json.dumps(tier_metrics_cfg)};
var cityCfg={json.dumps(bar_cfg(city_labels,city_vals,"Red Sellers","#ef4444"))};

new Chart(document.getElementById('riskDist'), riskCfg);
new Chart(document.getElementById('scoreDist'), scoreCfg);
new Chart(document.getElementById('tierMetrics'), tierCfg);
new Chart(document.getElementById('citiesRed'), cityCfg);
</script>
</body>
</html>"""

os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
with open(OUT_FILE, "w", encoding="utf-8") as f:
    f.write(HTML)

print(f"Master dashboard -> {OUT_FILE}")
print(f"  Total: {total} | Red: {len(red)} | Amber: {len(amber)} | Green: {len(green)}")
print(f"  Enterprise segments: {list(ent_data.keys())}")
print(f"  Subscription types: {list(ct_data.keys())}")
