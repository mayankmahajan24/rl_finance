# S5 — critique (claude-opus-5)

> Does sentiment expressed on earnings calls predict a company's outperformance versus its peers?

---

## Verdict

This is a well-informed plan — the timestamp discipline, the FinBERT-vs-GPT contamination point, the frozen holdout, the randomization bug hunts, and the explicit "tone is mechanically correlated with SUE" framing are all things most analysts get wrong. I'm not going to manufacture objections about those.

But the plan has one structural problem that makes it likely to produce a confident non-answer, and four specification errors that could produce a confident *wrong* answer. And the sequencing is backwards relative to the decision it's supposed to inform.

---

## 1. The decision rule is arithmetically impossible. This is the biggest flaw.

The stated bar is post-cost IR > 0.5. The stated hurdle is t > 3.0 (Harvey-Liu-Zhu). The holdout is 6 years.

An IR of 0.5 over 6 years produces t ≈ 1.2. Over the 11-year in-sample, t ≈ 1.66. Over the full 17 years, t ≈ 2.1. **You have pre-committed to a hurdle that your own target effect size cannot clear on any subsample, or on the whole thing.** So either the go/no-go is undefined, or you've guaranteed a "no" before writing a line of code.

Same problem with the "40% haircut is a red flag" rule. The standard error on a 6-year out-of-sample IR estimate is roughly 1/√6 ≈ 0.41. A signal with true IR 0.5 will produce measured out-of-sample IRs between roughly 0.0 and 1.0 about two-thirds of the time. A 40% haircut is dead centre of the noise distribution. The rule cannot distinguish decay from sampling error.

**Fix:** do the power calculation in week 0, before anything else, and set the decision rule from it. Realistically that means: (a) pick *one* pre-registered headline specification and accept a t≈2 full-sample hurdle for it, (b) treat the robustness grid as a shrinkage exercise rather than a set of hypothesis tests — report the posterior mean IR after shrinking for the number of specifications tried and make the allocation call on the shrunk number, and (c) replace "40% haircut" with "out-of-sample IR point estimate and its confidence interval; proceed if the lower bound clears zero *and* the point estimate clears costs." If none of that produces a decidable question, the honest conclusion is that this project cannot answer the question with 17 years of data, which is itself worth knowing in week 0 rather than week 8.

## 2. Orthogonalizing tone on the [−1,+1] call-window return does two bad things at once.

First, conceptually: if tone is news, the announcement return *is partly the market's reaction to the tone*. Residualizing on it strips out exactly the informative component and leaves you testing a different, much weaker hypothesis — "tone the market ignored." That may be the underreaction story you want, but it is not H1 as written, and you should not discover the difference in week 5.

Second, mechanically: it induces a spurious positive result. Write R₁ = signal + microstructure noise. Residual tone = tone − b·R₁ carries −b·(noise). Bid-ask bounce and short-horizon reversal make that same noise negatively correlated with the [+2,+63] return. Product of two negatives: **your residualization manufactures positive predictive power out of nothing.** With b > 0 (which it will be, tone and call-window return are strongly positively correlated) this is a live path to a false positive that survives all your bug hunts, because the randomization and date-shift tests both destroy the correlation structure that creates it.

**Fix:** drop the call-window return from the primary orthogonalization. Report "tone | fundamentals" as the primary and "tone | fundamentals + price reaction" as a clearly-labelled secondary underreaction test. If you keep the second, use open-to-close on day 0 only, and add a control for the [+2,+5] return to absorb the bounce reversal.

## 3. "Within sector-quarter" is doing two incompatible jobs, and one of them is degenerate.

You define peers as GICS sub-industry (level 4, ~160 buckets), then say you orthogonalize and standardize "within sector-quarter" and form "quintiles within sector." With 1,500 names, sub-industry cells average ~9 firms. You cannot run a 10-regressor cross-sectional regression in a 9-observation cell. You cannot form quintiles in one either. And z-scoring in a 9-name cell then winsorizing at ±3 is theatre.

