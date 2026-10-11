# febb35

## The question and the hypothesis

We want to know whether a user who starts trading on Kalshi subsequently spends less on DraftKings than that same user would have spent had they never opened a Kalshi account. The hypothesis is that event contracts — particularly single-game and season-outcome markets — are a partial substitute for sportsbook wagering, so that a dollar and an hour that would have gone to DraftKings goes to Kalshi instead. The null we are trying to reject is that Kalshi adoption is purely additive: adopters are high-appetite bettors who add a new venue to an existing wallet without shrinking any of the old ones.

The estimand is precise: the average change in DraftKings outcomes among users who adopted Kalshi, relative to what those same adopters would have done absent adoption, over the six months following adoption. It is not the effect of Kalshi's existence on the market, and it is not the effect on a randomly chosen consumer. Adopters are a selected group and the answer is about them.

Three outcomes, in order of priority. First, DraftKings gross deposit dollars per user-month (debits to DraftKings, excluding payouts). Second, monthly retention: an indicator for any DraftKings debit of $5 or more in the month. Third, DraftKings deposit transaction count. Secondary outcomes: net dollars (deposits minus withdrawals), DraftKings' share of the user's total sportsbook wallet, total sportsbook wallet including Kalshi, and time to a 90-day lapse.

## Data required

A user-month panel from January 2022 to the most recent complete month, built from card and ACH transactions, with one row per user per calendar month regardless of activity, so that zero months are explicit zeros rather than missing rows.

Merchant identification is the load-bearing data task and deserves a week on its own. DraftKings appears under many descriptors — `DRAFTKINGS`, `DK*`, `DRAFTKINGS SPORTSBOOK`, `DRAFTKINGS CASINO`, `DRAFTKINGS DFS`, plus acquirer-prefixed variants and the Golden Nugget Online brand. Kalshi appears as `KALSHI`, `KALSHIEX`, `KALSHI EXCHANGE LLC` on ACH, and via debit-card and crypto on-ramp descriptors. Build the taxonomy by pulling every distinct descriptor string whose normalized form contains the stems, hand-labeling the top 300 by transaction volume plus a random sample of 200 in the tail, and reporting the share of dollars covered by hand-labeled strings (target: above 99%). Do the same for the comparison venues we need as covariates and placebos: FanDuel, BetMGM, Caesars, ESPN Bet, Fanatics, PrizePicks, Underdog, Polymarket, PredictIt, Robinhood, Interactive Brokers, and the major crypto exchanges.

Sign convention matters. DraftKings payouts arrive as credits and must never be netted into the deposit measure by accident; a user who wins big and re-bets from their DraftKings balance generates no new debit, which will look like churn. Keep debits and credits as separate fields from the raw ingest onward.

Per user we also need: account tenure in the panel (first and last observed transaction of any kind), total monthly inflow to the linked deposit account as an income proxy, state of residence, age bucket where available, and a monthly panel-activity flag defined as five or more transactions of any type at any merchant in that month. That last variable is not optional; it is the instrument we use to distinguish leaving DraftKings from leaving the dataset.

## Building the sample

Treatment date is the user's first Kalshi debit of $5 or more. The floor removes $1 card authorizations and micro test deposits, and the first-debit rule ignores credits so that a withdrawal never gets read as an entry. Assign each adopter to a cohort by the calendar month of that first debit. Restrict cohorts to those with at least six months of panel history before and six months after, which given a panel through the present means adoption months from roughly January 2023 through six months before the panel end.

Eligibility for the analysis requires being a real DraftKings user before adoption: at least two months with a DraftKings debit during event months −6 through −1, and at least $50 in cumulative DraftKings debits over that window. Users with no pre-period DraftKings activity cannot show a reduction and only add noise; report their count separately, because "Kalshi adopters who were not DraftKings users" is itself an interesting number for the business.

The comparison pool is users who never record a Kalshi debit anywhere in the panel window, who satisfy the same DraftKings baseline requirement, and who record no debit to Polymarket, PredictIt, or another event-contract venue. Also build a second pool of users who adopt Kalshi more than twelve months after the cohort month, used only as a robustness check; the primary result should not lean on people who are merely slower to do the same thing.

