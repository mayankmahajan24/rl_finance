Who this is for:

A mid-size fundamental long/short equity fund. ~30 investment staff, a three-person data team that licenses and cleans alt-data panels, and one engineer. Horizon is six to eighteen months. They can run a panel study or a cohort analysis and routinely buy transaction and web data, but they do not have tick data or execution infrastructure and will not build production ML. Output is expected to change position sizing on named companies, and to be defensible to a PM who will ask what would have to be true for it to be wrong.

Research question:

Do changes in next-two-year revenue and EBITDA CAGR drive earnings-multiple re-ratings among peers within an industry?

---

PLAN A:

"Does CAGR drive multiple re-rating" is circular as posed: forward multiples have the revised estimate in the denominator. Reframe as three pre-committed hypotheses.

**H0 (feasibility gate):** consensus 2-year-out revenue/EBITDA move enough, often enough, across enough names to support inference; if not, say so and stop.

**H1 (primary):** peer-relative re-rating sensitivity β is not stable across regimes — larger when discount-rate volatility is high, growth-minus-value spread is trending, and cross-sectional revision dispersion is wide, beyond sampling noise.

**H2 (primary):** the initial re-rating is not efficient — either underreaction (continues accruing over 1-12 months) or overreaction (partially reverses), judged against a benchmark β* from realized persistence of the revised growth path.

**Data/measurement.** Build a constant-horizon 24-month-forward estimate by time-weighting FY1/FY2 consensus by months to fiscal year-end, for revenue and EBITDA separately; 2-year log CAGR = ½·[ln(E₂₄ᵐ)−ln(base)], revision variable ΔCAGR = ½·Δln(E₂₄ᵐ). Consensus changes computed on the fixed same-analyst set live at both endpoints, from I/B/E/S (or CIQ) detail files, not summary tape; report how much raw consensus change survives this filter. Primary DV: Δln(EV/LTM EBITDA), LTM EBITDA held fixed through the window (denominator is realized, not estimated). Robustness: EV/LTM sales, P/LTM EPS; never EV/NTM EBITDA as primary. Everything demeaned within GICS sub-industry × date, industry×date fixed effects; robustness on Hoberg-Phillips TNIC-3 and FF48. Filters: exclude financials/REITs, ≥8 peers in industry-month, ≥3 brokers with live FY2 revenue and EBITDA, price>$5, cap above NYSE 20th percentile, US common shares, 2003-2025.

**Identification.** Event = single broker's FY2 EBITDA/revenue revision moving same-analyst 24-month growth path ≥50bp annualized, timestamped via I/B/E/S detail activation; CAR windows (−1,+1) primary, (0,+1) reported. Main sample restricted to off-cycle days (no earnings ±2 RDQ days, no guidance, no M&A, no material 8-K, no other same-day revision) — costs ~60-70% of events; earnings-day sample reported separately with SUE controls. From 2010, TAQ check: compare pre- vs post-activation 2-hour signed returns to gauge reverse causality.

**Gate.** Per industry-month: SD of trailing 3-month same-analyst ΔCAGR_ebitda ≥75bp annualized, median |Δ|≥25bp, ≥50% of firm-months with a live revision in prior 90 days, in ≥60% of months — else exclude the industry. First-stage threshold: pooled announcement-window β ≥20bp peer-relative abnormal return per 100bp revision, t>5, else stop.

**Estimation.** Monthly cross-sectional regressions of Δln(EV/LTM EBITDA) on standardized ΔCAGR_ebitda and ΔCAGR_rev jointly, controls for size, book/market, momentum, prior revision, FY1 revision, analyst count, broker FE; Fama-MacBeth with Newey-West (6 lags), plus two-way-clustered panel. Stability tested via: Wald test across pre-committed regime buckets (VIX terciles, trailing 6-month real-yield sign, growth-value spread terciles, revision-dispersion terciles, NFCI sign) with stationary block bootstrap (12-month blocks, 10,000 reps); Bai-Perron sup-F (15% trimming, ≤3 breaks); variance ratio VR=Var(β̂_t)/mean(SE_t²), instability declared only if VR≥2 and bootstrap p<0.05; Kalman-filtered β path as complement. Over/underreaction: (i) drift regressions on CAR(+2,+63)/(+64,+252) plus calendar-time quintile portfolios vs FF5+momentum, t>3; (ii) β* from regressing realized years 3-5 growth on the original revision, fed into a two-stage DCF (r=9%, terminal growth 3%) with sensitivity grid; (iii) 2SLS of days +22-252 multiple change on fitted initial (0-21 day) re-rating.

**Validation.** Placebo (shift events 30 days, coefficient should vanish); randomization (shuffle magnitudes within industry-month, 1,000 draws); reverse-window CAR(−5,−2) as leakage estimate; split-sample (fit 2003-2014, test once on 2015-2025); Benjamini-Hochberg across regime interactions, VIX terciles as sole named primary; minimum detectable β reported before interpreting nulls.

**Pitfalls.** Composition-driven pseudo-revisions; stale consensus (use only estimates refreshed within 90 days); negative/near-zero LTM EBITDA (screen margin≥2%, rank-based check); point-in-time data (unrestated Compustat, contemporaneous GICS, split-unadjusted I/B/E/S, CRSP delistings, net debt lagged to filing date); asymmetric up/down coefficients estimated separately; duration-driven rate loading controlled via real-yield-change × duration interaction; non-rejection of stability is not proof of stability.

---

PLAN B:

