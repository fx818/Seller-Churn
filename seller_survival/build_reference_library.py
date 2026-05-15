"""
Builds snapshots.parquet from cohort.csv.
Run once: python -m seller_survival build
"""
import csv, json, os, time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from .slim_loader import fetch_for_glid, MAX_WORKERS
from .feature_schema import extract_snapshot
from .mcat_embeddings import embed_batch

_COHORT_CSV     = os.path.join(os.path.dirname(__file__), "..", "cohort.csv")
_SNAPSHOTS_PATH = os.path.join(os.path.dirname(__file__), "data", "snapshots.parquet")


def load_cohort() -> list[dict]:
    rows = []
    with open(_COHORT_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({"glid": int(row["glid"]), "label": row["label"]})
    return rows


def _fetch_and_extract(glid: int, label: str) -> dict | None:
    try:
        responses = fetch_for_glid(glid, verbose=True)
        snap = extract_snapshot(glid, label, responses)
        return snap
    except Exception as e:
        print(f"  [GLID {glid}] extract error: {e}", flush=True)
        return None


def build_library(force: bool = False) -> str:
    """Fetch + extract 292 cohort GLIDs, write snapshots.parquet. Returns path."""
    cohort = load_cohort()
    print(f"Cohort: {len(cohort)} sellers", flush=True)

    snapshots = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {
            ex.submit(_fetch_and_extract, row["glid"], row["label"]): row
            for row in cohort
        }
        done = 0
        for fut in as_completed(futures):
            done += 1
            snap = fut.result()
            if snap is not None:
                snapshots.append(snap)
            if done % 20 == 0:
                print(f"  {done}/{len(cohort)} done ({time.time()-t0:.0f}s)", flush=True)

    print(f"\nExtracted {len(snapshots)}/{len(cohort)} snapshots", flush=True)

    # Collect all mcats for batch embedding
    all_mcats: set[str] = set()
    for s in snapshots:
        all_mcats.update(s["context"].get("mcats", []))
    if all_mcats:
        print(f"Embedding {len(all_mcats)} unique mcats...", flush=True)
        embed_batch(list(all_mcats))
        print("Embeddings cached.", flush=True)

    # Flatten to rows for parquet
    rows = []
    for s in snapshots:
        ctx = s["context"]
        beh = s["behavioral"]
        bl  = beh["bl"]
        lms = beh["lms"]
        act = beh["activity"]
        rows.append({
            "glid":    s["glid"],
            "label":   s["label"],
            "company": ctx.get("company", ""),
            "turnover": ctx.get("turnover", ""),
            "city":    ctx.get("city", ""),
            "state":   ctx.get("state", ""),
            "mcats":   json.dumps(ctx.get("mcats", [])),
            "custtype": ctx.get("custtype", ""),
            "account_age_days": ctx.get("account_age_days", 0),
            "rag_category":     ctx.get("rag_category", ""),
            "bl_received_90d":  bl.get("received_90d", 0),
            "bl_consumed_90d":  bl.get("consumed_90d", 0),
            "consumption_rate": bl.get("consumption_rate"),
            "reply_rate":       bl.get("reply_rate"),
            "blni_count_1yr":   bl.get("blni_count_1yr", 0),
            "weekly_bl_active": json.dumps(bl.get("weekly_bl_active", [])),
            "call_attempts_90d": lms.get("call_attempts_90d", 0),
            "call_answered_90d": lms.get("call_answered_90d", 0),
            "pickup_ratio_90d":  lms.get("call_pickup_ratio_90d"),
            "calls_1min_plus_90d": lms.get("calls_1min_plus_90d", 0),
            "lms_active_days_90d": lms.get("lms_active_days_90d", 0),
            "last_succ_call_dt":   lms.get("last_succ_call_dt"),
            "activity_30d":    act.get("activity_30d", 0),
            "event_count":     act.get("event_count", 0),
            "weekly_activity": json.dumps(act.get("weekly_activity", [])),
            "monthly_trend":   json.dumps(act.get("monthly_trend", [])),
            # Store full snapshot JSON for LLM prompt
            "snapshot_json":   json.dumps(s, ensure_ascii=False, default=str),
        })

    os.makedirs(os.path.dirname(_SNAPSHOTS_PATH), exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_parquet(_SNAPSHOTS_PATH, index=False)
    retained = (df["label"] == "retained").sum()
    churned  = (df["label"] == "churned").sum()
    print(f"\nWrote {_SNAPSHOTS_PATH}", flush=True)
    print(f"  retained={retained}, churned={churned}, total={len(df)}", flush=True)
    return _SNAPSHOTS_PATH


def load_library() -> pd.DataFrame:
    if not os.path.exists(_SNAPSHOTS_PATH):
        raise FileNotFoundError(
            f"snapshots.parquet not found at {_SNAPSHOTS_PATH}. "
            "Run: python -m seller_survival build"
        )
    return pd.read_parquet(_SNAPSHOTS_PATH)
