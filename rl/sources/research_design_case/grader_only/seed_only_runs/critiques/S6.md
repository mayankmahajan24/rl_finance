# S6 — critique (claude-opus-5)

> Do changes in next-two-year revenue and EBITDA CAGR drive earnings-multiple re-ratings among peers within an industry?

---

## Bottom line

The plan is well above average — the null-to-beat framing, the DCF calibration benchmark, the placebo instinct, and the EBITDA-definition-drift concern are all things most analysts skip. But it has one structural error that runs through the whole design, one missing gate that could make the entire eight weeks unanswerable, and a portfolio test that is almost certainly measuring something already known. It is also roughly three times the work the calendar allows.

I'd approve a scoped-down version gated on a three-day data check. Details below.

---

## 1. The mechanical-bias section has the sign backwards, and that matters

§5 says a naive regression "can produce a *negative* coefficient for purely arithmetic reasons." Work it through:

- log M = log EV − log E_NTM
- g ≈ ½(log E_N3Y − log E_NTM)

Both the dependent variable and the regressor are *decreasing* in E_NTM. If NTM is revised up and the far-year estimate is sticky (which it is — see §2 below), Δg falls and Δlog M falls together. The mechanical bias is **positive**, in the direction of the hypothesis. That is the dangerous case, and the analyst has written himself instructions to look for it in the wrong direction.

The good news: including Δlog E_NTM as a control fixes it *exactly*, in algebra. Regressing (Δlog EV − Δlog E_NTM) on ½(Δlog E_N3Y − Δlog E_NTM) and Δlog E_NTM is identical to regressing Δlog EV on Δlog E_N3Y and Δlog E_NTM. β₁ is then a clean "elasticity of EV to the far leg of the forecast path, holding the near leg fixed."

The bad news: **every transformation in §2 breaks that cancellation.**
- g is defined as a ratio-power minus one, not in logs, so cancellation is only approximate and fails in the tails where the interesting observations live.
- g is winsorized at ±60% *in levels* before differencing, and Δg is winsorized separately at 1/99 within date, while the control presumably gets its own treatment. Asymmetric winsorization of algebraically linked terms reintroduces exactly the bias you were purging.
- The FY4 fallback ("extrapolate FY3 forward at the FY2→FY3 growth rate") makes E_N3Y a deterministic function of FY2, which is a component of E_NTM. For ~60% of the sample the numerator and denominator of g share a term. This is not a robustness flag; it's contamination of the majority of the panel.

**Fix:** work in logs end to end. Define the regressor as Δlog E_N3Y with Δlog E_NTM as a control, apply identical winsorization to both, and make the FY4-available subsample the primary specification with the extrapolated sample reported separately. Also note this reframes the exercise honestly: you are testing whether EV responds to the *shape* of the forecast path. "Multiple re-rating" is a presentational wrapper, not the object of estimation.

## 2. Missing kill gate: does FY3/FY4 EBITDA consensus actually move?

This is the risk that ends the project in week 6 rather than week 1. FY3 and FY4 EBITDA consensus for the median Russell 3000 name is contributed by 3–5 analysts, updated infrequently, and for many contributors is a mechanical rollforward of a model rather than a view. If Δlog E_N3Y is a smoothed, lagged image of Δlog E_NTM, then after conditioning on the NTM control there is nothing left to estimate and every downstream result is noise.

**This must be step zero, not week 3 descriptives:**
- Fraction of firm-months with *any* change in FY3 EBITDA consensus.
- Distribution of days since last FY3 revision.
- R² of Δlog E_N3Y on Δlog E_NTM (contemporaneous and with leads/lags). If it's above ~0.8, or if the median firm-quarter shows zero FY3 movement, the question cannot be answered with summary consensus and you need a different growth proxy — analyst-level path shape from the Detail file, or LTG consensus, or realized forward growth.

Pre-commit to the kill threshold before running it.

## 3. Spec 4 may not be constructible as written

The event study needs Δg over the **5 trading days after RDQ**. The standard I/B/E/S Summary History file is a monthly snapshot (third Thursday). If that's the file being used, a 5-day window is impossible. You need the weekly/daily summary file (licensing check) or you need to build rolling consensus from Detail History yourself — which is a week of work, not an afternoon, and is not in the schedule.

Separately, the matched control group is matched on sub-industry, size, and starting multiple, but **not on the near-term revision**. A firm in the top decile of Δg at the print almost certainly also beat and got FY1/FY2 raised. Without matching on ΔlogE_NTM decile, Spec 4 will "work" and what it will have measured is post-earnings-announcement drift. Add the near-term revision to the match, or the event study proves nothing.

## 4. The portfolio test is measuring something you already know

Three problems, in order:

**Sign convention.** The signal is the residual from a regression whose LHS is *contemporaneous* Δlog M. A large positive residual = a firm whose multiple went up more than revisions justify. The plan describes ranking on "firms whose growth was upgraded more than their multiple response would suggest," which is the *negative* residual. As written the trade is ambiguous, and whichever way you resolve it, you're trading a short-horizon multiple-change residual.

**What it actually is.** That residual is a linear combination of short-term reversal, industry-relative value (cheapness vs. peers), and revision momentum. The factor set includes revision and 12-1 momentum but omits short-term reversal, HML, and any industry-relative value control. Add all three or the alpha is not interpretable.

