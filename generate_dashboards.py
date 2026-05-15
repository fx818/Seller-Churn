"""
Generic Dashboard Generator
Reads response.json from each api_outputs/<folder>/ and generates dashboard.html
The HTML is self-contained, data-embedded, and works with any JSON structure.
"""
import json, os, re, math
from datetime import datetime

BASE = os.path.join(os.path.dirname(__file__), "api_outputs")

# ── Helpers ──────────────────────────────────────────────────────────────────

def safe_parse(val):
    """Try to parse a JSON string recursively."""
    if isinstance(val, str):
        val = val.strip()
        if val.startswith("{") or val.startswith("["):
            try:
                return safe_parse(json.loads(val))
            except Exception:
                pass
    if isinstance(val, dict):
        return {k: safe_parse(v) for k, v in val.items()}
    if isinstance(val, list):
        return [safe_parse(i) for i in val]
    return val

def flatten_dwh(data):
    """DWH wraps response in a JSON string under data.response"""
    if isinstance(data, dict) and "response" in data:
        inner = safe_parse(data["response"])
        if isinstance(inner, dict):
            for key in ["summary", "competitors", "mcat_data", "res"]:
                if key in inner:
                    return key, inner[key]
            return "data", inner
    return "data", data

def to_js_json(obj):
    return json.dumps(obj, ensure_ascii=False, default=str)

def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')

def humanize(key):
    return re.sub(r'[_\-]+', ' ', str(key)).title()

def detect_type(val):
    try:
        float(str(val).replace(",",""))
        return "number"
    except Exception:
        pass
    if isinstance(val, bool): return "bool"
    if isinstance(val, (int, float)): return "number"
    if isinstance(val, dict): return "object"
    if isinstance(val, list): return "array"
    return "string"

def is_numeric_key(k, sample_vals):
    nums = [v for v in sample_vals if v is not None and detect_type(v) == "number"]
    return len(nums) >= len(sample_vals) * 0.6

