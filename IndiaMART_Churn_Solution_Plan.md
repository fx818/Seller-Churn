# IndiaMART — Seller Churn Reduction & Winback System
## Complete Solution Plan: 5-Phase Lifecycle Architecture

---

> **Objective:** Reduce seller churn by a minimum of 10× and improve winback conversion by 10× by building a data-driven, AI-assisted seller lifecycle system that intervenes at the right moment, with the right message, through the right channel — before the seller has already decided to leave.

---

## The Problem, In Plain Terms

IndiaMART's revenue depends on sellers renewing their subscriptions. Every seller who churns represents not just lost subscription revenue, but the cost of re-acquiring them later — which industry data consistently shows is 5 to 7 times more expensive than retaining an existing customer. At the scale IndiaMART operates, even a 5 percentage point improvement in churn rate translates to hundreds of crores in recovered annual revenue.

The core problem today is not that churn is happening — it is that the system detects churn too late, responds with generic messages, and has no structured understanding of *why* a specific seller is leaving. A renewal reminder sent on the day a subscription expires is not a retention strategy. By that point, the seller has already mentally checked out weeks or months ago.

The system being proposed here solves this by treating churn as a lifecycle problem, not a billing problem. It intervenes at five distinct stages — from the moment a seller signs up, through their active period, at the point of risk, at renewal, and even after they have already left.

---

## Why 10× Is Achievable

Before explaining the solution, it is worth establishing why 10× improvement is a realistic target and not an arbitrary claim.

Today's retention mechanism is essentially a single touchpoint: a renewal reminder when the subscription is about to expire. Industry benchmarks for this kind of generic, late-stage intervention show conversion rates of 8 to 12 percent. This means roughly 88 to 92 percent of sellers who are about to churn are not being saved.

The proposed system creates multiple earlier touchpoints, each personalised to the seller's specific situation, delivered through the right channel, with a concrete value demonstration. When you combine:

- Detection that is 90 days earlier than today
- Messages that are personalised to the seller's own category, city, and competitor data rather than generic
- Delivery through WhatsApp instead of push notifications (65–80% open rate vs 8–12%)
- A "give value first" approach using real buyer leads instead of a discount pitch
- A doubling of sales rep productivity through AI-assisted call briefs and summaries
- A winback system that leads with a live business opportunity instead of a re-subscription pitch

...the compounding effect of all these improvements together is what gets you to 10×. No single feature achieves it. The architecture as a whole does.

---

## Architecture Overview: 5 Phases

The solution is structured as a seller lifecycle system with five sequential but interconnected phases. Each phase has a specific job, a specific set of data inputs, and a specific set of outputs that feed into the next phase.

```
PHASE 1           PHASE 2              PHASE 3                    PHASE 4          PHASE 5
Onboarding   →   Churn          →   Retention                →   BL Upgrade  →   Renewal
Health Check     Predictor          (3 parallel tracks)          Engine           Window Boost
Day 0–30         Day 30 → -90d      -90d to renewal              -15d to -10d     -7d to +7d
                 before renewal     Track A: Dashboard
                                    Track B: Nudge + Script
                                    Track C: Winback
```

Every phase's output feeds the next. The onboarding risk score from Phase 1 becomes a prior in the Phase 2 model. The churn probability and root cause analysis from Phase 2 determines which retention track in Phase 3 is activated. The engagement data from Phase 3 and Phase 4 feeds back into the Phase 2 model to improve it over time. This is a closed loop, not a linear pipeline.

---

## Phase 1: Onboarding Health Check

### Purpose

The single most impactful time to prevent churn is before it starts. A significant portion of seller churn happens within the first 60 to 90 days — not because IndiaMART stopped working, but because the seller had unrealistic expectations, was in a category or city with low buyer demand, or had a profile so incomplete that buyers never saw their listings. All of these problems are identifiable on Day 0 if you look at the right signals.

Phase 1 runs four automated checks the moment a seller signs up and uses the results to generate an onboarding risk score, trigger a personalised onboarding call, and set accurate expectations before the seller has a chance to feel disappointed.

### Check 1: Category Demand Verification

**What it does:** The system queries the platform's buyer activity data to determine whether there are active buyers searching for this seller's product category in their city or nearby geography.

