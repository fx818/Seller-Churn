---
name: peer_benchmark
version: "1.0"
category: analysis
description: Compare seller vs peers in same enterprise+ctype segment. Returns percentile ranks.
python_class: peer_benchmark

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

## Purpose
Compares seller's key metrics against peers in the same enterprise segment and subscription type.
Provides percentile rank and gap vs peer median.

## How to Run
```bash
python -m churn_analysis skill peer_benchmark 11282573 --pretty
```

## Metrics Compared
- Enquiries (30d)
- LMS active days (30d)
- CQS (catalog quality)
- PNS success rate

## Output
```json
{
  "peer_group": "ME|BL Paid",
  "peer_percentile": 23.5,
  "peer_delta_pct": -45.0,
  "peer_median_enq": 18.0,
  "peer_benchmark_result": {
    "enq_percentile": 23.5,
    "active_days_pct": 12.0,
    "verdict": "Below median — significant gap vs peers"
  }
}
```

## Notes
- Peer data is derived from the cohort library when available
- Without peer_benchmarks input, skill uses heuristic defaults
