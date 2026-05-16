---
name: bl-upgrade
description: Identify sellers eligible for a Buy Lead (BL) tier upgrade and choose between two modes — a retention-mode (at-risk seller close to renewal) and a growth-mode (FreeList seller showing healthy engagement around day 25-35). Use this skill in the action phase of the churn pipeline whenever you want to know whether and how to pitch a BL upgrade to a specific seller.
compatibility: Requires Python 3.11+, seller_survival package
---

# BL Upgrade Skill

## Instructions

Decide whether a seller should be offered a BL tier upgrade, and which of two modes applies. The skill consumes the current `churn_score`, `days_to_renewal`, account type, age, and recent engagement signals, then returns an eligibility verdict plus a tier-specific pitch in Hindi and English.

Modes:

- **AT_RISK_RETENTION (Mode A)** — Triggers when `churn_score >= 70` AND `days_to_renewal <= 15`, OR when the LLM cohort scorer flagged risk as `Critical` / `Very High`. The pitch unlocks 5 premium leads before renewal, framed as a value demonstration to prevent churn. Mode A wins when both modes trigger.
- **MONTHLY_TO_ANNUAL (Mode B)** — Triggers when a `FREELIST` seller is between day 25 and day 35 of their account, has been active at least 10 days in the last 30, and has replied to at least one Buy Lead. The pitch previews 3 leads they cannot currently access on monthly to nudge an annual upgrade.

If neither mode triggers, return `eligible=false` with a reason string for the rep.

## Examples

```bash
python -m churn_analysis skill bl-upgrade 11282573 --pretty
```

Example output for a retention-mode seller:
```json
{
  "eligible": true,
  "mode": "AT_RISK_RETENTION",
  "upgrade_leads_count": 5,
  "upgrade_message_hi": "Ramesh Bhai, renewal se pehle aapke liye 5 premium leads unlock ki hain — yeh normal sellers ko nahi milti.",
  "upgrade_message_en": "We've unlocked 5 premium leads for you before renewal — these aren't available to regular sellers.",
  "action": "OFFER_PREMIUM_LEADS",
  "expected_conversion_uplift": 0.22
}
```