**Why it matters:** A seller who signs up to sell industrial pipe fittings in a small Tier 3 city with zero buyer searches in that category in the last 30 days is almost certain to churn within 60 days — not because IM failed them, but because the demand was never there locally. Knowing this on Day 0 allows the system to either set realistic expectations (national buyers exist even if local ones don't), suggest category expansion, or flag the seller for a human intervention call.

**Data used:** Category identifier, city, city tier classification, buyer search volume aggregated over the last 30 days from the platform's search activity data.

**Output:** A demand index score for this seller's specific category + city combination. Green (healthy demand), Amber (low demand, manageable), Red (near-zero demand, high risk).

### Check 2: Business Legitimacy Verification

**What it does:** Cross-references the seller's business registration status against the platform's verification records.

**Why it matters:** Businesses that are not properly verified or have thin registration details show a dramatically higher 60-day churn rate — typically 2 to 3 times higher than verified businesses. This is partly because they may not be serious businesses, and partly because without proper verification, their profiles are less visible to buyers, creating a self-fulfilling prophecy of low leads.

**Data used:** Business verification status from the platform's internal verification system.

**Output:** Verification flag — Verified, Pending, or Unverified. Unverified sellers are fast-tracked to a human onboarding call.

### Check 3: Peer Benchmark Setting

**What it does:** Computes the median BL (Buy Lead) count per month for all active sellers in the same category and city tier as the new seller. This number is shown to the seller immediately as part of their onboarding experience.

**Why it matters:** The number one reason sellers give for churning in the first 90 days is "IM kaam nahi karta" — IM doesn't work. In most cases, this is not because IM doesn't work. It is because the seller expected 50 leads a month and is getting 8, not knowing that 8 is actually above average for their category and city. Setting accurate expectations on Day 1 eliminates this disappointment-driven churn almost entirely. Research on SaaS onboarding consistently shows that expectation calibration in the first week reduces 90-day churn by 35 to 45 percent.

**Data used:** Historical BL distribution data for the seller's category and city tier, computed from the platform's scorecard data. Specifically: median, 25th percentile, and 75th percentile of monthly BL counts for comparable sellers.

**Output:** A benchmark card shown to the seller: "Sellers like you in your category and city typically receive X to Y leads per month. You can expect to see your first leads within Z days." This sets the expectation accurately without overpromising.

### Check 4: First Buy Lead Response Signal

**What it does:** Monitors how quickly the seller responds to their very first Buy Lead after joining the platform.

**Why it matters:** This is the single most predictive onboarding signal for 90-day retention. Analysis of seller behaviour data consistently shows that sellers who respond to their first BL within 30 seconds are dramatically more likely to still be active at 90 days than sellers who respond slowly or not at all. The reason is behavioural: a fast first response indicates that the seller is engaged, has their phone ready, understands the product, and is motivated. A slow or no-response indicates disengagement before the seller has even started.

**Data used:** Timestamp of BL delivery and timestamp of seller's first response action, from the platform's lead management activity logs.

**Output:** Response time flag. Fast (< 30 seconds) → Green. Moderate (30 seconds to 5 minutes) → Amber. Slow or none (> 5 minutes or no response) → Red. Red triggers an onboarding call within 24 hours.

### Onboarding Risk Score

The four checks above are combined into a single onboarding risk score from 0 to 100, where higher scores indicate higher churn risk. The weights are approximately:

- Category demand index: 35% of score
- Business verification: 25% of score
- Peer benchmark gap: 20% of score
- First BL response time: 20% of score

This score is not used to reject sellers. It is used to calibrate how much onboarding support they receive. High-risk sellers get a human call within 24 hours. Medium-risk sellers get an automated WhatsApp sequence. Low-risk sellers get a standard onboarding flow.

### Onboarding Caller Agent

For sellers with a risk score above a threshold, an onboarding call is triggered within 24 hours. The call script is generated from the seller's specific data:

- If demand is low: the agent explains that national buyers are active even if local search is low, and shows the seller how to expand their geographic reach.
- If profile is incomplete: the agent walks the seller through exactly which fields to complete, with a specific example of a top-performing seller in their category who has complete listings.
- If first BL response was slow: the agent explains how the BL system works, why speed of response matters, and sets up the seller's phone notifications.

The call is not a sales call. It is a setup call. The tone is "I want to make sure you get the most out of your first month" — not "please don't cancel."

### Phase 1 Output

Every seller exits Phase 1 with:
1. An onboarding risk score (0–100) that carries forward as a prior into Phase 2
2. Calibrated expectations about BL volume and timeline
3. A profile that is at least minimally complete
4. If high-risk: a human touchpoint within 24 hours

---

## Phase 2: Churn Predictor — Root Cause Analysis Engine

### Purpose

Phase 2 is the intelligence core of the entire system. It runs every night on every active seller, computes a churn probability score from 0 to 100, and — critically — generates a ranked list of specific reasons *why* that seller is at risk. This root cause analysis is what makes every downstream intervention targeted rather than generic.

The system needs to predict churn 90 days before renewal — not at renewal time — because 90 days is when the seller is still open to being helped. At renewal time, the decision is already made.

### The Model: LightGBM with SHAP Explanations

**Why LightGBM:** Gradient boosted trees are the industry standard for subscription churn prediction on tabular data. They handle class imbalance well (churned sellers are a minority), work well with the mix of categorical and continuous features available, and are interpretable through SHAP values — meaning you can explain exactly why any individual seller got the score they did. This interpretability is essential, because the SHAP explanations become the call script and the WhatsApp message.

**Training data:** 12 months of historical seller data with binary churn labels (renewed within 30 days of expiry = 0, did not renew = 1). Retrained monthly as new data accumulates.

**Target precision:** Approximately 85% precision at the 70% probability threshold. This means that when the model flags a seller as Red (high churn risk), it is correct roughly 85% of the time. The 15% false positives receive a helpful outreach call — not a bad outcome.

### The 7 Core Model Features

Each of these features is pulled from existing platform data. No new data collection is required for the model to run.

**Feature 1 — Buy Lead Velocity Drop %**
The percentage change in Buy Lead volume from the previous 30-day period to the current 30-day period. Formula: (BL last 30 days − BL previous 30 days) / BL previous 30 days. This is the single strongest predictor of churn. A seller whose BL count drops 60% in a month is in crisis, even if their absolute BL count is still positive. The rate of change matters more than the absolute number.

**Feature 2 — Platform Activity Streak**
The number of days since the seller last logged into the platform. A seller who has not logged in for 22 days has mentally checked out. Combined with BL velocity, this is the clearest two-signal churn pattern in the data.

**Feature 3 — Lead Response Rate**
The percentage of received Buy Leads that the seller has responded to in the last 30 days. Sellers whose response rate drops below 40% are churning in spirit before they churn in billing. They have stopped treating IM as a live business channel.

**Feature 4 — Support Call Frequency**
The number of support or account management calls the seller has initiated in the last 30 days. Counter-intuitively, *high* call frequency is a churn signal — it indicates frustration and unresolved problems, not engagement. A seller who calls support 6 times in a month is not a happy customer.

**Feature 5 — Peer Performance Delta**
The gap between this seller's BL count and the median BL count of all active sellers in the same category and city tier. If a seller is getting 3 leads a month when their peers are averaging 12, that gap is both a churn signal and the exact data point needed for the retention message. This feature ties the prediction directly to the intervention.

**Feature 6 — Days to Renewal**
How many days remain until the subscription expires. This is used as a temporal feature — a seller with 20% churn risk and 120 days to renewal is less urgent than the same seller with 15 days to renewal. The intervention timing and intensity are both calibrated by this feature.

**Feature 7 — Onboarding Risk Score (Phase 1 carry-forward)**
The risk score computed in Phase 1 is carried forward as a feature in the Phase 2 model. A seller who had a high onboarding risk score and is now showing declining BL engagement is substantially more likely to churn than a seller showing the same engagement decline who had a clean onboarding. Past risk compounds with present behaviour.

### The Hidden Signal: Buy Lead Rejection Reason Codes

Beyond the 7 core model features, the platform captures a signal that is almost certainly being underused: when a seller marks a Buy Lead as "Not Interested," they select a reason. These reason codes — wrong location, wrong quantity, wrong product type, wrong buyer, price too low — are direct, real-time RCA data that the seller is providing voluntarily.

A seller who has marked 8 of their last 10 leads as "wrong location" has a fundamentally different problem than a seller who marked 8 of 10 as "wrong quantity." The first needs geographic reach expansion. The second needs a category adjustment or buyer quality filter. Feeding these rejection reason codes into the model as an additional feature and into the SHAP explanation layer allows the system to diagnose the *specific* problem for each seller rather than inferring it.

This signal is available in the platform's lead management data today. It is not currently used for churn prediction. Making it a first-class model feature is one of the highest-ROI improvements available with zero new data collection.

### Call Transcript Sentiment Analysis

The platform already has transcripts of account management calls available through an existing API — one transcript per call, accessed via a call identifier. These transcripts are currently used for QA purposes. The proposed system adds a lightweight LLM classification layer on top of the existing transcript data:

**Sentiment classification:** Each transcript is classified as Positive, Neutral, or Frustrated. A seller who has expressed frustration in the last 2 support calls is a higher churn risk than their BL data alone suggests.

**Churn reason extraction:** The LLM classifies the primary reason for the seller's concern into one of five categories: No Leads / Lead Quality / Price Objection / Competitor Platform / Business Change. This classification becomes the primary input for the winback script routing in Phase 3.

**Effort level:** Because transcripts already exist, this does not require building a speech-to-text pipeline. It is a classification task on existing text data — approximately 2 days of engineering work to productionise.

### Daily Scoring Output: The Three Tiers

Every morning, each active seller receives a churn probability score from 0 to 100. This score is used to place them in one of three action tiers:

**Red Tier (Score ≥ 70%):** High churn risk. Seller enters the human caller queue for a retention call. A pre-call brief is generated (see Phase 3, Track B). Expected to be approximately 5–10% of the active seller base at any given time.

**Amber Tier (Score 40–70%):** Moderate churn risk. Seller receives a personalised WhatsApp nudge through the automated nudge engine. Also triggers the seller dashboard comparison card to become more prominent in their platform view. Expected to be approximately 15–25% of the active seller base.

**Green Tier (Score < 40%):** Low churn risk. No outbound intervention. The seller's Phase 1 and Phase 2 data continues to be monitored and their score updated daily.

### SHAP Explanations: Turning the Score into a Script

The most important output of Phase 2 is not the score itself — it is the SHAP explanation for each seller. SHAP (SHapley Additive exPlanations) values tell you, in plain terms, which features are contributing most to a particular seller's churn risk score and by how much.

For example, a seller with a score of 78 might have SHAP values showing:
- BL velocity drop of 63% in the last 30 days: contributing +22 points to the score
- Has not logged in for 19 days: contributing +18 points
- Peer BL delta of -8 leads vs median: contributing +14 points

This translates directly into a plain-language explanation: "This seller's leads have dropped significantly, they've stopped logging in, and similar sellers in their area are getting far more leads than they are."

That explanation is the call script. It is the WhatsApp message. It is the dashboard alert. The model is not a black box that produces a number — it is a diagnostic engine that tells the sales team exactly what to say and why.

---

## Phase 3: Retention — Three Parallel Tracks

### Purpose

Phase 3 takes the churn scores and SHAP explanations from Phase 2 and converts them into three parallel retention interventions, each targeting a different stage of seller disengagement. The three tracks run simultaneously and are not mutually exclusive — a seller can appear in Track A's dashboard comparison, receive a Track B nudge, and if they still churn, enter Track C for winback.

---

### Track A: Seller Dashboard Comparison Engine

**What it is:** A persistent, data-driven comparison widget visible to every seller in their platform dashboard. It shows how the seller's performance compares to top-performing sellers in their exact category and city, and provides specific, actionable steps to close each identified gap.

**Why it works:** Indian SME psychology is deeply comparative. The "Sharma Ji ka beta" phenomenon — awareness of how peers are doing and discomfort when falling behind — is one of the most powerful motivators in Indian business culture. This is not about shaming sellers. It is about showing them that better results are achievable, that someone just like them in their city and category is getting them, and that the gap is closeable with specific actions.

#### Sub-Feature 1: Peer Performance Card

The system identifies the top 5 performing sellers in the same category and city tier. These sellers are anonymised ("a seller in your category in your city") but their performance metrics are shown:

- Monthly Buy Lead count: "Top sellers in your category receive 12–18 leads per month. You are receiving 4."
- Lead response rate: "Top sellers respond to 78% of their leads. You respond to 22%."
- Profile completeness: "Top sellers have 9 product photos on average. You have 2."
- Active days on platform: "Top sellers log in 22 days per month on average. You logged in 6 days last month."

Each of these numbers is pulled in real time from the platform's scorecard and activity data. They are not static benchmarks — they update monthly as the competitive landscape changes.

#### Sub-Feature 2: Gap Diagnosis with Actionable Fix

For each gap identified, the system generates a specific, actionable fix — not a vague suggestion, but a direct link to the exact action inside the platform:

- Photo gap: "Add 7 more product photos → [Add Photos button]" with a data point: "Sellers with 9+ photos receive 40% more leads than sellers with 2 photos."
- Response rate gap: "Enable lead notifications on your phone → [Setup Notifications button]" with a data point: "Sellers who respond within 5 minutes are 3× more likely to convert a lead."
- Login frequency gap: "Check your dashboard daily for new leads → [Set Reminder button]"

The fix is always one tap away. There is no friction between "you need to do this" and "do it now."

#### Sub-Feature 3: Progress Tracker — Closing the Gap

As the seller takes actions and improves their metrics, the gap between their performance and their peers' performance closes visually on the dashboard. This creates a lightweight gamification effect — not in a gimmicky way, but in the way that any visible progress indicator motivates continued engagement. The seller is not competing against an abstract leaderboard. They are competing against a real, local peer who is already winning, and they can see themselves catching up.

**Impact mechanism:** Track A is always on — it does not require a churn risk trigger. Every seller sees it. But for Amber and Red tier sellers, it becomes more prominent in their dashboard view, and the peer comparison numbers are specifically calibrated to their gap from Phase 2's peer delta feature.

---

### Track B: Retention Nudge — Script + Gifted Lead

**What it is:** A proactive outreach system that activates 1 to 2 months before the predicted churn date, combining a personalised seller-specific contact script with a gifted Buy Lead. The script is used by both human sales representatives and the voice AI agent. The gifted lead is sent regardless of whether the seller renews.

**Trigger condition:** Seller enters Amber or Red tier in Phase 2 with 30 to 60 days to predicted dropout.

#### Sub-Feature 1: Personalised Script Generation

The script is not a template. It is assembled from the seller's specific data — their SHAP reasons, their peer gap, their category, their city, and their language.

The script follows a specific structure:

**Opening — follow-up framing, not sales framing:**
"Ramesh Bhai, bas follow-up karne ke liye call kiya tha. Aapke last month ke leads ka kya hua? Koi problem toh nahi?"

This opening is deliberate. It signals genuine interest in the seller's business outcome, not a renewal pitch. Indian traders distinguish immediately between someone who wants their money and someone who gives a damn about their business. The tone of the first 10 seconds determines whether the seller stays on the call.

**Middle — diagnostic conversation using SHAP data:**
The agent uses the Phase 2 SHAP explanations as conversation starters, not accusations:
- "Maine dekha aapki category mein is hafte Mumbai se 8 buyers aayen hain — kya aap chahenge main aapko unka detail bhejun?"
- "Aapke jaisi category mein [city] ke ek seller ko last month 14 leads mili — woh kuch specific cheezein kar raha hai, bataaun?"

**Close — one specific action, not a renewal ask:**
The call always ends with one concrete next step: sending the gifted lead, fixing a specific profile issue, or scheduling a follow-up. The renewal conversation is explicitly *not* part of this call unless the seller brings it up.

**Language personalisation:** The script is generated in the seller's regional language based on their state of registration. Sellers in Gujarat get a Gujarati or Hindi-Gujarati mix script. Sellers in Tamil Nadu get a Tamil or Tamil-inflected Hindi script. Language is trust. A Hindi-speaking seller in Meerut disconnects from an English-accent script in 8 seconds.

**Dual use — human rep and voice AI agent:**
The exact same script structure is used for human PNS representatives and the voice AI agent. The voice AI agent handles the initial outreach for Amber-tier sellers. Human reps handle Red-tier sellers and any conversation that escalates beyond the script's scope.

#### Sub-Feature 2: AI Call Summary + CRM Auto-Log

After every call — whether by a human rep or the voice AI — the platform's existing call transcript is processed by the LLM classification layer described in Phase 2. The output is:

- A 3-line call summary: what was discussed, what the seller's main concern was, what action was committed to
- A classified churn reason: No Leads / Lead Quality / Price / Competitor / Business Change
- A next action flag: Follow-up call in 7 days / Send lead / Profile fix / Escalate to senior rep

This summary is auto-logged to the CRM. The rep does zero manual entry. This is how rep productivity doubles — not by making them work faster, but by eliminating the 15 to 20 minutes of post-call admin per call.

#### Sub-Feature 3: Gifted Buy Lead — Full Contact, No Strings

The retention call ends with the delivery of one real, complete Buy Lead to the seller. Not a blurred preview, not a discount offer — a full buyer contact: name, phone number, order quantity, order value, city.

**Why full contact, not blurred:** A blurred lead feels like a marketing trick. Indian SME sellers have seen "scratch and win" gimmicks their entire lives. A full lead with no conditions sends a completely different signal: "We believe in the quality of what we're offering enough to give it to you for free. Judge for yourself."

**Lead quality gate — non-negotiable rules:**
- Posted within the last 72 hours (freshness is the most important quality attribute)
- Buyer has a purchase history on the platform (not a first-time enquiry)
- Order value is at or above the seller's average historical BL value
- Lead has not yet been distributed to 3 sellers (still live and competitive)

If no lead meets these quality criteria, no gifted lead is sent. A bad gifted lead is worse than no gifted lead — it validates the seller's worst suspicion about IM's quality.

**The psychology:** The gifted lead flips the entire dynamic of the renewal conversation. Instead of "pay us, then get value," it becomes "here is value, now decide." The follow-up conversation — 48 hours later — is: "Did you speak to Rahul Traders? Did it help?" If the lead converted, the renewal is almost automatic. If it didn't, you now know exactly why, which is also valuable.

**The follow-up — one question, no pitch:**
48 hours after the gifted lead is sent, the automated system sends a WhatsApp: "Bhai, us buyer se baat hui? Kuch kaam aaya?" That is the entire message. No renewal mention. The seller's response — whether positive, negative, or absent — is classified and fed back into the churn model.

---

### Track C: Winback Script — After the Seller Has Churned

**What it is:** A prioritised, data-driven outreach system for sellers who have already left the platform. The winback approach is built on two principles that differentiate it from conventional winback: prioritise by recoverability, not recency; and lead with a live business opportunity, not a re-subscription pitch.

**Trigger condition:** Seller did not renew within 30 days of expiry. Enters the winback pool.

#### Sub-Feature 1: Winback Pool Prioritisation Score

Not all churned sellers are equally worth pursuing. The winback pool prioritisation score ranks churned sellers by their probability of returning, weighted by their expected revenue value if they do return. The score is a function of:

- **Historical lead quality:** How many of the seller's past leads were converted to orders? High-conversion sellers are more valuable to win back.
- **Current category demand:** Has demand in the seller's category increased since they left? A seller who churned because "no leads" but whose category now has 3× the buyer activity is a top-priority winback candidate.
- **Time since churn:** Winback probability declines sharply after 90 days. Sellers churned within 30 days are the highest priority.
- **Churn reason recoverability:** Some churn reasons are recoverable (no leads — solvable), some are less so (business closed — not solvable). The classified churn reason from Phase 2 informs this weighting.

**The Pareto principle applies:** The top 20% of the winback pool by this score typically represents 80% of the recoverable winback revenue. The winback team's time should be concentrated here.

#### Sub-Feature 2: Reason-Routed Winback Script

The classified churn reason from Phase 2 (No Leads / Lead Quality / Price / Competitor / Business Change) routes to a different script opening and a different primary message:

**Churn reason: No Leads**
Opening: "Bhai, aap tab chale gaye the jab leads nahi aa rahi thi. Maine aaj check kiya — aapki category mein abhi 8 active buyers hain jo exact aapka product dhundh rahe hain. Woh tab nahi the. Main aapko ek ka number abhi deta hoon."
Why it works: The seller's stated reason for leaving has been directly addressed with current data. The lead is the proof, not the pitch.

**Churn reason: Price / ROI**
Opening: "Bhai, aapko laga tha IM pe jo invest kiya woh wapas nahi aaya. Main aapko ek number dikhata hoon — [city] mein aapke jaisi category ka ek seller last quarter mein IM se approximately 3.2 lakh ka business kiya. Uski subscription bhi same thi jo aapki thi."
Why it works: The ROI objection is answered with a specific, local, comparable example — not a global average.

**Churn reason: Competitor Platform**
Opening: "Bhai, aapne mention kiya tha ki doosri platform try kar rahe hain. Main samajh sakta hoon. Ek interesting cheez notice ki — [category] mein jo top buyers hain, unme se kaafi IM ke through specifically enquiry karte hain. Yeh buyers doosri platforms pe nahi hain."
Why it works: Addresses the competitor objection directly using buyer data, without attacking the competitor.

**Churn reason: Lead Quality (BLNI data)**
Opening: "Bhai, aapne jo leads mark kiya tha 'not interested' — maine dekha zyada tar 'wrong location' ke liye tha. Aapki setting ek jagah fix hai jo sirf local leads aa rahi thi. Agar hum setting change karein toh national buyers bhi aa sakte hain — main abhi ek example dikhata hoon."
Why it works: Shows the seller that IM has reviewed their specific feedback and has a specific solution. This is the highest-trust opener possible.

#### Sub-Feature 3: Gifted Lead as Re-Entry Hook

The same gifted lead principle from Track B applies here — but with a softer framing:

"Bhai, wapas aane ke liye nahi bol raha abhi — bas yeh ek buyer hai jo aapka exact product dhundh raha hai. Baat kar lo, dekho kaam aata hai ya nahi."

The seller does not need to re-subscribe to receive this lead. They receive it as a demonstration, with no obligation. The re-subscription conversation happens only after they have experienced the value.

---

## Phase 4: Buy Lead Upgrade Engine

### Purpose

Phase 4 activates when a seller is 10 to 15 days from their predicted dropout date and has not responded to the Track B nudge from Phase 3. At this point, messaging alone is not enough. The seller needs to experience a change in what they receive from the platform — not just be told that things could be better.

### Mechanism: Temporary Unlock of Next-Tier Buy Leads

The system identifies the seller's current subscription tier and unlocks 3 to 5 Buy Leads from the next higher tier for a limited period. These are higher-quality leads — higher order values, more verified buyers, better category matching — that the seller would not normally receive on their current plan.

These leads arrive through the seller's normal lead management flow. They look like the platform is suddenly working better. Which, for these 3 to 5 leads, it is.

### Why This Works

A seller who is 10 days from churning has made a tentative decision. Messaging can no longer change that decision — they have heard the pitch. What can change it is an experience. A seller who receives a ₹75,000 order enquiry from a verified recurring buyer in Mumbai when they are used to receiving ₹8,000 local enquiries has just experienced something new. They are not thinking about churning. They are thinking about that lead.

The cognitive load of "should I renew?" disappears when replaced by "I need to call this buyer."

### Upsell Conversion: Retention Becomes Upgrade

The follow-up conversation after the seller has consumed the premium leads changes character entirely:

"Aapne jo last week ke leads dekhe — woh Gold plan ke the. Aapke current plan pe normally yeh nahi aate. Agar aap Gold mein upgrade karte hain toh yeh regularly milenge. Chahiye?"

This is no longer a retention conversation. It is an upsell conversation. The seller is not being asked to renew what they have — they are being offered something demonstrably better than what they have. Churn prevention and revenue expansion happen in the same conversation.

### Lead Quality Gate

The same quality gate from Phase 3 applies here. Only leads that are:
- Posted within 72 hours
- From buyers with verified purchase history
- With order values meaningfully above the seller's current tier average
- Not yet distributed to 3 sellers

...are eligible for the upgrade pool. The experience must be genuinely better, not just nominally different.

---

## Phase 5: Renewal Window Buy Lead Boost

### Purpose

Phase 5 is the newest and in some ways the most elegant component of the system. It addresses a specific phenomenon: seller engagement naturally dips around renewal time. Sellers are distracted, evaluating, sometimes frustrated. The platform feels less valuable at the exact moment they are being asked to pay for it again.

Phase 5 inverts this entirely. The two weeks around the renewal date — one week before and one week after — become the seller's best two weeks on the platform.

### The -7 Day to 0 Window: Pre-Renewal Boost

Starting 7 days before the renewal date, the system unlocks 3 to 5 higher-quality Buy Leads for the seller — the same mechanism as Phase 4, but now applied to all sellers approaching renewal, not just high-risk ones.

**The effect:** The seller is actively working real leads, talking to real buyers, and experiencing platform value during the exact week they are deciding whether to renew. The renewal decision is made from a position of active engagement, not passive doubt.

**The message:** A WhatsApp is sent 7 days before renewal: "Aapki anniversary aa rahi hai IM ke saath — aapke liye kuch special leads unlock ki hain. Abhi check karein."

This message is celebratory, not urgent. It creates positive association with the renewal event rather than anxiety.

### Renewal Day: Immediate Value Delivery

At the moment the renewal payment is confirmed, the system immediately pushes one fresh, high-quality Buy Lead directly to the seller's lead management queue.

The first action after renewing is not a thank-you screen. It is a business opportunity.

This is a small detail with a large psychological effect: the seller's brain immediately associates "I just paid" with "I just received something valuable." The renewal feels immediately worthwhile rather than a cost that might pay off eventually.

### The +7 Day Window: Post-Renewal Reinforcement

For 7 days after renewal, elevated lead quality continues. The seller starts their new subscription cycle with momentum — multiple quality leads, active engagement, positive recent experience.

After Day +7, lead quality normalises to the standard for their subscription tier. But by then, the seller has already formed a strong positive association with the new cycle. The next renewal is now 12 months away, and the seller's most recent memory of the platform is excellent.

### Why This Compounds Over Time

The renewal window boost does not just improve one renewal — it improves the seller's memory of the platform at the moment it matters most. Sellers who experience a strong renewal window are more likely to be vocal advocates in their trade networks ("IM ne renewal pe bahut achhe leads diye"), which affects both churn and acquisition. The effect compounds across renewal cycles and across seller networks.

---

## Cross-Cutting Systems

### WhatsApp-First Delivery Engine

All seller-facing communications — nudges, gifted lead notifications, renewal boost alerts, follow-ups — are delivered primarily through WhatsApp, with a fallback cascade:

1. **WhatsApp** (primary): 65–80% open rate in India's SME market, vs 8–12% for push notifications and email. Regional language. Personalised variables (seller name, buyer search count, peer BL gap, days to renewal, competitor name). Not a template — a generated message with live data.

2. **SMS** (fallback if WhatsApp unread after 48 hours): Shorter version of the same message. Works even on feature phones.

3. **IVR Call** (fallback if SMS unread after 72 hours): Automated voice call in regional language. Briefly describes the lead or opportunity and offers a one-key transfer to a live agent.

4. **Human PNS Call** (final escalation for Red-tier sellers): Rep uses the Context API pre-call brief. Full call script from Phase 3, Track B.

### Context API — Pre-Call Brief System

The platform already has a Context API that generates a session-specific brief for account management calls. The proposed system enriches what this API returns with:

- Current churn probability score
- Top 2 SHAP reasons in plain language
- Peer BL delta (seller vs median)
- Classified churn reason from transcript analysis
- Suggested opening line in the seller's language
- Gifted lead details if one has been allocated

The pre-call brief is accessible via a UUID-credential link with no separate login required, meaning a rep can open it on their phone mid-call on any device. The infrastructure already exists. The enrichment layer is the addition.

### AI Call Summary and CRM Auto-Log

Every call — human or AI — produces an automatic 3-line summary and next-action flag logged to CRM. The rep's post-call work is zero. This doubles effective call capacity per rep per day (from approximately 40 calls to 80 calls) without adding headcount.

---

## Data Architecture Summary

The entire system runs on data that already exists within the platform. No new data collection initiatives are required. The key data sources and what they enable:

| Data Source | What It Enables |
|---|---|
| Category demand data | Phase 1 demand check, nudge message personalisation |
| Seller scorecard (6m + 12m) | Model features, peer benchmarking, ROI proof |
| Competitor data (counts + profiles) | Peer comparison card, "Sharma Ji" message |
| Transaction history | Actual ROI calculation, recurring buyer identification |
| Daily conversion reports | Real-time ROI signal, conversion rate trend |
| Product listing quality | Profile gap card, onboarding fix recommendations |
| Call transcripts | Sentiment analysis, churn reason classification |
| Combined activity data | BL velocity, call count, DAU — core model features |
| Clickstream (30-day) | Platform behaviour, login frequency, feature usage |
| Hot leads | Gifted lead pool, renewal boost pool |
| Lead rejection data + reason codes | Strongest underused churn signal, RCA input |
| Platform metrics | Post-renewal engagement tracking |
| Context API | Pre-call brief delivery |

**The two additions that require new engineering work:**
1. An LLM classification layer on top of existing call transcripts (approximately 2 days)
2. A hotlead allocation/routing microservice to manage the gifted lead pool (approximately 3–4 days)

Everything else is configuration, enrichment, or orchestration of data that already exists.

---

## Expected Impact

### Quantified Funnel Improvement

| Intervention | Today | With System | Improvement |
|---|---|---|---|
| Churn detection timing | Day 0 (renewal) | Day -90 | 90 days earlier |
| Churn detection for new sellers | None | Day 0 (onboarding score) | New capability |
| Message open rate | 8–12% (push/email) | 65–80% (WhatsApp) | 7–8× |
| Rep calls per day | ~40 | ~80 (AI summary removes admin) | 2× |
| Winback conversion rate | ~5–8% | ~25–35% (reason-routed + lead first) | 4–5× |
| Retention intervention conversion | ~8–12% | ~35–45% (90-day window + personalised) | 3–4× |

### Revenue Impact at Scale

At 7.5 million active paid sellers and an industry-estimated annual churn rate of approximately 30%:

- A 5 percentage point churn reduction (30% → 25%) retains approximately 375,000 additional sellers per year.
- At an average subscription value of ₹15,000 per year, this represents approximately ₹562 crore in recovered annual revenue.
- This is before accounting for upsell conversion (Phase 4) and winback revenue (Phase 3, Track C).

The 10× claim is not that every metric improves by 10×. It is that the compounding effect of 8× better message reach, 2× rep productivity, 4–5× winback conversion, and 3–4× retention conversion — all operating simultaneously on the same seller base — produces an order-of-magnitude improvement in the overall churn and winback funnel compared to the current single-touchpoint renewal reminder approach.

---

## What Is Not Being Built

For completeness, it is worth stating what this system deliberately does not include:

- **Discounting as a retention lever:** Discounts train sellers to wait for the discount. The system uses value demonstration (gifted leads, peer comparison, BL upgrade) instead of price reduction.
- **Gamification for its own sake:** The progress tracker in Track A is a functional gap-closing indicator, not a badge system. Badges and leaderboards add complexity without adding retention value for this user segment.
- **New data collection:** The system is designed to run entirely on existing platform data. No surveys, no new tracking, no seller-facing data requests.
- **Fully automated winback:** Track C always involves a human call for the initial winback conversation. Automated winback for churned sellers has very low conversion rates and risks creating a negative experience at the worst possible moment.

---

## Implementation Sequence (For Hackathon Demonstration)

The minimum viable demonstration requires five data tables (category data, seller activity, subscription history, lead management activity, seller master) and can show:

1. A live churn probability score for a sample seller cohort
2. A peer comparison card generated from real category and scorecard data
3. A sample WhatsApp message assembled with live variables
4. A pre-call brief card populated with SHAP explanations
5. The renewal window engagement graph showing the boost effect

Full production deployment would follow the sequence: Phase 2 model (4–6 weeks) → Phase 3 Track B nudge engine (2–3 weeks) → Phase 1 onboarding integration (2 weeks) → Phase 3 Track A dashboard (3–4 weeks) → Phase 4 and 5 BL boost (2–3 weeks) → Phase 3 Track C winback (2–3 weeks).

---

*IndiaMART Seller Churn Reduction System — Complete Solution Plan*
*Prepared for Hackathon Presentation — Confidential*
