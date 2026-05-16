"""
CLI for churn_analysis skill runner + pipeline.

  python -m churn_analysis skills                             # list skills from MD files
  python -m churn_analysis skill <name> <GLID> [--pretty]    # run one skill
  python -m churn_analysis skill <name> <GLID> [--json]      # compact JSON output
  python -m churn_analysis pipeline --glid <GLID>            # full MD-driven pipeline
  python -m churn_analysis pipeline --glids-file FILE        # batch pipeline
  python -m churn_analysis pipeline --glid <GLID> --no-llm   # skip LLM skills
"""
import json
import os
import sys
import time

_HACKATHON = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _HACKATHON not in sys.path:
    sys.path.insert(0, _HACKATHON)

_SKILLS_DIR = os.path.join(_HACKATHON, "skills")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fetch_snap(glid: int):
    from seller_survival.slim_loader import fetch_for_glid
    from seller_survival.feature_schema import extract_snapshot
    print(f"  Fetching APIs for GLID {glid}...", flush=True)
    api_resp = fetch_for_glid(glid, verbose=True)
    print(f"  Extracting snapshot...", flush=True)
    snap = extract_snapshot(glid, "target", api_resp)
    return snap, api_resp


def _print_pretty(skill_name: str, glid: int, version: str, sr) -> None:
    print(f"\n{'-'*60}")
    print(f"SKILL: {skill_name}  |  GLID: {glid}  |  v{version}")
    print(f"Status: {'OK' if sr.success else 'FAIL'}  |  "
          f"Confidence: {sr.confidence:.2f}  |  "
          f"Latency: {sr.latency_ms}ms")
    if sr.error:
        print(f"Error: {sr.error}")
    print()

    # Special pretty layouts
    if skill_name == "cross_platform_intelligence" and sr.success:
        _print_cross_platform_pretty(sr.data or {})
        return
    if skill_name == "churn_scoring" and sr.success:
        _print_churn_scoring_pretty(sr.data or {})
        return
    if skill_name == "winback_priority" and sr.success:
        _print_winback_pretty(sr.data or {})
        return

    for k, v in (sr.data or {}).items():
        if isinstance(v, list) and len(v) > 0 and isinstance(v[0], str):
            print(f"{k:<20}: ")
            for item in v:
                print(f"  - {item}")
        elif isinstance(v, dict):
            print(f"{k:<20}: {json.dumps(v, ensure_ascii=False, default=str)}")
        else:
            print(f"{k:<20}: {v}")
    print()


def _print_churn_scoring_pretty(d: dict) -> None:
    """Pretty output for v2.0 churn_scoring.

    Default shows a concise summary. Pass --explain to expand the full
    score-derivation breakdown.
    """
    score = d.get("churn_score")
    risk  = d.get("risk", "—")
    print(f"  CHURN SCORE:        {score}/100   ({risk})")
    print(f"  Red flags:          {d.get('red_flag_count', 0)}")
    print(f"  Signals available:  {d.get('signals_available', '?')}")
    print(f"  Reply rate (30d):   {d.get('reply_rate_30d', 0)}%")
    print()

    reasons = d.get("churn_reasons") or []
    if reasons:
        print("  Churn signals detected:")
        for r in reasons:
            print(f"    - {r}")
        print()

    tags = d.get("reason_tags") or []
    if tags:
        print(f"  Reason tags: {', '.join(tags)}")
        print()

    # --- Score derivation breakdown (hidden by default; --explain to show) ---
    show_breakdown = bool(os.getenv("_CHURN_EXPLAIN"))
    if not show_breakdown:
        print("  [ Run with --explain to see how this score was calculated ]")
        print()
        return

    print("  +" + "-" * 64 + "+")
    print("  | SCORE DERIVATION                                                |")
    print("  +" + "-" * 64 + "+")
    print(f"    1. Base (sum of penalties):    {d.get('base_score', 0)}")
    cmult = d.get("compound_multiplier", 1.0)
    if cmult and cmult > 1.0:
        print(f"    2. Compound penalty:           x{cmult}  ({d.get('red_flag_count', 0)} Red flags)")
        print(f"       -> Compounded score:        {d.get('compounded_score', 0)}")
    else:
        print(f"    2. Compound penalty:           not triggered (need 3+ Red flags)")
    tadj = d.get("trajectory_adjustment", 0)
    if tadj:
        print(f"    3. Trajectory adjustment:      {tadj:+d}  ({d.get('trajectory_note','')})")
    else:
        print(f"    3. Trajectory adjustment:      0")
    if d.get("pre_llm_score") is not None:
        print(f"    4. Pre-LLM score:              {d['pre_llm_score']}")
    if d.get("llm_used"):
        ladj = d.get("llm_adjustment", 0)
        print(f"    5. LLM second-opinion adj:     {ladj:+d}")
        if d.get("llm_justification"):
            print(f"       LLM says: {d['llm_justification'][:160]}")
    else:
        print(f"    5. LLM second opinion:         not run")
    print(f"    => FINAL CHURN SCORE:          {score}  ({risk})")
    print()
    sb = d.get("score_breakdown") or {}
    if sb:
        print("  Per-signal points contributing to base:")
        for k, v in sb.items():
            print(f"    {k:<20s}: +{v}")
        print()
    print("  Tiers: >=72 Red, 42-71 Amber, <42 Green")
    print("  Note: cross-platform adjustment is added separately in the BL Card.")
    print()


