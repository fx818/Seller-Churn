"""
Batch Results Viewer — standalone HTML browser for runs/batch_testid/*.json

Usage:
    python viewer.py [--dir runs/batch_testid] [--port 5001]
Then open: http://localhost:5001

Left sidebar: list of sellers (company + GLID + verdict/risk badge).
Right panel:  full BL Card view for the selected seller.

Reads JSON files written by `python -m churn_analysis pipeline --glids-file ...`.
Refreshes the seller list every time the page polls /api/sellers (so newly
finished sellers appear without restarting the server).
"""
import argparse
import json
import os
from flask import Flask, jsonify, render_template_string, send_from_directory, abort

app = Flask(__name__)
_DIR = os.path.abspath("runs/batch_testid")


def _scan_sellers() -> list[dict]:
    """Walk the batch directory and return one entry per seller_*.json."""
    out = []
    if not os.path.isdir(_DIR):
        return out
    for fn in sorted(os.listdir(_DIR)):
        if not (fn.startswith("seller_") and fn.endswith(".json")):
            continue
        path = os.path.join(_DIR, fn)
        glid = fn[len("seller_"):-len(".json")]
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        ctx     = data.get("context") or {}
        phases  = data.get("phases") or {}
        bl_card = (((phases.get("phase6_card") or {}).get("bl-card") or {})
                   .get("data") or {})
        header  = bl_card.get("header") or {}
        scores  = bl_card.get("scores") or {}
        out.append({
            "glid":     glid,
            "company":  ctx.get("company", "—"),
            "city":     ctx.get("city", ""),
            "state":    ctx.get("state", ""),
            "verdict":  header.get("verdict", "—"),
            "priority": header.get("priority", 0),
            "churn_score": scores.get("churn_score"),
            "risk_tier":   scores.get("risk_tier", "—"),
            "size_kb": round(os.path.getsize(path) / 1024, 1),
        })
    return out


@app.route("/")
def index():
    return render_template_string(_VIEWER_HTML)


@app.route("/api/sellers")
def api_sellers():
    return jsonify(_scan_sellers())


@app.route("/data/<glid>.json")
def api_seller_data(glid):
    safe = "".join(c for c in glid if c.isdigit())
    if not safe:
        abort(400)
    fn = f"seller_{safe}.json"
    if not os.path.isfile(os.path.join(_DIR, fn)):
        abort(404)
    return send_from_directory(_DIR, fn, mimetype="application/json")


# ── HTML / JS template (single file, no external deps) ──────────────────────

