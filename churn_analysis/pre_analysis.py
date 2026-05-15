"""
Pre-Analysis Pipeline — runs BEFORE the orchestrator.
Usage: python -m churn_analysis.pre_analysis <data_dir> [--glids glids.txt]

Outputs:
  <data_dir>/coverage_report.json
  <data_dir>/peer_benchmarks.json
  <data_dir>/baseline_distribution.json
"""
import json, os, sys, csv
from collections import defaultdict

_SNAPSHOTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "seller_survival", "data", "snapshots.parquet"
)

EXPECTED_APIS = [
    "scorecard_summary", "scorecard_12m", "product_details",
    "composite", "metrics", "activity", "hotleads", "blni",
]


# ── 1. Reference library readiness ────────────────────────────────────────────
def check_library() -> dict:
    exists = os.path.exists(_SNAPSHOTS_PATH)
    size_mb = os.path.getsize(_SNAPSHOTS_PATH) / 1e6 if exists else 0
    return {
        "available": exists,
        "path": _SNAPSHOTS_PATH,
        "size_mb": round(size_mb, 2),
        "message": (
            f"Reference library ready ({size_mb:.1f} MB)" if exists
            else "WARNING: snapshots.parquet missing. Run: python -m seller_survival build"
        ),
    }


# ── 2. API coverage check per GLID ────────────────────────────────────────────
def check_coverage(data_dir: str) -> dict:
    glid_dirs = [
        d for d in os.listdir(data_dir)
        if os.path.isdir(os.path.join(data_dir, d)) and d.isdigit()
    ]

    per_glid = {}
    api_totals = defaultdict(lambda: {"ok": 0, "fail": 0, "missing": 0})
    coverage_scores = []

    for glid in glid_dirs:
        glid_dir = os.path.join(data_dir, glid)
        api_status = {}
        ok_count = 0
        for api in EXPECTED_APIS:
            path = os.path.join(glid_dir, f"{api}.json")
            if not os.path.exists(path):
                api_status[api] = {"status": None, "has_data": False, "error": "file_missing"}
                api_totals[api]["missing"] += 1
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                status = data.get("status")
                has_data = status == 200 and data.get("data") is not None
                api_status[api] = {"status": status, "has_data": has_data, "error": data.get("error")}
                if has_data:
                    ok_count += 1
                    api_totals[api]["ok"] += 1
                else:
                    api_totals[api]["fail"] += 1
            except Exception as e:
                api_status[api] = {"status": None, "has_data": False, "error": str(e)}
                api_totals[api]["fail"] += 1

        cov_score = ok_count / len(EXPECTED_APIS)
        coverage_scores.append(cov_score)
        per_glid[glid] = {
            "ok_count": ok_count,
            "total": len(EXPECTED_APIS),
            "coverage": round(cov_score, 2),
            "tier": ("full" if ok_count >= 7 else ("partial" if ok_count >= 4 else "incomplete")),
            "apis": api_status,
        }

    avg_cov = round(sum(coverage_scores) / max(len(coverage_scores), 1), 2)
    excluded = [g for g, d in per_glid.items() if d["tier"] == "incomplete"]

    return {
        "total_glids":      len(glid_dirs),
        "average_coverage": avg_cov,
        "excluded_count":   len(excluded),
        "excluded_glids":   excluded,
        "api_success_rates": {
            api: round(v["ok"] / max(v["ok"] + v["fail"] + v["missing"], 1), 2)
            for api, v in api_totals.items()
        },
        "per_glid": per_glid,
    }