Meanwhile the "≥5 firms" peer-group minimum means some dependent variables are a stock's return minus a four-stock equal-weighted average — enormous idiosyncratic noise added to the left-hand side, which directly costs you the statistical power you don't have to spare (see #1).

**Fix:** be explicit and separate the three uses. Orthogonalize pooled with sector×quarter fixed effects (not cell-by-cell regressions). Form quintiles at GICS sector or industry-group level (11 or 25 buckets). Measure the dependent variable as a risk-model residual return or a beta-adjusted sub-industry-relative return with a minimum of 8–10 peers, not a raw difference against four names. Use normalized ranks rather than z-scores throughout.

## 4. Portfolio construction doesn't match the event structure, and the seasonality will bite.

The regressions measure [+2,+63] from the call. The portfolios rebalance monthly on "any call in the prior 63 days," so the average holding carries a signal ~30 trading days stale — you are systematically capturing the back half of the drift and paying full turnover for it. Worse, earnings are clustered in four five-week windows. In the off-season months your "fresh signal" cross-section collapses to off-cycle fiscal-year filers, which are heavily industry-clustered (retail, Nov/Jan-year-end tech). Sector-neutral quintiles in early March will have grotesque sector coverage.

**Fix:** run event-time portfolios as the primary construction — each name enters at the actionable open and is held exactly 63 trading days, weights renormalized daily. That's both the honest test and the implementable version. Then report the P&L decomposed by days-since-call. If the alpha lives in [+2,+10], monthly rebalancing throws most of it away and your entire cost analysis is answering the wrong question.

## 5. Nothing in the design tests the hypothesis you actually stated.

H1 claims the signal carries information about "the firm's competitive position." Your mechanism test is next-quarter SUE and FY1 revisions. Neither is a competitive-position variable, and next-quarter SUE is close to mechanically unpredictable from this call's tone: an upbeat CEO guides up, analysts move to the guide, and SUE resets to zero. You've chosen the one fundamental variable that management's own tone is designed to neutralise.

**Fix:** test what you claimed. Peer-relative revenue growth, peer-relative gross margin change, and peer-relative revision breadth over the next 2–4 quarters. Use FY2 rather than FY1 consensus (less anchored to the current guide). Add the sign of the *next* call's [0,+1] return. And run these peer-relative, to match the return test.

Related: your factor attribution includes a PEAD factor but no **analyst revisions** factor. If H3 works, the most likely reading of the whole exercise is that you've built an expensive proxy for earnings-revision momentum. That has to be in the regression or the memo is not credible.

## 6. FinBERT is the weakest of your three engines, not a neutral third leg.

ProsusAI FinBERT is fine-tuned on Financial PhraseBank — ~4,800 short analyst-style *news* sentences labelled by finance students. Applied sentence-wise to Q&A, it will score factual statements ("revenue grew 12%") as positive, i.e. it is *more* mechanically correlated with the reported numbers than Loughran-McDonald, not less. Plus: transcript Q&A is full of "Yes." / "Thanks, John." / cross-talk fragments, so an unweighted mean over sentences is dominated by non-substantive utterances. You need length weighting and utterance filtering, and you should expect FinBERT to underperform ΔTone.

More important: the genuinely differentiated measures are the ones you've relegated to a footnote in the crowding section — **question-answer semantic similarity, whether the answer contains a number, answer specificity relative to question specificity, deflection**. Those are cheap to build off the same parsed data, they are not what the vendors sell, and they are the only part of this that plausibly survives 2019–2024. Move them into scope from day one and drop FinBERT to a robustness cell.

---

## Smaller things that will cost you days

- **Guidance midpoint change** as a control: IBES Guidance coverage is spotty and non-random, undefined for non-guiders and metric-switchers, and vanished for hundreds of firms in 2020. As specified this silently drops or biases 40%+ of your sample. Needs an explicit missing-indicator design.
- **Prior-quarter tone as a control *and* ΔTone as a signal family** is near-double-counting; ΔTone residualized on lagged tone is close to mechanical.
- **The [−63,−2] placebo will "fail" even for a clean signal** — tone correlates with the pre-call run-up and 12-1 momentum won't absorb it at sub-industry-relative horizons. You'll over-interpret it. Use within-sector-quarter shuffles (preserving the cross-sectional distribution) instead, and add analysts'-question tone as a should-be-weak control.
- **Cost model.** Corwin-Schultz is noisy and biased for liquid names; use actual quoted spreads for the top 1,500. Flat 5bp impact ignores that this signal fires in clustered earnings windows where spreads widen and crowding peaks. And 400–600% turnover is optimistic once you add universe churn and the 63-day entry/exit; check it, don't assume it. Missing entirely: borrow cost and availability on the bottom quintile of the 501–1500 bucket.
- **Transcript versioning.** Hand-checking 200 calls doesn't fix it. Either reconstruct from the version-history table, or test whether revisions materially move tone; if they do and you can't reconstruct, you have a look-ahead you cannot remove and must disclose as a bound on the result.
- **Timeline.** Two weeks for CIQ transcript assembly, speaker/section parsing, timestamp validation, PIT Compustat, IBES Detail, Hoberg-Phillips, and co-coverage peers is off by a factor of three. Realistically 5–6 weeks of data engineering before any signal exists. Total is 14–16 weeks, not 8.

## What I'd cut

**Europe.** Half of STOXX 600 reports semi-annually, so your event design breaks, the panel halves, and the signal is twice as stale. Multi-language calls, thin Q&A. It will eat three weeks, not one, and produce an uninterpretable answer. Replace it with the **US 1,501–3,000 cap tier**: same pipeline, genuinely different cross-section, and it's where crowding is weakest — so it's both cheaper and more informative about where residual alpha lives.

---

## The sequencing problem, and the cheap version

Your own pitfalls section says: literature public since 2012, a decade of vendor products, expect the effect materially weaker post-2015, near-zero holdout alpha would be "a finding, not a failure." I agree with all of that. Which means **you have written a plan whose most likely outcome you have already predicted, and you've scheduled the deciding test for week 7 of 8.**

Invert it. Two weeks, one analyst:

1. **Two days of vendor and literature triage.** Amenity, Aiera, RavenPack, Bloomberg and Brain all sell transcript sentiment histories. Request a trial file. If a vendor's back-history shows near-zero sector-neutral IR post-2015, you've bought the answer for the cost of a phone call. Also pull the relevant papers beyond Mayew-Venkatachalam — Druz-Wagner-Zeckhauser, Jiang-Lee-Martin-Zhou, and the ML-on-transcripts literature — several already report the decay.
2. **A ten-day spike:** off-the-shelf LM net tone on management Q&A only, ΔTone version, sector-relative, event-time 63-day holding, top 1,500, **2015–2024 only**, no orthogonalization beyond SUE and no robustness grid. One number.

If that spike shows nothing in the recent decade, kill it — no eight-week build recovers a signal that isn't there in the raw data, and every specification choice you'd make to "find" it is the overfitting you're trying to guard against. If it shows something, you've earned the full build, and you now know which period matters.

The one argument for approving the full spend up front is if the real deliverable is the **parsed-transcript data asset and NLP pipeline** — speaker-tagged, section-tagged, timestamp-validated, question-answer paired — because that supports the deflection/specificity measures, topic exposure, supply-chain mentions, and a dozen future projects. That's a defensible infrastructure investment with lexical tone as its first and probably weakest application. If that's the pitch, say so explicitly and budget it as infrastructure. If the pitch is "lexical tone is an alpha signal," do the two-week version first.