**Hypothesis.** Within a GICS sub-industry-quarter, does a 1pp rise in consensus 2yr EBITDA CAGR raise log forward EV/EBITDA relative to peers? H1: yes — a two-stage DCF (8.5% WACC) implies ~8–12%/100bp for durable growth, but measured elasticity should be smaller (~2–5%/100bp) since revisions are partly treated as transitory. H2: conditional on EBITDA revision, revenue-CAGR revisions carry additional positive weight (revenue-led growth reads as more durable); zero/negative would be a genuine surprise. H3: relation strengthens when within-industry dispersion of ΔCAGR is high (interaction positive) — revisions separating peers look like firm-specific information, not industry news. H4: elasticities largest in software, semis, life-science tools, medtech; smallest in utilities, integrated energy, telecom, real estate.

**Data.** Russell 3000 plus MSCI World developed ex-US, 2005Q1–present, point-in-time constituency including dead/acquired tickers. Consensus: I/B/E/S Detail or Refinitiv/LSEG, monthly point-in-time snapshots (Visible Alpha preferred for EBITDA); FY1–FY3 revenue/EBITDA means, contributor counts, estimate SD, fiscal period ends. Prices/shares point-in-time; net debt, minority interest, preferred, pension deficit (Compustat/Worldscope, filing-dated); TTM revenue/EBITDA; GICS sub-industry (8-digit), point-in-time. Auxiliaries: US/EUR/JPY 10yr yields/breakevens, within-industry return dispersion, IFRS16/ASC842 (FY2019) flag.

**Construction.** Forward multiple: constant-horizon NTM EBITDA (time-weighted FY1/FY2) against EV at same month-end, off latest filed balance sheet; DV = Δlog(EV/NTM EBITDA), QoQ, quarter-end snapshots. Growth: time-weighted NTM and N2Y (next-24mo) revenue/EBITDA; CAGR = N2Y-implied year-2 level/NTM level − 1; ΔCAGR = QoQ change in pp. Screens: NTM and N2Y EBITDA > 0; ≥4 FY2 contributors; market cap > $500m (2024$); multiple in [2×,60×]; ≥8 firms per sub-industry-quarter else roll to 6-digit GICS industry, drop if still <8. Winsorize both at 1st/99th percentiles within industry-quarter.

**Estimator.** Δlog(EV/EBITDA_NTM) = β1·ΔCAGR^EBITDA + β2·ΔCAGR^Rev + γ'X + δ_st + ε, sub-industry×quarter FE (~150×80, reghdfe/pyfixest.feols) — no macro controls, common shocks absorbed. Controls: log market cap(t-1); net debt/NTM EBITDA(t-1), Δ; NTM margin level(t-1), Δmargin; 12mo lagged return; Δlog NTM EBITDA; analyst count, Δ; CV of FY2 EBITDA estimates, Δ. SEs two-way clustered (firm, quarter), plus Driscoll-Kraay(8 lags); trust conservative one if divergent. Weighting: equal-weight primary, cap-weighted (sqrt) rerun. Report β1 as %/100bp and turns at industry median multiple.

DV and regressor share the EBITDA tape, so whole-curve revision mechanically depresses the multiple. Fix: decompose Δlog EV, Δlog EBITDA_NTM, and multiple as one identity (β_EV=β_EBITDA+β_multiple, pipeline check); headline on β for Δlog EV; report multiple regression with/without Δlog NTM EBITDA as control.

Dispersion test: standardize D_st (cross-sectional SD of ΔCAGR within sub-industry-quarter) over time, interact with ΔCAGR (H3: β3>0), plus tercile split and two alternate proxies (return dispersion, share with |ΔCAGR|>200bp). Industry elasticities: interact ΔCAGR with GICS industry dummies, empirical-Bayes shrink (w=τ²/(τ²+σ̂²)), check rank stability via pre/post-2015 Spearman correlation (<~0.4 → pooled).

**Validation.** Placebo peer reassignment (500 draws) should collapse β1. Timing: monthly predictive version (month-t revision, t+1 multiple), plus post-earnings-5-day subsample. Pre-trend: ΔCAGR(t+1) should be insignificant. Robustness grid: alt DVs (EV/Sales, fwd P/E, EV/EBIT); horizons (1yr,3yr); FY-based vs time-weighted; FE granularity; crisis exclusions (2008Q3–09Q2, 2020Q1–Q2); ex-2019; US vs ex-US; contributor cutoff. Economic validation: β1 vs three-stage theoretical elasticity (industry-beta WACC, 2.5% terminal growth, median cash conversion); 25–50% of theoretical is coherent, above signals pipeline error. Practical validation: quarterly within-industry quintile sort by ΔCAGR, out-of-sample from 2012 (expanding window), report spread/t-stat.

**Pitfalls.** Restated/backfilled consensus data; EBITDA definitional drift (reported/adjusted/pre-SBC) — drop firm-quarters with |ΔCAGR|>20pp absent earnings event or >5% price move; IFRS16 2019 transition as data break for retail/restaurants/airlines/shipping; near-zero-EBITDA denominator instability — check β1 isn't bottom-margin-decile-driven; thin-coverage staleness (analyst-count split diagnoses it); survivorship bias from dropping acquirees (biases upward); FE identification from tiny (8–10 firm) groups (minimum-15-firm check); dispersion-test endogeneity from news volume, partly controlled via earnings/guidance event counts, residual ambiguity stated not resolved.

---

Which plan would you put an analyst on? Answer in the required structured format.
