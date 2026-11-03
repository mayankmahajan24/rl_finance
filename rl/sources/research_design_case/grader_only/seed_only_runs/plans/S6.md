# S6 — plan (claude-opus-5)

> Do changes in next-two-year revenue and EBITDA CAGR drive earnings-multiple re-ratings among peers within an industry?

---

# Research Plan: Does the Change in Forward Two‑Year Growth Explain Intra‑Industry Multiple Re‑Ratings?

## 1. The hypothesis, stated precisely enough to be falsified

The loose version of the idea — "growth drives multiples" — is almost certainly true and almost useless. The plan is built around a sharper claim.

**Primary hypothesis (H1).** Within a narrowly defined peer group, changes in a company's consensus next‑two‑year EBITDA CAGR, measured *relative to the contemporaneous change for its peers*, are associated with contemporaneous changes in its relative forward EV/EBITDA multiple, with an elasticity that is economically large (I expect roughly 0.5–1.5 turns of EV/EBITDA per 100bp of two‑year CAGR for a median industrial, i.e. an elasticity of log‑multiple to CAGR in the range 5–15).

**Secondary hypotheses worth separating out, because they are where the money is:**

- **H2 (composition).** Growth delivered through revenue is priced differently from growth delivered through margin expansion. Decompose the EBITDA CAGR change into a revenue‑CAGR component and a margin‑change component and test whether the coefficients differ. Prior: revenue‑driven upgrades earn a higher multiple response because they are perceived as more persistent.
- **H3 (quality conditioning).** The re‑rating per unit of growth is increasing in the spread between the firm's ROIC and its cost of capital, and approximately zero or negative for firms earning below their cost of capital. This is standard valuation theory and is the most useful cross‑sectional conditioner if it holds.
- **H4 (asymmetry).** Downgrades de‑rate more than equivalent upgrades re‑rate, particularly in the top quartile of starting multiple.
- **H5 (drift / tradability).** The re‑rating is incomplete on impact and continues for one to two quarters, so that the residual from the contemporaneous relationship predicts future relative multiple change. This is the only hypothesis with direct portfolio implications; H1–H4 are the diagnostic scaffolding.

**Null to beat.** The relationship is entirely mechanical (see §5) or entirely subsumed by two known effects: analyst EPS revision momentum and price momentum. If the growth‑CAGR variable adds nothing once you control for the change in the *level* of the NTM estimate and trailing 12‑1 momentum, the idea is dead as a standalone signal even if H1's coefficient is significant.

## 2. Universe, data, and construction

**Coverage.** US + developed Europe, 2003–2025. Start in 2003 because I/B/E/S consensus EBITDA and revenue coverage for FY3 is too thin before then. Universe is Russell 3000 constituents plus STOXX Europe 600, with filters at each rebalance date: market cap > $300m, 60‑day median ADV > $2m, price > $5 (or local equivalent), consensus FY3 EBITDA available from ≥3 analysts, and NTM EBITDA > 0. Exclude GICS 40 (Financials) and 60 (Real Estate) from the main test — EV/EBITDA is not a meaningful metric there — and run those separately on P/TBV and P/E if the sponsor cares.

**Sources.**

- *Estimates:* I/B/E/S (Refinitiv) Summary History, unadjusted file, for consensus mean revenue, EBITDA, and EPS for FY1/FY2/FY3, plus number of estimates and standard deviation. Use the unadjusted file and apply the CRSP/Compustat adjustment factor yourself; the adjusted I/B/E/S file has known rounding damage on split‑adjusted historical estimates. As a robustness cross‑check, replicate two years of the panel using FactSet Estimates or S&P Capital IQ consensus — I/B/E/S EBITDA definitions (pre‑ or post‑stock comp, pre‑ or post‑exceptional) are not uniform across contributors, and I want to know how much the answer moves.
- *Prices and returns:* CRSP (US) and Compustat Global / Refinitiv Datastream (Europe), total return, in USD.
- *Balance sheet:* Compustat Fundamentals Quarterly, point‑in‑time via the Compustat PIT/snapshot files where available; otherwise lag reported items by the actual report date (`RDQ`) plus two trading days.
- *Industry:* GICS sub‑industry (8‑digit) from the historical GICS file, which is point‑in‑time. Robustness: Hoberg‑Phillips TNIC‑3 peer groups (updated annually, available through 2023) and an analyst co‑coverage peer network built from I/B/E/S detail files.

