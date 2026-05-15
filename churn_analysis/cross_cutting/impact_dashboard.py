# impact_dashboard.py
# Generates {run_dir}/impact_report.html — dark-theme HTML impact report.

import json
import os
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# CSS variables (matching scorer.html palette)
# ---------------------------------------------------------------------------
_CSS_VARS = """
  --bg:   #0f1117;
  --s1:   #1a1d27;
  --s2:   #22263a;
  --bdr:  #2e3350;
  --acc:  #6366f1;
  --red:  #ef4444;
  --amber:#f59e0b;
  --green:#10b981;
  --txt:  #e2e8f0;
  --mut:  #94a3b8;
"""

_FULL_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {""" + _CSS_VARS + """}
body {
  background: var(--bg);
  color: var(--txt);
  font-family: 'Segoe UI', system-ui, sans-serif;
  font-size: 15px;
  line-height: 1.6;
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}
h1, h2, h3 { font-weight: 700; }
h1 { font-size: 1.8rem; margin-bottom: .25rem; }
h2 { font-size: 1.2rem; color: var(--acc); margin: 2rem 0 .75rem; text-transform: uppercase; letter-spacing: .06em; }
h3 { font-size: 1rem; color: var(--mut); margin-bottom: .5rem; }
.subtitle { color: var(--mut); font-size: .9rem; margin-bottom: 2rem; }
/* Cards */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}
.card {
  background: var(--s1);
  border: 1px solid var(--bdr);
  border-radius: 10px;
  padding: 1.25rem 1.5rem;
}
.card-label { font-size: .78rem; color: var(--mut); text-transform: uppercase; letter-spacing: .05em; margin-bottom: .4rem; }
.card-value { font-size: 2rem; font-weight: 700; line-height: 1; }
.card-value.red    { color: var(--red); }
.card-value.amber  { color: var(--amber); }
.card-value.green  { color: var(--green); }
.card-value.accent { color: var(--acc); }
.card-sub  { font-size: .78rem; color: var(--mut); margin-top: .3rem; }
/* Efficiency row */
.eff-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}
.eff-card {
  background: var(--s2);
  border: 1px solid var(--bdr);
  border-radius: 10px;
  padding: 1rem 1.25rem;
}
.eff-label { font-size: .78rem; color: var(--mut); text-transform: uppercase; letter-spacing: .04em; margin-bottom: .3rem; }
.eff-value { font-size: 1.5rem; font-weight: 700; color: var(--acc); }
.eff-sub   { font-size: .75rem; color: var(--mut); margin-top: .2rem; }
/* RCA bar chart */
.rca-table { width: 100%; border-collapse: collapse; margin-bottom: 2rem; }
.rca-table th { text-align: left; font-size: .78rem; color: var(--mut); padding: .4rem .6rem; border-bottom: 1px solid var(--bdr); }
.rca-table td { padding: .45rem .6rem; border-bottom: 1px solid var(--bdr); vertical-align: middle; }
.rca-bar-wrap { width: 100%; background: var(--s2); border-radius: 4px; height: 14px; }
.rca-bar { height: 14px; border-radius: 4px; background: var(--acc); }
.rca-count { color: var(--txt); font-weight: 600; width: 40px; text-align: right; }
.rca-pct   { color: var(--mut); font-size: .8rem; width: 55px; text-align: right; }
/* Action queue table */
.queue-wrap { overflow-x: auto; margin-bottom: 2rem; }
table.queue { width: 100%; border-collapse: collapse; font-size: .85rem; }
table.queue th { text-align: left; padding: .5rem .75rem; background: var(--s2); color: var(--mut); text-transform: uppercase; font-size: .72rem; letter-spacing: .05em; }
table.queue td { padding: .55rem .75rem; border-bottom: 1px solid var(--bdr); }
table.queue tr:hover td { background: var(--s1); }
.tier-badge {
  display: inline-block;
  padding: .1rem .55rem;
  border-radius: 999px;
  font-size: .72rem;
  font-weight: 700;
  text-transform: uppercase;
}
.tier-red    { background: rgba(239,68,68,.15);   color: var(--red); }
.tier-amber  { background: rgba(245,158,11,.15);  color: var(--amber); }
.tier-green  { background: rgba(16,185,129,.15);  color: var(--green); }
.action-badge {
  display: inline-block;
  padding: .1rem .55rem;
  border-radius: 4px;
  font-size: .72rem;
  font-weight: 600;
  background: rgba(99,102,241,.15);
  color: var(--acc);
}
footer {
  margin-top: 3rem;
  padding-top: 1rem;
  border-top: 1px solid var(--bdr);
  color: var(--mut);
  font-size: .8rem;
  text-align: center;
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: str, default=None):
    if default is None:
        default = {}
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _fmt_inr(value: int) -> str:
    """Format integer as Indian Rupee string with lakh/crore abbreviation."""
    if value >= 10_000_000:
        return f"₹{value/10_000_000:.2f} Cr"
    if value >= 100_000:
        return f"₹{value/100_000:.2f} L"
    return f"₹{value:,}"


