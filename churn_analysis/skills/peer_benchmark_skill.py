"""SKILL 3 — PeerBenchmarkSkill: Compare seller vs peers in same enterprise_type+ctype group."""
from .base_skill import Skill, SkillResult


class PeerBenchmarkSkill(Skill):
    name = "peer_benchmark"
    version = "1.0"
    required_inputs = ["glid"]
    optional_inputs = [
        "enterprise", "ctype", "enq_30d", "active_days_30d",
        "cqs", "pns_success_pct", "peer_benchmarks",
    ]

    def invoke(self, inputs: dict) -> SkillResult:
        enterprise = (inputs.get("enterprise") or "").strip()
        ctype      = (inputs.get("ctype") or "").strip()
        enq_30     = inputs.get("enq_30d") or 0
        active_30  = inputs.get("active_days_30d") or 0
        cqs        = inputs.get("cqs")
        pns_pct    = inputs.get("pns_success_pct")
        benchmarks = inputs.get("peer_benchmarks") or {}

        peer_group = f"{enterprise}|{ctype}" if enterprise and ctype else enterprise or ctype or "Unknown"

        group_data = benchmarks.get("groups", {}).get(peer_group)
        if group_data is None:
            # Try enterprise-level fallback
            for key, val in benchmarks.get("groups", {}).items():
                if key.startswith(enterprise):
                    group_data = val
                    peer_group = key + " (enterprise fallback)"
                    break

        if group_data is None:
            return SkillResult(
                success=True,
                data={
                    "peer_group": peer_group,
                    "peer_n": 0,
                    "peer_data_available": False,
                    "gap_severity": "unknown",
                    "peer_summary_line": f"No peer data available for group {peer_group}.",
                },
                confidence=0.2,
            )

        peer_n           = group_data.get("n", 0)
        median_enq       = group_data.get("median_enq_30d", 0) or 0
        p25_enq          = group_data.get("p25_enq_30d", 0) or 0
        p75_enq          = group_data.get("p75_enq_30d", 0) or 0
        median_active    = group_data.get("median_active_days", 0) or 0
        median_cqs       = group_data.get("median_cqs", 0) or 0
        median_pns       = group_data.get("median_pns_rate", 0) or 0

        enq_delta_abs = enq_30 - median_enq
        enq_delta_pct = round((enq_30 - median_enq) / max(median_enq, 1) * 100, 1)

        # Rough percentile approximation from p25/p75
        if enq_30 <= p25_enq:
            enq_pct = 15
        elif enq_30 <= median_enq:
            enq_pct = 35
        elif enq_30 <= p75_enq:
            enq_pct = 65
        else:
            enq_pct = 82

        cqs_delta   = round((cqs or 0) - median_cqs, 1) if cqs is not None else None
        active_pct  = round(active_30 / max(median_active, 1) * 50, 0) if active_30 < median_active else 70

        gap_severity = (
            "high"   if enq_delta_pct < -50 else
            "medium" if enq_delta_pct < -20 else
            "low"
        )

        peer_delta_pct = enq_delta_pct

        summary = (
            f"Peers in {peer_group} get avg {median_enq} enquiries/month. "
            f"You got {enq_30} ({'+' if enq_delta_abs >= 0 else ''}{enq_delta_abs})."
        )

        return SkillResult(
            success=True,
            data={
                "peer_group":           peer_group,
                "peer_n":               peer_n,
                "peer_data_available":  True,
                "enq_delta_abs":        enq_delta_abs,
                "enq_delta_pct":        enq_delta_pct,
                "enq_percentile":       enq_pct,
                "cqs_delta_abs":        cqs_delta,
                "active_days_percentile": int(active_pct),
                "peer_median_enq":      median_enq,
                "peer_p25_enq":         p25_enq,
                "peer_p75_enq":         p75_enq,
                "peer_median_cqs":      median_cqs,
                "peer_median_pns_rate": median_pns,
                "peer_delta_pct":       peer_delta_pct,
                "gap_severity":         gap_severity,
                "peer_summary_line":    summary,
            },
            confidence=0.85,
        )

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=False,
            data={"peer_data_available": False, "gap_severity": "unknown"},
            error=str(error), confidence=0.1, used_fallback=True,
        )
