"""
Full seller survival pipeline — runs all phases end-to-end for a list of GLIDs.

Usage:
    python run_pipeline.py [glids_file]            # file with one GLID per line
    python run_pipeline.py 488587 27257635 ...     # inline GLIDs
    python run_pipeline.py                          # reads glids.txt by default

Outputs land in: runs/run_YYYYMMDD_HHMMSS/
"""
import os, sys, json, time
from datetime import datetime

# Ensure Hackathon root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()


def _make_run_dir() -> str:
    run_id = "run_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join("runs", run_id)
    for sub in ("analysis", "action_plans", "analysis/skill_outputs"):
        os.makedirs(os.path.join(run_dir, sub), exist_ok=True)
    return run_dir, run_id


def _load_glids(args: list[str]) -> list[int]:
    if not args:
        path = "glids.txt"
        if not os.path.exists(path):
            print(f"No GLIDs provided and {path} not found.")
            sys.exit(1)
        with open(path) as f:
            return [int(l.strip()) for l in f if l.strip().isdigit()]
    # Single file argument
    if len(args) == 1 and os.path.exists(args[0]):
        with open(args[0]) as f:
            return [int(l.strip()) for l in f if l.strip().isdigit()]
    # Inline GLIDs
    return [int(a) for a in args if a.isdigit()]


def _fetch_signals(glid: int) -> tuple[dict, dict]:
    """Fetch API responses + extract signals dict for one GLID."""
    from seller_survival.slim_loader import fetch_for_glid
    from seller_survival.feature_schema import extract_snapshot

    api_responses = fetch_for_glid(glid, verbose=False)
    snap = extract_snapshot(glid, "target", api_responses)
    ctx, beh = snap["context"], snap["behavioral"]
    monthly = beh["activity"].get("monthly_trend", [])

    def bl_vel(m):
        if len(m) < 2:
            return None
        l = (m[-1].get("total_enq", 0) or 0)
        p = (m[-2].get("total_enq", 0) or 0)
        return round((l - p) / p * 100, 1) if p else None

    signals = {
        "glid":            glid,
        "company":         ctx.get("company", ""),
        "city":            ctx.get("city", ""),
        "enterprise":      ctx.get("custtype", ""),
        "ctype":           ctx.get("custtype", ""),
        "rag":             ctx.get("rag_category", ""),
        "account_age":     ctx.get("account_age_days", 0),
        "account_age_days": ctx.get("account_age_days", 0),
        "paid_history":    ctx.get("paid_history", False),
        "mcats":           ctx.get("mcats", []),
        "cqs":             beh["activity"].get("cqs"),
        "enq_30d":         beh["bl"].get("received_30d", 0),
        "replied_30d":     beh["bl"].get("consumed_30d", 0),
        "active_days_30d": beh["lms"].get("lms_active_days_30d", 0),
        "bl_velocity_pct": bl_vel(monthly),
        "pns_success_pct": monthly[-1].get("pns_success_prcnt") if monthly else None,
        "hotleads_count":  beh["bl"].get("hotleads_count", 0),
        "event_count":     beh["activity"].get("event_count", 0),
        "monthly_enq":     [m.get("total_enq", 0) for m in monthly],
    }
    return signals, api_responses


def _load_peer_benchmarks() -> dict:
    for p in ["churn_analysis/data/peer_benchmarks.json", "peer_benchmarks.json"]:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    return {"groups": {}}


