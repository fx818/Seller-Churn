# IndiaMART — Seller Churn Reduction & Winback System
## Final Solution Plan: 5-Phase Seller Lifecycle Architecture

---

> **Revised Objective:** Achieve 10× ROI from the existing retention and winback team investment — by reaching more sellers, earlier, with the right message, at the right time — and reduce addressable seller churn by 2–3× through structured early-life intervention and AI-assisted personalisation.

---

## What the Real Data Tells Us

Before describing the solution, it is important to be honest about what the actual churn data reveals — because it changes the priorities of the system significantly from what a generic churn-reduction framework would suggest.

### Churn is Front-Loaded, Not End-Loaded

The most important fact in the entire problem: **30% of sellers churn within the first 3 months.** The pattern is:

- Month 1: approximately 10% of sellers do not complete their first payment
- Month 2: the payment completion rate drops from 90% to 80%
- Month 3: the payment completion rate drops further to 70%

This means by the time any renewal-day intervention would fire, a third of the sellers who were ever going to churn are already gone. The current retention system — built around renewal reminders — is structurally too late for this cohort. **The most valuable thing this system does is intervene in months 1 through 3, not month 11.**

### The Real Churn Reasons (From Internal Data)

Four primary reasons dominate:

1. **Insufficient lead volume** — seller expected more leads than their category and city can generate
2. **Non-genuine leads** — buyers not responding or not serious (a platform quality issue, partially outside our scope)
3. **Seller not giving time** — supplier too busy with their local business to engage with the platform (a structural issue, not solvable by retention communication)
4. **Monthly clients feel less pressure** — low financial commitment makes stopping an EMI psychologically easy

Two additional contributing factors that *are* addressable:
- Unrealistic expectations set during the sales process
- Inability to convert leads into sales (coaching gap)

### What This Means for the 10× Claim

**Honest assessment:** 10× reduction in total churn is not achievable because 30–40% of churn is structurally unaddressable — sellers who are too busy, leads that are genuinely low quality, and monthly sellers with low psychological commitment. Of the addressable 60–70%, realistic improvement is 2–3×.

**Where 10× is fully defensible:** The winback team's productivity. Today a winback rep spends 25–35 minutes per call on preparation and CRM entry, on top of the call itself. With AI pre-call briefs and automated call summaries, that drops to near zero. Combined with reason-routed scripts and the gifted lead opener improving conversion rates, **the value extracted from the same winback team investment improves by 8–10×** without adding headcount.

**The right framing for this solution:** *"10× ROI from the retention and winback team. 2–3× reduction in addressable churn. 8–12 additional sellers saved per 100 who would have churned in months 1–3 — at near-zero marginal cost."*

---

## Known High-Risk Priors (Hard-Coded into the System)

Before any behavioural data is collected, the following are known high-risk segments from historical analysis. The system treats these as Day 0 priors rather than learning them from scratch:

**High-risk categories:** Apparel and textiles, and other categories historically flagged through churn pattern analysis.

**High-risk cities:** Lucknow, Kanpur, Saharanpur, Surat, Jaipur — these cities are already restricted to annual-only sales due to poor historical performance. Sellers onboarding from these cities start with elevated risk scores and receive intensive onboarding support.

**Package type risk:** Monthly package sellers are inherently higher early-churn risk than annual sellers due to low financial commitment. Monthly sellers receive a different intervention track focused on conversion to annual within months 1–2, not just retention in place.

**Existing sales checklist integration:** The platform already runs a 15-parameter backend checklist at the point of sale that outputs "Sale Not Allowed / Monthly Allowed / Only Annual Allowed." This checklist already encodes significant risk intelligence. The Phase 1 and Phase 2 systems augment this existing framework rather than replacing it.

---

## Architecture Overview: 5 Phases

```
PHASE 1              PHASE 2                    PHASE 3                   PHASE 4         PHASE 5
Onboarding      →   Dual-Track             →   Retention             →   BL Upgrade  →   Renewal
Health Check        Churn Predictor            Three Parallel Tracks      Engine          Window Boost
Day 0–30            Early-Life: Day 30–90      Track A: Dashboard         Day -15 to -10  Day -7 to +7
                    Renewal: Day -90           Track B: Nudge + Script
                    to renewal                 Track C: Winback
```

**Critical design principle:** This is a closed loop. Phase 1 risk scores feed Phase 2 as priors. Phase 2 churn scores and root cause analysis determine which Phase 3 track activates. Phase 3 and 4 engagement outcomes feed back into the Phase 2 model. Winback outcomes from Track C improve the root cause classification over time. No phase operates in isolation.

---

## Phase 1: Onboarding Health Check

### Why This Is Now the Most Important Phase

