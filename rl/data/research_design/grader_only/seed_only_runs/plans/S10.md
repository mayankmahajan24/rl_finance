# S10 — plan (claude-code subagent)

> A company went notably defensive around its annual vendor licence renegotiation. Is this a stronger near-term risk to margins than management has communicated, or is it not a sign of weakening fundamentals?

## What the idea actually claims, and how to make it testable

As stated the idea bundles three separate claims that need to be separated before anyone touches data. First, a *measurement* claim: management's behaviour on the call was unusually evasive relative to some baseline. Second, an *economic* claim: the licence in question is large enough that a bad renewal outcome would matter to gross margin. Third, an *information* claim: the evasiveness carries incremental news — i.e. it tells you something that is not already in guidance, consensus, or the price.

All three have to hold for the idea to be tradeable. Only the second is cheap to test, so it goes first and acts as a kill switch. If a plausible worst-case renewal cannot move gross margin by more than about 30bp on a full-year basis, the language analysis is irrelevant and the analyst should stop on Wednesday of week one rather than spend three weeks building an NLP pipeline to detect a rounding error.

The framing question also has an asymmetry worth naming: "defensive" is an observation about one company on one call, which is a sample of one. You cannot infer anything from n=1 without a reference class. So the plan has two tracks running in parallel: a bottom-up single-name case (what is the licence worth, what has management said, what does consensus embed) and a cross-sectional base-rate study (across many firms and many renewal events, does measured defensiveness predict subsequent margin disappointment, and under what conditions). The single name is scored against the base rate at the end.

## Hypotheses, stated so they can fail

**H1 (primary).** Conditional on a material vendor-licence renewal being live, an increase in management defensiveness on the topic predicts negative gross-margin surprise over the following four quarters, measured against the consensus margin path as of the day before the call.

**H0.** Defensiveness is uninformative about subsequent margin outcomes once you control for the firm's habitual communication style, the overall tone of the call, and the pre-call revision trend.

**H2 (the confound that matters most, and the one I expect to be true).** Defensiveness during a renewal is largely *mechanical*: management cannot discuss terms of a contract that is still under negotiation without damaging its own bargaining position, and counsel will have told them so. Under H2, defensiveness predicts nothing when the contract is still open at the call date, and predicts margin damage only when the contract was already signed at the call date — because then management knows the answer and is choosing not to give it. The interaction of defensiveness with contract status is therefore the single most informative test in this plan, not a robustness check.

**H3.** Any predictive content is concentrated in the tail rather than the mean: defensiveness raises the probability of a large negative margin surprise without much shifting the median outcome. This matters because the question asked is about *risk*, not about expected value.

## Data

*Transcripts.* S&P Capital IQ Transcripts, accessed via WRDS, 2010–2025, Russell 3000. Capital IQ is the right source rather than LSEG StreetEvents because it tags speaker identity, role, and — critically — pairs analyst question components with executive answer components, which is what the defensiveness measure needs. Pull the *original* transcript version and its timestamp; Capital IQ issues corrected versions later and using the corrected text introduces look-ahead.

*Financials.* Compustat Fundamentals Quarterly for REVTQ, COGSQ, XSGAQ, XRDQ, and the derived gross margin; Compustat Segment for mix shifts that can masquerade as margin damage.

*Line-item consensus.* Visible Alpha Standardized Data for gross margin and COGS consensus — IBES only carries EPS and revenue, and an EPS surprise conflates the margin question with buybacks, tax, and below-the-line items. Visible Alpha coverage is thin before roughly 2014 and skewed to large caps; where it is missing, fall back to IBES EPS surprise as a noisier secondary outcome and flag those observations, do not silently drop them.

*Contract facts.* SEC EDGAR full-text search for Exhibit 10 material agreements, amendments, renewals, and termination notices naming the vendor; 8-K Item 1.01/1.02 filings; confidential-treatment requests (which themselves signal an economically material agreement). The filing date of the executed amendment is what determines the "open vs signed at call date" split for H2. Where no filing exists, use the vendor's own disclosures and 10-K risk-factor language to date the renewal window, and mark the observation as low-confidence.

*Counterparty side.* FactSet Revere supply-chain relationships to identify licensor–licensee pairs; the vendor's own transcripts and filings, which frequently discuss the same renewal from the other side and provide an independent read on how it went.

*Prices.* CRSP daily for returns; TAQ for the intraday reaction in the call window; OptionMetrics IvyDB for changes in 30-day implied volatility and 25-delta skew across the call, which is the cleanest available read on whether the market perceived the call as raising tail risk.