def _print_winback_pretty(d: dict) -> None:
    """Pretty output for winback_priority v2.0.

    Default = concise summary. Pass --explain for full derivation breakdown.
    """
    ws  = d.get("winback_score")
    pri = d.get("priority", "—")
    print(f"  WINBACK SCORE:      {ws}/100   ({pri})")
    print(f"  Pre-LLM score:      {d.get('pre_llm_score','—')}")
    print(f"  Pitch type:         {d.get('winback_pitch_type','—')}")
    cool_str = "elapsed" if d.get("cool_off_elapsed") else f"{d.get('cool_off_days_remaining',0)}d left"
    print(f"  Cool-off:           {cool_str} (req: {d.get('cool_off_required_days','?')}d)")
    print(f"  Gifted lead OK:     {d.get('gifted_lead_eligible', False)}")
    print(f"  Est. conversion:    {int((d.get('estimated_conversion_probability') or 0)*100)}%")
    print(f"  Recommended pkg:    {d.get('recommended_package','—')}")
    print()
    if d.get("opening_line_hi"):
        print(f"  Opening line:       {d['opening_line_hi']}")
        print()

    show_breakdown = bool(os.getenv("_CHURN_EXPLAIN"))
    if not show_breakdown:
        print("  [ Run with --explain to see how this score was calculated ]")
        print()
        return

    print("  +" + "-" * 64 + "+")
    print("  | SCORE DERIVATION                                                |")
    print("  +" + "-" * 64 + "+")
    sub = d.get("sub_scores") or {}
    weights = d.get("weights") or {}
    wmap = {
        "historical_quality":   "historical_quality",
        "demand_score":         "demand_score",
        "recoverability_score": "recoverability",
        "paid_history_bonus":   "paid_history",
        "trajectory_factor":    "trajectory",
        "peer_recovery":        "peer_recovery",
        "recency_bonus":        "recency",
    }
    labels = {
        "historical_quality":   "Historical Quality",
        "demand_score":         "Demand Score",
        "recoverability_score": "Recoverability",
        "paid_history_bonus":   "Paid History Bonus",
        "trajectory_factor":    "Trajectory Factor",
        "peer_recovery":        "Peer Recovery",
        "recency_bonus":        "Recency Bonus",
    }

    base_sum = 0.0
    print(f"    {'Sub-score':<22} {'Value':>6}  x  {'Weight':>7}  =  {'pts':>6}")
    print(f"    {'-'*22} {'-'*6}     {'-'*7}     {'-'*6}")
    for key, label in labels.items():
        v = float(sub.get(key, 0) or 0)
        w = float(weights.get(wmap[key], 0) or 0)
        contrib = 100.0 * v * w
        base_sum += contrib
        print(f"    {label:<22} {v:>6.2f}  x  {w*100:>6.0f}%  =  {contrib:>6.2f}")
    print(f"    {'-'*22} {'-'*6}     {'-'*7}     {'-'*6}")
    print(f"    {'Weighted base sum':<22} {' ':>6}     {' ':>7}     {base_sum:>6.1f}")
    print()

    ib = d.get("interaction_bonus", 1.0)
    if ib and ib > 1.0:
        print(f"    Interaction bonus:        x{ib}  (demand & recoverability both strong)")
        print(f"      -> Bonused base:        {base_sum*ib:.1f}")
    else:
        print(f"    Interaction bonus:        x1.0  (no compounding)")

    print(f"    Pre-LLM score:            {d.get('pre_llm_score', 0)}")
    if d.get("llm_used"):
        ladj = d.get("llm_adjustment", 0)
        print(f"    LLM 2nd-opinion adj:      {ladj:+d}")
        if d.get("llm_justification"):
            print(f"      LLM: {d['llm_justification'][:160]}")
    else:
        print(f"    LLM 2nd opinion:          not run")
    print(f"    => FINAL WINBACK SCORE:   {ws}  ({pri})")
    print()

    if not d.get("cool_off_elapsed") and ws is not None and ws >= 65:
        print(f"    NOTE: score >= 65 but cool-off NOT elapsed "
              f"({d.get('cool_off_days_remaining',0)}d remaining) -> tier forced to MEDIUM.")
        print()

    if not d.get("demand_provided"):
        print(f"    NOTE: demand_index not provided -- its weight was redistributed to Recoverability.")
        print()

    print(f"    Tiers: >=65 + cool-off elapsed = HIGH | 40-64 or pre-cool-off = MEDIUM | <40 = LOW")
    print()