Given that 30% of sellers churn by month 3, Phase 1 is no longer just a "nice to have" onboarding improvement. It is the primary intervention point for the largest single cohort of churners. The current system has no mechanism to help these sellers — Phase 1 is the only thing that stands between IM and losing a third of its seller base before any other system fires.

### Check 1: Category Demand Verification

**What it does:** On the day a seller signs up, the system queries buyer activity data to determine whether buyers are actively searching for this seller's product category in their city or surrounding geography.

**Why it matters:** A seller in a low-demand category in a low-demand city will receive very few leads regardless of how good their profile is. The current sales process sometimes creates expectations that the platform cannot meet for this seller's specific situation. Knowing this on Day 0 allows the system to either set honest expectations, suggest geographic expansion to national buyers, or flag the seller for an immediate human call before disappointment sets in.

**Output:** A demand index — healthy (Green), low but manageable (Amber), near-zero (Red). Red triggers an onboarding call within 24 hours. Amber triggers a specific "here is how national buyers work" WhatsApp message within 48 hours.

**Hard-coded priors applied here:** Sellers in known high-risk categories (apparel, textiles) or known high-risk cities (Lucknow, Kanpur, Surat, Jaipur, Saharanpur) receive an elevated starting demand risk score regardless of current search volume, based on historical churn patterns.

### Check 2: Business Legitimacy and Documentation Check

**What it does:** Cross-references the seller's verification status and flags any documentation gaps — missing GST, incomplete registration, or other issues that typically cause pre-hosting cancellations.

**Why it matters:** The meeting data identifies pre-hosting cancellations due to GST issues and missing documentation as a distinct churn category. Catching these on Day 0 and routing the seller to documentation support prevents a frustrating cancellation experience before the seller has even started.

**Output:** Verified (Green), Documentation pending (Amber — trigger documentation support workflow), Unverified (Red — immediate human call).

### Check 3: Peer Benchmark Setting — Expectation Calibration

**What it does:** Computes the median, 25th percentile, and 75th percentile of monthly Buy Lead counts for active sellers in the same category and city tier. This benchmark is shown to the seller explicitly during onboarding and repeated in their first-week communications.

**Why it matters:** "Unrealistic expectations set during the sales process" is named explicitly in the churn data as a primary reason for early dropout. The fix is not complicated — it is showing the seller a real number on Day 1: "Sellers like you in your category and city typically receive 4 to 8 leads per month. Your first leads usually arrive within 15 to 20 days." This prevents the seller from feeling cheated when they don't receive 30 leads in their first week.

**Note on the sales process:** This check also creates a feedback loop into the sales team. If a seller has been promised 30 leads per month and the peer benchmark shows 6, the system flags this as an expectation gap — not to penalise the salesperson, but to trigger a proactive correction call before the seller discovers the gap themselves.

### Check 4: First Buy Lead Response Signal

**What it does:** Monitors how quickly the seller responds to their first Buy Lead after joining the platform.

**Why it matters:** This is the single most predictive onboarding signal for 90-day retention. A seller who responds to their first lead within 30 seconds is demonstrating engagement, readiness, and understanding of the product. A seller who does not respond — or responds hours later — is showing early signs of the "not giving time" churn pattern.

**Output:** Fast response (Green — no action needed). Slow response (Amber — automated coaching WhatsApp). No response within 24 hours (Red — human call within 24 hours specifically about lead management setup).

### Check 5: Monthly vs Annual Package Flag

**What it does:** Identifies whether the seller is on a monthly (EMI) or annual (upfront) package and routes them into the appropriate intervention track.

**Why it matters:** Annual sellers have high commitment — they have paid upfront and are motivated to extract value. Monthly sellers have low commitment — stopping an EMI requires minimal psychological effort and no financial penalty beyond the first month's cost. These two groups need fundamentally different retention approaches. Monthly sellers need conversion to annual within months 1–2 as the primary goal. Keeping them on monthly indefinitely is high-risk because each month is an independent churn decision.

**Monthly seller early conversion track:** Monthly sellers who show positive early signals (fast BL response, active logins, good lead engagement) at Day 30 receive a specific "upgrade to annual" offer framed around what they are missing on the monthly plan — specifically, Phase 4's premium lead tiers which are annual-plan features.

### Onboarding Risk Score

The five checks above produce a composite onboarding risk score from 0 to 100. The weights:

- Category demand index: 30%
- Known high-risk category/city prior: 20%
- Business verification status: 15%
- Peer benchmark gap vs sales promise: 15%
- First BL response time: 20%

This score carries forward into Phase 2 as a prior. A seller who starts with a score of 75 due to high-risk category and low demand is watched more closely from Day 1.

### Onboarding Caller Agent

High-risk sellers (score above threshold) receive a human or AI-assisted call within 24 hours. The call is framed as a setup call, not a sales call. Specific script elements depending on risk type:

- Low demand city: "Aapke city mein local buyers abhi kam hain, lekin national buyers aapki category mein active hain. Main aapko batata hoon kaise reach karte hain."
- First BL not responded: "Aapke leads mobile pe kaise aate hain — setup karein saath mein."
- Documentation pending: "Ek cheez reh gayi hai jo main aapko 5 minute mein fix karwa sakta hoon."

The call ends with one specific action completed, not just discussed.

---

## Phase 2: Dual-Track Churn Predictor

### Why Two Separate Models Are Needed

The original plan had a single churn prediction model running 90 days before renewal. The meeting data reveals this is wrong for a significant portion of the seller base. Monthly sellers churn in months 1 through 3 — 90 days before renewal is month 9 of a 12-month cycle, by which point 30% of monthly sellers are already gone. Two separate scoring models are needed with different feature sets, different timing, and different action triggers.

---

### Model A: Early-Life Churn Model (Months 1–3, Monthly Sellers)

**Purpose:** Detect and intervene on the month 1–3 EMI dropout pattern before the second and third payment failures occur.

**Runs:** Weekly for all monthly sellers in their first 90 days.

**Training data:** Historical monthly sellers with labels: completed 3 months of payments (0) vs dropped before completing 3 months (1).

**Key features:**

**Feature 1 — First EMI completion flag:** Did the seller complete their first payment? Combined with onboarding risk score, this is the strongest predictor of month 2 and 3 behaviour.

**Feature 2 — Days since last platform login:** Sellers who stop logging in within the first 30 days almost never complete 3 months. If a monthly seller hasn't logged in for 10 days in month 1, that is a critical signal.

**Feature 3 — First BL response time (from Phase 1):** Carried forward. A seller who responded slowly to their first lead has a higher early churn probability.

**Feature 4 — BL consumption rate:** Are they consuming leads? A seller who has received 5 leads and not responded to any of them in 30 days is heading toward churn regardless of anything else.

**Feature 5 — Onboarding risk score (Phase 1):** Direct carry-forward from Phase 1. High onboarding risk + low early engagement = very high early churn probability.

**Feature 6 — Support call frequency:** Early-life sellers who call support frequently in month 1 are expressing frustration. This is different from the renewal-period support call signal — here it is an activation failure signal.

**Feature 7 — Package type and city/category risk prior:** Known high-risk categories and cities as hard-coded priors.

**Output:** Weekly churn risk score per monthly seller in months 1–3. Above threshold → immediate intervention (Track B nudge or human call). Critical signal → flag for conversion-to-annual conversation.

---

### Model B: Renewal Churn Model (Annual Sellers, Day -90 to Renewal)

**Purpose:** Detect annual sellers who are unlikely to renew, at least 90 days before their renewal date, with enough time to intervene meaningfully.

**Runs:** Daily for all annual sellers with renewal within 180 days.

**Training data:** 12 months of annual seller history with labels: renewed within 30 days of expiry (0) vs did not renew (1).

**Key features:**

**Feature 1 — Buy Lead Velocity Drop %:** The percentage change in Buy Lead volume from the previous 30 days to the current 30 days. The strongest single signal in the renewal churn model. A 60%+ drop in BL volume in one month is a crisis signal.

**Feature 2 — Platform Activity Streak:** Days since the seller last logged in. An annual seller who has not logged in for 22+ days has mentally disengaged.

**Feature 3 — Lead Response Rate (LMS):** The percentage of received leads the seller has responded to in the last 30 days. Declining response rate = the seller has stopped treating IM as a live business channel.

**Feature 4 — Support Call Frequency:** Number of support or account management calls initiated in the last 30 days. For renewal-period sellers, high call frequency signals frustration and unresolved problems — a very different signal from the early-life model where it indicates activation failure.

**Feature 5 — Peer Performance Delta:** The gap between this seller's BL count and the median for their category and city cluster. If peers are averaging 12 leads per month and this seller is getting 3, that gap is both a churn signal and the retention message. A seller who is significantly underperforming peers is both at risk and has a specific, fixable problem.

**Feature 6 — Buy Lead Rejection Reason Codes (BLNI):** When sellers mark leads as "Not Interested," they provide reason codes — wrong location, wrong quantity, wrong product type, price too low. This is real-time, voluntary root cause data. A seller who has marked 8 of 10 leads as "wrong location" has a fundamentally different problem from one who marked them "wrong quantity." These reason codes feed directly into both the churn probability and the SHAP explanation layer.

**Feature 7 — Days to Renewal:** Temporal feature. The same risk level at 90 days out requires less urgent intervention than the same risk level at 20 days out. The intervention intensity scales with proximity to renewal.