_VIEWER_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Survival Index — Seller Cohort</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<!-- Distinctive display serif (Fraunces) + characterful body (Geist) + tabular mono -->
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700;9..144,900&family=Geist:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  /* ─────────────────────────────────────────────────────────────────────────
     AESTHETIC: Bloomberg terminal × editorial publication.
     Single dominant accent (ochre #d4a373) on near-black paper. Serif display
     headlines. Sharp 1px hairlines. Tabular monospace numerals. Film-grain
     noise overlay. Staggered detail-reveal animation on selection.
     ───────────────────────────────────────────────────────────────────────── */
  :root {
    --ink:#0a0908;          /* paper-black */
    --ink-2:#13110f;        /* slightly raised */
    --ink-3:#1c1916;        /* panel */
    --line:#2a2520;         /* hairline */
    --line-2:#3a342e;       /* heavier hairline */
    --paper:#f5efe6;        /* near-white text */
    --paper-2:#cdc5b8;      /* muted body */
    --paper-3:#7c766c;      /* labels / metadata */
    --paper-4:#4d4842;      /* deep mute */

    --accent:#d4a373;       /* dominant ochre — the single signature color */
    --accent-bright:#ecc8a0;
    --accent-dim:#8c6c4a;

    --crit:#c1432d;         /* terra cotta red (not neon) */
    --crit-bg:#3a1812;
    --warn:#d4a373;         /* amber == accent (intentional cohesion) */
    --warn-bg:#2e2418;
    --safe:#7a9572;         /* sage green (muted, not neon) */
    --safe-bg:#1a2218;
  }
  * { box-sizing: border-box; }
  html, body { margin:0; padding:0; }
  body {
    font-family: 'Geist', system-ui, -apple-system, sans-serif;
    background: var(--ink);
    color: var(--paper); font-size: 14px; line-height: 1.55; letter-spacing:-.005em;
    min-height: 100vh;
    -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
    font-variant-numeric: tabular-nums;
  }
  /* Grain overlay — gives the surface a paper / film-emulsion quality */
  body::before {
    content:''; position:fixed; inset:0; pointer-events:none; z-index:1000; opacity:.045;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>");
    mix-blend-mode: overlay;
  }
  /* Vignette */
  body::after {
    content:''; position:fixed; inset:0; pointer-events:none; z-index:999;
    background: radial-gradient(ellipse at center, transparent 60%, rgba(0,0,0,.35) 100%);
  }

  code, pre, .mono {
    font-family: 'JetBrains Mono', ui-monospace, Monaco, monospace;
    font-feature-settings: "tnum", "ss01";
  }
  /* Display serif for headlines / numerals */
  .display, h2 {
    font-family: 'Fraunces', 'Times New Roman', serif;
    font-optical-sizing: auto;
    font-weight: 700; letter-spacing:-.025em;
  }

  /* ─── Masthead (editorial top bar) ─── */
  .masthead {
    height: 64px; padding: 0 28px; display:flex; align-items:center; gap:24px;
    background: var(--ink); border-bottom: 1px solid var(--line);
    position: sticky; top:0; z-index: 50;
  }
  .masthead .brand {
    font-family:'Fraunces', serif; font-weight: 900; font-size: 22px;
    letter-spacing:-.035em; line-height:1; font-style: italic;
  }
  .masthead .brand .dot { color: var(--accent); }
  .masthead .strapline {
    font-size: 10px; letter-spacing:.18em; text-transform:uppercase;
    color: var(--paper-3); border-left:1px solid var(--line); padding-left:18px;
  }
  .masthead .ticker {
    display:flex; gap:0; margin-left:auto; align-items:stretch; height: 100%;
  }
  .tick {
    padding: 0 18px; display:flex; align-items:center; gap:10px;
    border-left:1px solid var(--line); font-size:11px; color: var(--paper-2);
  }
  .tick .num {
    font-family:'JetBrains Mono', monospace; font-weight:600; font-size:14px;
    color: var(--paper); letter-spacing:.02em;
  }
  .tick .label { color: var(--paper-3); text-transform:uppercase; letter-spacing:.12em; font-size:9px; }
  .tick.crit .num { color: var(--crit); }
  .tick.warn .num { color: var(--accent-bright); }
  .tick.safe .num { color: var(--safe); }

  .layout { display:grid; grid-template-columns: 320px 1fr; height: calc(100vh - 64px); }

  /* ─── Left rail ─── */
  aside {
    background: var(--ink); border-right: 1px solid var(--line);
    overflow-y: auto; padding: 22px 18px; display:flex; flex-direction:column; gap:14px;
  }
  aside::-webkit-scrollbar, main::-webkit-scrollbar, pre::-webkit-scrollbar { width:6px; height:6px; }
  aside::-webkit-scrollbar-thumb, main::-webkit-scrollbar-thumb, pre::-webkit-scrollbar-thumb { background:var(--line-2); }
  ::-webkit-scrollbar-track { background: transparent; }

  .rail-head {
    font-family:'Fraunces', serif; font-size: 11px; letter-spacing:.22em;
    text-transform:uppercase; color: var(--paper-3); padding-bottom: 4px;
    border-bottom: 1px solid var(--line); margin-bottom: 4px;
  }
  .filter-row { display:flex; gap:8px; flex-direction:column; }
  .search {
    width:100%; padding: 11px 12px 11px 34px; background: var(--ink-2); color: var(--paper);
    border: 1px solid var(--line); border-radius: 0; font-size: 13px;
    font-family: inherit;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='13' height='13' fill='none' stroke='%237c766c' stroke-width='1.8' viewBox='0 0 24 24'><circle cx='11' cy='11' r='8'/><path d='m21 21-4.3-4.3'/></svg>");
    background-repeat: no-repeat; background-position: 12px center;
    transition: border-color .15s;
  }
  .search::placeholder { color: var(--paper-4); }
  .search:focus { outline: none; border-color: var(--accent); }
  .sort-select {
    padding: 10px 12px; background: var(--ink-2); color: var(--paper); border:1px solid var(--line);
    border-radius: 0; font-size: 11px; cursor:pointer; font-family: 'JetBrains Mono', monospace;
    text-transform: uppercase; letter-spacing:.1em;
  }
  .sort-select:focus { outline:none; border-color: var(--accent); }

  .seller-list { display:flex; flex-direction:column; }
  .seller {
    padding: 12px 14px 14px; background: transparent;
    border: 0; border-top: 1px solid var(--line);
    cursor:pointer; transition: background .15s, padding-left .15s;
    position: relative;
  }
  .seller:last-child { border-bottom: 1px solid var(--line); }
  .seller:hover { background: var(--ink-2); padding-left: 18px; }
  .seller.active { background: var(--ink-3); padding-left: 18px; }
  .seller.active::before {
    content:''; position:absolute; left:0; top:0; bottom:0; width:2px; background: var(--accent);
  }
  .seller .row1 { display:flex; justify-content:space-between; align-items:baseline; gap:8px; margin-bottom: 5px; }
  .seller .company {
    font-family:'Fraunces', serif; font-weight:600; font-size:15px; line-height:1.2;
    color: var(--paper); letter-spacing:-.012em;
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1;
  }
  .seller .row2 {
    display:flex; gap:8px; align-items:center; font-size:10px; color: var(--paper-3);
    font-family:'JetBrains Mono', monospace; letter-spacing:.04em;
  }
  .seller .glid { color: var(--paper-3); }
  .seller .sep { color: var(--paper-4); }
  .seller .row3 { display:grid; grid-template-columns: 1fr 34px; gap:10px; margin-top: 7px; align-items:center; }
  .score-mini {
    height: 2px; background: var(--ink-3); position:relative; overflow:hidden;
  }
  .score-mini-fill { height:100%; transition: width .4s ease; }
  .score-mini-fill.Red    { background: var(--crit); }
  .score-mini-fill.Amber  { background: var(--accent); }
  .score-mini-fill.Green  { background: var(--safe); }
  .seller .score-num {
    font-family:'JetBrains Mono', monospace; font-weight:600; font-size:12px;
    color: var(--paper); text-align:right;
  }

  .pill {
    display:inline-flex; align-items:center; gap:6px; padding: 2px 9px;
    font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing:.14em;
    border:1px solid; border-radius:0; font-family: 'JetBrains Mono', monospace;
  }
  .pill .dot { width:5px; height:5px; }
  .pill.Red    { background: var(--crit-bg); color: var(--crit); border-color: var(--crit); }
  .pill.Red .dot { background: var(--crit); }
  .pill.Amber  { background: var(--warn-bg); color: var(--accent-bright); border-color: var(--accent); }
  .pill.Amber .dot { background: var(--accent); }
  .pill.Green  { background: var(--safe-bg); color: var(--safe); border-color: var(--safe); }
  .pill.Green .dot { background: var(--safe); }
  .pill.Unknown { background: var(--ink-3); color: var(--paper-3); border-color: var(--line-2); }

  /* ─── Main panel ─── */
  main {
    overflow-y: auto; padding: 36px 56px 80px;
    background: linear-gradient(180deg, var(--ink) 0%, var(--ink-2) 100%);
  }
  .hint {
    color: var(--paper-3); font-size:14px; padding:120px 0; text-align:center;
    display:flex; flex-direction:column; align-items:center; gap:18px;
    font-family:'Fraunces', serif; font-style: italic; font-size: 18px;
  }
  .hint .arrow {
    font-family:'JetBrains Mono', monospace; font-style: normal;
    font-size:11px; color: var(--paper-4); letter-spacing:.2em; text-transform:uppercase;
  }

  /* ─── Detail header ─── */
  .detail-head { animation: rise .5s ease both; }
  @keyframes rise   { from { opacity:0; transform: translateY(8px); } to { opacity:1; transform: none; } }
  @keyframes fade   { from { opacity:0; } to { opacity:1; } }

  .eyebrow {
    font-family: 'JetBrains Mono', monospace; font-size:10px; letter-spacing:.22em;
    text-transform: uppercase; color: var(--paper-3); margin-bottom: 12px;
    display:flex; align-items:center; gap:14px;
  }
  .eyebrow .rule { flex:0 0 36px; height:1px; background: var(--accent); }

  h2.title {
    font-size: clamp(32px, 4vw, 52px); line-height: 1.02;
    margin: 0 0 18px; color: var(--paper); font-weight: 700;
    max-width: 26ch;
  }
  .detail-meta {
    color: var(--paper-2); font-size: 12px; display:flex; gap:0;
    border-top: 1px solid var(--line); border-bottom: 1px solid var(--line);
    padding: 14px 0; margin-bottom: 28px; font-family: 'JetBrains Mono', monospace;
    letter-spacing:.05em;
  }
  .detail-meta .col { flex:1; padding-right: 16px; }
  .detail-meta .col + .col { border-left: 1px solid var(--line); padding-left:16px; }
  .detail-meta .lbl {
    font-size: 9px; color: var(--paper-3); text-transform:uppercase; letter-spacing:.18em;
    margin-bottom: 4px;
  }
  .detail-meta .val { color: var(--paper); font-weight: 500; }

  /* ─── Verdict — full-width slab ─── */
  .verdict {
    padding: 26px 30px; margin: 0 0 36px;
    border: 1px solid var(--line); position:relative;
    display:flex; align-items:center; gap:22px;
    background: var(--ink-2);
  }
  .verdict .mark {
    font-family: 'Fraunces', serif; font-weight: 900; font-size: 56px; line-height:.9;
    color: var(--accent);
  }
  .verdict.CRITICAL .mark, .verdict.CRITICAL .head { color: var(--crit); }
  .verdict.HEALTHY  .mark, .verdict.HEALTHY .head  { color: var(--safe); }
  .verdict .copy { flex:1; }
  .verdict .label {
    font-family:'JetBrains Mono', monospace; font-size:10px; letter-spacing:.22em;
    text-transform:uppercase; color: var(--paper-3); margin-bottom:6px;
  }
  .verdict .head {
    font-family:'Fraunces', serif; font-weight:700; font-size: 26px; letter-spacing:-.02em;
    color: var(--accent); line-height: 1.15;
  }
  .verdict.CRITICAL { border-color: var(--crit); }
  .verdict.HEALTHY  { border-color: var(--safe); }

  /* ─── KPI strip — newspaper data block ─── */
  .kpi-strip {
    display:grid; grid-template-columns: repeat(4, 1fr); gap:0;
    border-top: 1px solid var(--line); border-bottom: 1px solid var(--line);
    margin-bottom: 36px;
  }
  .kpi {
    padding: 22px 24px; border-right: 1px solid var(--line); background: var(--ink-2);
    position: relative; opacity:0; animation: rise .55s ease forwards;
  }
  .kpi:last-child { border-right: 0; }
  .kpi:nth-child(1) { animation-delay: .05s; }
  .kpi:nth-child(2) { animation-delay: .15s; }
  .kpi:nth-child(3) { animation-delay: .25s; }
  .kpi:nth-child(4) { animation-delay: .35s; }
  .kpi .lbl {
    font-family:'JetBrains Mono', monospace; font-size:9px;
    color: var(--paper-3); text-transform: uppercase; letter-spacing: .22em;
    margin-bottom: 14px;
  }
  .kpi .val {
    font-family:'Fraunces', serif; font-size: 48px; font-weight: 700;
    line-height: .95; letter-spacing:-.035em; color: var(--paper);
  }
  .kpi .val .unit { font-size: 16px; color: var(--paper-3); font-weight:400; margin-left:4px; }
  .kpi .sub {
    font-size: 11px; color: var(--paper-2); margin-top: 12px;
    display:flex; align-items:center; gap:8px;
  }
  .kpi.Red .val    { color: var(--crit); }
  .kpi.Amber .val  { color: var(--accent-bright); }
  .kpi.Green .val  { color: var(--safe); }

  /* progress bar */
  .progress {
    height: 3px; background: var(--ink-3); margin-top: 14px; position:relative; overflow:hidden;
  }
  .progress-fill { height:100%; transition: width .8s cubic-bezier(.22, 1, .36, 1); }
  .progress-fill.Red    { background: var(--crit); }
  .progress-fill.Amber  { background: var(--accent); }
  .progress-fill.Green  { background: var(--safe); }
  .progress-fill.Blue   { background: var(--accent-dim); }

  /* ─── Section headers — numbered editorial style ─── */
  h3 {
    margin: 56px 0 18px; font-family:'Fraunces', serif; font-weight:700;
    font-size: 22px; letter-spacing: -.02em; color: var(--paper);
    display:flex; align-items:baseline; gap: 16px;
  }
  h3 .num {
    font-family:'JetBrains Mono', monospace; font-weight:500; font-size:11px;
    color: var(--accent); letter-spacing:.2em; flex:0 0 36px;
  }
  h3 .rule {
    flex:1; height:1px; background: var(--line); position:relative; top:-6px;
  }

  /* ─── Sections ─── */
  .section { padding: 0; background: transparent; border:0; margin-bottom: 0; }
  .panel {
    background: var(--ink-2); border: 1px solid var(--line); padding: 22px 26px;
  }
  .panel + .panel { border-top: 0; }

  .kv  {
    display:grid; grid-template-columns: 200px 1fr; gap: 12px 24px; font-size:13px;
    align-items: baseline;
  }
  .kv .k {
    color: var(--paper-3); font-family:'JetBrains Mono', monospace;
    font-size:10px; text-transform:uppercase; letter-spacing:.16em;
  }
  .kv .v { color: var(--paper); }
  .kv .v b { font-weight: 600; color: var(--paper); }
  .kv .v code {
    font-size: 11px; background: var(--ink); padding: 1px 6px; border:1px solid var(--line);
  }

  /* ─── Quotes — pull-quote style ─── */
  .quote {
    background: transparent; border-left: 2px solid var(--accent);
    padding: 6px 16px; margin: 10px 0;
    font-family:'Fraunces', serif; font-style: italic; font-size: 17px; line-height:1.55;
    color: var(--paper); max-width: 70ch;
  }
  .quote.small { font-size: 14px; }
  .quote .lang {
    font-family:'JetBrains Mono', monospace; font-style: normal; font-size: 9px;
    color: var(--accent); letter-spacing:.22em; text-transform: uppercase;
    margin-bottom: 6px; display: block;
  }

  /* ─── Tags ─── */
  .tag-row { display:flex; flex-wrap:wrap; gap:5px; }
  .tag {
    background: transparent; border:1px solid var(--line); padding: 3px 9px;
    font-size: 10px; font-family:'JetBrains Mono', monospace; color: var(--paper-2);
    letter-spacing: .06em;
  }
  .tag.red   { color: var(--crit); border-color: var(--crit); background: var(--crit-bg); }
  .tag.amber { color: var(--accent-bright); border-color: var(--accent); background: var(--warn-bg); }

  /* ─── Reasons ─── */
  .reasons { display:flex; flex-direction:column; gap: 0; }
  .reason {
    padding: 10px 0 10px 18px; font-size: 13px; color: var(--paper);
    border-bottom: 1px solid var(--line); position: relative;
  }
  .reason:last-child { border-bottom: 0; }
  .reason::before {
    content:'›'; position:absolute; left: 0; top: 9px;
    color: var(--accent); font-family:'Fraunces', serif; font-weight: 700; font-size: 16px;
  }

  /* ─── Skill output grid ─── */
  .skill-grid {
    display:grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 0;
    border-top: 1px solid var(--line); border-left: 1px solid var(--line);
  }
  .skill-card {
    background: var(--ink-2);
    border-right: 1px solid var(--line); border-bottom: 1px solid var(--line);
    padding: 16px 18px; font-size: 12px;
  }
  .skill-card .skill-title {
    font-family:'JetBrains Mono', monospace; font-size:10px; letter-spacing:.18em;
    text-transform: uppercase; color: var(--accent); margin-bottom: 10px;
    padding-bottom: 6px; border-bottom: 1px solid var(--line);
  }
  .skill-card .skill-row {
    display:flex; justify-content:space-between; padding: 4px 0;
    border-bottom: 1px dotted var(--line);
  }
  .skill-card .skill-row:last-child { border-bottom: 0; }
  .skill-card .skill-row .k {
    color: var(--paper-3); font-family:'JetBrains Mono', monospace;
    font-size:10px; letter-spacing: .04em;
  }
  .skill-card .skill-row .v {
    color: var(--paper); font-weight: 500; max-width: 160px; text-align:right;
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size: 11px;
  }

  /* ─── Score derivation bar chart ─── */
  .bar-chart { display:flex; flex-direction:column; gap: 8px; font-size: 12px; }
  .bar-row {
    display:grid; grid-template-columns: 200px 1fr 50px; gap: 14px; align-items:center;
  }
  .bar-row .lbl {
    color: var(--paper-2); font-family:'JetBrains Mono', monospace;
    font-size: 10px; letter-spacing: .06em;
  }
  .bar-track { height: 10px; background: var(--ink-3); position:relative; overflow:hidden; }
  .bar-fill {
    height:100%; background: var(--accent);
    transition: width .8s cubic-bezier(.22, 1, .36, 1);
  }
  .bar-val {
    font-family:'JetBrains Mono', monospace; font-size: 11px; text-align:right;
    color: var(--paper); font-weight:600;
  }
  .derivation-line {
    font-family:'JetBrains Mono', monospace; font-size: 11px; color: var(--paper-2);
    letter-spacing: .04em; margin-bottom: 18px;
    padding-bottom: 14px; border-bottom: 1px solid var(--line);
  }
  .derivation-line b { color: var(--accent); font-weight: 600; }

  /* ─── Cross-platform ─── */
  .platform-grid {
    display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 0;
    border: 1px solid var(--line); margin: 14px 0;
  }
  .platform {
    background: var(--ink-2); padding: 16px 14px; text-align:center;
    border-right: 1px solid var(--line);
  }
  .platform:last-child { border-right: 0; }
  .platform.found .pcount { color: var(--paper); }
  .platform.im .pcount    { color: var(--accent); }
  .platform .pname {
    font-family:'JetBrains Mono', monospace; font-size:9px;
    color: var(--paper-3); text-transform:uppercase; letter-spacing:.18em;
    margin-bottom: 8px;
  }
  .platform .pcount {
    font-family:'Fraunces', serif; font-size: 32px; font-weight: 700;
    line-height:1; color: var(--paper-4);
  }
  .platform .psub {
    font-size: 10px; color: var(--paper-3); margin-top: 6px;
    font-family:'JetBrains Mono', monospace; letter-spacing:.06em;
  }

  .gap-bar { margin-top: 18px; padding: 16px 18px; background: var(--ink); border:1px solid var(--line); }
  .gap-line { display:flex; justify-content:space-between; align-items:baseline; margin-bottom: 10px; }
  .gap-line .gap-meta { font-size: 12px; color: var(--paper-2); }
  .gap-line .gap-meta b { color: var(--paper); }
  .gap-line .gap-val {
    font-family: 'Fraunces', serif; font-weight: 700; font-size: 26px; letter-spacing: -.02em;
  }
  .gap-bar-track { height: 4px; background: var(--ink-3); position:relative; overflow:hidden; }
  .gap-bar-fill { height:100%; transition: width .8s; }
  .gap-bar-fill.high   { background: var(--crit); }
  .gap-bar-fill.medium { background: var(--accent); }
  .gap-bar-fill.low    { background: var(--safe); }

  /* ─── Onboarding checks ─── */
  .check-list { display:flex; flex-direction:column; }
  .check {
    display:grid; grid-template-columns: 1fr auto auto; gap: 14px; align-items:center;
    padding: 12px 16px; border-bottom: 1px solid var(--line); font-size: 13px;
    background: var(--ink-2); border-left: 2px solid var(--line);
  }
  .check:last-child { border-bottom: 1px solid var(--line); }
  .check.Green  { border-left-color: var(--safe); }
  .check.Amber  { border-left-color: var(--accent); }
  .check.Red    { border-left-color: var(--crit); }
  .check .cname { font-weight: 500; color: var(--paper); }
  .check .cnote { font-size: 11px; color: var(--paper-3); margin-top: 3px; }
  .check .cscore {
    font-family:'JetBrains Mono', monospace; font-size: 12px; color: var(--paper-2);
  }

  /* ─── Lookalikes ─── */
  .glid-chips { display:flex; flex-wrap:wrap; gap: 5px; }
  .glid-chip {
    font-family:'JetBrains Mono', monospace; font-size: 11px; padding: 4px 10px;
    background: transparent; border: 1px solid var(--line); color: var(--paper-2);
  }
  .glid-chip.churned  { color: var(--crit); border-color: var(--crit); background: var(--crit-bg); }
  .glid-chip.retained { color: var(--safe); border-color: var(--safe); background: var(--safe-bg); }

  /* ─── Misc ─── */
  details {
    margin: 10px 0; background: var(--ink-2); border: 1px solid var(--line);
    padding: 14px 18px;
  }
  details[open] { padding-bottom: 18px; }
  details summary {
    cursor:pointer; font-family:'JetBrains Mono', monospace; font-size: 10px;
    letter-spacing: .18em; text-transform:uppercase; color: var(--paper-3);
    list-style:none; display:flex; align-items:center; gap:10px; user-select:none;
  }
  details summary::before {
    content:'+'; color: var(--accent); font-size:14px;
    transition: transform .2s; line-height: 1; width:10px;
  }
  details[open] summary::before { content:'−'; }
  details summary:hover { color: var(--paper); }

  pre {
    background: var(--ink); padding: 16px; overflow: auto; font-size: 11px;
    line-height: 1.5; max-height: 480px; color: var(--paper-2);
    margin-top: 14px; border: 1px solid var(--line);
  }
  pre.summary { color: var(--paper); font-family:'JetBrains Mono', monospace; font-size: 11px; }

  .list { font-size: 13px; line-height: 1.9; margin: 8px 0; padding-left: 22px; color: var(--paper); }
  .list li { margin-bottom: 2px; }
  .list li::marker { color: var(--accent); }

  /* ─── Two-column split ─── */
  .split-2 { display:grid; grid-template-columns: 1fr 1fr; gap: 0; }
  .split-2 > * + * { border-left: 0; }
  .split-2 > * { border-top: 1px solid var(--line); }
  .split-2 > *:first-child + * { border-left: 1px solid var(--line); }

  /* ─── Animation utility — stagger child sections ─── */
  .reveal > * { opacity: 0; animation: rise .5s ease forwards; }
  .reveal > *:nth-child(1) { animation-delay: .05s; }
  .reveal > *:nth-child(2) { animation-delay: .12s; }
  .reveal > *:nth-child(3) { animation-delay: .19s; }
  .reveal > *:nth-child(4) { animation-delay: .26s; }
  .reveal > *:nth-child(5) { animation-delay: .33s; }
  .reveal > *:nth-child(6) { animation-delay: .40s; }
  .reveal > *:nth-child(7) { animation-delay: .47s; }
  .reveal > *:nth-child(8) { animation-delay: .54s; }
  .reveal > *:nth-child(9) { animation-delay: .61s; }
  .reveal > *:nth-child(10), .reveal > *:nth-child(n+10) { animation-delay: .68s; }
