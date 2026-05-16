---
name: bl-card
description: Final aggregator skill — runs last in the pipeline and combines every prior skill's output into a single seller briefing card containing verdict, churn and winback scores, root cause analysis, signals, action plan, messaging, interventions and lookalikes. Use this skill at the end of the churn pipeline to produce the CRM-pasteable briefing for a sales rep before they call a seller.
compatibility: Requires Python 3.11+, seller_survival package
---

# BL Card Skill

## Instructions

Aggregate accumulated `flow.*` state from every prior pipeline phase into one structured BL Card with these sections:

- **header** — GLID, company, location, customer type, verdict, priority
- **scores** — final churn score, risk tier, LLM risk, BL/LMS/Activity bands, plus the full churn-score derivation breakdown
- **root_cause** — RCA category, explanations in Hindi and English, intervention hint
- **signals** — churn reasons, trajectory, demand, peer comparison
- **action_plan** — opening line, suggested actions, do-not-mention list
- **messaging** — WhatsApp message plus the 5-part call script (Hindi and English)
- **interventions** — BL upgrade eligibility, full winback derivation (sub-scores, weights, LLM adjustment)
- **lookalikes** — churned and retained seller GLIDs from the LLM cohort scorer
- **cross_platform** — JustDial / TradeIndia / own-website findings, IM catalog gap, headline pitch
- **summary_text** — plain-text printable card for CRM paste

Compute a 0-100 priority score (boosted by Red risk, LLM Critical/High, near-renewal, and HIGH winback priority) and a verdict string. Verdict ladder:

1. `Red risk OR churn_score >= 70` → CRITICAL — Immediate retention call
2. `winback_score >= 75 AND winback_priority == HIGH` → CRITICAL — HIGH winback priority, call immediately
3. `Amber risk OR churn_score >= 40` → AT RISK — Schedule retention call within 7 days
4. `LLM risk in [Critical, High, Very High]` → AT RISK — LLM-flagged, prioritize
5. `winback_score >= 65` → AT RISK — Recoverable churn, prioritize
6. `winback_score >= 40` → AT RISK — Winback opportunity, schedule call
7. Otherwise → HEALTHY — Routine check-in

Apply a cross-platform churn adjustment if the seller is "stronger elsewhere": gap < -40% adds +10 to the churn score (capped at 100), gap < -20% adds +5.

When run standalone (not via the full pipeline), `flow.*` fields are empty — the card only shows snapshot context. Always invoke through the pipeline for the full card.

## Examples

```bash
python -m churn_analysis skill bl-card 11282573 --pretty
python -m churn_analysis pipeline --glid 11282573
```

Output sketch:
```json
{
  "header":   {"glid": 11282573, "company": "...", "verdict": "CRITICAL — Immediate retention call", "priority": 92},
  "scores":   {"churn_score": 78, "risk_tier": "Red", "churn_breakdown": {...}},
  "root_cause": {"rca_category": "LOW_ENGAGEMENT", "explanation_hi": "...", "intervention": "..."},
  "messaging": {"call_script_hi": {...}, "whatsapp_hi": "..."},
  "interventions": {"winback_score": 72, "winback_priority": "HIGH", "winback_sub_scores": {...}},
  "summary_text": "..."
}
```
