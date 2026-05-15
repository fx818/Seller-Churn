"""
CLI entry point.
  python -m seller_survival build                   # build reference library
  python -m seller_survival score <GLID> [--model]  # score a single seller
  python -m seller_survival score <GLID> --no-llm   # rule-based only (skip LLM)
"""
import json, os, sys

_SNAPSHOTS_PATH = os.path.join(os.path.dirname(__file__), "data", "snapshots.parquet")


def cmd_build(args):
    from .build_reference_library import build_library
    path = build_library()
    print(f"\nDone -> {path}")


def cmd_score(args):
    if len(args) < 1:
        print("Usage: python -m seller_survival score <GLID> [--model gpt-4o-mini] [--no-llm]")
        sys.exit(1)

    glid = int(args[0])
    model  = None
    no_llm = False
    i = 1
    while i < len(args):
        if args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]; i += 2
        elif args[i] == "--no-llm":
            no_llm = True; i += 1
        else:
            i += 1

    print(f"\n[1/3] Fetching APIs for GLID {glid}...")
    from .slim_loader import fetch_for_glid
    responses = fetch_for_glid(glid, verbose=True)

    print("\n[2/3] Extracting snapshot...")
    from .feature_schema import extract_snapshot
    snap = extract_snapshot(glid, "target", responses)
    print(f"  city={snap['context']['city']}  state={snap['context']['state']}")
    print(f"  turnover={snap['context']['turnover']}  custtype={snap['context']['custtype']}")
    print(f"  mcats={snap['context']['mcats'][:3]}{'...' if len(snap['context']['mcats']) > 3 else ''}")

    card = {
        "glid":     glid,
        "snapshot": snap,
    }

    llm_available = os.path.exists(_SNAPSHOTS_PATH)
    account_age   = snap["context"].get("account_age_days", 0) or 0

    if no_llm or not llm_available or account_age <= 90:
        if not llm_available:
            print("\n[3/3] snapshots.parquet not found — skipping LLM cohort scoring.")
            print("      Run: python -m seller_survival build")
        elif account_age <= 90:
            print(f"\n[3/3] account_age_days={account_age} ≤ 90 — skipping LLM (insufficient history).")
        else:
            print("\n[3/3] LLM scoring disabled via --no-llm flag.")

        card["llm_cohort"] = None
    else:
        print("\n[3/3] Loading reference library and scoring...")
        from .build_reference_library import load_library
        from .cohort_filter import filter_cohort, filter_stats
        from .llm_scorer import score as llm_score

        library = load_library()
        target_ctx = snap["context"]

        stats = filter_stats(target_ctx, library)
        print(f"  Cohort filter: {stats['n_filtered']} sellers matched (tier={stats['tier']})")

        churned_ex, retained_ex, mean_score, tier = filter_cohort(target_ctx, library, k=10)
        print(f"  Showing LLM: {len(churned_ex)} churned, {len(retained_ex)} retained examples")

        result = llm_score(
            snap,
            churned_ex,
            retained_ex,
            mean_match_score=mean_score,
            n_filtered=stats["n_filtered"],
            model=model,
        )

        card["llm_cohort"] = {
            "bands":            result["bands"],
            "risk_level":       result["risk_level"],
            "confidence_score": result["confidence_score"],
            "cohort_match": {
                "n_filtered":  stats["n_filtered"],
                "tier":        tier,
                "shown_to_llm": len(churned_ex) + len(retained_ex),
            },
            "llm_output": result["llm_output"],
        }

        print(f"\n  Risk: {result['risk_level']}  Confidence: {result['confidence_score']}")
        print(f"  Bands: BL={result['bands']['bl']} LMS={result['bands']['lms']} Activity={result['bands']['activity']}")

    print("\n" + "═" * 60)
    out = json.dumps(card, indent=2, ensure_ascii=False, default=str)
    print(out)
    return card


def main():
    args = sys.argv[1:]
    if not args:
        print("Commands: build | score <GLID> [--model MODEL] [--no-llm]")
        sys.exit(1)

    cmd = args[0]
    rest = args[1:]

    if cmd == "build":
        cmd_build(rest)
    elif cmd == "score":
        cmd_score(rest)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