</style>
</head>
<body>

<header class="masthead">
  <div class="brand">Survival Index<span class="dot">.</span></div>
  <div class="strapline">Seller Cohort Bulletin · IndiaMART Retention</div>
  <div class="ticker" id="topstats">
    <div class="tick"><div class="num">—</div><div class="label">Loading</div></div>
  </div>
</header>

<div class="layout">

  <aside>
    <div class="rail-head">The Cohort</div>
    <div class="filter-row">
      <input class="search" id="search" placeholder="Search company or GLID" />
      <select class="sort-select" id="sort" onchange="renderList()">
        <option value="priority">Sort · Priority desc</option>
        <option value="churn">Sort · Churn desc</option>
        <option value="company">Sort · Company A–Z</option>
        <option value="glid">Sort · GLID</option>
        <option value="risk">Sort · Risk tier</option>
      </select>
    </div>
    <div class="seller-list" id="list"></div>
  </aside>

  <main id="main">
    <div class="hint">
      <div>An untold story waits.</div>
      <div class="arrow">← Choose a seller to read</div>
    </div>
  </main>

</div>

<script>
let SELLERS = [];
let CURRENT = null;

async function loadSellers() {
  try {
    const r = await fetch('/api/sellers');
    SELLERS = await r.json();
  } catch (e) {
    return;
  }
  renderTopStats();
  renderList();
}