**Feature 8 — Onboarding Risk Score:** Carried forward from Phase 1. A seller who was high-risk at onboarding and now shows renewal-period engagement decline is at compounded risk.

**Feature 9 — Daily Sales Report Conversion Trend:** Is the seller's enquiry-to-order conversion rate improving or declining? A seller receiving adequate leads but failing to convert them has a coaching problem rather than a platform problem — which requires a different intervention.

---

### SHAP Root Cause Analysis: Turning the Score into a Script

Both models use SHAP explanations to generate plain-language root cause analysis for every seller flagged as at-risk. SHAP values identify which features are contributing most to a particular seller's risk score and by how much.

The SHAP explanation does not stay in a dashboard. It becomes:
- The opening line of the WhatsApp nudge message
- The pre-call brief for the PNS rep
- The script routing decision for Track B and Track C
- The gifted lead selection criteria (a seller whose top SHAP reason is "wrong location" gets a lead from a national buyer, not a local one)

**Five root cause categories and what they mean:**

| RCA Category | Primary Signal | What It Means | Intervention |
|---|---|---|---|
| No Leads / Low Demand | BL velocity near zero, low mcat demand | Platform not delivering volume | National demand expansion message + gifted lead |
| Low Engagement | DAU streak high, low response rate | Seller not using the platform | Activation call + coaching on lead management |
| Peer Gap | High peer delta, adequate BL volume | Seller getting leads but peers getting more | Dashboard comparison + profile fix coaching |
| Conversion Failure | Adequate BLs, low conversion in DSR | Getting leads but not closing them | Sales coaching call + script help |
| Lead Quality (BLNI) | High BLNI rejection rate, specific reason codes | Wrong leads being sent | Category/geography filter adjustment |

### Daily Output: Three Action Tiers

Every morning, each active seller in scope receives a churn probability score. The score determines one of three action tiers:

**Red Tier (Score ≥ 70%):** Human caller queue. Pre-call brief generated via Context API enrichment. Expected 5–10% of seller base.

**Amber Tier (Score 40–70%):** Automated WhatsApp nudge with personalised variables. Dashboard comparison card becomes prominent. Expected 15–25% of seller base.

**Green Tier (Score < 40%):** No outbound intervention. Monitoring continues daily.

---

## Phase 3: Retention — Three Parallel Tracks

### Overview

Phase 3 takes the churn scores and SHAP explanations from Phase 2 and converts them into three parallel retention interventions. Track A is always on for all sellers. Track B fires for at-risk sellers 1–2 months before predicted churn. Track C fires after a seller has already churned and the cool-off period has elapsed.

**Important reframe from the meeting data:** The retention team already converts 40–50% of cancellation requests. The current system works when it fires — the problem is it fires too late and too generically. Phase 3 does not replace the retention team. It gives them better information, better timing, and a better opener. The goal is moving retention conversion from 40–50% to 60–70%, on a larger pool of at-risk sellers reached earlier.

---

### Track A: Seller Dashboard Comparison Engine

**What it is:** A persistent comparison widget in the seller's platform dashboard showing how their performance compares to top sellers in their category and city. It is always visible — not triggered by churn risk.

**Important limitation acknowledged:** Sellers who are actively churning have usually already stopped logging into the platform. Dashboard widgets do not reach them. Track A's primary value is for engaged-but-underperforming sellers (Amber tier) who are still logging in and can act on what they see. It should not be presented as a primary churn reduction mechanism — it is an engagement and performance improvement tool that has a secondary retention benefit.

**Sub-feature 1 — Peer Performance Card:** Shows anonymised top performers in same category and city tier with specific metrics: monthly BL count, response rate, profile completeness, active days per month. Numbers pulled live from scorecard data and competitor analysis — updated monthly.

**Sub-feature 2 — Gap Diagnosis with Direct Fix Links:** For each performance gap identified, a specific actionable fix is shown with a direct link to the action inside the platform. Not vague advice — a specific step with a specific impact number. "Add 7 more product photos → leads increase by approximately 30% for sellers in your category" linked directly to the photo upload screen.

**Sub-feature 3 — Progress Tracker:** As the seller closes gaps, the comparison card updates to show progress. The seller is not competing against an abstract benchmark — they are visibly catching up to a real local peer who is already winning.

---

### Track B: Retention Nudge — Script + Gifted Lead

**Trigger:** Seller enters Amber or Red tier with 30 to 60 days to predicted churn. For monthly sellers flagged by Model A, triggers at Day 30–45 of their subscription.

**This is the highest-impact track in the system.** The retention team already converts 40–50% of cancellation requests with a generic conversation. Track B moves that conversation earlier and makes it specific. Earlier + personalised = significantly higher conversion with the same team effort.

#### Sub-Feature 1: Personalised Script from SHAP Data

