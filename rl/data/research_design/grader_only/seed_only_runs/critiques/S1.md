# S1 — critique (claude-opus-5)

> Do customers who start trading on Kalshi subsequently reduce their spend and activity on DraftKings? We have a credit-card and bank-deposit transaction panel covering both.

---

## Verdict

The plan is well-constructed and the analyst is clearly competent — the pre-registration discipline, the honest-DiD sensitivity, the "what will go wrong" section that actually names the right things. But it is scoped as a six-week causal-inference project when the decision-relevant answer is probably a two-day cross-tab, and the causal core has a power problem the plan never checks and an identification strategy whose two headline placebos don't test what they claim to test.

I'd approve **week 1 and week 2 only**, as a standalone deliverable, with a hard gate before anything else runs. Details below.

---

## 1. There is no power calculation, and this is likely fatal to Q1

The falsification criterion is "CI tight enough to exclude −10%." Nothing in the plan establishes that this is achievable. Work the funnel: panel households → households with ≥$100 DK net deposits and ≥3 deposits in a 12-month window → of those, first Kalshi funding ≥$25 in a specific monthly cohort → surviving the ≥10/12 pre and ≥5/6 post presence screens → matched within a 0.05 caliper → in the top pre-period DK quintile (the only cut that matters for revenue). In a Yodlee-type panel that funnel plausibly ends in the low thousands overall and the low hundreds in the cell you care about. Monthly household net deposits are heavy-tailed with a CV north of 2 even after winsorizing at 99.5.

You will get a CI like [−28%, +4%] and a writeup that says "directionally consistent with substitution." That is not worth six weeks.

**Fix:** before anything else, compute the pre-period variance of cumulative 6-month DK net deposits in the panel, count the actual treated N by cohort after every screen, and produce an MDE. If the MDE on the top-quintile cut is worse than ~20%, kill Q1 as a precision exercise and reframe it as descriptive. This is a half-day of work and it determines whether weeks 3–5 exist.

Related: the heterogeneity plan slices five ways. Romano–Wolf on underpowered cells produces nothing but adjusted p-values near 1. Pre-specify **one** cut — pre-period DK value quintile — and power for it.

## 2. The cheap version answers most of the question

The investable number is the product of Q1 × Q2 × Q3, and Q2 and Q3 require no econometrics. Do these first:

- **Overlap:** what share of Kalshi funders were DK-active in the prior 12 months, and — more important, and not in the plan — what share of DK's *spend-weighted* customer base has ever funded Kalshi? If 6% of DK's dollars sit with households that have touched Kalshi, then even a −30% substitution effect is under 2 points of B2C revenue and the debate is over.
- **Wallet-share time series:** among DK-active households, plot DK's share of total gambling+prediction wallet for ever-Kalshi vs never-Kalshi households, raw, no matching. If the series don't diverge, you're done.
- **Sizing arithmetic:** Kalshi revenue-equivalent (matched volume × take rate, ~1% or less) against DK B2C revenue. Prediction-market *notional* is not handle and not revenue; §7's "cross-check against Kalshi's disclosed notional volume" invites exactly this category error.

**Gate:** if overlap is small or the wallet-share series are indistinguishable, stop. Publish the two-pager. If both are alarming and the power calc clears, spend the six weeks.

## 3. The two headline placebos don't do what the plan says

**Regulatory placebo (§4, design 2).** In non-legal states, DK-active households are DFS/Jackpocket users, not sportsbook bettors — a structurally different population, different spend levels, different substitutability. And Kalshi in a non-legal state is the *only* legal way to bet a game, so if anything the displacement pressure on whatever DK product exists there is higher, not lower. The plan asserts that "a similar effect in both means you are picking up a household-level shock." That inference is wrong; it is equally consistent with genuine substitution away from DFS. The test doesn't discriminate. Either drop it or reframe it as "is the effect bigger where sportsbook substitution is possible," which is a much weaker claim.

Note also that DK's sportsbook and iCasino share a wallet in most states, so the outcome variable cannot be attributed to sportsbook at all. Say that up front.