function renderTopStats() {
  const counts = {Red:0, Amber:0, Green:0, Unknown:0};
  let totalChurn = 0, withChurn = 0, totalPri = 0;
  for (const s of SELLERS) {
    const t = s.risk_tier || 'Unknown';
    counts[t] = (counts[t] || 0) + 1;
    if (s.churn_score != null) { totalChurn += s.churn_score; withChurn++; }
    totalPri += (s.priority || 0);
  }
  const avg = withChurn ? Math.round(totalChurn / withChurn) : '—';
  const avgPri = SELLERS.length ? Math.round(totalPri / SELLERS.length) : '—';
  document.getElementById('topstats').innerHTML = `
    <div class="tick"><div class="num">${SELLERS.length}</div><div class="label">Cohort</div></div>
    <div class="tick crit"><div class="num">${counts.Red||0}</div><div class="label">Critical</div></div>
    <div class="tick warn"><div class="num">${counts.Amber||0}</div><div class="label">At Risk</div></div>
    <div class="tick safe"><div class="num">${counts.Green||0}</div><div class="label">Healthy</div></div>
    <div class="tick"><div class="num">${avg}</div><div class="label">Avg Churn</div></div>
    <div class="tick"><div class="num">${avgPri}</div><div class="label">Avg Priority</div></div>
  `;
}