*Ancillary.* Lightcast or Revelio job postings for procurement, vendor-management, and licensing roles at the company — a hiring spike in contract negotiation roles is weak but independent corroboration that something real is happening.

## Measuring defensiveness

This is where the study lives or dies, so the construct is defined precisely, pre-registered before outcomes are examined, and built from components that are individually interpretable.

Restrict attention to *topic-relevant* Q&A: question–answer pairs where the question mentions the vendor, the licence, the renewal, or the cost line it sits in. Identify these with a keyword seed list expanded by embedding similarity, then have a human confirm the topic tags on a 200-pair audit sample.

Seven components, each computed on topic-relevant pairs:

1. **Non-answer rate.** Fraction of topic questions whose answer contains no new quantitative or dated content — no number, no range, no timeline, no commitment. Scored by rubric, 0/1/2.
2. **Deflection.** Answer pivots to a different subject than the one asked. Binary per pair.
3. **Hedging density.** Hedge and uncertainty terms per hundred words, using the Loughran–McDonald uncertainty and weak-modal lists plus Hyland's hedge list. Crucially this is computed as a *difference*: the same speaker's hedging density on topic-relevant answers minus their density on non-topic answers on the same call. That within-call, within-speaker differencing removes the CFO who is simply a vague person, which a raw tone score would flag every quarter.
4. **Analyst persistence.** Number of follow-ups and re-asks on the topic, and whether a second analyst returns to it. This is generated by third parties rather than by management, so it is the least gameable component and I would weight it heavily if weights were fitted — they are not, see below.
5. **Speaker substitution.** CEO or IR takes the answer from the CFO, or the answer is handed off mid-topic.
6. **Prepared-remarks avoidance.** The topic was covered in prepared remarks in the prior-year equivalent call and is absent this year, despite the renewal being live.
7. **Guidance-scope narrowing.** Margin guidance moves from point to range, widens, is qualified as "subject to renewal", or is withdrawn.

Each component is z-scored within sector-quarter, then equal-weighted into a composite, DEF. **Equal weights, deliberately** — fitted weights on a few hundred events will overfit, and equal-weighting a set of positively correlated indicators is close to optimal in small samples. "Notably defensive" is pre-specified as DEF exceeding the firm's own trailing eight-quarter mean by more than 1.5 standard deviations, so the threshold is within-firm and does not simply pick out habitually opaque management teams.

Scoring is done by an LLM with a structured-output rubric on the full sample, but only after it is calibrated: a human analyst scores 100 randomly drawn events blind (transcripts stripped of dates and of any reference to subsequent periods, so the scorer cannot see how it turned out), and the LLM must reach a correlation of at least 0.7 with the human composite and Krippendorff's alpha of at least 0.6 on subcomponents before it is trusted on the remainder. Run each transcript through the scorer twice with question order permuted; discard components whose test–retest correlation is below 0.8.

## Sample and estimation

The event universe is firm-quarters in which a material vendor-licence renewal was live, identified from the union of EDGAR contract filings, risk-factor concentration language naming a licensor, and call mentions. I would expect somewhere in the range of 300–800 usable events across 2010–2025 after requiring Visible Alpha margin coverage. If it comes in under 200, widen from licences to supplier and distribution contract renewals generally and treat licence-specific results as a subsample.

The primary outcome is **standardized gross-margin surprise**: realized gross margin over t+1 to t+4 minus the Visible Alpha consensus gross-margin path as of five trading days before the call, divided by the firm's trailing twelve-quarter standard deviation of gross margin. Secondary outcomes, pre-specified and reported as a family: 90-day consensus gross-margin revision; realized COGS-to-revenue; an indicator for a guidance cut; and the H3 tail indicator, a surprise worse than −1.5 standard deviations. Falsification outcomes: revenue surprise and non-licence operating expense, which should show materially weaker relationships if the mechanism is really about licence cost rather than about generic bad news.

Primary estimator: panel regression of margin surprise on DEF with firm fixed effects and sector-by-quarter fixed effects, standard errors two-way clustered on firm and calendar quarter. Controls: lagged margin level and four-quarter trend, revenue growth, the current-quarter sales surprise, log size, leverage, analyst count and dispersion, overall Loughran–McDonald call tone, call length, and a CFO-turnover flag. The lagged revision trend is not optional — without it you will measure a margin problem that was already visible and simply re-detect it in the language.

Then the three tests that actually discriminate between the stories:

- **H2 test.** Interact DEF with a contract-status indicator (open versus signed at the call date, dated from the EDGAR amendment). Report the two conditional effects separately, not just the interaction coefficient.
- **Dose–response.** Interact DEF with licence exposure, defined as estimated licence cost as a share of COGS, bucketed into terciles. A real mechanism should show a monotone gradient. A flat gradient means DEF is picking up generic pessimism, which is a known and already-priced effect.
- **Habituation.** Interact DEF with prior-year DEF. If the effect is entirely in first-time defensiveness, that is informative about what the signal is.

For H3, quantile regression at the 10th and 25th percentiles of the surprise distribution, plus a logit on the large-negative-surprise indicator. Report marginal effects in basis points of margin and in probability terms, not just t-statistics.

As a robustness design, coarsened exact matching on sector, size decile, and pre-event margin trend, then nearest-neighbour matching with replacement on a propensity score built from the control set, caliper 0.05, Abadie–Imbens bias-corrected standard errors. If the matched ATT and the fixed-effects coefficient disagree by more than a factor of two, trust neither and investigate the overlap.

## Validation

Pre-register the DEF formula, the primary outcome, the primary estimator, and the H2 interaction in a dated file committed to the repo before any outcome variable is merged in. Fit on 2010–2020 and hold 2021–2025 completely untouched; the out-of-sample coefficient must retain the same sign and at least half the magnitude to proceed.

Three placebos. Shuffle DEF within sector-quarter — the effect must vanish. Compute DEF on calls of firms with no licence exposure — it should not predict margin surprise, or if it does, DEF is a general bad-news detector and the licence story is decoration. Shift the outcome window back four quarters so the "outcome" precedes the call — this pseudo-outcome must be null, and if it is not, the pre-trend controls are inadequate.

Across the secondary outcome family, report Romano–Wolf stepdown adjusted p-values. One primary outcome, one primary estimator, everything else labelled as secondary — otherwise with this many defensible specifications something will clear 5% by construction.

Economic validation: convert the estimated effect into basis points of gross margin and into a expected return on an event-window position, net of realistic costs, and check whether the option market already prices it — if implied vol and skew jump around these calls, the tail risk is known and the idea is not a source of return even if the statistics hold.

## The single-name work, which runs first

Independently of all the above, build a licence cost bridge from the bottom up in week one. Estimate the licence line as a share of COGS from segment disclosure, historical step-ups at prior renewals, the vendor's published rate card or disclosed take rate, and — where the vendor discloses customer concentration — the vendor's own reported revenue from this customer. Then compute gross-margin impact under +10%, +20%, and +30% price scenarios, and a volume or scope-change scenario. Set that against three reference points: what management has actually guided (quote the exact language and the exact numbers), what Visible Alpha consensus embeds for gross margin over the next four quarters, and your bottom-up range. The answer to the researcher's question is the gap between the second and the third, and defensiveness is only evidence about how likely the gap is to close badly.

Sensible calendar: week one, contract facts, cost bridge, consensus reconstruction, go/no-go on materiality. Week two, event universe construction and DEF scoring with human calibration. Week three, estimation, H2 and dose–response tests, out-of-sample check, write-up.

## Pitfalls

The legal-constraint confound (H2) is the one most likely to produce a false positive, and it will be invisible unless contract status is dated properly. Related, and worse: management may be defensive precisely because the renewal went *well* and they do not want to signal to the vendor or to competitors that they got favourable terms. Defensiveness is directionally ambiguous, and any writeup claiming it is one-signed needs to say why.

Reverse causality — defensiveness following a margin problem already visible in revisions — is handled by the pre-trend control and the shifted-window placebo, but check the residual correlation between DEF and the prior 90-day revision directly and report it.

Selection: renewals get discussed on calls mainly when analysts ask, and analysts ask mainly when the stock has been weak. Include prior six-month return as a control and report how much of the sample would be lost if you required the topic to appear in prepared remarks rather than Q&A.

Transcript revision look-ahead, Visible Alpha backfill and coverage skew toward large caps, and language regime drift in 2020 (exclude 2020H1 as a robustness cut) are all live data-integrity risks.

Scorer contamination is the subtlest one: any human or model that can see the eventual outcome will find defensiveness in the calls that went badly. Blind masking is not optional.

On compliance: expert-network calls about a specific live contract between two named parties are a genuine MNPI hazard. Do not speak to current employees of either the company or the vendor about this negotiation; route any expert call through compliance with the topic scoped to industry-level licensing economics.

Finally, pre-commit to the null being an acceptable and reportable answer. "Defensiveness during an open negotiation is normal and carries no incremental margin information, and the licence can move gross margin by at most 25bp anyway" is a complete, useful answer to the question asked, and the plan should be run in a way that can produce it.
