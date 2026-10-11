# S5 — plan (claude-opus-5)

> Does sentiment expressed on earnings calls predict a company's outperformance versus its peers?

---

# Research Plan: Does Earnings-Call Sentiment Predict Peer-Relative Outperformance?

## 1. The hypothesis, stated tightly

The loose version of the idea — "positive tone on calls means the stock goes up" — is almost certainly true and almost certainly useless, because tone is mechanically correlated with the earnings surprise the call is discussing. The tradable version is narrower:

**H1 (information content).** After controlling for the reported earnings surprise, guidance revisions, and the stock's contemporaneous price reaction, the tone of management's *unscripted* answers in the Q&A section contains incremental information about the firm's competitive position, and this information is impounded slowly.

**H2 (peer-relative).** Because tone is contaminated by industry-wide conditions (every semiconductor CEO sounds gloomy in a downturn), the signal is cleanest when both the sentiment measure and the return are measured relative to a peer group. Cross-sectionally demeaning tone within a sector-quarter should *increase* predictive power, not decrease it.

**H3 (mechanism).** If the signal is real, residual tone should predict future *fundamentals* — the next quarter's earnings surprise and the intervening analyst estimate revisions — not just returns. This is the test that separates a genuine information signal from a data-mined return pattern.

The primary economic question we are answering: is there a sector-neutral long/short signal here with a post-cost information ratio above ~0.5 on a monthly-rebalanced, three-month-holding basis, in the top 1,500 US stocks by market cap?

## 2. Data

**Transcripts.** S&P Global Market Intelligence (Capital IQ) transcripts, 2006–2024, accessed via the Xpressfeed transcript tables. Capital IQ is preferred over Refinitiv StreetEvents because it tags speaker role (executive vs. analyst), section (presentation vs. Q&A), and component type at the paragraph level, which we need for H1. Critically, we take the **call start and end timestamps**, not the transcript publication timestamp, and we verify against a sample of 200 calls that the transcript's "most recent version" flag is being handled correctly — Capital IQ revises transcripts, and naive pulls give you the corrected version with a stale date.

**Returns and prices.** CRSP daily, US common shares (share codes 10, 11), primary listing, plus CRSP delisting returns.

**Fundamentals and estimates.** Compustat quarterly (point-in-time via the Compustat Snapshot / unrestated file where available; otherwise lag reported items by the actual filing date from the SEC full-text index). I/B/E/S Detail History for consensus EPS, actuals, and analyst-level revisions — using the *unadjusted* files to avoid the well-known split-adjustment rounding problem in the summary file.

**Peer groups.** Primary definition: GICS sub-industry (level 4), requiring at least 5 firms in the group in that quarter. Robustness definition: Hoberg-Phillips TNIC-3 industries (text-based, time-varying), which better capture product-market competitors and are updated annually. A third check: analyst co-coverage peers from I/B/E/S (firms sharing ≥3 covering analysts).

**Universe.** Stocks in the top 1,500 by market cap at each month-end, price ≥ $5, with a transcript in the prior 63 trading days. Expect roughly 1,200–1,400 names per month with usable calls after 2010; coverage is thinner and biased toward large caps before 2008, which is why the sample starts in 2006 and the in-sample period starts in 2008.

## 3. Constructing the sentiment measures

Build three families so that no result depends on one vendor's black box.

**(a) Dictionary tone.** Loughran-McDonald 2023 master dictionary. Net tone = (positive − negative) / (positive + negative + 1), computed separately for: full call, prepared remarks, management's Q&A answers, and analysts' questions. Also compute the LM *uncertainty* and *litigious* word rates, and a hedging count using a hand-built list ("we believe," "should," "roughly," "somewhat," "we'll see," "hard to say").