Now build one self-contained dataset per adoption month. Within cohort $g$, take the adopters and match each to five comparison users, exact on state, exact on DraftKings tenure bucket (under 6 months, 6–12, 13–24, 25 or more months since first observed DraftKings debit), and nearest-neighbor on a logit propensity score estimated within the cohort. The score uses: log mean monthly DraftKings debit dollars over months −6 to −1; the number of active DraftKings months out of six; mean monthly DraftKings transaction count; the OLS slope of monthly DraftKings dollars over months −6 to −1, which captures whether the user was already fading; log monthly account inflow; age bucket; indicators for pre-period activity at FanDuel, BetMGM, Caesars, ESPN Bet, and daily-fantasy apps; a crypto-exchange activity indicator; and the pre-period share of DraftKings dollars falling in September–January, which proxies sports tilt versus casino tilt. Match with replacement, caliper 0.2 standard deviations of the linearized score, and drop adopters with no match inside the caliper — report how many, since heavy trimming changes who the answer is about.

Stack the cohort datasets into one file keyed on (user, cohort, event month), keeping event months −6 to +6 and requiring a balanced thirteen-month window. A comparison user may legitimately appear in several cohorts; keep the original user id alongside the user-by-cohort id, because the two serve different purposes below.

## Estimation

On the stacked file, estimate

$$y_{igt} = \sum_{k=-6,\,k\neq -1}^{6} \beta_k \cdot \mathbb{1}[\text{adopter}_i]\cdot\mathbb{1}[e_{it}=k] + \alpha_{ig} + \lambda_{g\tau} + \varepsilon_{igt}$$

where $\alpha_{ig}$ is a user-by-cohort fixed effect, $\lambda_{g\tau}$ is a cohort-by-calendar-month fixed effect, $e$ is event time and $\tau$ is calendar time. Event month −1 is the omitted reference. The cohort-by-calendar interaction is what keeps each cohort's adopters compared only to their own matched controls in the same calendar months, so no adopter ever serves as a control for another adopter and no cross-cohort comparison of already-treated to newly-treated can enter with a negative weight.

Weight comparison observations by 1/5 so each matched set carries the weight of one adopter, and weight matched sets so that each cohort contributes in proportion to its adopter count. Report the cohort weights explicitly in the output — the headline number is a weighted average of cohort-specific effects and the reader should be able to see that the November 2024 election cohort is not silently driving everything.

Cluster standard errors on the original user id, not the user-by-cohort id, since reused controls induce correlation across stacks. With fewer than thirty cohorts, also report a wild cluster bootstrap over cohorts.

Run three functional forms and pre-commit to which is primary. Primary: dollars, winsorized at the 99th percentile within cohort-by-calendar-month, estimated by OLS, giving an effect in dollars per user-month that finance can multiply by adopter counts. Second: the retention indicator under the same specification, a linear probability model, giving percentage-point churn. Third: a Poisson pseudo-maximum-likelihood fit with the same fixed effects on raw dollars and on transaction counts, which delivers a proportional effect, handles the mass of zeros properly, and avoids the arbitrary-scaling problem that makes $\log(1+y)$ and inverse hyperbolic sine coefficients uninterpretable when zeros are common. Do not report a $\log(1+y)$ result as the headline.

Aggregate $\beta_0$ through $\beta_6$ into a single post-adoption average with the delta method, and also report months $+1$ to $+3$ and $+4$ to $+6$ separately, because a transient novelty effect and a durable reallocation are different business facts.

Before running any of this, compute the minimum detectable effect from pre-period data alone: with residual within-user monthly dollar standard deviation $s$, $N_T$ adopters, five controls each, and seven post months, the 80%-power two-sided MDE is roughly $2.8\,s\sqrt{(1/N_T + 1/5N_T)/7}$. If that exceeds 5% of mean baseline DraftKings spend, say so in the plan document and widen the window or pool cohorts rather than discovering underpowerment afterward.

## Validation

Balance first. For every matching covariate and for a held-out set that was deliberately excluded from the score — FanDuel dollars, total discretionary spend, weekend transaction share — report standardized mean differences before and after matching, with a threshold of 0.10 for acceptance. Also plot raw mean DraftKings dollars by event month for adopters and matched controls; the two lines should be visually parallel over −6 to −1 before any regression is run.