function renderList() {
  const q = (document.getElementById('search').value || '').toLowerCase();
  const sort = document.getElementById('sort').value;
  let filtered = SELLERS.filter(s =>
    !q || (s.company || '').toLowerCase().includes(q) || s.glid.includes(q)
  );
  const riskOrder = {Red:0, Amber:1, Green:2, Unknown:3};
  filtered.sort((a, b) => {
    if (sort === 'priority') return (b.priority||0) - (a.priority||0);
    if (sort === 'churn')    return (b.churn_score||0) - (a.churn_score||0);
    if (sort === 'company')  return (a.company||'').localeCompare(b.company||'');
    if (sort === 'glid')     return (parseInt(a.glid)||0) - (parseInt(b.glid)||0);
    if (sort === 'risk')     return (riskOrder[a.risk_tier]||3) - (riskOrder[b.risk_tier]||3);
    return 0;
  });
  const html = filtered.map(s => {
    const tier = s.risk_tier || 'Unknown';
    const score = s.churn_score ?? 0;
    return `
    <div class="seller ${CURRENT === s.glid ? 'active' : ''}" onclick="loadSeller('${s.glid}')">
      <div class="row1">
        <div class="company">${escapeHtml(s.company || '—')}</div>
        <span class="pill ${tier}"><span class="dot"></span>${tier}</span>
      </div>
      <div class="row2">
        <span class="glid">${s.glid}</span>
        <span class="sep">·</span>
        <span>${escapeHtml(s.city || '—')}</span>
      </div>
      <div class="row3">
        <div class="score-mini"><div class="score-mini-fill ${tier}" style="width:${Math.min(100, score)}%"></div></div>
        <div class="score-num">${s.churn_score ?? '—'}</div>
      </div>
    </div>`;
  }).join('');
  document.getElementById('list').innerHTML = html || '<div style="color:var(--paper-3);font-size:12px;text-align:center;padding:30px;font-style:italic;font-family:\'Fraunces\',serif">No matches.</div>';
}

