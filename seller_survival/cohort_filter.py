"""
Filter the reference library to the most contextually similar sellers.
Returns top-k churned + top-k retained based on 4-field similarity.
"""
import json
from typing import Optional

import pandas as pd

from .mcat_embeddings import max_pairwise_cosine

STRICT_THRESHOLD = 0.5   # ≥2/4 fields
LOOSE_THRESHOLD  = 0.25  # ≥1/4 fields


def _filter_score(target_ctx: dict, hist_row: dict) -> float:
    score = 0.0

    # 1. Turnover exact match
    if target_ctx.get("turnover") and hist_row.get("turnover"):
        if target_ctx["turnover"] == hist_row["turnover"]:
            score += 1.0

    # 2. City + State match
    if (target_ctx.get("city") and hist_row.get("city") and
            target_ctx["city"].lower() == hist_row["city"].lower()):
        if (not target_ctx.get("state") or not hist_row.get("state") or
                target_ctx.get("state", "").upper() == hist_row.get("state", "").upper()):
            score += 1.0

    # 3. Mcat semantic overlap (cosine ≥ 0.7)
    target_mcats = target_ctx.get("mcats", [])
    hist_mcats   = json.loads(hist_row.get("mcats", "[]")) if isinstance(hist_row.get("mcats"), str) else (hist_row.get("mcats") or [])
    if target_mcats and hist_mcats:
        sim = max_pairwise_cosine(target_mcats, hist_mcats)
        if sim >= 0.7:
            score += 1.0

    # 4. Custtype exact match
    if target_ctx.get("custtype") and hist_row.get("custtype"):
        if target_ctx["custtype"].lower() == hist_row["custtype"].lower():
            score += 1.0

    return score / 4.0


def filter_cohort(
    target_context: dict,
    library: pd.DataFrame,
    k: int = 10,
) -> tuple[list[dict], list[dict], float, str]:
    """
    Returns:
      churned_examples   — list of up to k snapshot dicts
      retained_examples  — list of up to k snapshot dicts
      mean_match_score   — average filter_score of all shown
      tier               — 'strict' | 'loose'
    """
    rows = library.to_dict(orient="records")

    scored = []
    for row in rows:
        s = _filter_score(target_context, row)
        scored.append((s, row))

    scored.sort(key=lambda x: x[0], reverse=True)

    threshold = STRICT_THRESHOLD
    filtered = [(s, r) for s, r in scored if s >= threshold]

    tier = "strict"
    if len(filtered) < 5:
        threshold = LOOSE_THRESHOLD
        filtered = [(s, r) for s, r in scored if s >= threshold]
        tier = "loose"

    churned_all  = [(s, r) for s, r in filtered if r.get("label") == "churned"]
    retained_all = [(s, r) for s, r in filtered if r.get("label") == "retained"]

    churned_top  = [_row_to_snapshot(r) for _, r in churned_all[:k]]
    retained_top = [_row_to_snapshot(r) for _, r in retained_all[:k]]

    shown_scores = [s for s, _ in (churned_all[:k] + retained_all[:k])]
    mean_score   = round(sum(shown_scores) / len(shown_scores), 3) if shown_scores else 0.0

    return churned_top, retained_top, mean_score, tier


def filter_stats(target_context: dict, library: pd.DataFrame) -> dict:
    """Return filter stats without returning full examples."""
    rows = library.to_dict(orient="records")
    scored = [((_filter_score(target_context, r)), r) for r in rows]
    scored.sort(key=lambda x: x[0], reverse=True)

    strict = [(s, r) for s, r in scored if s >= STRICT_THRESHOLD]
    loose  = [(s, r) for s, r in scored if s >= LOOSE_THRESHOLD]

    tier = "strict" if len(strict) >= 5 else "loose"
    filtered = strict if tier == "strict" else loose

    n_churned  = sum(1 for _, r in filtered if r.get("label") == "churned")
    n_retained = sum(1 for _, r in filtered if r.get("label") == "retained")
    return {
        "n_filtered":  len(filtered),
        "n_churned":   n_churned,
        "n_retained":  n_retained,
        "tier":        tier,
        "threshold":   STRICT_THRESHOLD if tier == "strict" else LOOSE_THRESHOLD,
    }


def _row_to_snapshot(row: dict) -> dict:
    """Convert a parquet row back to a Snapshot dict for the LLM prompt."""
    raw = row.get("snapshot_json")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    # Fallback: reconstruct minimal
    return {
        "glid":  row.get("glid"),
        "label": row.get("label"),
        "context": {
            "turnover":  row.get("turnover"),
            "city":      row.get("city"),
            "state":     row.get("state"),
            "mcats":     json.loads(row.get("mcats", "[]")),
            "custtype":  row.get("custtype"),
        },
        "behavioral": {
            "bl": {
                "received_90d":    row.get("bl_received_90d"),
                "consumed_90d":    row.get("bl_consumed_90d"),
                "consumption_rate": row.get("consumption_rate"),
                "reply_rate":      row.get("reply_rate"),
                "weekly_bl_active": json.loads(row.get("weekly_bl_active", "[]")),
            },
            "lms": {
                "call_attempts_90d":    row.get("call_attempts_90d"),
                "call_answered_90d":    row.get("call_answered_90d"),
                "call_pickup_ratio_90d": row.get("pickup_ratio_90d"),
                "calls_1min_plus_90d":  row.get("calls_1min_plus_90d"),
                "last_succ_call_dt":    row.get("last_succ_call_dt"),
            },
            "activity": {
                "activity_30d":    row.get("activity_30d"),
                "event_count":     row.get("event_count"),
                "monthly_trend":   json.loads(row.get("monthly_trend", "[]")),
                "weekly_activity": json.loads(row.get("weekly_activity", "[]")),
            },
        },
    }