**(b) Transformer sentiment.** FinBERT (ProsusAI variant, pretrained on Reuters TRC2 1996–2007 and fine-tuned on Financial PhraseBank) scored at the sentence level, then aggregated as the mean of (P(positive) − P(negative)). FinBERT's known training cutoff matters: it lets us score the whole 2008–2024 sample without look-ahead contamination. **Do not** use GPT-4-class models for the primary signal — their training corpora extend through the test period and they may have memorized outcomes. If we want an LLM comparison, run it only on the 2023–2024 holdout as a descriptive check, and disclose it as contaminated.

**(c) Within-firm tone change.** ΔTone = current call tone minus the firm's trailing four-call mean. This differences out the CEO's baseline verbosity and the firm's boilerplate, which is the single largest source of cross-sectional variation in raw tone.

**Orthogonalization.** For each call, regress each tone measure cross-sectionally (within sector-quarter) on: standardized unexpected earnings (SUE, defined as actual minus median I/B/E/S consensus in the 90 days before the call, scaled by the standard deviation of analyst estimates), revenue surprise, the change in management guidance midpoint versus prior guidance, the stock's [−1, +1] abnormal return around the call, log market cap, book-to-market, 12-1 momentum, and the prior quarter's tone. **The residual from this regression is the signal.** Save the raw measures too, so we can show how much of the apparent predictive power is just the surprise in disguise.

Finally, standardize the residual within sector-quarter to a z-score, winsorized at ±3. This is `TONE_RESID`.

## 4. Dependent variables

Peer-relative return is defined as the stock's return minus the equal-weighted return of its GICS sub-industry peers (excluding itself), over:
- **[0, +1]**: the announcement window — a test of whether tone is *news* at all.
- **[+2, +63]**: the drift window — the tradable question, starting two days after the call so we are not assuming instantaneous execution.
- **[+2, +126]**: persistence.
- **Placebo: [−63, −2]**: sentiment should *not* predict past peer-relative returns beyond what momentum controls absorb. If it does, we have a leakage or timing bug.

For fundamental tests: next quarter's SUE, and the cumulative change in the FY1 consensus estimate over [+2, +63], scaled by price.

## 5. Estimation

**Step 1 — Panel regressions.** Regress each dependent variable on `TONE_RESID` with sector × quarter fixed effects and standard errors double-clustered by firm and calendar quarter. Report the coefficient in basis points per one-standard-deviation of tone. This is the cleanest statement of the effect size.

**Step 2 — Fama-MacBeth.** Every month-end, take all stocks with a call in the prior 63 trading days, run a cross-sectional regression of the next month's peer-relative return on `TONE_RESID` plus size, book-to-market, momentum, short-term reversal, gross profitability, asset growth, and SUE. Average the 200-odd monthly coefficients, Newey-West with 6 lags. This is the specification most comparable to the published literature and the one a portfolio manager will recognize.

**Step 3 — Portfolios.** Each month-end, sort within sector into quintiles on `TONE_RESID`. Long the top quintile, short the bottom, sector-neutral by construction, holding three months in overlapping tranches (one-third of the book rebalances monthly, Jegadeesh-Titman style). Run both equal-weighted and a capacity-realistic weighting (weight ∝ 20-day median dollar volume, capped at 2% per name). Evaluate the return series against the Fama-French five factors plus momentum plus short-term reversal, and — importantly — against a post-earnings-announcement-drift factor built from SUE-sorted portfolios, since PEAD is the most likely thing this signal is secretly picking up.

**Step 4 — Costs.** Apply a per-side cost of half the Corwin-Schultz effective spread estimate plus 5bp of market impact, and report turnover. The signal turns over roughly once per quarter by construction, so annual two-way turnover should be around 400–600%; at ~15bp round-trip for large caps this is 60–90bp per year of drag, which the gross alpha must clear comfortably.

## 6. Validation

**Sample split.** Estimate and specify everything on 2008–2018. Freeze the specification in writing — signal definition, universe, weighting, holding period — then run 2019–2024 once. Any degradation beyond a 40% haircut in the information ratio is a red flag for overfitting or crowding.

**Cross-market replication.** Rerun the frozen specification on STOXX Europe 600 constituents, 2010–2024 (Capital IQ transcript coverage in Europe is adequate from about 2010, English-language calls only). A signal that works in the US and not in Europe isn't necessarily dead, but it needs an explanation.

