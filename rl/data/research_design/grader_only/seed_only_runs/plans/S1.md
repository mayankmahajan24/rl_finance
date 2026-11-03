# S1 — plan (claude-opus-5)

> Do customers who start trading on Kalshi subsequently reduce their spend and activity on DraftKings? We have a credit-card and bank-deposit transaction panel covering both.

---

# Does Kalshi cannibalize DraftKings? A transaction-panel research plan

## 1. The question, sharpened

The loose version of this question ("is Kalshi a threat to DKNG?") is not estimable. Three distinct sub-questions are, and they have different investment implications:

**Q1 — Substitution intensity.** Among people who already had an active DraftKings relationship, how much does DK net deposit volume fall in the six months after they begin funding a Kalshi account, relative to statistically similar people who did not adopt Kalshi?

**Q2 — Incrementality.** What share of Kalshi adopters had *no* online sportsbook or DFS activity in the prior twelve months? If Kalshi is mostly recruiting non-bettors (politics traders, Robinhood-adjacent retail speculators, users in non-legal states), the share-shift narrative is wrong even if Q1 is large.

**Q3 — Scale.** How many households does this apply to, and what does the per-household effect translate to in DKNG B2C revenue dollars?

The investable number is the product of the three. A −25% substitution effect concentrated in 400k households is noise; a −10% effect across four million households that skews toward high-value bettors is a multi-point revenue headwind. The plan below produces all three, with Q1 as the econometric core.

**Primary estimand:** the ATT on cumulative DraftKings net deposits over event-months +1 through +6, for households with ≥$100 of DK net deposits in the twelve months prior to Kalshi adoption, expressed both in dollars and as a percentage of the matched-control counterfactual.

**Falsification:** the hypothesis is wrong if the 6-month ATT is statistically indistinguishable from zero with a confidence interval tight enough to exclude a −10% effect, *and* the same design detects the expected displacement in a benchmark case (Fanatics Sportsbook adoption, described below).

## 2. Data

**Primary panel: Envestnet Yodlee or MX bank-linked transaction data.** This must be a *bank-linked* panel, not a card panel. Kalshi accounts are funded predominantly via ACH and debit; Consumer Edge and similar card-transaction panels will systematically miss the treatment event. The panel needs both debits and credits at the account level so that withdrawals are observable.

**Secondary panels for replication:** Facteus (debit/prepaid, skews lower-income and younger — a population highly relevant here) and Bloomberg Second Measure. Run the identical script on at least one secondary panel; disagreement in sign is disqualifying, disagreement in magnitude beyond 2× is a flag to investigate rather than average away.

**Merchant identification is the first week of work and the most common place these studies quietly break.** Build and hand-audit a regex dictionary:
- Kalshi: `KALSHI`, `KALSHIEX`, `KALSHI INC`, plus the processor descriptors Kalshi has used (Zero Hash for crypto rails, and its ACH originator strings). Pull 500 random matched transactions and read them.
- DraftKings: `DRAFTKINGS`, `DK SPORTSBOOK`, `DRAFTKINGS NJ/PA/...`, `DKNG`. Decide explicitly whether to fold in Jackpocket (DK-owned lottery courier) and Golden Nugget Online. Recommendation: exclude Jackpocket from the primary DK outcome, track it separately.
- Competitor wallet: FanDuel, BetMGM, Caesars, ESPN Bet/Penn, bet365, Fanatics, Underdog, PrizePicks, Sleeper, Hard Rock, plus offshore (Bovada, MyBookie) and sweepstakes (Chumba, Stake.us, McLuck).
- Adjacent: Robinhood, Webull, Coinbase, Polymarket (US access via the QCX acquisition, late 2025).

**Critical known gap:** prediction-market volume routed through Robinhood Derivatives or Webull never produces a Kalshi merchant string. Those users appear as untreated. Estimate the size of this gap from Kalshi's disclosed volume mix and Robinhood's reported prediction-market contract counts; if Robinhood-routed users are a large share, the measured ATT is attenuated toward zero and you must say so. A partial fix: define a secondary treatment group as households with a step-change in Robinhood ACH funding that coincides with the March 2025 prediction-markets launch, but treat this as suggestive only.

**Coverage window:** January 2023 through the most recent complete month. Cohorts of interest are (a) the election cohort, Sept–Nov 2024, and (b) the sports-contract cohorts, Jan 2025 onward. Analyze these separately — the election cohort is a different animal and pooling them will produce an average that describes nobody.

## 3. Sample construction