# ── HTML template ─────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} — Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#0f1117;--s1:#1a1d27;--s2:#22263a;--bdr:#2e3350;--acc:#6366f1;--acc2:#8b5cf6;--acc3:#06b6d4;--grn:#10b981;--ylw:#f59e0b;--red:#ef4444;--txt:#e2e8f0;--mut:#94a3b8;--r:12px}}
body{{background:var(--bg);color:var(--txt);font-family:'Inter',system-ui,sans-serif;min-height:100vh}}
.hdr{{background:linear-gradient(135deg,#1e1b4b,#0f172a);border-bottom:1px solid var(--bdr);padding:20px 32px;display:flex;align-items:center;gap:16px}}
.hdr-icon{{width:44px;height:44px;background:linear-gradient(135deg,var(--acc),var(--acc2));border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0}}
.hdr h1{{font-size:18px;font-weight:700}}.hdr p{{font-size:12px;color:var(--mut);margin-top:2px}}
.hdr-right{{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}}
.badge{{background:var(--s2);border:1px solid var(--bdr);padding:4px 12px;border-radius:20px;font-size:12px;color:var(--mut)}}
.badge b{{color:var(--txt)}}
.badge.ok{{border-color:#10b98144;color:var(--grn)}}
.badge.err{{border-color:#ef444444;color:var(--red)}}
main{{padding:24px 32px}}
.grid{{display:grid;gap:16px}}
.g2{{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}}
.g3{{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}}
.g4{{grid-template-columns:repeat(auto-fit,minmax(160px,1fr))}}
.card{{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:20px;overflow:hidden}}
.card-title{{font-size:13px;font-weight:600;color:var(--mut);text-transform:uppercase;letter-spacing:.5px;margin-bottom:16px;display:flex;align-items:center;gap:8px}}
.card-title span{{flex:1}}
.metric-card{{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:18px;position:relative;overflow:hidden}}
.metric-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--c,var(--acc))}}
.metric-lbl{{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.5px}}
.metric-val{{font-size:26px;font-weight:800;margin:6px 0 4px;color:var(--c,var(--txt))}}
.metric-sub{{font-size:11px;color:var(--mut)}}
.section{{margin-bottom:28px}}
.section-title{{font-size:15px;font-weight:700;margin-bottom:14px;display:flex;align-items:center;gap:8px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
thead{{background:var(--s2)}}
th{{padding:10px 12px;text-align:left;font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.5px;white-space:nowrap;border-bottom:1px solid var(--bdr)}}
td{{padding:10px 12px;border-bottom:1px solid var(--bdr);vertical-align:top}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:var(--s2)}}
.tbl-wrap{{overflow-x:auto;border-radius:var(--r);border:1px solid var(--bdr)}}
.tag{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:500}}
.tag-green{{background:#064e3b;color:#34d399}}
.tag-blue{{background:#1e3a5f;color:#60a5fa}}
.tag-yellow{{background:#451a03;color:#fbbf24}}
.tag-purple{{background:#2d1b69;color:#a78bfa}}
.tag-red{{background:#450a0a;color:#fca5a5}}
.kv-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}}
.kv-item{{background:var(--s2);border:1px solid var(--bdr);border-radius:8px;padding:12px}}
.kv-key{{font-size:11px;color:var(--mut);margin-bottom:4px}}
.kv-val{{font-size:14px;font-weight:600;word-break:break-all}}
.chart-wrap{{position:relative;height:300px}}
.chart-wrap-sm{{position:relative;height:220px}}
.progress-bar{{height:8px;background:var(--s2);border-radius:4px;overflow:hidden;margin-top:6px}}
.progress-fill{{height:100%;border-radius:4px;transition:width .6s ease}}
.empty{{text-align:center;padding:40px;color:var(--mut);font-size:14px}}
.json-viewer{{background:#0a0a12;border:1px solid var(--bdr);border-radius:var(--r);padding:16px;font-family:monospace;font-size:12px;overflow:auto;max-height:400px;color:#a8b4c8;white-space:pre-wrap;word-break:break-all}}
.toggle-btn{{background:var(--s2);border:1px solid var(--bdr);border-radius:6px;padding:6px 14px;color:var(--mut);cursor:pointer;font-size:12px;transition:all .15s}}
.toggle-btn:hover{{border-color:var(--acc);color:var(--acc)}}
.timeline{{display:flex;flex-direction:column;gap:0}}
.tl-item{{display:flex;gap:16px;padding:12px 0;border-bottom:1px solid var(--bdr)}}
.tl-item:last-child{{border-bottom:none}}
.tl-dot{{width:10px;height:10px;border-radius:50%;background:var(--acc);flex-shrink:0;margin-top:5px}}
.tl-content{{flex:1}}
.tl-title{{font-size:13px;font-weight:600}}
.tl-time{{font-size:11px;color:var(--mut);margin-top:2px}}
.tl-meta{{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}}
.dual-bar{{display:flex;align-items:center;gap:10px;margin-bottom:8px}}
.dual-lbl{{width:180px;font-size:12px;color:var(--mut);text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.dual-track{{flex:1;display:flex;gap:4px}}
.dual-fill{{height:22px;border-radius:4px;display:flex;align-items:center;padding:0 8px;font-size:11px;font-weight:600;color:#fff;min-width:28px}}
.no-data{{background:var(--s2);border:1px solid var(--bdr);border-radius:var(--r);padding:40px;text-align:center;color:var(--mut)}}
::-webkit-scrollbar{{width:5px;height:5px}}
::-webkit-scrollbar-track{{background:var(--bg)}}
::-webkit-scrollbar-thumb{{background:var(--bdr);border-radius:3px}}
@media(max-width:640px){{main{{padding:16px}}.hdr{{padding:16px}}.dual-lbl{{width:100px}}}}
</style>
</head>
<body>
<div class="hdr">
  <div class="hdr-icon">{icon}</div>
  <div><h1>{title}</h1><p>{subtitle}</p></div>
  <div class="hdr-right">
    <div class="badge {status_cls}"><b>{status_label}</b></div>
    <div class="badge">GLID: <b>{glid}</b></div>
    <div class="badge">Generated: <b>{generated}</b></div>
  </div>
</div>
<main id="main">
{body}
<div class="section">
  <div class="section-title">🔍 Raw JSON Explorer</div>
  <button class="toggle-btn" onclick="toggleRaw()">Show / Hide Raw JSON</button>
  <div id="raw-json" class="json-viewer" style="display:none;margin-top:12px">{raw_json_escaped}</div>
</div>
</main>
<script>
const DATA = {data_json};
function toggleRaw(){{document.getElementById('raw-json').style.display=document.getElementById('raw-json').style.display==='none'?'block':'none'}}
{js}
</script>
</body>
</html>
"""

# ── Chart palette ─────────────────────────────────────────────────────────────
PALETTE = ["#6366f1","#8b5cf6","#06b6d4","#10b981","#f59e0b","#ef4444","#ec4899","#14b8a6","#f97316","#a855f7"]

def chartjs_config(type_, labels, datasets, opts=None):
    cfg = {"type": type_, "data": {"labels": labels, "datasets": datasets}, "options": {
        "responsive": True, "maintainAspectRatio": False,
        "plugins": {"legend": {"labels": {"color": "#94a3b8"}}},
        "scales": {
            "x": {"ticks": {"color": "#94a3b8"}, "grid": {"color": "#2e3350"}},
            "y": {"ticks": {"color": "#94a3b8"}, "grid": {"color": "#2e3350"}}
        } if type_ != "doughnut" and type_ != "pie" else {}
    }}
    if opts:
        cfg["options"].update(opts)
    return to_js_json(cfg)

# ── Generators per API type ───────────────────────────────────────────────────

def gen_scorecard_summary(data):
    inner = safe_parse(data.get("data", {}).get("response", "{}"))
    summary = inner.get("summary", [])
    if not summary:
        return "<div class='no-data'>No scorecard summary data available.</div>", ""

    s = summary[0]
    # Parse nested JSON strings
    for k in ["seller_init_conn","buyers_responded","wp_enq_count","non_wp_enq_wp_conv_count",
               "lms_active_days","tot_enq","enq_replied","bl_cons"]:
        if k in s:
            s[k] = safe_parse(s[k])

    def tri(d, label, icon, color):
        if not isinstance(d, dict): return ""
        return f"""
        <div class="metric-card" style="--c:{color}">
          <div class="metric-lbl">{icon} {label}</div>
          <div class="grid g3" style="margin-top:12px">
            {' '.join(f'<div><div class="metric-lbl">{p.upper()}</div><div class="metric-val" style="font-size:18px;color:{color}">{d.get(p,0)}</div></div>' for p in ['7d','30d','90d'])}
          </div>
        </div>"""

    profile_html = f"""
    <div class="section">
      <div class="section-title">👤 Seller Profile</div>
      <div class="grid g4">
        <div class="metric-card" style="--c:#6366f1"><div class="metric-lbl">City</div><div class="metric-val" style="font-size:18px">{esc(s.get('gl_city_name','-'))}</div><div class="metric-sub">{esc(s.get('gl_state_code','-'))}</div></div>
        <div class="metric-card" style="--c:#06b6d4"><div class="metric-lbl">Client Since</div><div class="metric-val" style="font-size:18px">{esc(s.get('client_since','-'))}</div></div>
        <div class="metric-card" style="--c:#10b981"><div class="metric-lbl">Enterprise Type</div><div class="metric-val" style="font-size:14px;padding-top:6px">{esc(s.get('enterprise_type','-'))}</div></div>
        <div class="metric-card" style="--c:#f59e0b"><div class="metric-lbl">GLID</div><div class="metric-val" style="font-size:18px">{esc(s.get('glid','-'))}</div></div>
      </div>
    </div>"""

    engagement_html = f"""
    <div class="section">
      <div class="section-title">📊 Engagement (7d / 30d / 90d)</div>
      <div class="grid g2">
        {tri(s.get('tot_enq'), 'Total Enquiries', '📩', '#6366f1')}
        {tri(s.get('enq_replied'), 'Enquiries Replied', '✉️', '#10b981')}
        {tri(s.get('buyers_responded'), 'Buyers Responded', '👥', '#06b6d4')}
        {tri(s.get('seller_init_conn'), 'Seller Initiated Connects', '📞', '#f59e0b')}
        {tri(s.get('lms_active_days'), 'LMS Active Days', '📅', '#8b5cf6')}
        {tri(s.get('bl_cons'), 'BL Consumption', '🔗', '#ec4899')}
      </div>
    </div>"""

    return profile_html + engagement_html, ""


def gen_scorecard_monthly(data, months=6):
    inner = safe_parse(data.get("data", {}).get("response", "{}"))
    summary = inner.get("summary", [])
    if not summary:
        return "<div class='no-data'>No monthly scorecard data.</div>", ""

    # Sort by year_month
    summary = sorted(summary, key=lambda x: x.get("year_month", 0))[-months:]
    labels = [f"{r.get('data_month','')} {r.get('data_year','')}" for r in summary]

    def chart_id(name): return name.replace(" ","_").replace("/","_")

    def metric_chart(field, label, color, chart_type="bar"):
        vals = [r.get(field, 0) or 0 for r in summary]
        cid = f"ch_{chart_id(field)}"
        cfg = chartjs_config(chart_type, labels, [{"label": label, "data": vals,
            "backgroundColor": color+"88", "borderColor": color, "borderWidth": 2,
            "tension": 0.4, "fill": chart_type == "line"}])
        return f"""<div class="card">
          <div class="card-title"><span>{label}</span></div>
          <div class="chart-wrap-sm"><canvas id="{cid}"></canvas></div>
        </div>""", f"new Chart(document.getElementById('{cid}'),{cfg});"

    charts_html = ""
    charts_js = ""
    metrics = [
        ("pns_calls_recd","PNS Calls Received","#6366f1","bar"),
        ("pns_calls_ans","PNS Calls Answered","#10b981","bar"),
        ("pns_success_prcnt","PNS Success %","#f59e0b","line"),
        ("total_enq","Total Enquiries","#06b6d4","bar"),
        ("replies","Replies","#8b5cf6","bar"),
        ("bl_cons","BL Consumption","#ec4899","line"),
        ("bl_active_days","BL Active Days","#14b8a6","bar"),
        ("lms_active_days","LMS Active Days","#f97316","bar"),
    ]
    card_parts = []
    for field, label, color, ctype in metrics:
        if any(r.get(field) is not None for r in summary):
            ch, js = metric_chart(field, label, color, ctype)
            card_parts.append(ch)
            charts_js += js

    charts_html = f'<div class="grid g2">{"".join(card_parts)}</div>'

    # Table
    cols = ["data_month","data_year","pns_calls_recd","pns_calls_ans","pns_success_prcnt",
            "total_enq","replies","bl_cons","bl_active_days","lms_active_days","service"]
    cols = [c for c in cols if any(r.get(c) is not None for r in summary)]
    thead = "".join(f"<th>{humanize(c)}</th>" for c in cols)
    tbody = ""
    for r in reversed(summary):
        tbody += "<tr>" + "".join(f"<td>{esc(r.get(c,''))}</td>" for c in cols) + "</tr>"

    table_html = f"""<div class="section"><div class="section-title">📋 Monthly Detail</div>
      <div class="tbl-wrap"><table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div></div>"""

    html = f"""<div class="section"><div class="section-title">📈 Monthly Trends ({months}m)</div>{charts_html}</div>""" + table_html
    return html, charts_js


def gen_competitors(data):
    inner = safe_parse(data.get("data", {}).get("response", "{}"))
    competitors = inner.get("competitors", [])
    if not competitors:
        return "<div class='no-data'>No competitor data found.</div>", ""

    # Stats
    cities = {}
    types = {}
    for c in competitors:
        ct = c.get("competitor_city","-")
        ct_type = c.get("custtype_name","-")
        cities[ct] = cities.get(ct, 0) + 1
        types[ct_type] = types.get(ct_type, 0) + 1

    top_cities = sorted(cities.items(), key=lambda x: -x[1])[:8]
    top_types = sorted(types.items(), key=lambda x: -x[1])[:6]

    city_chart_cfg = chartjs_config("doughnut",
        [x[0] for x in top_cities],
        [{"data": [x[1] for x in top_cities], "backgroundColor": PALETTE[:len(top_cities)], "borderWidth": 0}])
    type_chart_cfg = chartjs_config("bar",
        [x[0] for x in top_types],
        [{"label": "Count", "data": [x[1] for x in top_types], "backgroundColor": "#6366f188", "borderColor": "#6366f1", "borderWidth": 2}])

    charts_html = f"""<div class="grid g2">
      <div class="card"><div class="card-title"><span>By City</span></div><div class="chart-wrap"><canvas id="ch_city"></canvas></div></div>
      <div class="card"><div class="card-title"><span>By Type</span></div><div class="chart-wrap-sm"><canvas id="ch_type"></canvas></div></div>
    </div>"""
    charts_js = f"new Chart(document.getElementById('ch_city'),{city_chart_cfg});new Chart(document.getElementById('ch_type'),{type_chart_cfg});"

    # Table
    rows = ""
    for i, c in enumerate(competitors[:50]):
        rows += f"""<tr>
          <td>{i+1}</td>
          <td><b>{esc(c.get('competitor_company','-'))}</b></td>
          <td><span class="tag tag-blue">{esc(c.get('custtype_name','-'))}</span></td>
          <td>{esc(c.get('competitor_city','-'))}</td>
          <td>{esc(c.get('competitor_membersince','-'))}</td>
          <td style="font-size:11px;color:var(--mut)">{c.get('competitor_glusr_id','')}</td>
          <td><a href="{esc(c.get('catalog_url','#'))}" target="_blank" style="color:var(--acc3);font-size:11px">View</a></td>
        </tr>"""

    table_html = f"""<div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Company</th><th>Type</th><th>City</th><th>Member Since</th><th>GLID</th><th>Catalog</th></tr></thead>
      <tbody>{rows}</tbody></table></div>"""

    stats_html = f"""<div class="grid g4" style="margin-bottom:20px">
      <div class="metric-card" style="--c:#6366f1"><div class="metric-lbl">Total Competitors</div><div class="metric-val">{len(competitors)}</div></div>
      <div class="metric-card" style="--c:#06b6d4"><div class="metric-lbl">Cities Covered</div><div class="metric-val">{len(cities)}</div></div>
      <div class="metric-card" style="--c:#10b981"><div class="metric-lbl">Types</div><div class="metric-val">{len(types)}</div></div>
    </div>"""

    html = f"""<div class="section"><div class="section-title">🏭 Competitor Overview</div>{stats_html}{charts_html}</div>
    <div class="section"><div class="section-title">📋 Competitor List</div>{table_html}</div>"""
    return html, charts_js


def gen_competitors_counts(data):
    inner = safe_parse(data.get("data", {}).get("response", "{}"))
    rows = inner.get("mcat_data", [])
    if not rows:
        return "<div class='no-data'>No competitor count data.</div>", ""

    r = rows[0]
    mcat_list = safe_parse(r.get("mcat_list", "[]"))
    mcat_names = [m.get("mcat_name","") for m in (mcat_list if isinstance(mcat_list, list) else [])]

    metrics = [
        ("total_bl","Total BL","#6366f1"),
        ("local_bl","Local BL","#06b6d4"),
        ("hyperlocal_bl","Hyperlocal BL","#10b981"),
        ("local_paid_sellers","Local Paid Sellers","#f59e0b"),
        ("hyperlocal_paid_sellers","Hyperlocal Paid Sellers","#8b5cf6"),
        ("total_paid_sellers","Total Paid Sellers","#ef4444"),
    ]
    stats_html = '<div class="grid g3">' + "".join(
        f'<div class="metric-card" style="--c:{c}"><div class="metric-lbl">{lbl}</div><div class="metric-val">{r.get(k,0)}</div></div>'
        for k, lbl, c in metrics) + '</div>'

    vals = [r.get(k, 0) or 0 for k, _, _ in metrics]
    colors = [c for _, _, c in metrics]
    lbls = [lbl for _, lbl, _ in metrics]
    cfg = chartjs_config("bar", lbls, [{"label":"Count","data":vals,"backgroundColor":[c+"88" for c in colors],"borderColor":colors,"borderWidth":2}])
    charts_html = f'<div class="card"><div class="card-title"><span>Market Presence</span></div><div class="chart-wrap"><canvas id="ch_mkt"></canvas></div></div>'
    charts_js = f"new Chart(document.getElementById('ch_mkt'),{cfg});"

    mcat_html = ""
    if mcat_names:
        tags = "".join(f'<span class="tag tag-purple" style="margin:3px">{esc(m)}</span>' for m in mcat_names)
        mcat_html = f'<div class="card" style="margin-top:16px"><div class="card-title"><span>MCat Categories</span></div><div>{tags}</div></div>'

    html = f"""<div class="section"><div class="section-title">📊 Market Counts</div>{stats_html}</div>
    <div class="section">{charts_html}{mcat_html}</div>"""
    return html, charts_js


def gen_ingestion_composite(data):
    d = data.get("data", data)
    profile = d.get("profile", {})
    gst = d.get("gst")
    engagement = d.get("engagement", {})

    profile_fields = [
        ("company_name","Company","#6366f1"),("city","City","#06b6d4"),
        ("customer_type","Type","#8b5cf6"),("rag_category","RAG Category","#10b981"),
        ("account_age_days","Account Age (days)","#f59e0b"),("creation_date","Created","#ec4899"),
        ("contact_name","Contact","#14b8a6"),("pincode","Pincode","#f97316"),
    ]

    rag_colors = {"Red":"#ef4444","Amber":"#f59e0b","Green":"#10b981","Green+":"#34d399"}
    rag = profile.get("rag_category","")
    rag_color = rag_colors.get(rag, "#6366f1")

    cards_html = f"""<div class="grid g4">
      {''.join(f'<div class="metric-card" style="--c:{c}"><div class="metric-lbl">{lbl}</div><div class="metric-val" style="font-size:16px">{esc(str(profile.get(f,"-")))}</div></div>' for f, lbl, c in profile_fields)}
    </div>"""

    # Engagement
    eng_html = ""
    if engagement:
        eng_rows = "".join(f'<div class="kv-item"><div class="kv-key">{humanize(k)}</div><div class="kv-val">{esc(str(v))}</div></div>' for k, v in engagement.items() if v is not None)
        eng_html = f'<div class="section"><div class="section-title">📊 Engagement</div><div class="kv-grid">{eng_rows}</div></div>'

    # Boolean indicators
    bools = [(k, profile.get(k)) for k in ["paid_history","hrs_bs_conflict","mcat_negative"] if k in profile]
    bool_html = "".join(
        f'<span class="tag {"tag-green" if v else "tag-red"}" style="margin:3px">{humanize(k)}: {"Yes" if v else "No"}</span>'
        for k, v in bools)

    html = f"""<div class="section"><div class="section-title">👤 Seller Profile</div>{cards_html}
    <div style="margin-top:12px">{bool_html}</div></div>{eng_html}"""
    return html, ""


def gen_ingestion_metrics(data):
    d = data.get("data", data)

    # 90d vs 1yr pairs
    pairs = [
        ("enq_received","Enquiries Received","#6366f1"),
        ("enq_replies","Enquiries Replied","#10b981"),
        ("pns_received","PNS Received","#06b6d4"),
        ("pns_answered","PNS Answered","#8b5cf6"),
        ("callback","Callbacks","#f59e0b"),
        ("call_attempts","Call Attempts","#ec4899"),
        ("answered_calls","Answered Calls","#14b8a6"),
        ("meetings","Meetings","#f97316"),
        ("hot_meetings","Hot Meetings","#a855f7"),
        ("ni_count","NI Count","#ef4444"),
        ("np_count","NP Count","#6366f1"),
    ]

    # Build comparison chart
    labels_90d = []
    vals_90d = []
    vals_1yr = []
    for key, label, color in pairs:
        v90 = d.get(f"{key}_90d", 0) or 0
        v1yr = d.get(f"{key}_1yr", 0) or 0
        if v90 or v1yr:
            labels_90d.append(label)
            vals_90d.append(v90)
            vals_1yr.append(v1yr)

    charts_js = ""
    charts_html = ""
    if labels_90d:
        cfg = chartjs_config("bar", labels_90d, [
            {"label":"90 Days","data":vals_90d,"backgroundColor":"#6366f188","borderColor":"#6366f1","borderWidth":2},
            {"label":"1 Year","data":vals_1yr,"backgroundColor":"#10b98188","borderColor":"#10b981","borderWidth":2},
        ])
        charts_html = f'<div class="card"><div class="card-title"><span>90-Day vs 1-Year Comparison</span></div><div class="chart-wrap"><canvas id="ch_metrics"></canvas></div></div>'
        charts_js = f"new Chart(document.getElementById('ch_metrics'),{cfg});"

    # Dual bars
    bars_html = '<div class="section"><div class="section-title">📊 Metrics Breakdown</div>'
    max_1yr = max((d.get(f"{k}_1yr",0) or 0 for k,_,_ in pairs), default=1) or 1
    for key, label, color in pairs:
        v90 = d.get(f"{key}_90d", 0) or 0
        v1yr = d.get(f"{key}_1yr", 0) or 0
        w90 = max(4, round(v90 / max_1yr * 100))
        w1yr = max(4, round(v1yr / max_1yr * 100))
        bars_html += f"""<div class="dual-bar">
          <div class="dual-lbl">{label}</div>
          <div class="dual-track">
            <div class="dual-fill" style="width:{w90}%;background:{color}">{v90}</div>
            <div class="dual-fill" style="width:{w1yr}%;background:{color}44;border:1px solid {color}">{v1yr}</div>
          </div>
        </div>"""
    bars_html += '</div>'

    # Summary KPIs
    pns_rate = 0
    if (d.get("pns_received_1yr") or 0) > 0:
        pns_rate = round((d.get("pns_answered_1yr",0) or 0) / d.get("pns_received_1yr",1) * 100, 1)

    kpis_html = f"""<div class="grid g4" style="margin-bottom:20px">
      <div class="metric-card" style="--c:#6366f1"><div class="metric-lbl">Enq Replies (1yr)</div><div class="metric-val">{d.get("enq_replies_1yr",0)}</div></div>
      <div class="metric-card" style="--c:#10b981"><div class="metric-lbl">PNS Answer Rate</div><div class="metric-val">{pns_rate}%</div><div class="metric-sub">of {d.get("pns_received_1yr",0)} received</div></div>
      <div class="metric-card" style="--c:#f59e0b"><div class="metric-lbl">Meetings (1yr)</div><div class="metric-val">{d.get("meetings_1yr",0)}</div></div>
      <div class="metric-card" style="--c:#06b6d4"><div class="metric-lbl">As Of</div><div class="metric-val" style="font-size:16px">{d.get("as_of","")}</div></div>
    </div>"""

    html = kpis_html + f'<div class="section">{charts_html}</div>' + bars_html
    return html, charts_js


def gen_ingestion_hotleads(data):
    d = data.get("data", data)
    items = d.get("items", [])
    total = d.get("total", 0)

    if not items:
        return f'<div class="no-data">No hotlead data available. Total: {total}</div>', ""

    types = {}
    for item in items:
        t = item.get("data_type","-")
        types[t] = types.get(t, 0) + 1

    type_labels = list(types.keys())
    type_vals = [types[k] for k in type_labels]
    cfg = chartjs_config("doughnut", type_labels, [{"data":type_vals,"backgroundColor":PALETTE[:len(type_labels)],"borderWidth":0}])
    charts_html = f'<div class="card"><div class="card-title"><span>By Type</span></div><div class="chart-wrap-sm"><canvas id="ch_hl"></canvas></div></div>'
    charts_js = f"new Chart(document.getElementById('ch_hl'),{cfg});"

    tl_html = '<div class="timeline">'
    dt_colors = {"PUA":"#6366f1","UA":"#10b981","ENQR":"#f59e0b","CALL":"#06b6d4"}
    for item in items[:30]:
        dtype = item.get("data_type","-")
        color = dt_colors.get(dtype, "#94a3b8")
        tl_html += f"""<div class="tl-item">
          <div class="tl-dot" style="background:{color}"></div>
          <div class="tl-content">
            <div class="tl-title">{esc(item.get("activity","-"))}</div>
            <div class="tl-time">{esc(str(item.get("hotlead_date","")))}</div>
            <div class="tl-meta"><span class="tag tag-blue">{esc(dtype)}</span><span class="tag tag-purple">ID: {item.get("hotlead_id","")}</span></div>
          </div>
        </div>"""
    tl_html += "</div>"

    html = f"""<div class="section"><div class="section-title">🔥 Hotleads Overview</div>
      <div class="grid g2"><div class="metric-card" style="--c:#ef4444"><div class="metric-lbl">Total Hotleads</div><div class="metric-val">{total}</div></div>{charts_html}</div>
    </div>
    <div class="section"><div class="section-title">📅 Hotlead Timeline</div>{tl_html}</div>"""
    return html, charts_js


def gen_ingestion_activity(data):
    d = data.get("data", data)
    events = d.get("events", [])
    event_count = d.get("event_count", 0)

    if not events:
        return f'<div class="no-data">No activity data. event_count={event_count}</div>', ""

    # Frequency by modid
    modids = {}
    hours = [0] * 24
    pages = {}
    for ev in events:
        m = ev.get("modid","?")
        modids[m] = modids.get(m, 0) + 1
        dt = str(ev.get("datevalue",""))
        if len(dt) >= 10:
            try: hours[int(dt[8:10])] += 1
            except: pass
        page = ev.get("fk_display_title") or ev.get("request_url","?")
        if page and page != "-": pages[page] = pages.get(page, 0) + 1

    top_pages = sorted(pages.items(), key=lambda x:-x[1])[:10]
    modid_labels = list(modids.keys())
    modid_vals = [modids[k] for k in modid_labels]

    cfg_m = chartjs_config("doughnut", modid_labels, [{"data":modid_vals,"backgroundColor":PALETTE[:len(modid_labels)],"borderWidth":0}])
    cfg_h = chartjs_config("bar", [f"{h}h" for h in range(24)], [{"label":"Events","data":hours,"backgroundColor":"#6366f188","borderColor":"#6366f1","borderWidth":1}])

    page_bars = ""
    max_p = top_pages[0][1] if top_pages else 1
    for page, cnt in top_pages:
        w = max(4, round(cnt/max_p*100))
        page_bars += f'<div class="dual-bar"><div class="dual-lbl" title="{esc(page)}">{esc(page[:30])}</div><div class="dual-track"><div class="dual-fill" style="width:{w}%;background:#6366f1">{cnt}</div></div></div>'

    charts_html = f"""<div class="grid g2">
      <div class="card"><div class="card-title"><span>By Platform</span></div><div class="chart-wrap-sm"><canvas id="ch_mod"></canvas></div></div>
      <div class="card"><div class="card-title"><span>Activity by Hour</span></div><div class="chart-wrap-sm"><canvas id="ch_hr"></canvas></div></div>
    </div>"""
    charts_js = f"new Chart(document.getElementById('ch_mod'),{cfg_m});new Chart(document.getElementById('ch_hr'),{cfg_h});"

    # Timeline
    tl_html = '<div class="timeline">'
    for ev in events[:20]:
        dt = str(ev.get("datevalue",""))
        fmt_dt = f"{dt[:4]}-{dt[4:6]}-{dt[6:8]} {dt[8:10]}:{dt[10:12]}:{dt[12:14]}" if len(dt)>=14 else dt
        page = ev.get("fk_display_title") or ev.get("request_url","?")
        tl_html += f"""<div class="tl-item">
          <div class="tl-dot"></div>
          <div class="tl-content">
            <div class="tl-title">{esc(str(page))}</div>
            <div class="tl-time">{fmt_dt}</div>
            <div class="tl-meta"><span class="tag tag-blue">{esc(str(ev.get("modid","")))}</span><span class="tag tag-purple">{esc(str(ev.get("gl_country","")))}</span></div>
          </div>
        </div>"""
    tl_html += "</div>"

    html = f"""<div class="section"><div class="section-title">📊 Activity Overview</div>
      <div class="grid g4" style="margin-bottom:20px">
        <div class="metric-card" style="--c:#6366f1"><div class="metric-lbl">Total Events</div><div class="metric-val">{event_count}</div></div>
        <div class="metric-card" style="--c:#06b6d4"><div class="metric-lbl">Platforms</div><div class="metric-val">{len(modids)}</div></div>
        <div class="metric-card" style="--c:#10b981"><div class="metric-lbl">Unique Pages</div><div class="metric-val">{len(pages)}</div></div>
      </div>{charts_html}</div>
    <div class="section"><div class="section-title">🏆 Top Pages</div>{page_bars}</div>
    <div class="section"><div class="section-title">📅 Recent Events</div>{tl_html}</div>"""
    return html, charts_js


def gen_context_data(data):
    d = data.get("data", {}).get("data", {})
    if not d:
        return '<div class="no-data">No context data available.</div>', ""

    all_js = []

    # ── helpers ──
    def fmt_activity_time(s):
        s = str(s)
        if len(s) >= 14:
            return f"{s[:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}:{s[12:14]}"
        return s

    activity_type_colors = {
        "Browse": "#6366f1", "Others": "#94a3b8", "Enquiry": "#10b981",
        "Search": "#f59e0b", "Connect": "#06b6d4", "Call": "#ec4899",
    }

    # ── 1. ActualData ──
    actual = d.get("ActualData", {})
    cities = actual.get("preferred_cities", [])
    city_tags = "".join(f'<span class="tag tag-blue" style="margin:3px">{esc(c)}</span>' for c in cities)
    upload_time = (actual.get("upload_metadata") or {}).get("upload_time", "")[:19]
    section_actual = f"""<div class="section">
      <div class="section-title">🧾 Actual Data</div>
      <div class="grid g4">
        <div class="metric-card" style="--c:#6366f1"><div class="metric-lbl">GLID</div><div class="metric-val">{esc(str(actual.get("glid","")))}</div></div>
        <div class="metric-card" style="--c:#06b6d4"><div class="metric-lbl">Preferred Cities</div><div class="metric-val" style="font-size:16px">{", ".join(cities) or "—"}</div></div>
        <div class="metric-card" style="--c:#8b5cf6"><div class="metric-lbl">Uploaded At</div><div class="metric-val" style="font-size:13px">{esc(upload_time)}</div></div>
      </div>
    </div>"""

    # ── 2. BL Details ──
    bl = d.get("BLdetails", {})
    bl_metrics = [
        ("BL_available_gl_city",        "BL Available (City)",     "#6366f1"),
        ("bl_available_pref_city",       "BL Available (Pref City)","#06b6d4"),
        ("bl_available_a_rank",          "A-Rank BL",               "#10b981"),
        ("bl_available_a_rank_pref_city","A-Rank BL (Pref City)",   "#8b5cf6"),
    ]
    bl_cards = "".join(
        f'<div class="metric-card" style="--c:{c}"><div class="metric-lbl">{lbl}</div><div class="metric-val">{bl.get(k, 0)}</div></div>'
        for k, lbl, c in bl_metrics)
    active_bl = bl.get("active_bl_details", [])
    active_bl_html = ""
    if active_bl:
        cols = list(active_bl[0].keys())
        thead = "".join(f"<th>{humanize(c)}</th>" for c in cols)
        tbody = "".join("<tr>" + "".join(f"<td>{esc(str(r.get(c,'')))}</td>" for c in cols) + "</tr>" for r in active_bl)
        active_bl_html = f'<div class="tbl-wrap" style="margin-top:16px"><table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>'
    section_bl = f"""<div class="section">
      <div class="section-title">📦 BL Details</div>
      <div class="grid g4">{bl_cards}</div>
      {active_bl_html if active_bl_html else '<div class="no-data" style="margin-top:12px;padding:16px">No active BL details.</div>'}
    </div>"""

    # ── 3. Activity Details ──
    act = d.get("activitydetails", {})
    buyer_activity = act.get("BUYER_ACTIVITY", []) if isinstance(act, dict) else []
    act_type_counts = {}
    for ev in buyer_activity:
        t = ev.get("ACTIVITY_TYPE", "Unknown")
        act_type_counts[t] = act_type_counts.get(t, 0) + 1
    act_labels = list(act_type_counts.keys())
    act_vals   = [act_type_counts[k] for k in act_labels]
    act_colors = [activity_type_colors.get(k, "#94a3b8") for k in act_labels]

    act_chart_cfg = chartjs_config("doughnut", act_labels,
        [{"data": act_vals, "backgroundColor": act_colors, "borderWidth": 0}])
    all_js.append(f"new Chart(document.getElementById('ch_act'),{act_chart_cfg});")

    tl_act = '<div class="timeline">'
    for ev in buyer_activity[:20]:
        atype = ev.get("ACTIVITY_TYPE", "")
        dot_c = activity_type_colors.get(atype, "#94a3b8")
        cat   = ev.get("CATEGORY_NAME", "-")
        kw    = ev.get("KEYWORD", "")
        tl_act += f"""<div class="tl-item">
          <div class="tl-dot" style="background:{dot_c}"></div>
          <div class="tl-content">
            <div class="tl-title">{esc(atype)}{(' — ' + esc(kw)) if kw and kw not in ('-','') else ''}</div>
            <div class="tl-time">{fmt_activity_time(ev.get('ACTIVITY_TIME',''))}</div>
            <div class="tl-meta">
              {f'<span class="tag tag-blue">{esc(cat)}</span>' if cat and cat != "-" else ""}
              {f'<span class="tag tag-purple">Seller: {esc(str(ev.get("SELLER_GLUSR_ID","")))}</span>' if ev.get("SELLER_GLUSR_ID","0") not in ("0","") else ""}
            </div>
          </div>
        </div>"""
    tl_act += "</div>"

    section_activity = f"""<div class="section">
      <div class="section-title">⚡ Buyer Activity ({len(buyer_activity)} events)</div>
      <div class="grid g2">
        <div class="card"><div class="card-title"><span>By Activity Type</span></div><div class="chart-wrap-sm"><canvas id="ch_act"></canvas></div></div>
        <div class="card"><div class="card-title"><span>Recent Activity Timeline</span></div>{tl_act}</div>
      </div>
    </div>"""

    # ── 4. Connect Details ──
    conn = d.get("connectdetails", {})
    conn_30d = conn.get("connect_30D", []) if isinstance(conn, dict) else []
    section_conn_cards = f"""<div class="grid g4" style="margin-bottom:16px">
      <div class="metric-card" style="--c:#06b6d4"><div class="metric-lbl">Connects (30D)</div><div class="metric-val">{len(conn_30d)}</div></div>
      <div class="metric-card" style="--c:#8b5cf6"><div class="metric-lbl">App Sharing</div><div class="metric-val">{conn.get("app_sharing_counts",0)}</div></div>
    </div>"""

    tl_conn = '<div class="timeline">'
    for ev in conn_30d[:15]:
        has_note = bool(ev.get("call_sts_update","").strip())
        has_meet = bool(ev.get("meet_sts_update","").strip())
        dot_c = "#10b981" if has_note else "#6366f1"
        tl_conn += f"""<div class="tl-item">
          <div class="tl-dot" style="background:{dot_c}"></div>
          <div class="tl-content">
            <div class="tl-title">Call by EmpID {esc(str(ev.get("call_by","")))}
              {' — <span class="tag tag-green">Has Note</span>' if has_note else ""}
              {' — <span class="tag tag-blue">Meeting Update</span>' if has_meet else ""}
            </div>
            <div class="tl-time">{esc(str(ev.get("call_answered_date","")))}</div>
            {f'<div style="font-size:12px;color:var(--mut);margin-top:6px">{esc(ev.get("call_sts_update",""))}</div>' if has_note else ""}
            {f'<div style="font-size:12px;color:var(--acc3);margin-top:4px">Meet: {esc(ev.get("meet_sts_update",""))}</div>' if has_meet else ""}
          </div>
        </div>"""
    tl_conn += "</div>"

    section_connect = f"""<div class="section">
      <div class="section-title">📞 Connect Details (30D)</div>
      {section_conn_cards}
      <div class="card">{tl_conn}</div>
    </div>"""

    # ── 5. KYC Details — Last 10 Supplier Activities ──
    kyc = d.get("kycdetails", {})
    last10 = kyc.get("LAST_10SUPPLIER_ACTIVITIES", []) if isinstance(kyc, dict) else []
    tl_kyc = '<div class="timeline">'
    for ev in last10:
        tl_kyc += f"""<div class="tl-item">
          <div class="tl-dot" style="background:#f59e0b"></div>
          <div class="tl-content">
            <div class="tl-title">{esc(ev.get("fk_display_title",""))}</div>
            <div class="tl-time">{esc(ev.get("date",""))} {esc(ev.get("time_new",""))}</div>
            <div class="tl-meta">
              <span class="tag tag-blue">{esc(ev.get("supplier_days",""))}</span>
              <span class="tag tag-purple">{esc(ev.get("gl_country",""))}</span>
              {f'<span class="tag tag-yellow" style="background:#451a0344;color:#fbbf24">{esc(ev.get("request_url","")[:60])}</span>' if ev.get("request_url","") else ""}
            </div>
          </div>
        </div>"""
    tl_kyc += "</div>"
    section_kyc = f"""<div class="section">
      <div class="section-title">🔍 KYC — Last 10 Supplier Activities</div>
      <div class="card">{tl_kyc if last10 else '<div class="empty">No supplier activities.</div>'}</div>
    </div>"""

    # ── 6. Tickets Details ──
    tkt = d.get("ticketsdetails", {})
    d7  = tkt.get("last_7_days", {}) if isinstance(tkt, dict) else {}
    d90 = tkt.get("last_8_to_90_days", {}) if isinstance(tkt, dict) else {}
    tkt_metrics = [
        ("total_ticket_count",               "Total Tickets"),
        ("irate_complaint_count",            "Irate Complaints"),
        ("negative_feedback_count",          "Negative Feedback"),
        ("board_social_media_ticket_count",  "Social Media Tickets"),
        ("whatsapp_negative_feedback_count", "WhatsApp Negative"),
    ]
    tkt_labels = [lbl for _, lbl in tkt_metrics]
    tkt_7d  = [d7.get(k, 0) or 0 for k, _ in tkt_metrics]
    tkt_90d = [d90.get(k, 0) or 0 for k, _ in tkt_metrics]

    tkt_cfg = chartjs_config("bar", tkt_labels, [
        {"label":"Last 7 Days", "data":tkt_7d,  "backgroundColor":"#6366f188","borderColor":"#6366f1","borderWidth":2},
        {"label":"8–90 Days",   "data":tkt_90d, "backgroundColor":"#ef444488","borderColor":"#ef4444","borderWidth":2},
    ])
    all_js.append(f"new Chart(document.getElementById('ch_tkt'),{tkt_cfg});")

    bs_conflict = d90.get("bs_conflict_status", "Unknown")
    wip = tkt.get("wip_tickets", {}) or {}
    wip_html = ""
    if wip.get("ticket_id","").strip():
        wip_html = f"""<div class="metric-card" style="--c:#ef4444;margin-top:16px">
          <div class="metric-lbl">WIP Ticket</div>
          <div class="metric-val" style="font-size:16px">{esc(wip.get("ticket_type",""))}</div>
          <div class="metric-sub">#{esc(wip.get("ticket_id",""))} — {esc(wip.get("ticket_status",""))}</div>
          <div style="font-size:12px;color:var(--mut);margin-top:6px">{esc(wip.get("ticket_opening_comments","")[:150])}</div>
        </div>"""

    section_tickets = f"""<div class="section">
      <div class="section-title">🎫 Tickets Details</div>
      <div class="grid g4" style="margin-bottom:16px">
        <div class="metric-card" style="--c:#6366f1"><div class="metric-lbl">Total (7D)</div><div class="metric-val">{d7.get("total_ticket_count",0)}</div></div>
        <div class="metric-card" style="--c:#f59e0b"><div class="metric-lbl">Total (8–90D)</div><div class="metric-val">{d90.get("total_ticket_count",0)}</div></div>
        <div class="metric-card" style="--c:{'#ef4444' if bs_conflict=='Yes' else '#10b981'}"><div class="metric-lbl">B/S Conflict</div><div class="metric-val" style="font-size:16px">{esc(bs_conflict)}</div></div>
      </div>
      <div class="card"><div class="card-title"><span>Ticket Breakdown</span></div><div class="chart-wrap"><canvas id="ch_tkt"></canvas></div></div>
      {wip_html}
    </div>"""

    # ── 7. Duplicate GLIDs ──
    dup = d.get("duplicate_glids_details", {})
    dup_glid = dup.get("duplicate_glid") if isinstance(dup, dict) else None
    dup_paid = dup.get("duplicate_paid_ids") if isinstance(dup, dict) else None
    section_dup = f"""<div class="section">
      <div class="section-title">🔗 Duplicate GLID Details</div>
      <div class="grid g2">
        <div class="metric-card" style="--c:{'#ef4444' if dup_glid else '#10b981'}">
          <div class="metric-lbl">Duplicate GLID</div>
          <div class="metric-val" style="font-size:16px">{'⚠ ' + esc(str(dup_glid)) if dup_glid else 'None'}</div>
        </div>
        <div class="metric-card" style="--c:{'#ef4444' if dup_paid else '#10b981'}">
          <div class="metric-lbl">Duplicate Paid IDs</div>
          <div class="metric-val" style="font-size:16px">{'⚠ ' + esc(str(dup_paid)) if dup_paid else 'None'}</div>
        </div>
      </div>
    </div>"""

    full_html = section_actual + section_bl + section_activity + section_connect + section_kyc + section_tickets + section_dup
    return full_html, "\n".join(all_js)


def gen_history_raw(data):
    """Renders the raw HTML history log returned by newHistory as a readable timeline."""
    d = data.get("data", {})
    raw_html = ""
    if isinstance(d, dict) and "_raw" in d:
        raw_html = d["_raw"]
    elif isinstance(d, list) and d and isinstance(d[0], dict):
        inner = d[0].get("data", [])
        if isinstance(inner, list):
            raw_html = "\n".join(str(i) for i in inner)

    if not raw_html:
        return gen_generic(data, "Call / DSR History")[0], ""

    import re as _re
    # Split on date-like lines
    entries = _re.split(r'(?=\d{2}\s+[A-Z]{3}\s+\d{4}\s+\d{2}:\d{2}:\d{2})', raw_html)
    entries = [e.strip() for e in entries if e.strip()]

    tl_html = '<div class="timeline">'
    dot_colors = ["#6366f1","#10b981","#f59e0b","#06b6d4","#8b5cf6","#ec4899"]
    for i, entry in enumerate(entries[:50]):
        # strip HTML tags for display
        clean = _re.sub(r'<[^>]+>', ' ', entry)
        clean = _re.sub(r'&nbsp;', ' ', clean)
        clean = _re.sub(r'\s+', ' ', clean).strip()
        # Extract date from start
        date_match = _re.match(r'(\d{2}\s+[A-Z]{3}\s+\d{4}\s+\d{2}:\d{2}:\d{2}\s*[APM]*)', clean)
        date_str = date_match.group(1).strip() if date_match else ""
        body = clean[len(date_str):].strip().lstrip(',').strip()
        color = dot_colors[i % len(dot_colors)]
        tl_html += f"""<div class="tl-item">
          <div class="tl-dot" style="background:{color}"></div>
          <div class="tl-content">
            <div class="tl-title">{esc(body[:300])}</div>
            <div class="tl-time">{esc(date_str)}</div>
          </div>
        </div>"""
    tl_html += "</div>"

    total = len(entries)
    html = f"""<div class="section">
      <div class="section-title">📋 History Log</div>
      <div class="metric-card" style="--c:#6366f1;margin-bottom:16px"><div class="metric-lbl">Total Entries</div><div class="metric-val">{total}</div></div>
      {tl_html}
    </div>"""
    return html, ""


def gen_product_summary(data):
    """Product quality summary — CQS score + percentage breakdown."""
    d = data.get("data", {})
    inner = d.get("data", d) if isinstance(d, dict) else d
    if not inner or not isinstance(inner, dict):
        return '<div class="no-data">No product summary data.</div>', ""

    cqs = inner.get("CQS", 0) or 0
    total = inner.get("total_products", 0) or 0

    # CQS gauge color
    cqs_color = "#10b981" if cqs >= 80 else "#f59e0b" if cqs >= 60 else "#ef4444"

    perc_metrics = [
        ("photo_prod_perc",    "Photos",           "#10b981"),
        ("desc_prod_perc",     "Description",      "#6366f1"),
        ("isq_prod_perc",      "ISQ",              "#06b6d4"),
        ("brochure_prod_perc", "Brochure",         "#8b5cf6"),
        ("video_prod_perc",    "Video",            "#f59e0b"),
        ("incorrect_price_prod_perc", "Incorrect Price", "#ef4444"),
    ]

    pqs_dist = [
        ("pqs_more_than80_products", "PQS > 80",  "#10b981"),
        ("pqs_less_than80_products", "PQS 60–80", "#f59e0b"),
        ("pqs_less_than60_products", "PQS < 60",  "#ef4444"),
    ]

    # CQS gauge via doughnut
    gauge_cfg = chartjs_config("doughnut",
        ["CQS Score", "Remaining"],
        [{"data": [cqs, 100-cqs], "backgroundColor": [cqs_color, "#2e3350"], "borderWidth": 0,
          "circumference": 180, "rotation": 270}],
        {"cutout": "75%", "plugins": {"legend": {"display": False}}})

    # Attribute coverage bars
    bars_html = ""
    for key, lbl, color in perc_metrics:
        val = inner.get(key, 0) or 0
        bars_html += f"""<div class="dual-bar">
          <div class="dual-lbl">{lbl}</div>
          <div class="dual-track">
            <div class="dual-fill" style="width:{max(4,val)}%;background:{color}">{val}%</div>
          </div>
        </div>"""

    # PQS distribution doughnut
    pqs_vals = [inner.get(k,0) or 0 for k,_,_ in pqs_dist]
    pqs_cfg = chartjs_config("doughnut",
        [lbl for _,lbl,_ in pqs_dist],
        [{"data": pqs_vals, "backgroundColor": [c for _,_,c in pqs_dist], "borderWidth": 0}])

    kpis_html = f"""<div class="grid g4" style="margin-bottom:20px">
      <div class="metric-card" style="--c:{cqs_color}">
        <div class="metric-lbl">CQS Score</div>
        <div class="metric-val" style="color:{cqs_color}">{cqs}</div>
        <div class="metric-sub">Catalog Quality Score</div>
      </div>
      <div class="metric-card" style="--c:#6366f1"><div class="metric-lbl">Total Products</div><div class="metric-val">{total}</div></div>
      <div class="metric-card" style="--c:#ef4444"><div class="metric-lbl">Unapproved</div><div class="metric-val">{inner.get("unapproved_products",0)}</div></div>
    </div>"""

    charts_html = f"""<div class="grid g2">
      <div class="card">
        <div class="card-title"><span>CQS Gauge</span></div>
        <div class="chart-wrap-sm"><canvas id="ch_cqs"></canvas></div>
        <div style="text-align:center;font-size:28px;font-weight:800;color:{cqs_color};margin-top:-60px">{cqs}</div>
      </div>
      <div class="card">
        <div class="card-title"><span>PQS Distribution</span></div>
        <div class="chart-wrap-sm"><canvas id="ch_pqs"></canvas></div>
      </div>
    </div>"""

    charts_js = f"new Chart(document.getElementById('ch_cqs'),{gauge_cfg});new Chart(document.getElementById('ch_pqs'),{pqs_cfg});"

    html = f"""<div class="section"><div class="section-title">🛍️ Product Quality Overview</div>{kpis_html}{charts_html}</div>
    <div class="section"><div class="section-title">📊 Attribute Coverage</div>{bars_html}</div>"""
    return html, charts_js


def gen_product_details(data):
    """Product quality details — table with YES/NO badges + PQS scores."""
    d = data.get("data", {})
    inner = d.get("data", d) if isinstance(d, dict) else d
    products = inner if isinstance(inner, list) else []

    if not products:
        return '<div class="no-data">No product detail data.</div>', ""

    # PQS distribution
    pqs_vals = []
    for p in products:
        try: pqs_vals.append(float(p.get("pqs", 0) or 0))
        except: pass
    pqs_avg = round(sum(pqs_vals)/len(pqs_vals), 1) if pqs_vals else 0
    pqs_color = "#10b981" if pqs_avg >= 80 else "#f59e0b" if pqs_avg >= 60 else "#ef4444"

    # mcat distribution
    mcats = {}
    for p in products:
        m = p.get("glcat_mcat_name", "Unknown")
        mcats[m] = mcats.get(m, 0) + 1
    mcat_labels = list(mcats.keys())[:8]
    mcat_vals = [mcats[k] for k in mcat_labels]
    mcat_cfg = chartjs_config("bar", mcat_labels,
        [{"label":"Products","data":mcat_vals,"backgroundColor":"#6366f188","borderColor":"#6366f1","borderWidth":2}])

    # PQS histogram buckets
    buckets = {"<60":0,"60-70":0,"70-80":0,"80-90":0,"90-100":0}
    for v in pqs_vals:
        if v < 60: buckets["<60"] += 1
        elif v < 70: buckets["60-70"] += 1
        elif v < 80: buckets["70-80"] += 1
        elif v < 90: buckets["80-90"] += 1
        else: buckets["90-100"] += 1
    hist_cfg = chartjs_config("bar", list(buckets.keys()),
        [{"label":"Products","data":list(buckets.values()),
          "backgroundColor":["#ef444488","#f59e0b88","#f59e0b88","#10b98188","#10b98188"],
          "borderColor":["#ef4444","#f59e0b","#f59e0b","#10b981","#10b981"],"borderWidth":2}])

    charts_html = f"""<div class="grid g2">
      <div class="card"><div class="card-title"><span>Products by MCat</span></div><div class="chart-wrap-sm"><canvas id="ch_mcat"></canvas></div></div>
      <div class="card"><div class="card-title"><span>PQS Distribution</span></div><div class="chart-wrap-sm"><canvas id="ch_pqsh"></canvas></div></div>
    </div>"""
    charts_js = f"new Chart(document.getElementById('ch_mcat'),{mcat_cfg});new Chart(document.getElementById('ch_pqsh'),{hist_cfg});"

    def yn_tag(val):
        v = str(val).upper()
        if v == "YES": return '<span class="tag tag-green">YES</span>'
        if v == "NO": return '<span class="tag tag-red">NO</span>'
        return esc(str(val))

    def pqs_badge(val):
        try:
            v = float(val)
            color = "#10b981" if v >= 80 else "#f59e0b" if v >= 60 else "#ef4444"
            return f'<b style="color:{color}">{v}</b>'
        except: return esc(str(val))

    rows = ""
    for i, p in enumerate(products):
        rows += f"""<tr>
          <td>{i+1}</td>
          <td style="font-size:12px;max-width:200px;white-space:normal">{esc(p.get('pc_item_name',''))}</td>
          <td>{esc(p.get('glcat_mcat_name',''))}</td>
          <td>{pqs_badge(p.get('pqs',''))}</td>
          <td>{yn_tag(p.get('photo1',''))}</td>
          <td>{yn_tag(p.get('description',''))}</td>
          <td>{yn_tag(p.get('price',''))}</td>
          <td>{yn_tag(p.get('brochure',''))}</td>
          <td>{yn_tag(p.get('video',''))}</td>
          <td>{yn_tag(p.get('other_isqs',''))} ({p.get('other_isqs_count',0)})</td>
          <td><span class="tag tag-blue">{esc(p.get('mcat_rank',''))}</span></td>
        </tr>"""

    table_html = f"""<div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Product</th><th>MCat</th><th>PQS</th><th>Photo</th><th>Desc</th><th>Price</th><th>Brochure</th><th>Video</th><th>ISQ</th><th>Rank</th></tr></thead>
      <tbody>{rows}</tbody></table></div>"""

    kpis_html = f"""<div class="grid g4" style="margin-bottom:20px">
      <div class="metric-card" style="--c:{pqs_color}"><div class="metric-lbl">Avg PQS</div><div class="metric-val" style="color:{pqs_color}">{pqs_avg}</div></div>
      <div class="metric-card" style="--c:#6366f1"><div class="metric-lbl">Total Products</div><div class="metric-val">{len(products)}</div></div>
      <div class="metric-card" style="--c:#10b981"><div class="metric-lbl">MCat Categories</div><div class="metric-val">{len(mcats)}</div></div>
    </div>"""

    html = f"""<div class="section"><div class="section-title">📦 Product Quality Details</div>{kpis_html}{charts_html}</div>
    <div class="section"><div class="section-title">📋 Product List</div>{table_html}</div>"""
    return html, charts_js


def gen_generic(data, title):
    """Fallback generic renderer for any JSON."""
    def render_val(val, depth=0):
        if val is None: return '<span style="color:var(--mut)">null</span>'
        if isinstance(val, bool): return f'<span class="tag {"tag-green" if val else "tag-red"}">{val}</span>'
        if isinstance(val, (int, float)): return f'<b style="color:var(--acc3)">{val}</b>'
        if isinstance(val, str):
            if len(val) > 200: return f'<span style="color:var(--mut);font-size:11px">{esc(val[:200])}...</span>'
            return esc(val)
        if isinstance(val, list):
            if not val: return '<span style="color:var(--mut)">[]</span>'
            if depth > 1: return f'<span class="tag tag-blue">Array({len(val)})</span>'
            if isinstance(val[0], dict):
                cols = list(val[0].keys())[:8]
                thead = "".join(f"<th>{humanize(c)}</th>" for c in cols)
                tbody = "".join("<tr>" + "".join(f"<td>{render_val(row.get(c), depth+1)}</td>" for c in cols) + "</tr>" for row in val[:30])
                return f'<div class="tbl-wrap"><table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>'
            return "<br>".join(render_val(v, depth+1) for v in val[:20])
        if isinstance(val, dict):
            if depth > 2: return f'<span class="tag tag-purple">Object({len(val)})</span>'
            rows = "".join(f'<div class="kv-item"><div class="kv-key">{humanize(k)}</div><div class="kv-val">{render_val(v, depth+1)}</div></div>' for k, v in val.items())
            return f'<div class="kv-grid">{rows}</div>'
        return esc(str(val))

    d = data.get("data", data)
    return f'<div class="section"><div class="section-title">📋 {title}</div>{render_val(safe_parse(d))}</div>', ""


# ── Config per folder ─────────────────────────────────────────────────────────
FOLDER_CONFIG = {
    "01_mcat":                 ("🗂️", "MCAT Location Details",     "DWH POST — mcatLocDtls",       gen_generic),
    "02_scorecard_summary":    ("📊", "Scorecard Summary",          "DWH POST — cust_wh_summary_api", gen_scorecard_summary),
    "03_scorecard_6m":         ("📈", "Scorecard 6-Month",          "DWH POST — cust_scorecard_api",  lambda d: gen_scorecard_monthly(d, 6)),
    "04_scorecard_12m":        ("📅", "Scorecard 12-Month",         "DWH POST — cust_wh_apiv2",       lambda d: gen_scorecard_monthly(d, 12)),
    "05_competitors":          ("🏭", "Competitor Analysis",        "DWH POST — nsdprepplus (flag=1)", gen_competitors),
    "06_competitors_counts":   ("🔢", "Competitor Market Counts",   "DWH POST — nsdprepplus (flag=2)", gen_competitors_counts),
    "07_history":              ("📞", "Call History",               "MERP GET — newHistory (AK param)", gen_history_raw),
    "08_dsr":                  ("📋", "DSR — History (glid=236)",   "MERP GET — newHistory (AK param)", gen_history_raw),
    "09_product_summary":      ("🛍️", "Product Quality Summary",   "MERP GET — qualityScoreDetails (AK param)", gen_product_summary),
    "10_product_details":      ("📦", "Product Quality Details",    "MERP GET — qualityScoreDetails (AK param)", gen_product_details),
    "11_ingestion_composite":  ("🏢", "Seller Composite Profile",   "Ingestion — /sellers/{glid}",    gen_ingestion_composite),
    "12_ingestion_calls":      ("📞", "Calls",                      "Ingestion — /calls",             gen_generic),
    "13_ingestion_hotleads":   ("🔥", "Hotleads",                   "Ingestion — /hotleads",          gen_ingestion_hotleads),
    "14_ingestion_blni":       ("📡", "BLNI",                       "Ingestion — /blni",              gen_generic),
    "15_ingestion_metrics":    ("📊", "Seller Metrics",             "Ingestion — /metrics",           gen_ingestion_metrics),
    "16_ingestion_activity":   ("⚡", "Activity Clickstream",       "Ingestion — /activity",          gen_ingestion_activity),
    "17_context_uid":          ("🔑", "Context UID",                "Context API — generateContextUID", gen_generic),
    "18_context_data":         ("🧩", "Context Data",               "Context API — getContext",        gen_context_data),
}


def generate_for_folder(folder):
    resp_path = os.path.join(BASE, folder, "response.json")
    if not os.path.exists(resp_path):
        print(f"  [SKIP] {folder} — no response.json")
        return

    with open(resp_path, encoding="utf-8") as f:
        raw = json.load(f)

    cfg = FOLDER_CONFIG.get(folder)
    if cfg:
        icon, title, subtitle, gen_fn = cfg
        if gen_fn == gen_generic:
            body_html, extra_js = gen_generic(raw, title)
        else:
            try:
                body_html, extra_js = gen_fn(raw)
            except Exception as e:
                print(f"  [WARN] {folder} gen_fn failed: {e}, falling back to generic")
                body_html, extra_js = gen_generic(raw, title)
    else:
        icon, title, subtitle = "📄", folder, "API Response"
        body_html, extra_js = gen_generic(raw, title)
        extra_js = ""

    status = raw.get("status")
    error = raw.get("error")
    status_cls = "ok" if status and 200 <= int(status) < 300 else "err"
    status_label = f"HTTP {status}" if status else ("Error" if error else "Unknown")
    glid = "488587"
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    raw_json_escaped = json.dumps(raw, indent=2, ensure_ascii=False, default=str).replace("</", "<\\/")

    html = HTML_TEMPLATE.format(
        title=title, icon=icon, subtitle=subtitle,
        status_cls=status_cls, status_label=status_label,
        glid=glid, generated=generated,
        body=body_html,
        raw_json_escaped=esc(json.dumps(raw, indent=2, ensure_ascii=False, default=str)),
        data_json=to_js_json(raw),
        js=extra_js,
    )

    out_path = os.path.join(BASE, folder, "dashboard.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  [OK] {folder} -> dashboard.html")


def main():
    folders = sorted(os.listdir(BASE))
    for folder in folders:
        if folder.startswith("_"): continue
        fp = os.path.join(BASE, folder)
        if os.path.isdir(fp):
            generate_for_folder(folder)
    print("\nAll dashboards generated.")


if __name__ == "__main__":
    main()