**Fanatics benchmark (§4, design 3).** Fanatics adoption in this window is overwhelmingly promo-driven and partly PointsBet migration. Those adopters are bonus-hoppers whose bankroll temporarily relocates and reverts. Calibrating "Kalshi is a third as cannibalistic as a real competitor" against a selection mechanism that different is not a scale calibration. Keep it as a **power/sanity check** — "does this pipeline detect displacement when displacement certainly exists" — and delete the ratio interpretation.

**What I'd substitute:**

- **Active control.** Replace (or supplement) never-adopters with households that first fund a *different* novel speculative product in the same month — a new brokerage, a crypto exchange, Underdog. This differences out the thing that actually drives the confound: "household at a moment of novelty-seeking or budget change." Matching on levels and trends does not remove selection on a transient shock; matching on the *type of event* gets closer.
- **Robinhood exposure as ITT.** The plan treats Robinhood-routed prediction markets purely as measurement leakage. It's your best instrument-adjacent variation: households with a pre-existing Robinhood relationship had prediction markets pushed into their app in March 2025 without seeking Kalshi out. Pre-period Robinhood × post-March-2025 DiD against comparable non-Robinhood households is an exposure design that does not condition on the adoption moment. Still not random, but it doesn't have the killer confound. Promote it.
- Promote the state C&D design (design 4) to co-primary for the same reason.

Blunt version: the matched-adopter event study will not identify a causal ATT, for exactly the reason §8 gives, and the plan's own remedies don't rescue it. Lead with the exposure designs; present the adopter event study as descriptive with the escalation-then-reversion pattern shown honestly.

## 4. Internal inconsistency in the control group

§3 defines controls as "never observed with any Kalshi or Polymarket transaction through the end of the sample." §4 uses Callaway–Sant'Anna with **not-yet-treated** comparisons. These are incompatible, and the §3 version conditions on the future: it excludes households that adopt in month t+4, i.e., selects controls on an outcome-correlated future choice. The resulting control pool is systematically less novelty-seeking, which biases the ATT more negative. Fix the matching pool to not-yet-treated at each cohort's adoption month.

Also: matching 1:3 with replacement and then running a DR estimator on the matched sample, with the CS bootstrap ignoring the matching step, understates SEs. Either put the covariates in the DR step on the full not-yet-treated pool (preferred) or bootstrap the whole pipeline.

## 5. The DK measurement problem is bigger than the Kalshi one

The plan worries at length about invisible Kalshi and treats the DK dictionary as routine regex. It isn't. A large share of sportsbook ACH deposits route through **VIP Preferred / Global Payments**, whose descriptor does not name the operator. **Play+ prepaid** loads look like prepaid card funding. PayPal- and Venmo-routed deposits are frequently just `PAYPAL`. If you miss these, a household that changes funding rails looks like DK churn.

The dangerous version is **differential** misclassification: Kalshi adopters are plausibly younger, more app-native, and more likely to be on the rails you're missing. That mechanically manufactures the result you're looking for. Aggregate panel-to-reported reconciliation will not catch it, because the aggregate can reconcile while the rail mix is correlated with treatment.

**Fix:** in the 200-household hand audit (which is the right instinct), specifically reconstruct funding *rails*, not just the deposit/withdrawal ladder. Then test whether rail mix differs between treated and control pre-adoption, and whether rail composition shifts around the event.

## 6. The reconciliation gate is not a real gate

"R² > 0.90 on levels" between two trending quarterly series over ~14 quarters is passed by construction and will get quoted in the writeup as validation. Delete it. Keep only the YoY growth tracking error, and specify the number of quarters it must hold across.

Second issue: DKNG B2C revenue is net of promo and includes iCasino; net deposits map to *net customer losses*. The net-deposit-to-revenue relationship has been drifting because structural hold has been rising with parlay mix. A regression on 2022–2025 will fit a relationship that is mostly a hold trend, and §7 then applies that conversion to a treated subpopulation whose product mix is precisely what's in question. Estimate the conversion on the treated-like subpopulation, or present the revenue translation as a range across plausible hold assumptions rather than a point.