**Panel presence:** a household-month counts as "present" if it shows ≥10 transactions and ≥1 inflow of ≥$500 (payroll/transfer proxy). Require presence in ≥10 of the 12 pre-period months and ≥5 of the 6 post-period months. Attrition is not random — a household that blows up its bank account may drop out — so also run the whole thing on an unbalanced panel with inverse-probability-of-attrition weights, where the attrition model is a logit on pre-period gambling intensity, income proxy, and balance volatility.

**Treatment definition:** first outflow to Kalshi of ≥$25 in month *t*, with zero Kalshi transactions in the prior 12 months. The $25 floor screens out promotional micro-deposits and $1 account verifications.

**Treated sample for Q1:** treated households with ≥$100 DK net deposits and ≥3 DK deposit transactions in the 12 months before adoption. This is the population the substitution question is about.

**Control pool:** households present in the panel, never observed with any Kalshi or Polymarket transaction through the end of the sample, meeting the same DK activity screen.

**Matching:** logit propensity score on pre-adoption DK net deposits (level, in deciles), 6-month DK trend, number of distinct sportsbooks used, total gambling wallet size, monthly inflow (income proxy), state, panel tenure, Robinhood/Coinbase indicator, and calendar month of pseudo-adoption. Match 1:3 nearest-neighbor with replacement, caliper 0.05 on the logit index. Report standardized mean differences on all covariates post-match; target |SMD| < 0.10 on every one. Any covariate that won't balance goes into the outcome regression as a control.

## 4. Estimation

**Primary specification: Callaway–Sant'Anna (2021), doubly-robust, with not-yet-treated households as the comparison group**, stacked across monthly adoption cohorts, aggregated to a dynamic event study over −12 to +6 and to a simple 6-month ATT. Do not use two-way fixed effects with staggered adoption; the negative-weighting problem is severe here because cohort effect sizes plausibly grow over time as Kalshi's sports product matured.

**Outcomes, in order of priority:**
1. DK net deposits (deposits minus withdrawals), dollars per month. This is the economically meaningful measure — it approximates the household's contribution to DK gross gaming revenue. Gross deposits overstate everything because of recycled winnings.
2. Indicator: any DK deposit in the month (extensive margin).
3. DK deposit count.
4. Churn: zero DK deposits for three consecutive months.
5. Total gambling-wallet net deposits (all operators). This distinguishes "Kalshi took DK's share" from "Kalshi expanded this household's total gambling budget."
6. DK share of gambling wallet.

Because net deposits are zero-inflated and can be negative, run the primary in dollar levels with winsorization at the 99.5th percentile, and a companion in Poisson pseudo-maximum-likelihood on gross deposits (handles zeros, gives a multiplicative interpretation). Cluster standard errors by household; also report state-clustered errors.

**Second design — the regulatory placebo.** Kalshi is available nationwide; DraftKings' online sportsbook is not. For households in states where DK sportsbook is illegal (CA, TX, FL, GA, MN, WI, etc.), Kalshi adoption *cannot* cannibalize DK sportsbook, though it could still hit DFS. Estimate the same ATT separately in legal and non-legal states. A large negative effect in legal states and ~zero in non-legal states is strong evidence of genuine substitution; a similar effect in both means you are picking up a household-level shock (a losing streak, a budget cut, a life event) that causes both Kalshi adoption and DK reduction.

**Third design — the competitor benchmark.** Run the identical pipeline with "first funds Fanatics Sportsbook" as the treatment. Fanatics is an unambiguous direct substitute for DK. This calibrates the scale: if new-Fanatics adoption displaces 35% of DK net deposits over six months and Kalshi adoption displaces 12%, you can say Kalshi is roughly a third as cannibalistic as a conventional competitor, which is a far more useful sentence than any standalone coefficient.

**Fourth design — state-level supply shocks.** Several states issued cease-and-desist orders against Kalshi in March–April 2025 (NV, NJ, MD, AZ, MT, OH among them), with varying litigation outcomes. Where an order actually suppressed Kalshi activity — verify in the panel that state-level Kalshi funding flows dropped — run a state-level DiD on aggregate DK net deposits per panelist. This uses variation that is not chosen by the household. It is noisy and the treated-state count is small, so treat it as corroboration, not the headline.

## 5. Heterogeneity (pre-specified, not fished)