def _tier_badge(tier: str) -> str:
    cls = {"Red": "tier-red", "Amber": "tier-amber", "Green": "tier-green"}.get(tier, "tier-green")
    return f'<span class="tier-badge {cls}">{tier}</span>'


def _action_badge(action: str) -> str:
    return f'<span class="action-badge">{action}</span>'


def _rca_rows(rca_breakdown: dict, total: int) -> str:
    if not rca_breakdown or total == 0:
        return '<tr><td colspan="4" style="color:var(--mut)">No RCA data available.</td></tr>'
    sorted_rca = sorted(rca_breakdown.items(), key=lambda x: -x[1])
    max_count = max(v for _, v in sorted_rca) if sorted_rca else 1
    rows = []
    for label, count in sorted_rca:
        pct = count / total * 100
        bar_w = int(count / max_count * 100)
        rows.append(f"""
        <tr>
          <td style="color:var(--txt);font-weight:500;min-width:160px">{label}</td>
          <td class="rca-count">{count}</td>
          <td class="rca-pct">{pct:.1f}%</td>
          <td style="width:100%">
            <div class="rca-bar-wrap"><div class="rca-bar" style="width:{bar_w}%"></div></div>
          </td>
        </tr>""")
    return "\n".join(rows)


def _queue_rows(action_queue: list) -> str:
    top10 = [e for e in action_queue if e.get("final_tier") == "Red"][:10]
    if not top10:
        top10 = action_queue[:10]
    if not top10:
        return '<tr><td colspan="8" style="color:var(--mut)">No actions queued.</td></tr>'
    rows = []
    for i, entry in enumerate(top10, 1):
        tier  = entry.get("final_tier", "")
        score = entry.get("churn_score", 0)
        rca   = entry.get("rca", "")
        action = entry.get("action_type", "")
        urgency = entry.get("urgency", "")
        rows.append(f"""
        <tr>
          <td style="color:var(--mut)">{i}</td>
          <td style="font-family:monospace;font-size:.8rem">{entry.get('glid','')}</td>
          <td>{entry.get('company','')}</td>
          <td style="color:var(--mut)">{entry.get('city','')}</td>
          <td style="text-align:center;font-weight:700;color:var(--red)">{score}</td>
          <td>{_tier_badge(tier)}</td>
          <td style="color:var(--mut);font-size:.8rem">{rca}</td>
          <td>{_action_badge(action)} <span style="color:var(--mut);font-size:.72rem">{urgency}</span></td>
        </tr>""")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_impact_report(run_dir: str, master_plan: dict = None) -> str:
    """
    Generate {run_dir}/impact_report.html.

    Parameters
    ----------
    run_dir     : path to the run directory
    master_plan : pre-loaded master_action_plan dict; if None, read from disk

    Returns
    -------
    str — absolute path to generated HTML file
    """
    if master_plan is None:
        plan_path = os.path.join(run_dir, "action_plans", "master_action_plan.json")
        master_plan = _load_json(plan_path, {})

    s   = master_plan.get("summary", {})
    run_id       = master_plan.get("run_id", os.path.basename(run_dir.rstrip("/\\")))
    generated_at = master_plan.get("generated_at", datetime.utcnow().isoformat() + "Z")
    action_queue = master_plan.get("action_queue", [])
    rca_breakdown = master_plan.get("rca_breakdown", {})

    total        = s.get("total_sellers", 0)
    count_red    = s.get("red", 0)
    arr_risk     = s.get("estimated_arr_at_risk", 0)
    arr_save     = s.get("estimated_arr_saveable", 0)
    llm_scored   = s.get("llm_scored", 0)
    llm_upgraded = s.get("llm_upgraded_to_red", 0)

    human_calls  = s.get("human_calls_queued", 0)
    wa_queued    = s.get("whatsapp_queued", 0)
    rep_saved    = round(human_calls * 24.5, 1)
    crm_saved    = round(human_calls * 17.5, 1)

    rca_rows_html   = _rca_rows(rca_breakdown, total)
    queue_rows_html = _queue_rows(action_queue)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Seller Survival Intelligence — Impact Report</title>
  <style>{_FULL_CSS}</style>
</head>
<body>

<!-- ── Header ─────────────────────────────────────────────────────────── -->
<h1>Seller Survival Intelligence</h1>
<p class="subtitle">
  Impact Report &nbsp;·&nbsp;
  <span style="color:var(--acc)">{run_id}</span>
  &nbsp;·&nbsp;
  Generated: {generated_at}
