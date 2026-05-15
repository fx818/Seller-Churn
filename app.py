"""
Seller Survival Intelligence — Flask Web UI
Usage: python app.py
Then open http://localhost:5000
"""
import json, os, sys, time
from flask import Flask, render_template, request, Response, jsonify

# Ensure Hackathon root is on path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__, template_folder="templates")

_SNAPSHOTS_AVAILABLE = os.path.exists(
    os.path.join("seller_survival", "data", "snapshots.parquet")
)
@app.route("/")
def index():
    return render_template(
        "scorer.html",
        snapshots_available=_SNAPSHOTS_AVAILABLE,
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        llm_base=os.getenv("LLM_BASE_URL", ""),
    )


@app.route("/score/stream")
def score_stream():
    """SSE endpoint — streams skill results as JSON events."""
    glid_raw = request.args.get("glid", "").strip()
    model    = request.args.get("model", os.getenv("LLM_MODEL", "gpt-4o-mini")).strip()
    skip_llm = request.args.get("skip_llm", "false").lower() == "true"

    if not glid_raw.isdigit():
        def bad():
            yield f"data: {json.dumps({'event': 'error', 'message': 'Invalid GLID — must be numeric'})}\n\n"
        return Response(bad(), mimetype="text/event-stream")

    glid = int(glid_raw)

    def generate():
        def emit(event: str, data: dict):
            payload = {"event": event, **data}
            yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"

        try:
            # Step 1: Fetch APIs
            yield from emit("progress", {"step": "fetch_apis", "label": "Fetching seller data from APIs...", "pct": 5})
            from seller_survival.slim_loader import fetch_for_glid
            api_responses = fetch_for_glid(glid, verbose=False)

            # Step 2: Extract signals
            yield from emit("progress", {"step": "extract", "label": "Extracting signals...", "pct": 20})
            from seller_survival.feature_schema import extract_snapshot

            snap = extract_snapshot(glid, "target", api_responses)
            ctx  = snap["context"]
            beh  = snap["behavioral"]

            # Build signals dict compatible with orchestrator
            ss_bl = beh["bl"]
            ss_lms = beh["lms"]
            ss_act = beh["activity"]
            monthly = ss_act.get("monthly_trend", [])

            signals = {
                "glid":           glid,
                "company":        ctx.get("company", ""),
                "city":           ctx.get("city", ""),
                "enterprise":     ctx.get("custtype", ""),
                "ctype":          ctx.get("custtype", ""),
                "rag":            ctx.get("rag_category", ""),
                "account_age":    ctx.get("account_age_days", 0),
                "paid_history":   ctx.get("paid_history", False),
                "mcats":          ctx.get("mcats", []),
                "cqs":            ss_act.get("cqs"),
                "enq_30d":        ss_bl.get("received_30d", 0),
                "replied_30d":    ss_bl.get("consumed_30d", 0),
                "active_days_30d": ss_lms.get("lms_active_days_30d", 0),
                "bl_velocity_pct": _compute_bl_velocity(monthly),
                "pns_success_pct": monthly[-1].get("pns_success_prcnt") if monthly else None,
                "hotleads_count": ss_bl.get("hotleads_count", 0),
                "event_count":    ss_act.get("event_count", 0),
                "total_bl_market": None,
                "total_paid_market": None,
                "monthly_enq":    [m.get("total_enq", 0) for m in monthly],
            }

            yield from emit("snapshot", {
                "step": "snapshot",
                "label": "Snapshot extracted",
                "pct": 30,
                "data": {
                    "context":    ctx,
                    "behavioral": {
                        "bl":       {k: v for k, v in ss_bl.items() if k != "hotleads_count"},
                        "lms":      ss_lms,
                        "activity": {k: v for k, v in ss_act.items() if k != "daily_activity"},
                    },
                },
            })

            # Step 3: Pre-analysis (lightweight — peer benchmarks from cache)
            yield from emit("progress", {"step": "pre_analysis", "label": "Loading peer benchmarks...", "pct": 35})
            peer_benchmarks = _load_peer_benchmarks()

            # Step 4: Run orchestrator with skill progress callbacks
            yield from emit("progress", {"step": "orchestrator", "label": "Running skill chain...", "pct": 40})

            pct_map = {
                "conversion_point":  42,
                "churn_scoring":     48,
                "shap_rca":          54,
                "peer_benchmark":    59,
                "demand_index":      63,
                "onboarding_health": 67,
                "llm_cohort_scorer": 73,
                "whatsapp_message":  77,
                "pre_call_brief":    81,
                "cross_platform":    85,
                "script_generation": 88,
                "gifted_lead":       90,
                "winback_priority":  92,
                "bl_upgrade":        94,
                "complete":          100,
            }
            label_map = {
                "conversion_point":  "Detecting journey pattern...",
                "churn_scoring":     "Computing churn score...",
                "shap_rca":          "Identifying root cause...",
                "peer_benchmark":    "Benchmarking against peers...",
                "demand_index":      "Assessing market demand...",
                "onboarding_health": "Running onboarding checks...",
                "llm_cohort_scorer": "Running AI cohort scoring (LLM)...",
                "whatsapp_message":  "Generating WhatsApp message...",
                "pre_call_brief":    "Building pre-call brief...",
                "cross_platform":    "Scanning competitor platforms...",
                "script_generation": "Generating call script...",
                "gifted_lead":       "Qualifying gifted leads...",
                "winback_priority":  "Computing winback priority...",
                "bl_upgrade":        "Checking BL upgrade opportunity...",
                "complete":          "Finalizing action plan...",
            }

            _buffer = []

            def progress_cb(step: str, data: dict):
                status = data.get("status", "")
                if status in ("running", "skipped", "done"):
                    pct   = pct_map.get(step, 50)
                    label = label_map.get(step, step)
                    if status == "skipped":
                        label = f"{label} (skipped)"
                    elif status == "done":
                        label = f"{label.replace('...', '')} ✓"
                    _buffer.append(json.dumps({
                        "event": "skill_progress",
                        "step":  step,
                        "label": label,
                        "pct":   pct,
                        "status": status,
                        "data":  {k: v for k, v in data.items() if k != "status"},
                    }, ensure_ascii=False, default=str))

            from churn_analysis.agent.orchestrator import run_seller
            action_plan = run_seller(
                glid       = glid,
                signals    = signals,
                api_responses = api_responses,
                peer_benchmarks = peer_benchmarks,
                model      = None if skip_llm else model,
                progress_cb = progress_cb,
            )

            for msg in _buffer:
                yield f"data: {msg}\n\n"

            yield from emit("result", {
                "step":  "result",
                "label": "Complete",
                "pct":   100,
                "data":  action_plan,
            })

        except Exception as exc:
            import traceback
            yield from emit("error", {"message": str(exc), "trace": traceback.format_exc()})

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/score", methods=["POST"])
def score_json():
    """Non-streaming JSON endpoint for programmatic use."""
    body = request.get_json(force=True) or {}
    glid_raw = str(body.get("glid", "")).strip()
    model    = body.get("model", os.getenv("LLM_MODEL", "gpt-4o-mini"))

    if not glid_raw.isdigit():
        return jsonify({"error": "Invalid GLID"}), 400

    glid = int(glid_raw)
    try:
        from seller_survival.slim_loader import fetch_for_glid
        from seller_survival.feature_schema import extract_snapshot
        from churn_analysis.agent.orchestrator import run_seller

        api_responses   = fetch_for_glid(glid, verbose=False)
        snap            = extract_snapshot(glid, "target", api_responses)
        ctx, beh        = snap["context"], snap["behavioral"]
        monthly         = beh["activity"].get("monthly_trend", [])

        signals = {
            "glid": glid,
            "company":        ctx.get("company", ""),
            "city":           ctx.get("city", ""),
            "enterprise":     ctx.get("custtype", ""),
            "ctype":          ctx.get("custtype", ""),
            "rag":            ctx.get("rag_category", ""),
            "account_age":    ctx.get("account_age_days", 0),
            "paid_history":   ctx.get("paid_history", False),
            "mcats":          ctx.get("mcats", []),
            "cqs":            beh["activity"].get("cqs"),
            "enq_30d":        beh["bl"].get("received_30d", 0),
            "replied_30d":    beh["bl"].get("consumed_30d", 0),
            "active_days_30d": beh["lms"].get("lms_active_days_30d", 0),
            "bl_velocity_pct": _compute_bl_velocity(monthly),
            "pns_success_pct": monthly[-1].get("pns_success_prcnt") if monthly else None,
            "hotleads_count": beh["bl"].get("hotleads_count", 0),
            "event_count":    beh["activity"].get("event_count", 0),
            "monthly_enq":    [m.get("total_enq", 0) for m in monthly],
        }

        peer_benchmarks = _load_peer_benchmarks()
        plan = run_seller(glid, signals, api_responses, peer_benchmarks, model=model)
        return jsonify(plan)
    except Exception as exc:
        import traceback
        return jsonify({"error": str(exc), "trace": traceback.format_exc()}), 500