async function loadSeller(glid) {
  CURRENT = glid;
  renderList();
  const main = document.getElementById('main');
  main.innerHTML = '<div class="hint">Loading…</div>';
  try {
    const r = await fetch(`/data/${glid}.json`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    main.innerHTML = renderSeller(data);
  } catch (e) {
    main.innerHTML = `<div class="hint">Failed to load: ${e.message}</div>`;
  }
}

function escapeHtml(s) {
  return (s == null ? '' : String(s))
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function verdictClass(v) {
  if (!v) return '';
  if (v.startsWith('CRITICAL')) return 'CRITICAL';
  if (v.startsWith('AT'))       return 'AT';
  if (v.startsWith('HEALTHY'))  return 'HEALTHY';
  return '';
}

function severityClass(score, redAt, amberAt) {
  if (score == null) return '';
  if (score >= redAt) return 'Red';
  if (score >= amberAt) return 'Amber';
  return 'Green';
}

function renderSeller(data) {
  const ctx     = data.context || {};
  const phases  = data.phases  || {};
  const blCard  = (((phases.phase6_card || {})['bl-card'] || {}).data) || {};
  const header  = blCard.header  || {};
  const scores  = blCard.scores  || {};
  const rca     = blCard.root_cause  || {};
  const signals = blCard.signals     || {};
  const action  = blCard.action_plan || {};
  const messaging = blCard.messaging || {};
  const intv    = blCard.interventions || {};
  const cp      = blCard.cross_platform || {};
  const onb     = blCard.onboarding || {};
  const looks   = blCard.lookalikes || {};

  // -- Per-phase skill outputs (every skill, structured) --
  const phaseOut = {};
  for (const [pid, pdata] of Object.entries(phases)) {
    if (!pdata || pdata.skipped) continue;
    for (const [skill, sr] of Object.entries(pdata)) {
      if (sr && typeof sr === 'object' && 'data' in sr) phaseOut[skill] = sr.data;
    }
  }

  const verdict   = header.verdict || '—';
  const company   = ctx.company || '—';
  const initial   = (company && company !== '—') ? company.trim().charAt(0).toUpperCase() : '·';
  const riskTier  = scores.risk_tier || 'Unknown';
  const churnScore = scores.churn_score ?? 0;
  const priority  = header.priority ?? 0;

  return `
    <div class="detail-header">
      <div class="avatar">${escapeHtml(initial)}</div>
      <div style="flex:1">
        <h2>${escapeHtml(company)}</h2>
        <div class="detail-meta">
          <span><b>GLID</b> <code class="mono">${ctx.glid || data.glid || '—'}</code></span>
          <span class="sep">•</span>
          <span>${escapeHtml(ctx.city || '—')}${ctx.state ? ', ' + escapeHtml(ctx.state) : ''}</span>
          <span class="sep">•</span>
          <span>${escapeHtml(ctx.custtype || '—')}</span>
          <span class="sep">•</span>
          <span>${ctx.account_age_days || 0}d old</span>
          ${ctx.paid_history ? '<span class="sep">•</span><span style="color:var(--green)">✓ Paid history</span>' : ''}
        </div>
      </div>
    </div>

    <div class="verdict-banner ${verdictClass(verdict)}">
      <span class="verdict-icon">${verdictClass(verdict) === 'CRITICAL' ? '🚨' : verdictClass(verdict) === 'AT' ? '⚠️' : '✓'}</span>
      <span>${escapeHtml(verdict)}</span>
    </div>

    <!-- ─── KPI cards ─── -->
    <div class="kpi-grid">
      <div class="kpi ${riskTier}">
        <div class="lbl">Churn Score</div>
        <div class="val">${scores.churn_score ?? '—'}<span style="font-size:14px;color:var(--mut);font-weight:400">/100</span></div>
        <div class="sub"><span class="pill ${riskTier}"><span class="dot"></span>${riskTier}</span></div>
        <div class="progress"><div class="progress-fill ${riskTier}" style="width:${Math.min(100, churnScore)}%"></div></div>
      </div>
      <div class="kpi Purple">
        <div class="lbl">LLM Risk</div>
        <div class="val" style="font-size:24px">${escapeHtml(scores.llm_risk || '—')}</div>
        <div class="sub">Confidence ${scores.llm_confidence ?? '—'}</div>
      </div>
      <div class="kpi Blue">
        <div class="lbl">Priority</div>
        <div class="val">${priority}<span style="font-size:14px;color:var(--mut);font-weight:400">/100</span></div>
        <div class="progress"><div class="progress-fill Blue" style="width:${Math.min(100, priority)}%"></div></div>
      </div>
      <div class="kpi Green">
        <div class="lbl">IM Products</div>
        <div class="val">${header.im_product_count ?? 0}</div>
        <div class="sub">${scores.bands ? `BL ${scores.bands.bl || '—'} · LMS ${scores.bands.lms || '—'} · Act ${scores.bands.activity || '—'}` : ''}</div>
      </div>
    </div>

    <!-- ─── Root cause ─── -->
    <h3>🎯 Root Cause Analysis</h3>
    <div class="section">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
        <span class="pill Red" style="background:var(--acc-glow);color:var(--acc-2);border-color:var(--acc)">${escapeHtml(rca.category || 'UNKNOWN')}</span>
        <span style="font-size:11px;color:var(--mut)">Confidence: <b style="color:var(--fg)">${Math.round((rca.confidence || 0) * 100)}%</b></span>
        ${rca.intervention ? `<span class="sep" style="color:var(--line-2)">•</span><span style="font-size:12px;color:var(--mut-2)">Hint: ${escapeHtml(rca.intervention)}</span>` : ''}
      </div>
      ${rca.english ? `<div class="quote"><div class="lang">EN</div>${escapeHtml(rca.english)}</div>` : ''}
      ${rca.hindi ? `<div class="quote"><div class="lang">HI</div>${escapeHtml(rca.hindi)}</div>` : ''}
    </div>

    <!-- ─── Score derivation (per-signal bars) ─── -->
    ${renderScoreBreakdown(phaseOut['churn-scoring'])}

    <!-- ─── Signals ─── -->
    <h3>📊 Signals & Reasons</h3>
    <div class="section">
      <div class="kv" style="margin-bottom:14px">
        <div class="k">Reply rate (30d)</div>   <div class="v"><b style="color:${(signals.reply_rate_30d ?? 0) < 15 ? 'var(--red)' : 'var(--fg)'}">${signals.reply_rate_30d ?? '—'}%</b></div>
        <div class="k">Trajectory</div>         <div class="v">${escapeHtml(signals.trajectory || '—')}</div>
        <div class="k">Demand</div>             <div class="v"><b>${escapeHtml(signals.demand_tier || '—')}</b> <span style="color:var(--mut)">(${signals.demand_index ?? '—'}/100)</span></div>
        <div class="k">Peer comparison</div>    <div class="v">${escapeHtml(signals.peer_comparison || '—')}</div>
      </div>
      ${(signals.churn_reasons || []).length ? `
        <div style="font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">Detected reasons</div>
        <div class="reasons">${(signals.churn_reasons || []).map(r => `<div class="reason">${escapeHtml(r)}</div>`).join('')}</div>
      ` : ''}
      ${(signals.reason_tags || []).length ? `
        <div style="font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em;margin:14px 0 6px">Reason tags</div>
        <div class="tag-row">${(signals.reason_tags || []).map(t => `<span class="tag ${t.includes('ZERO_') || t.includes('CRITICAL_') || t.includes('CATASTROPHIC') ? 'red' : t.includes('LOW_') || t.includes('NO_') ? 'amber' : ''}">${escapeHtml(t)}</span>`).join('')}</div>
      ` : ''}
    </div>

    <!-- ─── Action plan ─── -->
    <h3>🎬 Action Plan</h3>
    <div class="section">
      ${action.opening_en ? `<div class="quote"><div class="lang">Opening · EN</div>${escapeHtml(action.opening_en)}</div>` : ''}
      ${action.opening_hi ? `<div class="quote"><div class="lang">Opening · HI</div>${escapeHtml(action.opening_hi)}</div>` : ''}
      ${(action.suggested_actions || []).length ? `
        <div style="font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em;margin:12px 0 6px">Suggested actions</div>
        <ul class="list">${(action.suggested_actions || []).map(a => `<li>${escapeHtml(a)}</li>`).join('')}</ul>
      ` : ''}
      ${(action.do_not_mention || []).length ? `
        <div style="margin-top:12px;font-size:11px;color:var(--mut)">⚠ Do not mention: ${(action.do_not_mention || []).map(escapeHtml).join(' · ')}</div>
      ` : ''}
    </div>

    <!-- ─── Messaging ─── -->
    <h3>💬 Messaging</h3>
    <div class="section">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:10px">
        <div>
          <div style="font-size:11px;color:var(--mut);margin-bottom:4px">📱 WhatsApp · HI</div>
          <div class="quote">${escapeHtml(messaging.whatsapp_hi || '—')}</div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--mut);margin-bottom:4px">📱 WhatsApp · EN</div>
          <div class="quote">${escapeHtml(messaging.whatsapp_en || '—')}</div>
        </div>
      </div>
      ${renderCallScript(messaging.call_script_hi, 'HINDI')}
      ${renderCallScript(messaging.call_script_en, 'ENGLISH')}
    </div>

    <!-- ─── Interventions ─── -->
    <h3>🔄 Interventions</h3>
    <div class="section" style="display:grid;grid-template-columns:1fr 1fr;gap:18px">
      <div>
        <div style="font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">BL Upgrade</div>
        <div style="font-size:18px;font-weight:700;color:${intv.bl_upgrade_eligible ? 'var(--green)' : 'var(--mut)'}">
          ${intv.bl_upgrade_eligible ? '✓ Eligible' : '✗ Not eligible'}
        </div>
        <div style="font-size:12px;color:var(--mut-2);margin-top:4px">${escapeHtml(intv.bl_upgrade_reason || '')}</div>
      </div>
      <div>
        <div style="font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Winback</div>
        <div style="font-size:24px;font-weight:700;color:${intv.winback_priority === 'HIGH' ? 'var(--red)' : intv.winback_priority === 'MEDIUM' ? 'var(--amber)' : 'var(--green)'}">
          ${intv.winback_score ?? '—'}<span style="font-size:14px;color:var(--mut);font-weight:400">/100</span>
          <span class="pill ${intv.winback_priority === 'HIGH' ? 'Red' : intv.winback_priority === 'MEDIUM' ? 'Amber' : 'Green'}" style="margin-left:8px;font-size:9px">${intv.winback_priority || '—'}</span>
        </div>
        ${intv.winback_pitch ? `<div class="quote" style="margin-top:8px">${escapeHtml(intv.winback_pitch)}</div>` : ''}
      </div>
    </div>

    <!-- ─── Cross-platform ─── -->
    ${renderCrossPlatform(cp, header.im_product_count ?? 0)}

    <!-- ─── Onboarding ─── -->
    ${renderOnboarding(onb)}

    <!-- ─── Lookalikes ─── -->
    ${(looks.churned || []).length || (looks.retained || []).length ? `
      <h3>👥 Lookalikes — Cohort Match</h3>
      <div class="section" style="display:grid;grid-template-columns:1fr 1fr;gap:18px">
        <div>
          <div style="font-size:11px;color:var(--mut);text-transform:uppercase;margin-bottom:8px">Churned similar (${(looks.churned||[]).length})</div>
          <div class="glid-chips">${(looks.churned||[]).map(g => `<span class="glid-chip churned">${g}</span>`).join('')}</div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--mut);text-transform:uppercase;margin-bottom:8px">Retained similar (${(looks.retained||[]).length})</div>
          <div class="glid-chips">${(looks.retained||[]).map(g => `<span class="glid-chip retained">${g}</span>`).join('')}</div>
        </div>
      </div>
    ` : ''}

    <!-- ─── All skill outputs grid ─── -->
    <h3>🧪 Skill Outputs — Phase by Phase</h3>
    <div class="skill-grid">
      ${Object.entries(phaseOut).map(([skill, out]) => `
        <div class="skill-card">
          <div class="skill-title">${escapeHtml(skill)}</div>
          ${Object.entries(out).filter(([, v]) => typeof v !== 'object' || v === null).slice(0, 8).map(([k, v]) => `
            <div class="skill-row"><span class="k">${escapeHtml(k)}</span><span class="v" title="${escapeHtml(String(v))}">${escapeHtml(String(v ?? '—').slice(0, 28))}</span></div>
          `).join('')}
        </div>
      `).join('')}
    </div>

    <!-- ─── Raw JSON dumps ─── -->
    ${blCard.summary_text ? `
      <h3>📋 CRM-Pasteable Summary</h3>
      <pre style="font-family:'JetBrains Mono', monospace">${escapeHtml(blCard.summary_text)}</pre>
    ` : ''}

    <details style="margin-top:18px">
      <summary>📦 Full pipeline JSON (raw)</summary>
      <pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>
    </details>
  `;
}

function renderScoreBreakdown(churnData) {
  if (!churnData || !churnData.score_breakdown) return '';
  const sb = churnData.score_breakdown;
  const max = Math.max(...Object.values(sb), 1);
  const total = Object.values(sb).reduce((a, b) => a + (b || 0), 0);
  const bars = Object.entries(sb)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `
      <div class="bar-row">
        <div class="lbl">${escapeHtml(k)}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${(v / max) * 100}%"></div></div>
        <div class="bar-val">+${v}</div>
      </div>
    `).join('');
  return `
    <h3>🔬 Churn Score Derivation</h3>
    <div class="section">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;font-size:12px">
        <div>Base ${churnData.base_score} → × ${churnData.compound_multiplier} (${churnData.red_flag_count || 0} Red flags) ${churnData.trajectory_adjustment ? '→ +' + churnData.trajectory_adjustment + ' trajectory' : ''} ${churnData.llm_used ? '→ ' + (churnData.llm_adjustment >= 0 ? '+' : '') + churnData.llm_adjustment + ' LLM' : ''}</div>
        <div style="font-weight:700;color:var(--fg-bright)">= ${churnData.churn_score}/100</div>
      </div>
      <div class="bar-chart">${bars}</div>
      ${churnData.llm_justification ? `
        <div class="quote" style="margin-top:14px">
          <div class="lang">💬 LLM Justification (${churnData.llm_adjustment >= 0 ? '+' : ''}${churnData.llm_adjustment})</div>
          ${escapeHtml(churnData.llm_justification)}
        </div>
      ` : ''}
    </div>
  `;
}