**Constructing the growth variable.** Fiscal‑year estimates jump discontinuously when the fiscal year rolls; do not use raw FY1/FY3. Calendarize: for each firm‑month, let $w$ = months remaining in FY1 divided by 12, and define
$$E_{NTM} = w\cdot E_{FY1} + (1-w)\cdot E_{FY2}, \qquad E_{N3Y} = w\cdot E_{FY3} + (1-w)\cdot E_{FY4}$$
where FY4 is used only if available (≈40% of the sample); otherwise extrapolate FY3 forward at the FY2→FY3 growth rate and flag the observation for a robustness split. Then
$$g_{i,t} = \left(E^{N3Y}*{i,t}/E^{NTM}*{i,t}\right)^{1/2}-1.$$
Require $E^{NTM}>0$ and $E^{N3Y}>0$. Winsorize $g$ at ±60% and $\Delta g$ at the 1st/99th percentile *within each date*. Build the identical object for revenue (no positivity issue) and for EPS.

**Constructing the multiple.** Enterprise value = month‑end market cap (all share classes) + total debt + preferred + minority interest − cash and equivalents, using the most recently reported quarter as of the month end. Multiple $M_{i,t} = EV_{i,t}/E^{NTM}_{i,t}$. Work in logs throughout. Drop observations with $M < 2$ or $M > 60$.

**Relative measures.** For every variable, compute the peer‑demeaned version: $\tilde{x}*{i,t} = x*{i,t} - \text{median}*{j \in P(i,t)} x*{j,t}$, where $P(i,t)$ is the GICS sub‑industry excluding firm $i$, requiring ≥6 surviving peers; if fewer, fall back to the GICS industry (6‑digit), then industry group (4‑digit), and record which level was used.

**Frequency.** Monthly observations of 3‑month changes and 12‑month changes. Overlapping windows demand the standard error treatment in §3.

## 3. Core methodology

**The decomposition that frames everything.** Over any interval,
$$\Delta \log EV_{i} = \Delta \log E^{NTM}*{i} + \Delta \log M*{i}.$$
The change in the multiple is, by construction, the part of enterprise value change *not* explained by revision to the near‑term earnings base. The research question is whether the market's reappraisal of the *trajectory beyond* the next twelve months explains that residual. This framing makes the exercise clean and pre‑empts the mechanical‑relationship objection.

**Specification 1 — the workhorse panel.**
$$\Delta_{3} \log M_{i,t} = \alpha_{s(i),t} + \beta_1 \Delta_3 g^{EBITDA}*{i,t} + \beta_2 \Delta_3 g^{REV}*{i,t} + \gamma' X_{i,t} + \varepsilon_{i,t}$$
with sub‑industry × month fixed effects $\alpha_{s,t}$ — which mechanically imposes the "within industry, versus peers" requirement of the question and absorbs all sector‑level rate, commodity, and sentiment shocks. Controls $X$: $\Delta_3 \log E^{NTM}$ (the level revision, essential), $\Delta_3$ NTM EBITDA margin, $\Delta_3$ net debt/EBITDA, log market cap, trailing 12‑1 return, $\Delta_3$ estimate dispersion (std/|mean| of FY2), $\Delta_3$ analyst count, and the starting log multiple $\log M_{i,t-3}$ (mean reversion / regression‑to‑peer term). Standard errors two‑way clustered by firm and by month; because the 3‑month windows overlap at monthly frequency, additionally report Driscoll‑Kraay errors with 6 lags and confirm the quarterly non‑overlapping panel gives the same point estimate.

