# S9 — plan (claude-code subagent)

> A company just guided to product shortages lasting through next year. Does that portend more customer long-term agreements and more durable revenue?

## What we are actually asking

The idea contains two claims stacked on top of each other, and they need to be separated before anything is testable.

The first claim is behavioral and fairly mechanical: when a supplier tells the market it cannot meet demand for the next several quarters, customers respond by trying to lock in allocation — long-term agreements, capacity reservations, take-or-pay commitments, prepayments and capacity deposits. That claim is close to a truism and I expect it to be true in the data. It is worth measuring anyway, because the effect size and the *type* of commitment are the interesting part.

The second claim is the one that carries money: that this contracting activity makes the supplier's revenue more durable — higher, less volatile, and slower to mean-revert than a comparable non-constrained firm's. This is much less obviously true, and the prior from the 2021–2023 semiconductor cycle points the other way. Companies that converted shortage into long-term commitments (Microchip's Preferred Supply Program is the canonical case, ON Semiconductor's and Wolfspeed's LTA books close behind) saw those commitments renegotiated, deferred or quietly abandoned once lead times normalized, and several of them printed steeper revenue drawdowns than peers who had refused to sign LTAs at all — Texas Instruments being the deliberate abstainer. If that generalizes, shortage guidance plus a rush of LTAs is a cycle-peak marker, not a durability signal. (Those examples are from my own recollection and are illustrative only; the analyst should verify each before it appears in any writeup.)

So the plan is deliberately two-sided. The hypothesis is stated as: **firms that guide to multi-quarter product shortages subsequently show a significant increase in disclosed long-term customer commitments (H1), and this increase predicts more durable revenue over the following eight to twelve quarters only in the subset where the commitments are cash-collateralized and the shortage is supply-caused rather than demand-caused (H2).** The null we are genuinely willing to accept is that H1 holds, H2 fails, and shortage-plus-LTA is on net a negative forward signal.

## Defining the event and the outcomes

**Shortage guidance.** Build the event tape from earnings call transcripts (S&P Capital IQ Transcripts, or AlphaSense if that is the seat we have) plus 10-Q/10-K MD&A and 8-K Item 2.02 exhibits, US-listed, 2003 through 2026Q2. An event requires a management statement (prepared remarks or Q&A, executives only, not analysts) that asserts supply cannot meet demand *and* attaches a forward horizon of at least four quarters — "through next year," "at least into the second half of 2027," "sold out through," "allocation through." The four-quarter horizon is doing real work: it is what separates this from routine quarterly tightness, and it matches the language in the research idea.

Do the classification with an LLM over sentence windows, but anchor it: hand-label 800 snippets stratified across sectors and years, hold out 200 for scoring, and require Cohen's kappa of at least 0.75 against a second human coder before the classifier is trusted. Tune the threshold for precision over recall — a diluted event tape is the fastest way to kill this study. Record, for each event, the transcript timestamp (not the filing date) so nothing is look-ahead contaminated.

Also code, from the same text, an **attribution label**: is the constraint blamed on a supply-side cause (fab fire, natural disaster, export control, qualification bottleneck, single-source component, capacity time-to-build) or on demand exceeding plan? This split is the closest thing we have to identification and it should be built in from day one, not added later as a robustness check.

**Long-term agreements (H1 outcomes).** Three measures, triangulated because each is individually incomplete:
1. 8-K Item 1.01 material-definitive-agreement filings and EX-10 exhibits mentioning supply, capacity reservation, take-or-pay, minimum purchase, or prepayment — counted per firm-quarter, with the exhibit hand-coded for whether it is binding, whether it carries a customer prepayment or deposit, and whether a termination fee exists.
2. Transcript mentions of LTA/long-term agreement/capacity reservation/prepayment normalized by transcript length.
3. Balance-sheet evidence: `us-gaap:ContractWithCustomerLiabilityCurrent` and `Noncurrent`, plus customer deposits/advances, from the SEC Financial Statement Data Sets XBRL tags, scaled by trailing-twelve-month revenue. This is the hardest to game and should be the primary of the three.

**Durability (H2 outcomes).** Remaining performance obligation (`us-gaap:RevenueRemainingPerformanceObligation`) scaled by TTM revenue, and separately the share expected to be recognized beyond twelve months. Then the actual revenue path: quarterly YoY growth from t+1 to t+12, the depth of the worst four-quarter drawdown in the t+4 to t+12 window, the AR(1) persistence coefficient of YoY growth estimated on rolling windows, realized revenue volatility, and gross margin over the same path. Include margin explicitly — prepaid capacity repaid in product at fixed prices produces revenue that persists but does not create value, and revenue-only durability measures will not catch that.

**Market outcomes.** CAR(-1,+2) around the guidance event using a Fama-French five-factor plus momentum model, and forward 12- and 24-month DGTW-adjusted returns, to answer whether any of this is already priced.

## Data

Compustat Fundamentals Quarterly for financials, using the **unrestated/preliminary** quarterly file so we see what was reported at the time; CRSP for returns and the CRSP/Compustat merge; IBES for consensus revenue revisions and the dispersion of forward-year estimates (a good proxy for how legible the shortage is to the sell side); Compustat Segments and the ASC 280 major-customer disclosures for customer concentration; Ken French's library for factors. Order backlog (Compustat `ORDBKLG`) is worth pulling but it is voluntary, sparsely populated and inconsistently defined — treat it as supporting evidence only.

For the macro control, ISM Manufacturing supplier-deliveries and backlog-of-orders indices give an economy-wide shortage diffusion measure; for semis specifically, SIA billings and SEMI book-to-bill. These matter because without them we will simply rediscover the business cycle.

Finally, assemble a hand-built list of exogenous supply disruptions to sharpen the attribution split — the Renesas Naka fire and AKM fire, Winter Storm Uri, the Taiwan drought and the 2024 Hualien earthquake, the Ever Given, port actions, and the gallium/germanium and Nexperia-style export-control episodes. Events whose shortage narrative maps to one of these are the cleanest supply-driven cases.

## Estimation

Sample: US-listed non-financials, market cap above $300m at event, with at least eight quarters of pre-event data. Expect somewhere in the range of 400–900 qualifying events; if fewer than 120 survive outside the 2020–2022 window, the study collapses into a single macro episode and we should say so rather than dress it up.

Design: a cohort-stacked event study with **Callaway and Sant'Anna (2021)** group-time average treatment effects using not-yet-treated firms as controls, over a window of t-8 to t+12 quarters. Report **Sun and Abraham (2021)** interaction-weighted estimates and **Borusyak–Jaravel–Spiess** imputation as robustness. Do not run a naive two-way fixed-effects specification with leads and lags as the headline — with treatment this staggered the negative-weighting problem is severe.

Control construction: within four-digit GICS sub-industry, propensity-score match on log assets, revenue growth over t-4 to t-1, gross margin, capex/PP&E, inventory days and leverage; 1:3 with replacement, caliper 0.05, and require standardized mean differences below 0.10 on every covariate before proceeding.

Standard errors two-way clustered on firm and event-cohort-quarter. If the number of cohorts falls below 40, use wild cluster bootstrap-t.

For the durability outcomes, complement the event study with **Jordà local projections** for horizons h = 1…12, with firm and calendar-quarter fixed effects and the ISM supplier-deliveries index plus industry revenue growth entered as contemporaneous controls. This is the specification that answers "does this survive controlling for the cycle," which is the whole ballgame.

The key cut, run as a pre-specified interaction rather than a fishing expedition: shortage events split by (a) supply-caused vs demand-caused attribution, (b) whether the resulting agreements carry customer cash — prepayment or deposit — versus non-binding capacity reservations, (c) customer concentration, (d) whether the firm simultaneously ramps capex (capex/sales rising more than 50% over the following four quarters), which mechanically undermines the scarcity that produced the commitments, and (e) qualification/switching cost, proxied crudely by industry (aerospace, medical, auto-grade silicon high; commodity components low). My prior is that (a) and (b) carry essentially all of the durability effect and that (d) reverses its sign.

## Validation

Pre-trends first and honestly: joint F-test on leads t-8 through t-2, and we require both p > 0.10 and all lead coefficients under 0.25 standard deviations of the outcome. Then report **Rambachan and Roth honest-DiD** sensitivity and state the breakdown value of M̄ at which the t+8 effect loses significance. If the result only survives at M̄ near zero, it is not a result.

Placebos: randomly assigned pseudo-event dates within the same firm-industry-year cells, 1,000 draws, to get an empirical null; and a placebo outcome (SG&A/sales) that should show nothing.

Sample splits: estimate on 2003–2015 and treat 2016–2026 as a holdout; separately re-estimate excluding 2020Q2–2022Q4 entirely. If the effect exists only in the COVID window, the honest conclusion is that we have one observation of a supply-chain regime, not a generalizable relationship.

Bottom-up reconciliation, which I would weight as heavily as the panel: pick twelve firms with large disclosed LTA books and trace, by hand, announced contract face value → subsequent RPO → revenue actually recognized, computing a realization ratio for each. If the panel says durability improved but the case studies show realization ratios of 0.5, the panel is measuring an accounting artifact. This step is also the one that will surface renegotiations, which never appear cleanly in structured data.

Investability check: form a sector- and beta-neutral long/short book — long shortage-guiders flagged durable by the moderator model, short those flagged fragile — rebalanced quarterly, 20bps round-trip costs, with an ADV-based capacity estimate. Report information ratio and turnover. A relationship that is real but unimplementable should be reported as such.

## Pitfalls I would watch

**The cycle-peak problem is the central threat.** Shortage guidance is largely an indicator that demand is running hot, and demand running hot is a mean-reverting state. Any positive H2 result must clear the cycle controls and the supply-vs-demand attribution split, or it is just a long position on the peak of the manufacturing cycle wearing a disguise.

**Shortage talk is partly a negotiating instrument.** Telling customers the shortage will last a year is how you get customers to sign LTAs and accept price increases. The disclosure is endogenous to the commercial strategy. Test this directly: does shortage language predict a physical constraint (falling inventory days, rising lead times, capacity utilization) or only rising ASPs? If only price, we are studying rhetoric.

**Double ordering.** Customers over-order across multiple suppliers during shortages, which inflates backlog and LTA face value with demand that does not exist. Measure backlog-to-shipment *conversion*, never backlog level.

**RPO is not comparable across firms.** ASC 606 adoption in 2018–19 breaks the series entirely; practical expedients let firms exclude contracts under one year and variable consideration; some firms exclude cancellable amounts and some do not. Use within-firm changes only, and never level comparisons across companies.

**Disclosure selection.** Firms announce favorable LTAs and stay quiet about unfavorable or cancelled ones. Absence of an 8-K is not absence of a contract. This biases H1 upward and adds classical measurement error to H2 that attenuates toward zero — so a null on H2 is weaker evidence than a positive.

**Event clustering.** Most events will land in semis, autos and aerospace in 2021–22. The effective sample size is far smaller than the nominal one. Report the cohort-year histogram in the first exhibit; if any single cohort-year holds more than 40% of events, present the finding as one episode with wide error bars.

**Enforceability is social, not legal.** "Non-cancellable" holds up in court and dissolves in a relationship where the counterparty is 30% of your revenue. Expect renegotiation, and code for it.

**Price versus volume.** Shortage-period revenue is disproportionately price, and price gains unwind faster than volume gains. Decompose wherever unit data exists.

**Multiple testing.** Pre-register the primary outcome (contract liabilities/TTM revenue for H1; the t+8 revenue-path coefficient for H2) and apply Romano–Wolf stepdown p-values across the moderator family.

## Sequencing and kill criteria

Six weeks. Week 1: pull Compustat/CRSP/XBRL and stand up the transcript corpus. Week 2: hand-label, train and score the shortage classifier and the attribution label; deliver the event tape and its cohort histogram. Week 3: matching, balance tables, pre-trend plots — this is the first go/no-go. Week 4: H1 estimation plus the twelve hand-built case studies. Week 5: H2 local projections and the moderator interactions. Week 6: honest-DiD sensitivity, holdout, backtest, writeup.

Stop the project at the end of week 3 if fewer than 120 events survive outside 2020–2022, or if the pre-trend test fails on the primary outcome. Stop at the end of week 5 if H1 holds but the t+8 to t+12 revenue path is flat or negative across every moderator cut — and write that up, because "shortage guidance plus a wave of LTAs is a late-cycle sell signal" is a more valuable finding than the one the idea was hoping for.