@app.route("/runs")
def list_runs():
    """List all pipeline runs with their impact reports."""
    runs_dir = os.path.join(os.path.dirname(__file__), "runs")
    if not os.path.exists(runs_dir):
        return jsonify({"runs": []})
    runs = []
    for name in sorted(os.listdir(runs_dir), reverse=True):
        run_path = os.path.join(runs_dir, name)
        if not os.path.isdir(run_path):
            continue
        master = os.path.join(run_path, "action_plans", "master_action_plan.json")
        summary = {}
        if os.path.exists(master):
            with open(master, encoding="utf-8") as f:
                summary = json.load(f).get("summary", {})
        runs.append({
            "run_id":      name,
            "impact_url":  f"/impact/{name}",
            "summary":     summary,
        })
    return jsonify({"runs": runs})


@app.route("/impact/<run_id>")
def serve_impact(run_id: str):
    """Serve impact report HTML for a run."""
    report = os.path.join("runs", run_id, "impact_report.html")
    if not os.path.exists(report):
        return f"Impact report for {run_id} not found. Run the pipeline first.", 404
    with open(report, encoding="utf-8") as f:
        return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/run/batch", methods=["POST"])
def run_batch():
    """Trigger a batch pipeline run for a list of GLIDs."""
    import threading
    body   = request.get_json(force=True) or {}
    glids  = body.get("glids", [])
    model  = body.get("model", os.getenv("LLM_MODEL", "gpt-4o-mini"))
    if not glids:
        return jsonify({"error": "No GLIDs provided"}), 400
    glids = [int(g) for g in glids if str(g).isdigit()]

    def _run():
        from run_pipeline import run as run_pipeline
        run_pipeline(glids, model=model, verbose=True)

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started", "glids": len(glids), "model": model})


def _compute_bl_velocity(monthly_trend: list) -> float | None:
    if len(monthly_trend) < 2:
        return None
    last = monthly_trend[-1].get("total_enq", 0) or 0
    prev = monthly_trend[-2].get("total_enq", 0) or 0
    if prev == 0:
        return None
    return round((last - prev) / prev * 100, 1)


def _load_peer_benchmarks() -> dict:
    paths = [
        os.path.join("churn_analysis", "data", "peer_benchmarks.json"),
        os.path.join("peer_benchmarks.json"),
    ]
    for p in paths:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    return {"groups": {}}


if __name__ == "__main__":
    print("Starting Seller Survival Intelligence UI at http://localhost:5000")
    status = "Available" if _SNAPSHOTS_AVAILABLE else "Not built (run: python -m seller_survival build)"
    print(f"Reference library: {status}")
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