**Specification 2 — Fama‑MacBeth.** Run the same cross‑section month by month within industry (i.e., on peer‑demeaned variables), then test the mean of the 250+ coefficient series with Newey‑West(6) errors. This is the honest check on whether the panel result is driven by a handful of periods; plot the coefficient time series and look at 2008–09, 2020, and 2022 specifically.

**Specification 3 — composition and conditioning.** Replace $\Delta g^{EBITDA}$ with its orthogonalized parts: regress $\Delta g^{EBITDA}$ on $\Delta g^{REV}$ within industry‑month and use fitted and residual components, so the coefficients are interpretable despite the ~0.6–0.75 correlation I expect between the two. Then interact the growth change with (a) ROIC − WACC, using NOPAT/(net debt + equity) and a simple CAPM/Blume‑beta WACC; (b) starting log relative multiple, in quartiles; (c) sign of the change, for H4; (d) a "growth persistence" proxy, the firm's own historical R² of realized versus forecast two‑year CAGR over the prior 5 years.

**Specification 4 — event study, to address timing.** Identify "growth shock" events: firm‑quarters where the peer‑demeaned $\Delta g^{EBITDA}$ over the 5 trading days following the earnings report date (`RDQ`) falls in the top or bottom decile of the industry‑quarter distribution. Because the revision follows a discrete information event, reverse causality from price to estimate is far weaker here. Track cumulative peer‑relative log multiple change from t−10 days to t+250 days, with a matched control group (same sub‑industry, nearest size and starting multiple, revision in the middle three deciles). This gives the impact‑versus‑drift split needed for H5.

**Specification 5 — a calibration benchmark, not just a regression.** Build a three‑stage DCF: two explicit forecast years from consensus, a fade of ROIC toward WACC over 8 years, terminal growth at 2.5% nominal. Perturb the two‑year CAGR by +100bp holding everything else fixed and record the implied change in EV/NTM EBITDA for a grid of (starting margin, ROIC spread, capital intensity). This tells you what the coefficient *should* be. The interesting result is not "$\beta > 0$" but "$\beta$ is 2× the DCF‑implied value in the top multiple quartile and 0.4× in the bottom" — that is a tradable finding; a significant t‑stat is not.

**Specification 6 — the portfolio test.** Each month, within each sub‑industry, rank firms on the residual from a rolling 36‑month estimation of Specification 1 lagged one month (i.e., firms whose growth was upgraded more than their multiple response would suggest). Form industry‑neutral, dollar‑neutral quintile portfolios, equal‑ and cap‑weighted, held 3 months with overlapping tranches. Report gross and net returns assuming 25bp round‑trip costs for US large cap and 45bp for smaller/European names, turnover, and alphas from a regression on Fama‑French five factors + momentum + a home‑built analyst‑EPS‑revision factor + QMJ. The signal must survive the revision factor; if it doesn't, the finding is that this is a re‑expression of revision momentum.

## 4. Validation

Split the sample at 31 December 2014: estimate everything on 2003–2014, then confirm sign, magnitude within a factor of two, and significance on 2015–2025 without re‑fitting. Report results separately for eight GICS sectors and check that the coefficient is positive in at least six — a result driven by Info Tech and Health Care alone is a different, narrower finding and should be described as such. Re‑run the entire pipeline with (i) TNIC peer groups instead of GICS, (ii) EV/NTM Sales and P/NTM EPS as alternative dependent variables, (iii) EBITDA *yield* (E/EV) rather than log multiple, which handles the skew and near‑zero denominators more gracefully, and (iv) FactSet consensus in place of I/B/E/S for 2015–2025. Run a placebo in which each firm is assigned to a randomly chosen sub‑industry's peer group for demeaning; the coefficient on peer‑relative growth change should collapse toward the raw, non‑demeaned coefficient — if it doesn't, the "within‑industry" claim is not doing any work and you are just measuring a market‑wide effect. Finally, bootstrap the Fama‑MacBeth coefficient series by block (12‑month blocks, 1,000 draws) to get a confidence interval that respects the serial correlation.