The analyst is *right* to use net deposits as the primary estimand — it's the household's GGR contribution, which is what you want. But use gross deposits and the extensive margin for the monthly dynamic event study; monthly net deposits sign-flip on withdrawals after a win and will make the event-time plot uninterpretable.

## 7. The estimable cohort is already stale

To get six months post, you need adoption by roughly mid-2025. Kalshi's H1-2025 sports product — pre-Robinhood-scale distribution, thinner in-game, less marketing — is not the product that is scaring people now. The headline ATT will describe a product that no longer exists, and the extrapolation error runs toward understatement. The plan half-anticipates this ("cohort effects plausibly grow") but then can't estimate the recent cohorts.

**Fix:** make the **cohort-by-horizon surface** the headline, not the pooled 6-month ATT. Report 3-month ATTs for the most recent estimable cohorts and show the trend across cohorts explicitly. If the 3-month effect is doubling across cohorts, that is the finding, and it's a more useful sentence than a pooled number.

## 8. Scaling: ratios only

§7 goes "panel adopter share × US adult population." Panel adopter share is a *level* from a panel that skews toward PFM-app users and, as §8 concedes, underrepresents high-value bettors. Every panel-derived input to the scaling must be a **ratio** (share of Kalshi funders who were DK customers; per-household effect as % of counterfactual), with the level anchor coming from outside the panel — Kalshi funded-account disclosures, Sensor Tower MAU with a download-to-funded conversion. State this as a rule, because the temptation to use panel levels will be strong and it's where the estimate goes wrong by 2–3x.

## 9. The framing assumes DK is a passive victim

DK is not standing still on prediction markets — its own exchange move, and FanDuel's exchange partnership, change the question from "does Kalshi take DK's customers" to "does the category migrate to a ~1–2% take rate from a ~10% hold, and who captures it." The second question is the one that determines the stock. A household that shifts handle to Kalshi may be revenue-neutral to DK in two years and still catastrophic to category economics. At minimum, add DK's prediction product to the outcome definition once it exists, and frame the writeup around take-rate compression, not share loss.

Also worth stating explicitly: DKNG's price action on this theme has been driven by regulatory and legislative headlines, not by realized cannibalization. A rigorous −8% ± 6% published in Q1 2026 may be correct and unactionable. Pre-commit: what do you do differently at −5% vs −15%? If the answer is "nothing," the project is a research exercise, not a trade.

---

## Smaller items

- **Placebo outcomes.** Grocery/fuel/utilities are low-variance and will be null by lack of power, not by design. Add discretionary categories with gambling-like volatility (food delivery, travel, retail) and one *positive* control that should move (total speculative-app funding).
- **Attrition IPW.** The logit doesn't include treatment status, but Kalshi adoption may itself cause account changes (new bank for gambling). Report attrition rates by arm and bound the result under worst-case differential attrition.
- **Q2 definition.** "No online sportsbook or DFS activity in the prior twelve months" over-counts incrementality if the household bets offshore, on sweepstakes, or in cash. The dictionary covers offshore/sweeps — make sure Q2 uses the full wallet, not just regulated operators.
- **Treatment definition.** ≥$25 first outflow is sensible, but check whether Kalshi's promotional credit structure produces first-funding events at a specific amount that would cluster at the threshold.

---

## What I'd approve

**Phase 0 (2 days):** treated-N funnel count, MDE on cumulative 6-month net deposits for the top-quintile cell, rail audit on 200 DK households. Hard gate.

**Phase 1 (1 week):** overlap and incrementality cross-tabs, spend-weighted DK exposure to Kalshi, raw wallet-share time series, Kalshi revenue-equivalent sizing. This is publishable on its own and probably settles the order of magnitude. Second gate.

**Phase 2 (only if both gates clear, 3–4 weeks):** exposure designs first (Robinhood ITT, state C&D), active-control adopter design second, Fanatics as a power check. Cohort-by-horizon surface as the headline. Honest DiD in the summary, as planned.

The instinct behind the plan is right and the risk register is unusually honest. The error is allocating the effort in inverse proportion to where the answer lives.
