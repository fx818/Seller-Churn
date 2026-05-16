---
name: peer-benchmark
description: Compare a seller's key metrics (enq_30d, active_days, CQS, PNS) against peers in the same enterprise + customer-type segment and return percentile rank, delta vs median, peer median, peer group size, gap severity tier, and a one-line summary. Use this skill in Phase 0 of the churn pipeline so downstream skills (onboarding-health, winback-priority, conversion-point) can frame the seller relative to comparable sellers rather than absolutes.
compatibility: Requires Python 3.11+, seller_survival package
metadata:
  version: "1.0"
  category: analysis
  python_class: peer-benchmark
  inputs:
    required:
      - key: glid
        source: snapshot.glid
        type: int
    optional:
      - key: enterprise
        source: context.custtype
        type: str
      - key: ctype
        source: context.custtype
        type: str
      - key: enq_30d
        source: behavioral.bl.received_30d
        type: int
        default: 0
      - key: active_days_30d
        source: behavioral.lms.lms_active_days_30d
        type: int
        default: 0
      - key: cqs
        source: behavioral.activity.cqs
        type: float
      - key: pns_success_pct
        source: derived.pns_success_pct
        type: float
  outputs:
    - key: peer_group
      type: str
    - key: peer_percentile
      type: float
    - key: peer_delta_pct
      type: float
    - key: peer_median_enq
      type: float
    - key: peer_benchmark_result
      type: dict
---

# Peer Benchmark Skill

## Instructions

Look up the seller's peer cohort (matching enterprise tier × subscription type) in the precomputed peer benchmarks file. Compute:

- `enq_percentile` — the seller's position among peers on 30-day enquiries
- `peer_delta_pct` — gap vs peer median as a percentage
- `peer_median_enq` — for the call brief
- `gap_severity` — high (<-50%), medium (<-20%), low (else)
- `peer_summary_line` — natural-language sentence the rep can read out

If no peer data is available (rare niche cohort), return `peer_data_available=False` and a fallback summary line.

## Examples

```bash
python -m churn_analysis skill peer-benchmark 11282573 --pretty
```

```json
{
  "peer_group": "PAID×MFG",
  "peer_percentile": 22.0,
  "peer_delta_pct": -45.0,
  "peer_median_enq": 12,
  "peer_benchmark_result": {"peer_n": 87, "peer_summary_line": "You're at the 22nd percentile..."}
}
```