def run(glids: list[int], model: str | None = None, verbose: bool = True) -> str:
    """Run the full pipeline. Returns run_dir path."""
    run_dir, run_id = _make_run_dir()
    peer_benchmarks = _load_peer_benchmarks()

    if verbose:
        print(f"\n{'='*60}")
        print(f"  Seller Survival Pipeline  —  {run_id}")
        print(f"  GLIDs: {len(glids)}   Model: {model or os.getenv('LLM_MODEL','gpt-4o-mini')}")
        print(f"  Output: {run_dir}")
        print(f"{'='*60}\n")

    # ── Phase 0: Fetch signals for all GLIDs ─────────────────────
    if verbose:
        print("[Phase 0] Fetching signals...")
    sellers = []
    api_map = {}
    for i, glid in enumerate(glids, 1):
        try:
            signals, api_resp = _fetch_signals(glid)
            sellers.append(signals)
            api_map[str(glid)] = api_resp
            if verbose:
                print(f"  [{i}/{len(glids)}] GLID {glid} — {signals.get('company','?')[:30]}")
        except Exception as e:
            print(f"  [{i}/{len(glids)}] GLID {glid} — ERROR: {e}")

    if not sellers:
        print("No sellers fetched. Aborting.")
        return run_dir

    # ── Phase 1: Onboarding Health ────────────────────────────────
    if verbose:
        print(f"\n[Phase 1] Onboarding health ({sum(1 for s in sellers if (s.get('account_age_days') or 0) <= 90)} new sellers)...")
    from churn_analysis.phases.phase1_onboarding import run_phase1
    phase1_out = run_phase1(run_dir, sellers, peer_benchmarks)
    if verbose:
        print(f"  Red: {phase1_out.get('red_count',0)}  Amber: {phase1_out.get('amber_count',0)}  Green: {phase1_out.get('green_count',0)}")

    # ── Phase 2: Dual-Track Predictor ─────────────────────────────
    if verbose:
        print(f"\n[Phase 2] Churn prediction ({len(sellers)} sellers)...")
    from churn_analysis.phases.phase2_predictor import run_phase2
    phase2_out = run_phase2(run_dir, sellers, peer_benchmarks, model=model)
    phase2_results = phase2_out.get("_phase2_results", {})
    if verbose:
        print(f"  Red: {phase2_out.get('red',0)}  Amber: {phase2_out.get('amber',0)}  Green: {phase2_out.get('green',0)}  LLM scored: {phase2_out.get('llm_scored',0)}")

    # ── Phase 3: Retention Tracks ──────────────────────────────────
    if verbose:
        print(f"\n[Phase 3] Retention actions...")
    from churn_analysis.phases.phase3_retention import run_phase3
    from churn_analysis.phases.phase3_track_a import run_track_a
    phase3_out   = run_phase3(run_dir, sellers, phase2_out.get("tiers", {}), phase2_results, peer_benchmarks, model=model)
    track_a_out  = run_track_a(run_dir, sellers, phase2_results, peer_benchmarks)
    if verbose:
        print(f"  Actions generated: {phase3_out.get('total_action_plans',0)}  Peer cards: {track_a_out.get('total_sellers',0)}")

    # ── Phase 4: BL Upgrade ───────────────────────────────────────
    if verbose:
        print(f"\n[Phase 4] BL upgrade check...")
    from churn_analysis.phases.phase4_bl_upgrade import run_phase4
    phase4_out = run_phase4(run_dir, sellers, phase2_results)
    if verbose:
        print(f"  Eligible: {phase4_out.get('total_eligible',0)}  Mode A: {phase4_out.get('mode_a_count',0)}  Mode B: {phase4_out.get('mode_b_count',0)}")

    # ── Phase 5: Renewal Boost ────────────────────────────────────
    if verbose:
        print(f"\n[Phase 5] Renewal window boost...")
    from churn_analysis.phases.phase5_renewal import run_phase5
    phase5_out = run_phase5(run_dir, sellers, phase2_results)
    if verbose:
        print(f"  Renewal actions: {phase5_out.get('total_eligible',0)}")

    # ── Phase 6: Cross-Platform Intelligence ─────────────────────
    if verbose:
        print(f"\n[Phase 6] Cross-platform product intelligence...")
    from churn_analysis.phases.phase6_cross_platform import run_phase6
    phase6_out = run_phase6(run_dir, sellers, phase2_results, api_map)
    if verbose:
        print(f"  Scanned: {phase6_out.get('total_scanned',0)}  "
              f"Found: {phase6_out.get('platforms_found_count',0)}  "
              f"High gap: {phase6_out.get('high_gap_count',0)}")

    # ── Cross-cutting: Delivery Cascade ───────────────────────────
    if verbose:
        print(f"\n[Cross] Building delivery cascade...")
    from churn_analysis.cross_cutting.delivery_cascade import build_cascade_plan, write_cascade_queue
    cascade_plans = {}
    for s in sellers:
        glid_str = str(s["glid"])
        tier_info = phase2_out.get("tiers", {}).get(glid_str, {})
        tier      = tier_info.get("final_tier", "Green")
        wa        = phase3_out.get("whatsapp_messages", {}).get(glid_str, {})
        cascade_plans[glid_str] = build_cascade_plan(glid_str, tier, {
            "company":     s.get("company", ""),
            "city":        s.get("city", ""),
            "rca":         tier_info.get("rca_category", "UNKNOWN"),
            "churn_score": tier_info.get("churn_score", 0),
            "whatsapp_message": wa,
        })
    write_cascade_queue(run_dir, cascade_plans)

    # ── Cross-cutting: Aggregate ──────────────────────────────────
    if verbose:
        print(f"\n[Cross] Aggregating master action plan...")
    from churn_analysis.cross_cutting.action_plan_aggregator import aggregate
    master = aggregate(run_dir, run_id)
    if verbose:
        s = master.get("summary", {})
        print(f"  Total: {s.get('total_sellers',0)}  Red: {s.get('red',0)}  ARR at risk: Rs {s.get('estimated_arr_at_risk',0):,}")

    # ── Cross-cutting: Impact Dashboard ───────────────────────────
    if verbose:
        print(f"\n[Cross] Building impact report...")
    from churn_analysis.cross_cutting.impact_dashboard import build_impact_report
    report_path = build_impact_report(run_dir, master)
    if verbose:
        print(f"  Report: {report_path}")

    # ── Summary ───────────────────────────────────────────────────
    if verbose:
        print(f"\n{'='*60}")
        print(f"  Pipeline complete!")
        print(f"  Run dir:       {run_dir}/")
        print(f"  Impact report: {report_path}")
        print(f"  Action plans:  {run_dir}/action_plans/master_action_plan.json")
        print(f"{'='*60}\n")

    return run_dir


if __name__ == "__main__":
    glids = _load_glids(sys.argv[1:])
    if not glids:
        print("Usage: python run_pipeline.py [glids_file | GLID ...]")
        sys.exit(1)
    model = os.getenv("LLM_MODEL")
    run(glids, model=model)