Pre-period coefficients are the identification test. Report the joint F-test of $\beta_{-6} = \cdots = \beta_{-2} = 0$, but do not treat a non-rejection as proof — report the pre-period test's power against the size of the post-period effect you are claiming. Then run a partial-identification sensitivity check: allow a hypothetical post-period differential trend as large as $M$ times the largest pre-period differential trend, and report the breakdown value of $M$ at which the confidence set for the post effect first includes zero. A result that survives only to $M=0.5$ is not a result.

Four placebos. First, placebo outcomes: grocery, fuel, and general e-commerce spend under the identical specification should be indistinguishable from zero; a decline there means we are picking up a general spending shock, not substitution. Second, placebo timing: re-run with pseudo-adoption dates shifted six months earlier for adopters who were inactive at Kalshi then, which should produce nothing. Third, placebo treatment: define adoption as a user's first transaction at an unrelated new merchant of comparable ticket size and match identically; a large negative DraftKings effect there indicates the matching is picking up mean reversion rather than substitution. Fourth, run the whole pipeline on FanDuel-only users with no DraftKings activity to confirm the estimated pattern is about sportsbook wallets generally rather than a DraftKings-specific artifact.

Robustness set, all pre-specified: not-yet-adopters instead of never-adopters as controls; 1:1 matching instead of 1:5; no winsorization; dropping the November 2024 and January 2025 cohorts; excluding adopters whose DraftKings spend had already fallen more than 50% in months −3 to −1 relative to −6 to −4; and restricting to users whose panel-activity flag is on in all thirteen months.

## Pitfalls to watch

The one that will bite hardest is confusing dataset attrition with DraftKings churn. If a user unlinks a card or switches to a bank we do not observe, every outcome goes to zero at once and the retention estimate absorbs it. Condition inclusion on the panel-activity flag, and additionally report the effect of adoption on total observed spend across all merchants; if adoption "causes" a 30% drop in total spend, we are measuring payment-method migration, not behavior. Present retention two ways — coding panel exit as missing and as zero — and if the two disagree, the honest headline is the deposit-dollars result among panel-active users.

Second, reverse causality in the timing. A user who gets limited, restricted, or self-excluded at DraftKings has a mechanical reason to try Kalshi in the following weeks. That produces exactly the pattern we are looking for with the causal arrow backwards. The pre-trend test partly catches it, the −3 to −1 fade exclusion catches more, and a stratified estimate splitting adopters by whether their DraftKings deposit sizes were already shrinking pre-adoption is the direct diagnostic. Report both strata.

Third, differential seasonality. DraftKings dollars are enormously seasonal and Kalshi adoption clusters at NFL kickoff and around elections. Cohort-by-calendar fixed effects remove the seasonality common to a cohort's adopters and controls, but if adopters are more sports-tilted than their matches, the post window covers a different part of the sports calendar for them. Matching on pre-period sports tilt handles this; the wallet-share outcome, which divides DraftKings by total sportsbook dollars, is the clean cross-check because common seasonality cancels in the ratio.

Fourth, we observe dollars moved, not what was traded. Bank data cannot tell a sports contract from an inflation contract, so any statement about sports-specific substitution must be inferred from adoption timing and heterogeneity, and should be labeled as inference rather than measurement.

Fifth, joint and shared accounts, users with multiple linked cards mapping to one person, and users depositing to DraftKings through PayPal or a wallet we see only as a generic transfer — each attenuates measured DraftKings spend in ways that need to be flagged in the coverage audit rather than discovered in the residuals.

Finally, discipline the analyst. Freeze the specification, the matching variables, the outcome definitions, and the robustness list in a written file, and build and validate the matching using pre-period data only, before any post-period outcome is computed. The temptation to tune the caliper until the pre-trends look flat is the main way an exercise like this produces a number nobody should believe.

## Deliverables

Week one: merchant taxonomy with coverage audit, panel build, adopter and comparison-pool counts by cohort. Week two: matching, balance tables, raw event-time plots, MDE calculation. Week three: estimation, the full validation battery, heterogeneity by pre-period intensity quartile, by state sportsbook legality, and by adoption season. Week four: a short memo whose first exhibit is the event-time plot, whose headline is the dollar effect per adopter-month with its confidence interval and the sensitivity breakdown value, and whose second section states plainly which of the pitfalls above remain unresolved.