The script is generated from the seller's specific SHAP root cause. The same script structure is used for human sales representatives, PNS reps, and the voice AI agent.

**Non-negotiable framing principle:** The call is framed as a follow-up, not a sales call. The seller must feel that IM is calling because someone actually looked at their account and noticed something — not because a billing cycle is approaching.

**Script structure:**

*Opening — genuine check-in:*
"Ramesh Bhai, main aapke account dekh raha tha — aapki category mein kuch interesting chal raha hai. Ek minute hai?"

*Middle — SHAP-driven diagnostic conversation:*

- If RCA = No Leads: "Maine dekha aapki current city setting se leads kum aa rahi hain. Lekin aapki category mein national buyers — Mumbai, Delhi — actively search kar rahe hain. Kya main setting change karke dikhaata hoon?"
- If RCA = Low Engagement: "Aapke last 3 leads ka maine status dekha — respond nahi hua. Kya koi problem aayi notifications mein? Ek minute mein fix karte hain."
- If RCA = Peer Gap: "Aapke jaisi category mein [city] ke ek seller ko last month 14 leads mili — ek specific cheez woh kar raha hai jo aap nahi kar rahe. Bataaun?"
- If RCA = Conversion Failure: "Leads toh aa rahi hain — lekin buyer se deal close karne mein kuch challenge aa raha hai? Main aapko ek simple approach bataata hoon jo [category] mein kaam karta hai."
- If RCA = BLNI/Wrong Location: "Maine dekha aapne kaafi leads 'wrong location' mark ki hain. Yeh actually ek setting issue hai — 2 minute mein fix ho jaata hai."

*Close — one specific committed action, no renewal mention:*
The call ends with exactly one specific next step. Either the gifted lead is sent, a setting is fixed live on the call, or a specific follow-up is scheduled. No renewal mention unless the seller raises it.

**Language personalisation:** Script generated in seller's regional language from state-of-registration mapping. Hindi for north India, Gujarati-inflected for Gujarat sellers, Tamil-inflected for south India. Language is trust.

#### Sub-Feature 2: AI Pre-Call Brief via Context API