</p>

<!-- ── Headline Metrics ────────────────────────────────────────────────── -->
<h2>Headline Metrics</h2>
<div class="card-grid">
  <div class="card">
    <div class="card-label">Total Sellers Analyzed</div>
    <div class="card-value accent">{total}</div>
  </div>
  <div class="card">
    <div class="card-label">Red Tier — Immediate Action</div>
    <div class="card-value red">{count_red}</div>
    <div class="card-sub">{s.get('amber',0)} Amber &nbsp;|&nbsp; {s.get('green',0)} Green</div>
  </div>
  <div class="card">
    <div class="card-label">Estimated ARR at Risk</div>
    <div class="card-value red">{_fmt_inr(arr_risk)}</div>
    <div class="card-sub">Red sellers × ₹15 K avg ARR</div>
  </div>
  <div class="card">
    <div class="card-label">Estimated ARR Saveable</div>
    <div class="card-value green">{_fmt_inr(arr_save)}</div>
    <div class="card-sub">60 % recovery assumption</div>
  </div>
  <div class="card">
    <div class="card-label">LLM Cohort Scored</div>
    <div class="card-value accent">{llm_scored}</div>
    <div class="card-sub">Coverage: {s.get('coverage_pct',0)*100:.1f}%</div>
  </div>
  <div class="card">
    <div class="card-label">LLM Upgraded to Red</div>
    <div class="card-value amber">{llm_upgraded}</div>
    <div class="card-sub">Caught by AI, missed by rules</div>
  </div>
</div>

<!-- ── Efficiency Metrics ──────────────────────────────────────────────── -->
<h2>Efficiency Metrics</h2>
<div class="eff-grid">
  <div class="eff-card">
    <div class="eff-label">Human Calls Queued</div>
    <div class="eff-value">{human_calls}</div>
    <div class="eff-sub">Same-day Red-tier escalations</div>
  </div>
  <div class="eff-card">
    <div class="eff-label">WhatsApp Messages Queued</div>
    <div class="eff-value">{wa_queued}</div>
    <div class="eff-sub">Amber + Green outreach</div>
  </div>
  <div class="eff-card">
    <div class="eff-label">Rep Time Saved (prep)</div>
    <div class="eff-value">{rep_saved:,.0f} min</div>
    <div class="eff-sub">24.5 min saved per call ({human_calls} calls)</div>
  </div>
  <div class="eff-card">
    <div class="eff-label">Post-call CRM Savings</div>
    <div class="eff-value">{crm_saved:,.0f} min</div>
    <div class="eff-sub">17.5 min saved per call ({human_calls} calls)</div>
  </div>
  <div class="eff-card">
    <div class="eff-label">Gifted Leads Allocated</div>
    <div class="eff-value">{s.get('gifted_leads_allocated',0)}</div>
    <div class="eff-sub">High-risk sellers with gifted lead offer</div>
  </div>
  <div class="eff-card">
    <div class="eff-label">Winback Eligible</div>
    <div class="eff-value">{s.get('winback_eligible',0)}</div>
    <div class="eff-sub">Lapsed sellers targeted for reactivation</div>
  </div>
</div>

<!-- ── RCA Breakdown ───────────────────────────────────────────────────── -->
<h2>Root Cause Analysis Breakdown</h2>
<table class="rca-table">
  <thead>
    <tr>
      <th>RCA Category</th>
      <th style="text-align:right">Count</th>
      <th style="text-align:right">% Total</th>
      <th>Distribution</th>
    </tr>
  </thead>
  <tbody>
    {rca_rows_html}
  </tbody>
</table>

<!-- ── Action Queue (Top 10 Red) ──────────────────────────────────────── -->
<h2>Action Queue — Top Priority Sellers</h2>
<div class="queue-wrap">
  <table class="queue">
    <thead>
      <tr>
        <th>#</th>
        <th>GLID</th>
        <th>Company</th>
        <th>City</th>
        <th style="text-align:center">Score</th>
        <th>Tier</th>
        <th>RCA</th>
        <th>Action</th>
      </tr>
    </thead>
    <tbody>
      {queue_rows_html}
    </tbody>
  </table>
</div>

<!-- ── Footer ─────────────────────────────────────────────────────────── -->
<footer>
  Generated by <strong>Seller Survival Intelligence</strong>
  &nbsp;·&nbsp; IndiaMART Hackathon 2026
</footer>

</body>
</html>
"""

    out_path = os.path.join(run_dir, "impact_report.html")
    os.makedirs(run_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    return out_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python impact_dashboard.py <run_dir>")
        sys.exit(1)
    path = build_impact_report(sys.argv[1])
    print(f"Report written to: {path}")