def _print_cross_platform_pretty(d: dict) -> None:
    """Tabular pretty output for cross-platform intelligence."""
    print(f"  Company:           {d.get('company_name_used','—')}")
    print(f"  IM product count:  {d.get('im_product_count', 0)}")
    print(f"  Own domain:        {d.get('own_website_domain') or '—'}")
    print(f"  Scrape status:     {d.get('scrape_status','—')}")
    print()
    print(f"  Platforms found:   {', '.join(d.get('platforms_found') or []) or '(none)'}")
    print()

    pdata = d.get("platform_data") or {}
    print(f"  ┌─{'─'*16}┬{'─'*9}┬{'─'*10}┬{'─'*9}┬{'─'*52}┐")
    print(f"  │ {'Platform':<16}│ {'Found':<7}│ {'Products':<8}│ {'Rating':<7}│ {'URL / note':<50}│")
    print(f"  ├─{'─'*16}┼{'─'*9}┼{'─'*10}┼{'─'*9}┼{'─'*52}┤")

    # IndiaMART row first (the seller's own platform — baseline)
    im_count = d.get("im_product_count", 0) or 0
    im_note  = "this seller's IndiaMART catalog"
    print(f"  │ {'IndiaMART':<16}│ {'yes':<7}│ {str(im_count):<8}│ {'—':<7}│ {im_note:<50}│")

    # Always list all 4 known competitor platforms (incl. own_website)
    known_platforms = ["justdial", "tradeindia", "own_website", "shopify"]
    display_names   = {
        "justdial":    "JustDial",
        "tradeindia":  "TradeIndia",
        "own_website": "Own Website",
        "shopify":     "Shopify",
    }
    for name in known_platforms:
        det = pdata.get(name) or {}
        found = "yes" if det.get("found") else "no"
        pc    = det.get("product_count", 0)
        rt    = det.get("rating", 0) or "—"
        url   = det.get("url") or det.get("domain") or ""
        if not det.get("found") and name == "own_website":
            url = "(email domain is generic — not checked)" if not url else url
        print(f"  │ {display_names[name]:<16}│ {found:<7}│ {str(pc):<8}│ {str(rt):<7}│ {url[:48]:<50}│")

    # Any platforms in pdata that weren't in our known list (future-proof)
    extras = [k for k in pdata if k not in known_platforms]
    for name in extras:
        det = pdata[name] or {}
        found = "yes" if det.get("found") else "no"
        pc    = det.get("product_count", 0)
        rt    = det.get("rating", 0) or "—"
        url   = (det.get("url") or "")[:48]
        print(f"  │ {name[:16]:<16}│ {found:<7}│ {str(pc):<8}│ {str(rt):<7}│ {url:<50}│")

    print(f"  └─{'─'*16}┴{'─'*9}┴{'─'*10}┴{'─'*9}┴{'─'*52}┘")
    print()

    gap = d.get("im_catalog_gap") or {}
    if gap:
        combo = gap.get("other_combination", "n/a")
        combo_label = {
            "single":       "single platform",
            "max_overlap":  "MAX (counts overlap)",
            "sum_distinct": "SUM (counts differ)",
            "none":         "no data",
        }.get(combo, combo)
        platform_counts = gap.get("platform_counts") or []
        print("  IM vs Other Platforms — Catalog Gap:")
        print(f"    IM products            : {gap.get('im_products', 0)}")
        print(f"    Other platforms total  : {gap.get('other_total_products', 0)}  "
              f"(combined via {combo_label})")
        if platform_counts:
            print(f"    Per-platform counts    : {platform_counts}")
        print(f"    Gap %                  : {gap.get('gap_pct', 0)}%")
        print(f"    Severity               : {gap.get('severity', '—')}")
        print()

    card = d.get("call_card") or {}
    if card:
        print("  Retention pitch:")
        if card.get("headline_en"):
            print(f"    EN: {card['headline_en']}")
        if card.get("headline_hi"):
            print(f"    HI: {card['headline_hi']}")
        if card.get("data_points"):
            print("    Data points:")
            for dp in card["data_points"]:
                print(f"      • {dp}")
        if card.get("suggested_action"):
            print(f"    🎯 Action: {card['suggested_action']}  ({card.get('effort_estimate','')})")
        if card.get("urgency"):
            print(f"    Urgency: {card['urgency']}")
    print()


# ── Subcommand: skills ────────────────────────────────────────────────────────