**Robustness grid.** Vary: peer definition (GICS sub-industry vs. TNIC-3 vs. co-coverage), sentiment engine (LM vs. FinBERT vs. ΔTone), section (Q&A-only vs. full call), size bucket (top 500 / 501–1500), and holding period (1, 3, 6 months). Report the *full* grid, not the best cell. A real effect should be positive in the large majority of the ~50 cells with the Q&A-only, TNIC-based, ΔTone version strongest; a fragile effect will be positive in a handful.

**Multiple-testing discipline.** With this many specifications, use a t-statistic hurdle of 3.0 for the headline claim, per Harvey-Liu-Zhu, and report the Benjamini-Hochberg adjusted p-values across the robustness grid.

**Mechanism test.** H3 above. If `TONE_RESID` predicts next-quarter SUE and analyst revisions with the same sign as returns, we have a story. If it predicts returns but not fundamentals, we should suspect that we're capturing a risk premium or a sentiment-driven mispricing that could reverse — check for reversal in [+127, +252].

**Bug hunts.** Randomize the transcript-to-firm mapping 500 times and confirm the alpha distribution is centered on zero. Shift all call dates forward by exactly one quarter and confirm the signal dies. Both are cheap and catch the most common catastrophic errors.

## 7. Pitfalls to watch

**Timing.** The most likely fatal error. Most calls happen after the close on the announcement day, but a meaningful minority happen the morning of the next trading day, and some happen mid-session. Rule: a call is only actionable from the open of the first trading session that begins at least 30 minutes after the call's *end* timestamp. Verify by hand-checking 100 calls against news archives.

**Tone is not orthogonal to the surprise.** Raw tone and SUE correlate around 0.3–0.4. Check VIFs after orthogonalization; if the residual signal has an R² above ~0.5 against the control set, the residual is mostly noise and the effect size will be unstable.

**Boilerplate and manager fixed effects.** Some CEOs are structurally cheerful. Raw cross-sectional tone sorts will systematically select the same firms every quarter, producing a signal that is really a slow-moving quality or industry tilt. The ΔTone variant and within-firm demeaning are the defense; always report the average within-firm standard deviation of the signal to confirm it actually varies over time.

**Sector composition.** Software companies use more superlatives than utilities. Within-sector standardization handles the mean, but not the variance — check that the signal's standard deviation is comparable across sectors and rescale if not.

**Regime breaks.** COVID (2020Q1–Q2) produced an enormous uniform negative tone shock and a suspension of guidance at hundreds of firms. Report results with and without 2020 excluded. Similarly, the shift to fully scripted calls with pre-submitted questions at some firms post-2021 mechanically reduces Q&A informativeness.

**Crowding.** This literature is public (Mayew-Venkatachalam 2012, Druz et al., a decade of quant vendor products). Expect the effect to be materially weaker post-2015. If the 2019–2024 holdout shows near-zero alpha, that is a finding, not a failure — and it points toward the residual opportunity being in the harder-to-process parts of the call (voice, hesitation, deflection of specific questions) rather than lexical tone.

**Survivorship and selection.** Firms that stop hosting calls are disproportionately distressed. Include them until delisting with CRSP delisting returns, and confirm the signal isn't driven by the tail of firms whose last call was gloomy.

## 8. Deliverables and timeline

Weeks 1–2: data assembly, timestamp validation, universe construction. Week 3: sentiment measure construction and orthogonalization. Weeks 4–5: in-sample panel, Fama-MacBeth, and portfolio results on 2008–2018. Week 6: robustness grid and mechanism tests; freeze specification. Week 7: holdout run and European replication. Week 8: write-up.

The output is a 15-page memo with a single headline table (effect size in bp per SD, in-sample and out-of-sample, gross and net of costs), the full robustness grid as an appendix, and an explicit recommendation on whether the signal warrants a paper-trading allocation.