## 5. Pitfalls I would watch, in order of how much damage they do

**The mechanical denominator problem.** If consensus NTM EBITDA is revised up and the price does not move, the multiple falls by construction. Since NTM revisions and two‑year CAGR revisions are correlated, a naive regression can produce a *negative* coefficient for purely arithmetic reasons. Two defenses: always include $\Delta \log E^{NTM}$ as a control (so $\beta_1$ is identified off changes in the *shape* of the forecast path holding the near‑term base fixed), and run a variant where the growth measure is built from FY2→FY4 only, which shares no term with the NTM denominator.

**Reverse causality.** Analysts revise after prices move, not only before. The panel result is a correlation, not a causal claim, and should be labelled as such. The earnings‑date event study (Spec 4) and a lead‑lag matrix (regress $\Delta_3 \log M$ at t on $\Delta_3 g$ at t−3, t, t+3) are the honest way to bound this.

**Point‑in‑time integrity.** GICS assignments, index membership, Compustat restatements, and I/B/E/S consensus all have look‑ahead traps. Use the historical GICS file, not the current one; use I/B/E/S summary *as of* the statistical period end date, not the latest vintage; lag Compustat by report date. Verify by reconstructing the peer median multiple for three sub‑industries on three historical dates against contemporaneous Bloomberg screens.

**EBITDA definition drift.** I/B/E/S EBITDA is a contributor‑defined, adjusted number that is neither Compustat's OIBDPQ nor the company's own "adjusted EBITDA." It has become progressively more inclusive of stock comp add‑backs over the sample. Check for a structural break by regressing (I/B/E/S NTM EBITDA − Compustat realized OIBDP over the same window) on time; if the gap trends, include a year‑by‑sector adjustment or restrict the main test to 2010 onward.

**Multicollinearity between revenue and EBITDA growth.** Expect VIFs of 3–6. Orthogonalize as described rather than reporting unstable individual coefficients, and report the joint F‑test.

**Negative and near‑zero denominators**, which produce explosive multiples and asymmetric truncation. The yield specification is the fix; the log‑multiple specification with the >0 filter creates a selection effect that must be checked by comparing the characteristics of dropped versus kept firms.

**Regime dependence.** 2020–21 will dominate any unfiltered estimate: growth forecasts and multiples both exploded, and 2022 reversed both. Report results with and without April 2020–June 2021, and include a control for $\Delta$ 10‑year real yield interacted with the firm's "duration" (starting multiple), because a large share of multiple variance in 2022 is discount‑rate driven and unrelated to the hypothesis.

**Overlapping windows and false precision.** t‑stats of 12 on monthly overlapping 12‑month changes are an artifact. Trust the non‑overlapping quarterly panel and the block bootstrap.

**Thin peer groups.** GICS sub‑industries with 6–8 members produce noisy medians and, when a single large name moves, mechanical negative correlation among the rest. Report the main result restricted to sub‑industries with ≥12 members.

## 6. Deliverables and sequence

Week 1–2: data assembly and the calendarization/EV construction, with a written data‑integrity memo including the Bloomberg spot checks. Week 3: descriptive work — distributions of $g$ and $\Delta g$ by sector, the correlation matrix, the raw scatter of $\Delta g$ against $\Delta \log M$ by sector decile, which will already tell you whether there is a there there. Week 4–5: Specifications 1–3 plus the DCF calibration grid. Week 6: event study and lead‑lag. Week 7: portfolio test and factor attribution. Week 8: out‑of‑sample and robustness battery, then a 10‑page write‑up whose central exhibit is a table of implied turns of EV/EBITDA per 100bp of two‑year CAGR change, by sector and by ROIC‑spread quartile, alongside the DCF‑implied benchmark. That table is what an analyst can actually use on a live name.