function renderCallScript(script, lang) {
  if (!script || Object.keys(script).length === 0) return '';
  return `
    <details>
      <summary>📞 5-part call script · ${lang}</summary>
      <div style="margin-top:10px">
        ${Object.entries(script).map(([part, text]) => `
          <div style="margin-bottom:10px">
            <div style="font-size:10px;color:var(--acc-2);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">${escapeHtml(part)}</div>
            <div class="quote" style="margin:0">${escapeHtml(String(text))}</div>
          </div>
        `).join('')}
      </div>
    </details>
  `;
}

function renderCrossPlatform(cp, imCount) {
  if (!cp) return '';
  const platforms = cp.platform_data || {};
  const gap = cp.im_catalog_gap || {};
  const found = cp.platforms_found || [];
  if (!found.length && !imCount) return '';

  // Build platform cards including IM as the anchor
  const all = [['indiamart', {found:true, product_count: imCount, is_im: true}]]
              .concat(Object.entries(platforms));

  const platformsHtml = all.map(([name, d]) => {
    if (!d) return '';
    const isIm = d.is_im;
    const label = name === 'own_website' ? '🌐 Own Website' :
                  name === 'indiamart'   ? '🏠 IndiaMART' :
                  name.charAt(0).toUpperCase() + name.slice(1);
    return `
      <div class="platform ${d.found ? 'found' : ''} ${isIm ? 'im' : ''}">
        <div class="pname">${escapeHtml(label)}</div>
        <div class="pcount">${d.product_count ?? '—'}</div>
        <div class="psub">${d.found ? 'products' : 'not found'}</div>
        ${d.rating > 0 ? `<div class="psub">⭐ ${d.rating}</div>` : ''}
      </div>
    `;
  }).join('');

  const gapPct = gap.gap_pct ?? 0;
  const sev = gap.severity || 'low';
  const gapAbs = Math.min(100, Math.abs(gapPct));

  return `
    <h3>🌐 Cross-Platform Intelligence</h3>
    <div class="section">
      <div style="margin-bottom:12px;font-size:12px;color:var(--mut-2)">
        Found on: ${found.length ? found.map(p => `<b style="color:var(--green)">${escapeHtml(p)}</b>`).join(' · ') : '<span style="color:var(--mut)">none</span>'}
        ${cp.competitive_positioning ? `<span class="sep" style="color:var(--line-2)"> • </span><b>${escapeHtml(cp.competitive_positioning)}</b>` : ''}
      </div>
      <div class="platform-grid">${platformsHtml}</div>
      ${gap.gap_pct != null ? `
        <div class="gap-bar">
          <div class="gap-line">
            <span>IM <b>${gap.im_products ?? '—'}</b> vs Others <b>${gap.other_total_products ?? gap.other_avg_products ?? '—'}</b> ${gap.match_method === 'names' ? '(name-matched)' : ''}</span>
            <span class="gap-val" style="color:${sev === 'high' ? 'var(--red)' : sev === 'medium' ? 'var(--amber)' : 'var(--green)'}">${gapPct > 0 ? '+' : ''}${gapPct}%</span>
          </div>
          <div class="gap-bar-track"><div class="gap-bar-fill ${sev}" style="width:${gapAbs}%"></div></div>
          <div style="font-size:10px;color:var(--mut);margin-top:6px">Severity: <span class="pill ${sev === 'high' ? 'Red' : sev === 'medium' ? 'Amber' : 'Green'}">${sev}</span></div>
        </div>
      ` : ''}
      ${cp.headline_en ? `<div class="quote" style="margin-top:12px"><div class="lang">Pitch · EN</div>${escapeHtml(cp.headline_en)}</div>` : ''}
      ${cp.headline_hi ? `<div class="quote"><div class="lang">Pitch · HI</div>${escapeHtml(cp.headline_hi)}</div>` : ''}
    </div>
  `;
}