# ── 3. Peer benchmark computation ────────────────────────────────────────────
def compute_peer_benchmarks(data_dir: str) -> dict:
    """Compute median enq/active_days/CQS per enterprise_type+ctype group."""
    import statistics

    groups: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))

    glid_dirs = [
        d for d in os.listdir(data_dir)
        if os.path.isdir(os.path.join(data_dir, d)) and d.isdigit()
    ]

    def _safe_parse(val):
        if isinstance(val, str):
            try:
                import json as _json
                return _safe_parse(_json.loads(val))
            except Exception:
                pass
        return val

    for glid in glid_dirs:
        glid_dir = os.path.join(data_dir, glid)

        # Load scorecard_summary
        ss_path = os.path.join(glid_dir, "scorecard_summary.json")
        comp_path = os.path.join(glid_dir, "composite.json")

        enterprise = ctype = ""
        enq_30 = active_30 = cqs = pns_pct = None

        try:
            with open(ss_path, encoding="utf-8") as f:
                ss = json.load(f)
            if ss.get("status") == 200:
                inner = _safe_parse(ss["data"].get("response", "{}"))
                if isinstance(inner, dict):
                    summ = (inner.get("summary") or [{}])[0]
                    tot_enq = _safe_parse(summ.get("tot_enq", "{}"))
                    lms_days = _safe_parse(summ.get("lms_active_days", "{}"))
                    enq_30 = (tot_enq.get("30d") or 0) if isinstance(tot_enq, dict) else 0
                    active_30 = (lms_days.get("30d") or 0) if isinstance(lms_days, dict) else 0
                    enterprise = summ.get("enterprise_type", "")
        except Exception:
            pass

        try:
            with open(comp_path, encoding="utf-8") as f:
                cp = json.load(f)
            if cp.get("status") == 200:
                prof = (cp.get("data") or {}).get("profile") or {}
                eng  = (cp.get("data") or {}).get("engagement") or {}
                ctype = prof.get("customer_type", "")
                cqs   = eng.get("cqs")
        except Exception:
            pass

        if enterprise and ctype:
            key = f"{enterprise}|{ctype}"
            if enq_30 is not None:
                groups[key]["enq_30d"].append(enq_30)
            if active_30 is not None:
                groups[key]["active_days_30d"].append(active_30)
            if cqs is not None:
                groups[key]["cqs"].append(cqs)

    result = {"groups": {}}
    for key, vals in groups.items():
        enqs = sorted(vals.get("enq_30d", []))
        n = len(enqs)
        if n == 0:
            continue
        result["groups"][key] = {
            "n":                 n,
            "median_enq_30d":    statistics.median(enqs) if enqs else 0,
            "p25_enq_30d":       enqs[max(0, n // 4 - 1)] if enqs else 0,
            "p75_enq_30d":       enqs[min(n - 1, 3 * n // 4)] if enqs else 0,
            "median_active_days": statistics.median(vals["active_days_30d"]) if vals.get("active_days_30d") else 0,
            "median_cqs":        statistics.median(vals["cqs"]) if vals.get("cqs") else 0,
            "median_pns_rate":   0,
        }
    return result


# ── 4. Baseline distribution ──────────────────────────────────────────────────
def compute_baseline(data_dir: str) -> dict:
    from collections import Counter
    rag_dist = Counter()
    enterprise_dist = Counter()
    city_dist = Counter()

    glid_dirs = [
        d for d in os.listdir(data_dir)
        if os.path.isdir(os.path.join(data_dir, d)) and d.isdigit()
    ]

    def _sp(val):
        if isinstance(val, str):
            try:
                return _sp(json.loads(val))
            except Exception:
                pass
        return val

    for glid in glid_dirs:
        glid_dir = os.path.join(data_dir, glid)

        try:
            with open(os.path.join(glid_dir, "composite.json"), encoding="utf-8") as f:
                cp = json.load(f)
            if cp.get("status") == 200:
                prof = (cp.get("data") or {}).get("profile") or {}
                rag_dist[prof.get("rag_category", "Unknown")] += 1
                city_dist[prof.get("city", "Unknown")] += 1
        except Exception:
            pass

        try:
            with open(os.path.join(glid_dir, "scorecard_summary.json"), encoding="utf-8") as f:
                ss = json.load(f)
            if ss.get("status") == 200:
                inner = _sp(ss["data"].get("response", "{}"))
                if isinstance(inner, dict):
                    summ = (inner.get("summary") or [{}])[0]
                    enterprise_dist[summ.get("enterprise_type", "Unknown")] += 1
        except Exception:
            pass

    return {
        "rag_distribution":        dict(rag_dist.most_common()),
        "enterprise_distribution": dict(enterprise_dist.most_common()),
        "city_distribution":       dict(city_dist.most_common(20)),
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def run_pre_analysis(data_dir: str, output_dir: str | None = None) -> dict:
    output_dir = output_dir or data_dir
    os.makedirs(output_dir, exist_ok=True)

    print("[pre_analysis] Checking reference library...", flush=True)
    lib_check = check_library()
    print(f"  {lib_check['message']}", flush=True)

    print("[pre_analysis] Checking API coverage...", flush=True)
    coverage = check_coverage(data_dir)
    print(f"  {coverage['total_glids']} GLIDs, avg coverage {coverage['average_coverage']*100:.0f}%, "
          f"{coverage['excluded_count']} excluded", flush=True)

    print("[pre_analysis] Computing peer benchmarks...", flush=True)
    benchmarks = compute_peer_benchmarks(data_dir)
    print(f"  {len(benchmarks['groups'])} peer groups computed", flush=True)

    print("[pre_analysis] Computing baseline distribution...", flush=True)
    baseline = compute_baseline(data_dir)

    # Write outputs
    with open(os.path.join(output_dir, "coverage_report.json"), "w", encoding="utf-8") as f:
        json.dump({**coverage, "library": lib_check}, f, indent=2, default=str)
    with open(os.path.join(output_dir, "peer_benchmarks.json"), "w", encoding="utf-8") as f:
        json.dump(benchmarks, f, indent=2, default=str)
    with open(os.path.join(output_dir, "baseline_distribution.json"), "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, default=str)

    print("[pre_analysis] Done. Outputs written to:", output_dir, flush=True)
    return {
        "library":    lib_check,
        "coverage":   coverage,
        "benchmarks": benchmarks,
        "baseline":   baseline,
    }


if __name__ == "__main__":
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    run_pre_analysis(data_dir)