def cmd_skills(_args: list) -> None:
    from .skill_loader import SkillLoader
    loader = SkillLoader(_SKILLS_DIR)
    specs = loader.list_skills()
    if not specs:
        print("No skill MD files found in skills/")
        return
    print(f"\n{'Name':<30} {'Version':<8} {'Category':<16} Description")
    print("-" * 90)
    for s in specs:
        print(f"{s.name:<30} {s.version:<8} {s.category:<16} {s.description[:50]}")
    print(f"\n{len(specs)} skills available.")
    print(f"Run:  python -m churn_analysis skill <name> <GLID> [--pretty]")


# ── Subcommand: skill <name> <GLID> ──────────────────────────────────────────

def cmd_skill(args: list) -> None:
    if len(args) < 2:
        print("Usage: python -m churn_analysis skill <skill_name> <GLID> [--pretty|--explain|--json]")
        sys.exit(1)

    skill_name = args[0]
    glid = int(args[1])
    pretty  = "--pretty" in args
    compact = "--json" in args
    explain = "--explain" in args   # show full score derivation breakdown
    if explain:
        pretty = True               # explain implies pretty
        os.environ.setdefault("_CHURN_EXPLAIN", "1")

    from .skill_loader import SkillLoader, compute_derived
    from .skills.registry import registry

    loader = SkillLoader(_SKILLS_DIR)
    spec = loader.get(skill_name)
    if spec is None:
        print(f"No MD spec found for '{skill_name}'. Run 'python -m churn_analysis skills' to list available.")
        sys.exit(1)

    snap, api_resp = _fetch_snap(glid)
    derived = compute_derived(snap)
    flow = {
        "api_responses":    api_resp,
        "account_age_days": snap["context"].get("account_age_days", 0) or 0,
    }

    inputs = loader.build_inputs(spec, snap, derived, flow)
    t0 = time.monotonic()
    sr = registry.run(spec.python_class, inputs)
    sr.latency_ms = int((time.monotonic() - t0) * 1000)

    if pretty:
        _print_pretty(skill_name, glid, spec.version, sr)
    elif compact:
        print(json.dumps({"success": sr.success, "data": sr.data, "error": sr.error},
                         ensure_ascii=False, default=str))
    else:
        out = {
            "skill":      skill_name,
            "glid":       glid,
            "version":    spec.version,
            "success":    sr.success,
            "confidence": sr.confidence,
            "latency_ms": sr.latency_ms,
            "data":       sr.data,
            "error":      sr.error,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))


# ── Subcommand: pipeline ──────────────────────────────────────────────────────

def cmd_pipeline(args: list) -> None:
    glid      = None
    glids_file = None
    no_llm    = "--no-llm" in args
    out_dir   = None
    verbose   = "--quiet" not in args

    i = 0
    while i < len(args):
        if args[i] == "--glid" and i + 1 < len(args):
            glid = int(args[i + 1]); i += 2
        elif args[i] == "--glids-file" and i + 1 < len(args):
            glids_file = args[i + 1]; i += 2
        elif args[i] == "--out-dir" and i + 1 < len(args):
            out_dir = args[i + 1]; i += 2
        else:
            i += 1

    if glid is None and glids_file is None:
        print("Usage: python -m churn_analysis pipeline --glid <GLID>")
        print("       python -m churn_analysis pipeline --glids-file FILE [--no-llm]")
        sys.exit(1)

    from .pipeline_runner import PipelineRunner
    runner = PipelineRunner(_SKILLS_DIR)

    if glid is not None:
        result = runner.run_seller(glid, no_llm=no_llm, verbose=verbose)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        if not os.path.isfile(glids_file):
            print(f"File not found: {glids_file}")
            sys.exit(1)
        with open(glids_file, encoding="utf-8") as f:
            glids = [int(line.strip()) for line in f if line.strip().isdigit()]
        if not glids:
            print(f"No valid GLIDs found in {glids_file}")
            sys.exit(1)
        runner.run_batch(glids, no_llm=no_llm, out_dir=out_dir, verbose=verbose)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Commands:")
        print("  skills                                  — list all available skills")
        print("  skill <name> <GLID> [--pretty|--explain|--json]   — run one skill")
        print("  pipeline --glid <GLID> [--no-llm]       — full pipeline for one seller")
        print("  pipeline --glids-file FILE [--no-llm]   — batch pipeline")
        sys.exit(0)

    cmd = args[0]
    rest = args[1:]

    if cmd == "skills":
        cmd_skills(rest)
    elif cmd == "skill":
        cmd_skill(rest)
    elif cmd == "pipeline":
        cmd_pipeline(rest)
    else:
        print(f"Unknown command: {cmd}")
        print("Run: python -m churn_analysis  (no args) for help")
        sys.exit(1)