function renderOnboarding(onb) {
  if (!onb || onb.health_score == null) return '';
  const tier = onb.health_tier || 'Unknown';
  const checks = onb.checks || {};
  const checkHtml = Object.entries(checks).map(([name, info]) => {
    if (!info || typeof info !== 'object') return '';
    const t = info.tier || (info.passed ? 'Green' : 'Red');
    return `
      <div class="check ${t}">
        <div>
          <div class="cname">${escapeHtml(name.replace(/_/g, ' '))}</div>
          ${info.note ? `<div class="cnote">${escapeHtml(info.note)}</div>` : ''}
        </div>
        <span class="pill ${t}">${t}</span>
        <span class="cscore">${info.score ?? '—'}/${info.weight ?? '—'}</span>
      </div>
    `;
  }).join('');
  return `
    <h3>🌱 Onboarding Health</h3>
    <div class="section">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:12px">
        <span class="pill ${tier}" style="font-size:11px"><span class="dot"></span>${tier}</span>
        <span style="font-size:22px;font-weight:700">${onb.health_score}<span style="font-size:12px;color:var(--mut);font-weight:400">/100</span></span>
        ${onb.trigger_action ? `<span class="sep">•</span><span style="font-size:12px;color:var(--mut-2)">${escapeHtml(onb.trigger_action)}</span>` : ''}
      </div>
      ${(onb.risk_priors||[]).length ? `<div style="margin-bottom:12px"><span style="font-size:11px;color:var(--mut)">Risk priors:</span> ${(onb.risk_priors||[]).map(r => `<span class="tag red" style="margin-right:4px">${escapeHtml(r)}</span>`).join('')}</div>` : ''}
      ${checkHtml ? `<div class="check-list">${checkHtml}</div>` : ''}
    </div>
  `;
}

// Wire up
document.getElementById('search').addEventListener('input', renderList);
loadSellers();
// Refresh sellers list every 15s so new completions appear during the batch
setInterval(loadSellers, 15000);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="runs/batch_testid")
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()
    _DIR = os.path.abspath(args.dir)
    print(f"Batch Results Viewer  →  http://localhost:{args.port}")
    print(f"Watching directory:   {_DIR}")
    print(f"Sellers found:        {len(_scan_sellers())}")
    app.run(host="0.0.0.0", port=args.port, debug=False)