Cut the primary ATT by: pre-period DK net-deposit quintile (the top quintile is most of the revenue and is the number that matters); DK-legal vs non-legal state; whether the adopter's Kalshi activity is sports-contract-timed (funding concentrated Sept–Feb, around NFL) versus election- or crypto-timed; DK tenure (<12 months vs longer); and adopter age proxy. Adjust for multiplicity across these cuts with Romano–Wolf stepdown; report both raw and adjusted p-values.

## 6. Validation

**Panel-to-reported reconciliation.** Aggregate panel DK net deposits by quarter, scale by panel coverage, and regress on DKNG reported B2C revenue for 2022–2025. Require R² > 0.90 on levels and a year-over-year growth tracking error under ~3pp; if the panel can't track the company it can't measure a 10% effect on a subpopulation. Do the same for FanDuel against Flutter's disclosed US revenue as an independent check that the tracking isn't a DK-specific artifact.

**Pre-trends.** Joint test on event-time coefficients −6 through −2; require p > 0.10. Then run Rambachan–Roth honest DiD and report the breakdown value of M — the degree of post-treatment differential trend that would overturn the sign. If the result only survives under an implausibly strong parallel-trends assumption, say so in the first paragraph of the writeup, not the appendix.

**Placebo outcomes.** Grocery, fuel, streaming subscription, and utility spend should show zero effect. A negative effect on all of them means you've identified households under financial stress, not substitution.

**Placebo timing.** Assign each treated household a fake adoption date 9 months before the real one, drop the real post-period, re-estimate. Should be null.

**Randomization inference.** 1,000 draws assigning treatment status at random within matched strata; compare the true ATT to the permutation distribution.

## 7. From coefficient to investment view

Compute: (adopter count in panel / panel size) × US adult population, cross-checked against Kalshi app downloads and MAU from Sensor Tower and against Kalshi's disclosed notional volume. Multiply the national adopter estimate by the share who were pre-existing DK customers, by the per-household 6-month dollar ATT, by a net-deposit-to-revenue conversion (DK's historical net-deposit-to-GGR relationship from the panel-to-reported regression). Present this as a range with the panel-scaling uncertainty made explicit — it will be the widest source of error, wider than the econometric standard error, and the writeup should lead with that.

## 8. What will go wrong

**Selection is the whole game.** People adopt Kalshi at moments when something is already changing — a losing streak, an account limit imposed by DK, a self-exclusion, a new interest in politics. The event study will very likely show DK spend *rising* into the adoption month (escalation) and then falling. That reversion is not causal substitution; it's mean reversion plus selection on a transient shock. This is why the regulatory placebo and the Fanatics benchmark exist. Budget real time for it.

**Invisible Kalshi.** Robinhood- and Webull-routed prediction market activity, crypto/USDC funding, and any wallet-to-wallet rails are unobserved. All of this pushes the estimate toward zero. Quantify the leakage before publishing a magnitude.

**Net vs. gross.** If withdrawal transactions are dropped or misclassified, "net deposits" becomes gross deposits and every result is contaminated by bankroll recycling. Audit a sample of 200 DK-active households by hand, reconstructing their deposit/withdrawal ladder.

**Seasonality and cohort composition.** Kalshi's sports adoption is concentrated in football season; DK's revenue is too. Any design without calendar-month controls that are cohort-specific will attribute NFL seasonality to Kalshi. Callaway–Sant'Anna handles this if the control group is drawn from the same calendar months — verify that it is.

**Panel representativeness.** Yodlee-type panels skew toward PFM-app users and underrepresent the high-frequency, high-value bettor who drives DK's revenue. Reweight to DK's disclosed monthly-unique-payer and ARPU distribution where possible; at minimum, report the panel's DK ARPU against DKNG's disclosed figure and disclose the gap.

**Equilibrium effects.** The ATT is measured relative to controls in the same market, so any economy-wide DK response (promo intensity, ad spend) is differenced out. If Kalshi's presence causes DK to spend more on promotions for *everyone*, the household-level estimate understates the P&L impact. Flag this as a directional caveat rather than trying to estimate it.

## 9. Sequencing

Week 1: merchant dictionaries, hand-audit, panel-to-reported reconciliation for DKNG. Do not proceed if reconciliation fails. Week 2: cohort and control construction, matching, balance tables, Q2 (incrementality shares) — this deliverable stands alone and is worth publishing early. Weeks 3–4: primary Callaway–Sant'Anna estimation, event studies, heterogeneity. Week 5: regulatory placebo, Fanatics benchmark, state-level C&D design, all placebos. Week 6: second-panel replication, scaling to revenue, writeup with the honest-DiD sensitivity in the summary.