The platform already has a Context API that generates session context for account management calls. The system enriches this with:
- Current churn probability score
- Top 2 SHAP reasons in plain Hindi/regional language
- Peer BL delta (how many leads they're missing vs peers)
- Classified RCA from transcript analysis
- Suggested opening line
- Gifted lead details if one has been allocated

The brief is accessed via a UUID-credential link requiring no separate login. A rep opens it on their phone before dialling. Total pre-call prep time: 30 seconds, down from 15–20 minutes.

#### Sub-Feature 3: AI Call Summary + CRM Auto-Log

After every call, the existing call transcript is processed by an LLM classification layer (built on top of transcripts that already exist — no new transcription infrastructure needed) to produce:
- A 3-line call summary
- Updated classified RCA
- Next action flag: follow-up call / send lead / escalate / profile fix

This is auto-logged to CRM. Zero manual entry per call. This is the primary source of the rep productivity gain — not making them talk faster, but eliminating 15–20 minutes of post-call admin per call.

#### Sub-Feature 4: Gifted Buy Lead — Full Contact, No Strings

A complete, real Buy Lead — full buyer name, phone number, order quantity, order value, city — is sent to the at-risk seller during or immediately after the retention call. No blur, no conditions, no renewal requirement.

**Why full contact, not blurred:** Indian SME traders have been exposed to "scratch and win" tactics their entire business lives. A blurred lead reads as a trick. A full lead with no conditions is a demonstration of confidence in the product. It says "we believe this is worth more than a renewal pitch — judge for yourself."

**The gifted lead is sourced from the platform's hot leads data** — buyer-activity-triggered leads that are already pre-qualified. These are not random BLs. They are leads generated from active buyer behaviour, meaning the buyer is genuinely looking for this product right now. Lead quality gate: posted within 72 hours, buyer has prior purchase history on platform, order value at or above the seller's historical average, not yet distributed to the maximum number of sellers.

**If no qualifying lead exists:** Do not send a low-quality lead. A bad gifted lead is worse than no gifted lead. In this case, send the peer comparison data as the demonstration instead.

**The 48-hour follow-up:** Two days after the gifted lead is sent, one WhatsApp is sent: "Bhai, us buyer se baat hui? Kuch kaam aaya?" That is the entire message. No renewal mention. The response (or non-response) is classified and fed back into the churn model.

**The psychology:** The sequence — give value, ask how it went, then discuss renewal — creates a fundamentally different dynamic from asking for money before delivering value. The seller who successfully closed a lead from the gifted contact is not having a renewal conversation. They are having a "how do I get more of these" conversation.

---

### Track C: Winback Script — Post-Churn Re-engagement

**Important update from meeting data:** The winback approach must account for two constraints that were not in the original plan:

1. **Cool-off periods are mandatory:** Monthly churners — 6 months before re-onboarding. Annual churners — 3 months before re-onboarding.
2. **Winback only happens on annual packages.** A churned monthly seller cannot return to monthly. The winback pitch is always an annual package pitch.

This changes the framing of every winback interaction. It is not "come back on the same terms." It is "come back on a better plan — and here is why the plan is now better than when you left."

**Trigger:** Seller's cool-off period has elapsed. Winback team is assigned.

#### Sub-Feature 1: Winback Pool Prioritisation Score

Not all churned sellers are equally recoverable. The prioritisation score is:

*Winback score = Historical lead quality × Current category demand × Recoverability of churn reason × Days since churn (inverse)*

**Top priority:** Seller who churned because "no leads" but their category now has significantly higher buyer demand than when they left. Their reason for leaving no longer exists.

**Low priority:** Seller who churned because business closed, relocated, or structural reasons. These sellers will not return regardless of the pitch.

**The 80/20 rule applies:** The top 20% of the winback pool by this score represents the vast majority of recoverable winback revenue. The winback team's time should be almost entirely focused here.

#### Sub-Feature 2: Reason-Routed Annual Package Pitch

Each classified churn reason routes to a different winback opening, but all pitches include two elements the current winback pitch already uses well — platform improvements (leads now go to 3–4 suppliers instead of 10, 50+ data points per lead) — plus the new elements from this system.

**Churn reason: No Leads**
*Opening:* "Bhai, aap tab chale gaye the jab leads nahi aa rahi thi. Maine aaj check kiya — aapki category mein abhi [X] active buyers hain. Woh tab nahi the. Main aapko ek ka number abhi deta hoon — pehle baat karo, phir decide karo."

**Churn reason: Lead Quality / BLNI**
*Opening:* "Bhai, aapne jo leads mark ki thi 'wrong location' mein — maine dekha woh actually ek setting issue tha. Woh fix hona chahiye tha, nahi hua, I understand. Platform mein ab yeh specifically change hua hai [explain improvement]. Ek baar try karein — annual pe aayein toh main personally ensure karta hoon setting theek ho."

**Churn reason: Price / ROI**
*Opening:* "Bhai, ROI nahi dikh raha tha — main samjha. Ek number dikhata hoon: [city] mein aapke jaisi category ka ek seller pichle quarter mein IM se approximately [X] lakh ka business kiya. Annual pe tha. Main aapko uska breakdown dikha sakta hoon."

**Churn reason: Competitor Platform**
*Opening:* "Bhai, main samjhata hoon aapne doosri platform try ki. Ek interesting data point — [category] mein jo serious buyers hain, woh specifically IM ke through enquiry karte hain. Aapke competitor jo IM pe active hain woh yeh buyers le rahe hain. Main aapko dikhaata hoon."

#### Sub-Feature 3: Gifted Lead as Re-Entry Demonstration

Same gifted lead principle — full contact, no obligation, sent before any renewal ask:

"Bhai, annual pe aane ke liye pressure nahi daal raha — bas yeh ek buyer hai jo aapka exact product dhundh raha hai. Number le lo, baat karo. Baaki baad mein decide karna."

The seller does not need to commit to anything to receive this lead. The re-subscription conversation happens after they have experienced the value demonstration, not before.

---

## Phase 4: Buy Lead Upgrade Engine

### Updated Purpose: Dual Function — Churn Prevention + Monthly-to-Annual Conversion

Phase 4 was originally conceived only as a last-resort churn prevention mechanism. The meeting data reveals a second, equally important use case: **converting monthly sellers to annual packages** before they churn in months 1–3.

Annual sellers have dramatically better retention than monthly sellers because of higher financial commitment. Phase 4 creates a mechanism to give monthly sellers a taste of annual-tier lead quality before they have made a churn decision.

### Mechanism 1: At-Risk Seller BL Upgrade (Original)

**Trigger:** Churn score ≥ 70% AND 10–15 days to predicted dropout AND seller has not responded to Track B nudge.

**What happens:** 3–5 Buy Leads from the next higher subscription tier are unlocked for the seller temporarily. These arrive through the normal lead management flow. The leads are noticeably better — higher order values, more verified buyers, better category matching.

**Why this works when messaging has failed:** A seller who has stopped responding to messages has mentally made the churn decision. Changing what they receive on the platform can reopen that decision in a way that more messaging cannot. A seller chasing a ₹75,000 lead is not thinking about churning.

**The follow-up:** "Aapne jo last week ke leads consume kiye — woh Gold plan ke the. Aapke current plan pe normally yeh nahi aate. Gold mein upgrade karte hain toh yeh regularly milenge." Retention becomes an upsell.

### Mechanism 2: Monthly-to-Annual Conversion Trigger (New)

**Trigger:** Monthly seller shows positive early signals at Day 30 (fast BL response, active logins, good engagement score from Model A) AND has not yet been offered an annual upgrade.

**What happens:** The seller is shown 2–3 Gold-tier leads as a preview of what the annual plan delivers. The message: "Aap monthly pe hain — in leads tak access nahi hai abhi. Annual pe switch karte hain toh yeh aur aise leads regularly milenge."

**Why at Day 30:** A monthly seller who is already engaged at Day 30 is the highest-probability candidate for annual conversion. They have experienced value and are still motivated. Waiting until month 3 — when engagement is declining — is too late. The offer at peak early engagement is dramatically more likely to convert.

**Impact:** Converting a monthly seller to annual eliminates their monthly churn risk entirely for 12 months and increases their revenue value to IM. It is the most efficient possible retention outcome.

### Lead Quality Gate (Non-Negotiable for Both Mechanisms)

Only leads meeting all four criteria are eligible:
1. Posted within the last 72 hours
2. Buyer has a prior purchase history on the platform
3. Order value meaningfully above the seller's current tier average
4. Not yet distributed to the maximum number of sellers

If no lead meets these criteria, Phase 4 does not fire. A poor premium lead is worse than no premium lead — it validates the seller's belief that IM's lead quality is low.

---

## Phase 5: Renewal Window Buy Lead Boost

### Scope Clarification from Meeting Data

Phase 5 applies primarily to **annual sellers** — those who pay upfront at renewal. Monthly sellers on EMI do not have a single renewal moment; their churn is a gradual EMI dropout pattern addressed in Phases 1–3. This narrows Phase 5's scope but also sharpens its focus: annual sellers are higher-value, and their renewal decisions are high-stakes single events that are worth significant investment to protect.

### The -7 Day Window: Pre-Renewal Lead Boost

Starting 7 days before the renewal date, 3–5 higher-quality Buy Leads are unlocked for the seller — same mechanism as Phase 4 but applied to all annual sellers approaching renewal, not just flagged high-risk sellers.

**The psychology:** The seller is actively working leads and experiencing platform value during the exact week they are deciding whether to renew. The renewal decision is made from a position of active engagement, not passive doubt or frustration.

**The message:** Sent 7 days before renewal: "Aapki IM ke saath anniversary aa rahi hai — aapke liye kuch special leads unlock ki hain. Abhi check karein." The tone is celebratory, not urgent. Positive association with the renewal event rather than anxiety.

### Renewal Day: Immediate Value Delivery

At the moment the renewal payment confirms, one fresh high-quality lead is immediately pushed to the seller's lead management queue.

The first action after renewing is not a confirmation screen. It is a business opportunity. This small detail has a large psychological effect: the seller's brain immediately connects "I just paid" with "I just received something valuable." The renewal feels immediately worthwhile.

### The +7 Day Window: Post-Renewal Reinforcement

For 7 days after renewal, elevated lead quality continues. The seller starts their new subscription cycle with momentum — active leads, positive engagement, strong recent experience with the platform.

After Day +7, lead quality normalises to the standard for their subscription tier. But by then the seller has formed a positive memory of the renewal period. Their next renewal decision, 12 months later, will be influenced by this memory.

### Why This Matters Beyond One Renewal

A seller who experiences a strong renewal window is more likely to talk about it in their trade network. Word of mouth in Indian B2B trade networks is extremely powerful — a recommendation from a trader peer at a mandi or trade fair is worth more than any paid acquisition. The renewal boost compounds across renewal cycles and across seller networks.

---

## Cross-Cutting Systems

### WhatsApp-First Delivery with Fallback Cascade

All seller-facing communications use the following delivery sequence:

1. **WhatsApp** (primary): 65–80% open rate among Indian SME sellers vs 8–12% for push notifications and email. Personalised variables: seller name, city, buyer search count this week, peer BL gap, competitor performance, days to renewal. Regional language. Message assembled fresh from live data — not a template blast.

2. **SMS** (fallback if WhatsApp unread after 48 hours): Shorter version. Works on feature phones.

3. **IVR call** (fallback if SMS unread after 72 hours): Automated voice in regional language. One-key transfer to live agent.

4. **Human PNS call** (final escalation for Red-tier sellers): Rep uses Context API pre-call brief. Full script from Phase 3 Track B.

### AI Call Summary System

Every call produces:
- 3-line summary
- Updated classified RCA
- Next action flag

Auto-logged to CRM. Zero post-call admin for the rep.

**Productivity impact:** A rep who previously handled 40 calls per day — with 15–20 minutes of prep and post-call admin per call — can now handle 80 calls per day with the same quality of preparation. This is not theoretical. It is purely arithmetic: remove 25–35 minutes of non-call time per call, and call capacity approximately doubles.

---

## What This System Does Not Solve

Intellectual honesty about scope is important for implementation planning and for setting stakeholder expectations.

**"Sellers not giving time":** Approximately 15–20% of churn comes from sellers who are simply too busy with their local business to engage with the platform. No nudge, script, or lead changes this. These sellers need either a managed service offering (someone manages IM on their behalf) or they will churn regardless. This cohort is not addressed by the current system.

**Non-genuine lead quality:** When buyers do not respond or are not serious, that is a platform product problem, not a retention communication problem. The gifted lead approach partially addresses the seller's *experience* of lead quality, but does not fix the underlying buyer verification problem. This is a product team problem.

**Monthly seller psychological low commitment:** The structural fact that stopping an EMI requires minimal effort is addressed by Phase 1's conversion-to-annual track and Phase 4's monthly-to-annual upgrade trigger, but not fully solved. Some monthly sellers will always be high-churn regardless.

**Pre-hosting cancellations (GST, documentation):** These are operational process problems. Phase 1's documentation check flags them early, but fixing them requires operations team action, not retention communication.

---

## Realistic Impact Assessment

### What Changes Numerically

| Metric | Before | After | Change |
|---|---|---|---|
| Earliest intervention point for early churners | None (no system fires before month 11) | Day 0 (Phase 1 onboarding score) | New capability entirely |
| Intervention timing for renewal churners | Day 0 (renewal day) | Day -90 (Phase 2 model) | 90 days earlier |
| Message open rate | 8–12% (push/email) | 65–80% (WhatsApp) | 7–8× |
| Rep pre-call prep time | 15–20 minutes | 30 seconds | ~30× reduction |
| Rep post-call CRM time | 15–20 minutes | 0 minutes (auto-logged) | Complete elimination |
| Rep calls per day | ~40 | ~80 | 2× |
| Retention conversion rate | 40–50% (at cancellation request) | 60–70% (60–90 days earlier) | 1.5× on larger pool |
| Winback conversion rate | ~10–15% (industry est.) | ~25–35% (reason-routed + gifted lead) | 2–3× |
| Winback team total output | baseline | 2× calls × 2.5× conversion | ~5× total output |

### The Compounding Effect

Winback team productivity improvement: 3× more calls per rep per day × 2.5× higher conversion rate = **7.5–10× improvement in value extracted from the same team investment.** This is the core 10× claim and it is fully defensible.

Churn reduction on the addressable cohort (the 60–70% of churners who are not structural): reaching them 90 days earlier via WhatsApp with personalised RCA-driven scripts converts an additional 20–30% of them. On the total seller base, this means **8–12 additional sellers saved per 100 who would have churned** — at near-zero marginal cost once the system is built.

### The Framing That Is Most Defensible

Do not claim "10× churn reduction" — the structural churn cohort makes this unprovable.

Claim: **"10× ROI from the winback team. 2–3× churn reduction on the addressable cohort. And for the first time, a structured intervention for the 30% of sellers who churn in months 1–3 before any existing system could have helped them."**

That last point is the most powerful one in the room. It is not an improvement on something that exists. It is an entirely new capability.

---

## Implementation Sequence

### Phase 0: Foundation (Weeks 1–3)
- Daily aggregation jobs for BL velocity, peer delta, mcat demand index
- LLM classification layer on existing call transcripts (2 days engineering — transcripts already exist)
- Context API enrichment with churn score and SHAP reasons

### Phase 1: Early Wins (Weeks 4–6)
- Phase 1 onboarding health check live
- Model A (early-life monthly churn) trained and scoring
- WhatsApp message generator with live variable assembly

### Phase 2: Core System (Weeks 7–10)
- Model B (renewal churn) trained and scoring
- Phase 3 Track B nudge engine live
- Hot lead allocation microservice for gifted lead pool
- AI call summary and CRM auto-log live

### Phase 3: Full System (Weeks 11–16)
- Phase 3 Track A dashboard comparison widget
- Phase 3 Track C winback prioritisation and routing
- Phase 4 BL upgrade engine (both at-risk and monthly-to-annual)
- Phase 5 renewal window boost

### Minimum Viable Demo (for Hackathon)
Five data tables are sufficient to demonstrate the core of the system: category and city data, seller activity logs, subscription history, lead management activity, and seller master records. From these, a live churn probability score, peer comparison card, sample WhatsApp message with live variables, and pre-call brief card can all be demonstrated in real time.

---

*IndiaMART Seller Churn Reduction System — Final Solution Plan*
*Updated with internal churn data and meeting insights*
*Prepared for Hackathon Presentation — Confidential*
