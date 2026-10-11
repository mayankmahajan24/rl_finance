# ff3e5e

## The question, stated so it can be falsified

The business question is whether prediction markets cannibalize sportsbooks. The analytical question is narrower and must be kept narrow: **conditional on a user's total speculative wallet, does an incremental dollar of Kalshi funding displace DraftKings deposit dollars, and how much?**

Primary hypothesis (H1): within a user, an increase in Kalshi's share of that user's speculative wallet is associated with a *more than mechanically implied* decline in DraftKings deposit dollars in the same and following months.

The "more than mechanically implied" clause is the whole ballgame and I will come back to it repeatedly. Kalshi share is `K / (K + DK + FD)`. DraftKings deposits sit in the denominator of the regressor and are the outcome. A regression of ΔDK on Δshare will produce a large negative coefficient even in a world with zero behavioral substitution, purely from arithmetic. The correct null is not zero. Any version of this analysis that tests against zero is wrong, and the single highest-value thing this plan does is pin down the right null and beat it.

Secondary hypotheses worth pre-registering because they change the business answer entirely:

- H2 (category vs. brand): if Kalshi substitutes for sports betting as a category, FanDuel should fall alongside DraftKings by a similar magnitude. If DraftKings falls and FanDuel rises, this is share shift between sportsbooks with Kalshi as a coincident third party — a completely different conclusion.
- H3 (incrementality): if total speculative wallet (K + DK + FD) is flat while its composition rotates, Kalshi is cannibalizing. If total wallet rises with Kalshi adoption, Kalshi is expanding the category and the "substitution" coefficient is measuring reallocation of a growing pie.
- H4 (heterogeneity): displacement is concentrated in long-tenured, high-spend users (they have a fixed gambling budget and are shopping for edge) rather than in new low-spend users (for whom Kalshi is novelty spend financed out of general consumption).

## Data required

**Panel.** User-month observations from a card-and-bank transaction panel. Target window January 2023 through the most recent complete month, monthly grain, with the user's full observable outflow ledger — not just gambling merchants, because the placebo tests and the budget-accounting check need consumption categories too.

**Merchant identification.** Build and hand-audit a descriptor dictionary before writing any regression. Kalshi funding appears under strings like `KALSHI`, `KALSHIEX`, `KALSHI EX LLC`, typically ACH or debit-card pull. DraftKings splits across sportsbook, DFS, and iGaming/casino descriptors (`DRAFTKINGS`, `DK SPORTSBOOK`, `DRAFTKINGS CASINO`); keep them as separate columns and sum them for the headline, because the casino vertical has different substitution logic than sportsbook. Same for FanDuel (`FANDUEL`, `FD SPORTSBOOK`, FanDuel Casino). Pull a random 500-transaction sample per platform and eyeball it; descriptor drift after app or processor changes is common and silently creates fake churn.

Two attribution gaps must be measured, not assumed away:

1. Kalshi contracts distributed through brokers (Robinhood's event-contract hub, Webull, and similar) generate no Kalshi descriptor at all. Those users look like non-adopters. Quantify by checking whether adopters-by-descriptor are unusually concentrated among users without brokerage relationships, and report the implied undercount.
2. Both sportsbooks moved into prediction markets themselves during late 2025 (DraftKings via its Railbird acquisition, FanDuel via a CME-linked product — verify exact launch dates against public filings before finalizing the window). After those launches the DraftKings descriptor may bundle prediction-market funding into the outcome variable, which mechanically kills the substitution signal. **Decision: end the primary estimation window the month before the first DraftKings prediction-market launch, and analyze subsequent months as a separate, clearly flagged regime.**

**Variables per user-month.** Gross deposits to each platform; payouts/credits from each platform; net funding (deposits minus payouts) as the preferred spend proxy since redeposited winnings inflate gross; deposit count; distinct active days; an any-deposit indicator. Plus: state of residence, months since first observed DraftKings deposit, pre-period wallet size, panel-completeness flags, income proxy from payroll credits.

**Sample filters, stated as thresholds.** Require the user to have an observed payroll or recurring-bill anchor (rent, mortgage, utility, or ≥2 subscriptions) in ≥10 of any 12 consecutive months, so we know we observe a primary account rather than a secondary card. Require ≥6 months of pre-adoption and ≥6 months of post-adoption observation for adopters, and ≥12 consecutive months for never-adopters. Restrict the main sample to states where DraftKings online sportsbook was legal for the entire window; users in non-legal states (California, Texas, Georgia, and the rest) become a placebo sample, not part of the estimate.

**Regime split.** Kalshi's product mix changed materially when sports-outcome contracts launched in early 2025. Estimate separately for the politics/economics-only regime and the post-sports-contract regime. Pooling them assumes an elasticity that almost certainly did not exist before sports contracts, and will attenuate the estimate toward zero.

## Methodology

**Core specification.**

    ΔDK_{u,t} = β · Δshare_{u,t} + α_u + δ_t + Γ'X_{u,t} + ε_{u,t}

where Δ is the month-over-month first difference, `share_{u,t} = K/(K+DK+FD)`, α_u is a user fixed effect (which in a differenced equation is a user-specific linear drift), δ_t is a calendar-month fixed effect, and X includes state × month indicators to absorb state tax changes, legalization events, and promo wars. Standard errors clustered at the user; Driscoll–Kraay with 4 lags reported alongside as a cross-sectional-dependence check, since users share national sports and news shocks. With only ~30 month clusters, do not two-way cluster naively — use a wild cluster bootstrap over months (999 replications) if a month-clustered inference is needed.

**Fixing the denominator problem — this is the central design choice.** Estimate three versions of the regressor and report all three:

1. **Raw share.** `K/(K+DK+FD)`. Known-contaminated. Reported only as the upper bound on apparent substitution.
2. **Baseline-deflated intensity (primary).** `K_{u,t} / W̄_u`, where `W̄_u` is the user's mean monthly speculative wallet over the six months *before* their first Kalshi transaction, held fixed thereafter. This preserves the "how big is Kalshi relative to this person's normal gambling budget" interpretation while removing contemporaneous DraftKings from the denominator entirely. This is the specification I would lead with.
3. **Leave-out share.** `K_{u,t} / (K_{u,t} + DK_{u,t-3..t-1} + FD_{u,t-3..t-1})`, using the trailing three-month average of the sportsbooks. Removes the same-month mechanical link but leaves a weaker serial one.

**Establish the mechanical null explicitly.** Since ∂share/∂DK = −K/W², a pure-arithmetic world implies a slope of roughly −W/s evaluated at the user's mean wallet W and mean share s. For a user with a $400 monthly wallet and 25% Kalshi share, that benchmark is about −1,600 dollars per unit of share (−$160 per 10-point share move) with no behavior whatsoever. Compute this benchmark two ways: analytically at the sample mean, and empirically via a permutation — hold each user's actual Kalshi series fixed, replace their DraftKings series with a random permutation of their *own* other months, recompute share, re-run the regression, repeat 1,000 times. The distribution of permuted β is the null. **The test of H1 is whether the observed β lies below the 5th percentile of that permuted distribution, not whether it is below zero.**

**Functional form for the dollar outcome.** Deposit dollars are non-negative, zero-inflated, and violently right-skewed — the top 1% of users are typically the majority of dollars. Lead with Poisson pseudo-maximum-likelihood with high-dimensional user and month fixed effects (`ppmlhdfe`), which handles zeros natively, is consistent under any conditional-mean specification, and yields a semi-elasticity. Report OLS on levels winsorized at the 99th percentile *by month* as the second spec, and asinh as a third with an explicit note that asinh coefficients depend on the units chosen. Do not use log(x+1); the results move with the choice of the constant.

**Timing and mean reversion.** Deposits are spiky. The month a user first funds Kalshi is disproportionately a high-wallet month, so the following month falls for reasons unrelated to substitution. Two defenses, both applied: (a) a donut — drop the adoption month itself from the estimation and compare the mean of months t+1..t+6 against t−6..t−1; (b) include two lags of DraftKings deposits, acknowledging Nickell bias is on the order of 1/T ≈ 3% here and reporting an Arellano–Bond variant as a robustness rather than as the headline.

**Instrument, for the version that supports a causal reading.** Construct a shift-share instrument: `Z_{u,t} = affinity_u × V_t`, where `V_t` is national Kalshi volume in *non-sports* contract categories (politics, economics, weather) and `affinity_u` is a user-level propensity to adopt event contracts, estimated on a 50% holdout of users from pre-period covariates only (crypto exchange funding, options-heavy brokerage activity, early-adopter fintech usage, age proxy). Using non-sports volume as the shifter is what makes the exclusion restriction arguable: national interest in an FOMC contract should not directly move an individual's NFL wagering. Report the first-stage F (require >20) and the Kleibergen–Paap statistic.

**Adoption event study, as the identification cross-check.** Independently estimate the effect of *first Kalshi transaction* on DraftKings deposits using Callaway–Sant'Anna with not-yet-adopters as controls, propensity-matched on pre-period DraftKings decile, tenure, state, and pre-period trend slope. Do not use naive two-way fixed effects here — adoption is staggered and the treatment effect almost certainly varies by cohort, which is exactly the case where TWFE weights go negative. The event study gives an average treatment effect in dollars; the share regression gives a dose–response slope. **The analysis is only credible if β × (mean Δshare at adoption) reconciles with the event-study ATT to within a factor of about two.** If they diverge, the share regression is picking up arithmetic or selection, and the event study is the number to trust.

**Required cuts.**

- *Tenure*: months since first observed DraftKings deposit, binned <6, 6–18, 18–36, 36+. Tenure is left-censored by panel start; compute it only for users whose first DraftKings deposit occurs at least 3 months after their panel entry, and report the censored group separately rather than assigning them a fake tenure.
- *Spend decile*: deciles of mean monthly (DK+FD) deposits over the **six months before first Kalshi transaction**. Never rank on contemporaneous or full-window spend — doing so guarantees that mean reversion appears as strong substitution in the top decile and negative substitution in the bottom, an artifact that has fooled a lot of published wallet-share work. Never-adopters get a pseudo-adoption date drawn from the adopter date distribution within their matched stratum.
- Report cuts both as interactions in one pooled regression (decile dummies × Δshare) and as ten split-sample regressions, and show they agree.

**Report the coefficient honestly.** β from dollars-on-share is *not* an elasticity — it is dollars of DraftKings deposit displaced per unit of Kalshi wallet share. Headline it as "dollars displaced per 10-percentage-point rise in Kalshi share." If a genuine elasticity is wanted, estimate the PPML log-log version (DraftKings deposits on Kalshi deposits) and quote that separately.

## Validation

Run all of these; pre-commit to which failures kill the result.

1. **Permutation null** (above). Kill criterion: observed β not distinguishable from the permuted distribution at 5%.
2. **Placebo outcomes.** Same specification with grocery spend, streaming subscriptions, and general-merchandise spend as the outcome. These should be indistinguishable from zero. If Kalshi share "displaces" groceries, the model is picking up an income or panel-completeness shock.
3. **Placebo geography.** Users in states without legal online sportsbooks. DraftKings sportsbook deposits are near-zero there, so any measured substitution is misclassification, and its magnitude is your measurement-error floor.
4. **Placebo treatment.** Replace Kalshi adoption with first funding of an unrelated fintech (a new neobank or P2P transfer app). A comparable coefficient means you are measuring "user opened a new financial account and reshuffled money," not substitution.
5. **Pre-trends.** Six event-study leads jointly insignificant at p > 0.10. Adopters commonly show a run-up in gambling activity in the 1–3 months before adopting; if that dip-and-spike pattern is present, the level effect is selection.
6. **FanDuel symmetry (H2).** Identical spec with FanDuel as outcome. Report the DK and FD coefficients side by side; the difference between them is the brand-switching component and should be reported as its own number.
7. **Wallet accounting (H3).** For adopters, decompose the dollar flows over the ±6-month window: ΔKalshi, ΔDraftKings, ΔFanDuel, Δother gambling (BetMGM, Caesars, ESPN Bet, PrizePicks, Underdog, Sleeper, Polymarket), Δsavings/investing transfers, Δdiscretionary consumption. Report the funding source of each incremental Kalshi dollar as percentages summing to 100. A substitution claim that doesn't survive the accounting identity isn't a claim.
8. **Randomization inference** on adoption dates: 1,000 within-user reassignments of the adoption month, producing a permutation p-value for the event-study ATT that does not rely on asymptotics.
9. **Panel integrity.** Re-run restricted to users with ≥95% wallet-completeness, and re-run dropping any user with a new card issuance or account switch mid-window. If the estimate moves more than 30%, the result is a coverage artifact.
10. **Temporal out-of-sample.** Fit on 2024 cohorts, predict 2025 adopters' DraftKings trajectories, compare predicted to actual.
11. **Power.** Before running anything, compute the minimum detectable effect: roughly 2.8 × sd(ΔDK) / (sd(Δshare) × √N_effective), with N_effective adjusted for within-user clustering via the design effect 1 + (m−1)ρ, where m is months per user and ρ the intra-user correlation of ΔDK (expect 0.05–0.15). State the MDE in dollars per 10-point share move in the writeup so a null result is interpretable.

## Pitfalls I would watch for

**The denominator.** Repeating it because it is the one that ruins this analysis. The regressor contains the outcome. Test against the permuted null, not zero, and lead with the baseline-deflated regressor.

**Gross deposits are not spend.** A user on a hot streak redeposits winnings and looks like a heavy spender; a user who loses everything stops depositing and looks like a churner. Net funding (deposits minus payouts) is closer to economic loss and should be the preferred outcome, with gross reported alongside. Kalshi users round-trip capital far more than sportsbook users — the same $100 can generate many multiples of notional — so never compare "volume" across the two platforms. Deposit dollars is the only common unit here.

**Deposit dollars are not revenue.** A sportsbook holds roughly 9–11% of handle; an exchange takes a small fee on notional. A dollar of displacement costs DraftKings far more gross revenue than it earns Kalshi. Any dollar figure presented to a business audience must be converted with explicit take-rate assumptions, or it will be misread by an order of magnitude.

**User-specific seasonality.** Month fixed effects remove common seasonality, but an NFL-only bettor and a year-round casino player have opposite within-year profiles. Kalshi adoption clusters around election weeks and major sporting events. Add user-type × season controls (classify users by the share of their annual gambling spend falling in the NFL window) or the seasonal pattern will be attributed to Kalshi.

**Common-cause shocks.** State tax and fee changes on sportsbooks, per-wager levies, promotional withdrawal, and app outages depress DraftKings and push users toward alternatives simultaneously. State × month fixed effects handle the geographic ones; the non-sports-volume instrument handles some of the rest; a national DraftKings-specific shock in the same month as a Kalshi surge is not separable and should be flagged as a residual threat.

**Selection into adoption.** Kalshi adopters are not random — they skew toward users already sophisticated, already high-volume, and often already at the end of an engagement arc with their sportsbook. The event study with matched not-yet-adopters and a clean pre-trend test is the defense, and if the pre-trends fail, the honest output is a bound rather than a point estimate.

**Attrition.** These panels lose a large fraction of users annually, and dropout correlates with the exact behavior being measured (card switching, account closure). Report the estimate on the balanced subpanel and on the full unbalanced panel; if they differ, run a Lee bound.

**Whales.** A handful of users move the dollar-weighted answer entirely. Report the dollar-weighted and user-weighted results separately and never present only one. If the top-decile coefficient drives everything, say so in the headline.

**Overclaiming the word "elasticity."** The coefficient is dollars per share point. Present it that way.

## First week

Monday: descriptor dictionary, hand-audit, coverage and undercount quantification, sample filters, and the regime/window decision on the sportsbooks' own prediction-market launches. Tuesday: panel construction, completeness flags, pre-period baselines, tenure and decile assignment. Wednesday: the permutation null and the analytic mechanical benchmark — before any headline regression, so the team knows what number it has to beat. Thursday: the three regressor variants, PPML and OLS specs, cuts by tenure and decile. Friday: event study, reconciliation against the share coefficient, and the placebo battery. The following Monday: wallet accounting and writeup, with the mechanical null, the FanDuel comparison, and the take-rate conversion on the first page rather than in an appendix.