**Implementation.** Monthly re-rank on a 3-month-change residual, quintiles within ~150 sub-industries requiring only 6 peers, equal-weighted: you get one or two names per side per bucket, dominated by the small-cap tail, at 400%+ turnover. 25/45bp round-trip is optimistic for the Russell 3000 lower half and European mid-caps. Report cap-weighted as primary, report capacity in dollars, and report the result restricted to sub-industries with ≥12 members (which §5 already promises for the panel but not for the backtest).

## 5. Specification issues that will produce unstable estimates

**Double demeaning.** §2 constructs peer-demeaned variables; Spec 1 adds sub-industry × month fixed effects. Applied together these are redundant and near-collinear. Pick one: peer-demeaned variables in the Fama-MacBeth (Spec 2), raw variables with FE in the panel (Spec 1). As a consequence, the §4 placebo — randomize the peer group used for demeaning — tests nothing in a specification where FE already absorb the industry-month mean. Restate the placebo as a randomized *fixed effect* assignment.

**Starting log multiple is doing four incompatible jobs**: mean-reversion control in Spec 1, duration proxy in the rate interaction, quality/expensiveness conditioner in H4, and quartile conditioner in Spec 3(b). You cannot include it as a control and simultaneously interpret coefficients on interactions with it. Choose the roles and be explicit.

**ROIC − WACC (H3) is really just ROIC.** Cross-sectional variation in a CAPM/Blume-beta WACC is small and mostly noise; the interaction will be ~95% driven by ROIC. And NOPAT/(net debt + book equity) is wrecked by buybacks and goodwill — a meaningful chunk of large-cap industrials have negative or trivial book equity. Drop the WACC pretense, use within-sub-industry ROIC deciles or gross-profit-to-assets, and report the acquisitive subsample separately. Also be honest that "growth is worth more at high-ROIC firms" is a well-documented result confounded with asset-light/intangible-intensive business models.

**Fama-MacBeth on 6-name peer groups.** After demeaning, within-group residuals sum to zero by construction; cross-sectional coefficients from 6–8 observation groups are severely biased and noisy. Weight by group size or use a rank-based within-group specification.

**Missing controls.** EV/EBITDA ignores capex — which is precisely why two firms with the same EBITDA CAGR trade at different multiples. Δ(capex/EBITDA) or Δ(EBITDA-to-FCF conversion) is a first-order omitted variable here and isn't in X.

## 6. The DCF benchmark (Spec 5) is the best idea in the plan and is underspecified

"Perturb the two-year CAGR by +100bp holding everything else fixed" — holding *what* fixed? If years 1–2 growth rises and the fade path and terminal ROIC are unchanged, essentially all the value change comes from compounding a higher base into perpetuity, and the implied elasticity is enormous and entirely driven by the arbitrary 8-year fade.

The empirical β you'd compare it against is a *relative*, 3-month-change elasticity in a world where consensus CAGR revisions are themselves partially transitory. To make the comparison meaningful you need one extra estimated object: **how much of a +100bp revision to the two-year path survives into realized years 3–5.** Regress realized medium-term growth on the revision. Feed that persistence into the DCF. Without it, "β is 2× DCF-implied in the top quartile" is uninterpretable.

## 7. Sequencing error: levels before changes

The plan jumps straight to changes. The *level* relationship — relative log EV/NTM EBITDA on relative NTM→N3Y growth, by sector, Fama-MacBeth — is cheap, robust, and is what actually produces the deliverable table in §6 ("turns per 100bp, by sector and ROIC quartile"). It also disciplines expectations for the changes regression: the changes elasticity will come in materially *below* the levels elasticity because of attenuation from measurement error in a small-variance regressor. Pre-commit to that expectation or you'll misjudge success and failure. The prior of 5–15 is a levels prior applied to a changes test.

## 8. Scope

Eight weeks for a two-region, two-vendor panel with PIT Compustat, historical GICS, TNIC, an analyst co-coverage network, six specifications, a DCF grid, an event study, a backtest, out-of-sample, and four alternative dependent variables — that's four to six months. "Weeks 1–2: data assembly plus Bloomberg reconciliation memo" for US + Europe with calendarization and EV construction is not real. Also, §4's out-of-sample criterion "magnitude within a factor of two" is not a criterion, and the 2015–2025 OOS window contains the 2020–21 period §5 wants excluded. Pick one.

---

## What I'd approve

**Days 1–3 (gate).** US only, Russell 1000 + S&P 400, 2005–2025, I/B/E/S only. Answer: does FY3/FY4 EBITDA consensus move independently of FY1/FY2? Kill thresholds pre-committed. Also confirm which I/B/E/S summary frequency you actually have licensed.

**Week 1–2.** Levels regression: relative log EV/NTM EBITDA on relative NTM→N3Y growth, Fama-MacBeth by sector, with margin, ROIC decile, leverage, size, capex intensity. Produces the deliverable table. Plus the DCF grid with an *estimated* revision-persistence input.

**Week 3–4.** Changes regression, non-overlapping quarterly, in logs throughout, Δlog E_N3Y with Δlog E_NTM as control, FY4-available subsample primary. Revenue/margin decomposition. Lead-lag matrix.

**Then stop and decide.** The event study, the drift test, the portfolio construction, Europe, TNIC, co-coverage peers, and the FactSet replication are a separate project, justified only if the changes regression survives the NTM control with a coefficient that is (a) statistically distinguishable from the mechanical bound and (b) economically distinguishable from the DCF benchmark.

The levels work is roughly 25% of the effort and produces the thing an analyst can use on a live name. The changes/drift/tradability work is a genuinely riskier bet and should be paid for separately, on evidence.
