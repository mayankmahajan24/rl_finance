# S8 — critique (claude-opus-5)

> Do round-lot orders identify retail flow that is profitable to trade against?

---

## Verdict up front

This is a well-written plan with an unusually honest pitfalls section — better than most of what crosses this desk. But it is structured backwards, and it's a nine-week (realistically four-to-six-month) commitment to a question that can be killed or advanced in about ten days. The decisive test is buried in Stage 3 as an afterthought ("does RLOIB add anything to BJZZ imbalance in a joint regression?"). That question should be run in week one. Everything upstream of it is mechanism narrative.

Below: the things that break, then the cheap version.

---

## 1. The gate logic is incoherent, and it front-loads the wrong work

The plan asserts "failing gate 1 makes gates 2 and 3 uninterpretable." That's false. If round-lot imbalance predicts returns net of costs, we have a signal regardless of whether round lots are retail. If it doesn't, no amount of Gate 1 classification success helps us. Gate 1 is a *mechanism* check that determines how much we trust out-of-sample stability — valuable, but not a prerequisite.

Worse, Gate 2 has no path to P&L for this firm and the plan says so itself ("Realized spread is not an achievable P&L... no one can select counterparties"). We are not going into wholesaling. Two weeks (weeks 5–6) are allocated to estimating Citadel's economic rents. **Cut Gate 2 entirely** or demote it to a descriptive paragraph. If you keep it, note it also duplicates a well-trodden literature (O'Hara–Yao–Ye on odd lots, and the price-improvement literature).

Correct ordering: Gate 3 first, on a recent short sample. Gate 1 second, only if Gate 3 shows something.

---

## 2. The Gate 1 label is biased in exactly the direction that determines the answer

This is the most serious technical flaw. The BJZZ subpenny label is only *available* for off-exchange prints that receive subpenny price improvement. Its availability is **correlated with trade size**: wholesalers price-improve small odd-size retail orders in subpennies, while larger and round-size internalized flow is more likely to print at the midpoint or at a round penny, where Z = 0.5 or 0.0 and the algorithm sees nothing.

So the Stage 1 logit is not estimating "does roundness predict retail." It is estimating "does roundness predict *the wholesaler's subpenny pricing convention*." The measurement error is not noise — it is a function of the treatment variable. The plan cites Barber–Huang–Jorgensen–Odean on ~30% misclassification but treats it as attenuation. It isn't; it's directional bias, and it will most likely push the coefficient toward "round lots aren't retail" whether or not that's true.

There is no clean fix with BJZZ. What you can do:
- Condition the analysis entirely *within* off-exchange subpenny-eligible prints and report that the estimand is now narrow.
- Use exchange retail liquidity program flags (NYSE RLP, Cboe/Nasdaq retail programs) as a size-unbiased, venue-limited second label.
- Accept that Gate 1 cannot be settled and lean on the return test, which does not require a label.

Also, the logit's dependent variable is mechanically zero for all lit trades. Running it on the pooled sample with venue dummies makes the venue dummy absorb ~all the variation. State clearly that Gate 1 is a within-off-exchange test or it will produce a garbage coefficient with a huge t-stat.

---

## 3. The "discontinuity in trade size" is not an RD and its neighbors are a selected population

Two problems:

**Density.** RD requires a smooth density of the running variable at the cutoff. Trade size has a massive point mass at 100 and near-zero mass at 96–99 and 101–104. A McCrary test doesn't fail marginally — it fails by construction. Calling this an RD will get it shot down internally and externally.

**Selection.** The identifying assumption — "a 101-share order and a 100-share order convey the same information" — is almost certainly wrong. Nobody discretionary sends 101 shares. 101-share prints are residuals of larger parent orders, partial fills, and algo remainders. That population is *more* informed on average, because it is the tail of institutional parent orders. So the comparison will mechanically show 100-share prints looking less toxic than their neighbors, for reasons having nothing to do with retail or roundness salience.

If you keep this, reframe it honestly as size-neighborhood matching and add the one diagnostic that matters: partition by whether the print is standalone versus part of a same-stock/side/venue burst within ~100ms. Standalone 101s are the only valid comparison group. My guess is there are very few of them.

---

## 4. Venue, not size, is the primary partition — and the signal as constructed pools them

RLOIB as defined pools lit and off-exchange round lots. Lit round-lot volume is dominated by algorithmic child orders; off-exchange round-lot volume is the only place a retail story lives. Pooling guarantees dilution and makes the coefficient uninterpretable. Make venue (D vs. lit) the primary partition and roundness the secondary cut, and report the four-cell table before anything else.

---

## 5. The timeline is off by roughly 3x

Ten years of Daily TAQ, ~3,000 names, nanosecond timestamps, full NBBO, Holden–Jacobsen interpolation, sale-condition filtering, and ITCH validation — in "weeks 1–2." That is not a two-week job unless the desk already owns a validated signed TAQ panel. If it doesn't, budget six to ten weeks for that step alone. Ask this question before approving anything: **do we already have a signed, NBBO-matched trade panel, and for what universe and period?** The answer determines whether this is a 9-week or a 6-month project.

Related: LOBSTER is Nasdaq-only. It gives true aggressor side for *lit Nasdaq* executions and tells you nothing about off-exchange prints — which is precisely where the retail flow and the hardest signing problem live. So the "Lee–Ready error rate by size bucket" validation, while a good idea, validates the part of the data that matters least. Say so, and don't pay for 4,000 LOBSTER stock-days to learn it.

---

## 6. The FINRA wholesaler list has a structural break at the sample split

The named list — Citadel, Virtu, G1 Execution, Jane Street, Two Sigma Securities, UBS — is not time-invariant. UBS exited retail wholesaling (flow moved to Citadel); G1 sits under Susquehanna; Jane Street is not a retail wholesaler in the same sense as the others. A fixed list produces a mechanical level shift in your "most reliable label" around 2021 — exactly where you split train and test. Build a time-varying wholesaler roster with documented entry/exit dates, or the label-independent check is contaminated at the seam.

Separately: FINRA non-ATS data is reported with a lag and at different frequencies by tier. Confirm the panel is actually weekly for your universe before building on it.

---

## 7. The out-of-sample split is out-of-regime, so failure will be uninformative

The plan argues forcefully that the object breaks in 2019–2021 (commission-free, fractional shares, the 2021 episode, MDI round-lot redefinition, 2024 tick-size amendments effective late 2025). Then it splits train/test at exactly that break. If the test fails, you will not be able to distinguish overfitting from regime change, and you'll have burned your one clean look.

Better: build on 2022–2024, hold out 2025. Use random stock-halves or interleaved quarters for overfit detection. Treat 2016–2020 as a historical appendix. The only regime we can deploy into is the current one.

Also note the 2024 tick-size amendments introduce half-penny quoting for tick-constrained names — this changes the subpenny distribution and partially breaks BJZZ mechanics for the affected symbols going forward. That belongs in the framing, not the pitfalls list.

---

## 8. Missing from the investability analysis

- **Borrow.** A signal that fades retail enthusiasm will short exactly the names with the worst borrow. The plan has no locate cost, no hard-to-borrow screen, no analysis of what happens to alpha when you restrict to GC names. For this specific strategy that is likely where most of the paper alpha dies.
- **Incrementality against our existing book.** FF5+MOM+STR alphas are an academic bar. The desk bar is the correlation of this signal's daily returns with our existing short-term reversal and order-flow signals. Run that before the factor regressions.
- **Turnover.** A daily-rebalanced imbalance signal is >100% daily turnover. Compute required turnover *first*, then decide whether the cost model matters. κ=0.5 square-root is fine as a placeholder but the half-spread assumption is optimistic for a signal whose entire premise is trading in the same direction as everyone else's reversal.
- **Contradiction in the entry rule.** Section 4 says enter at the open of t+1; Section 6 says skip a full day. Pick both and report both. If alpha only survives close-to-next-open, it's overnight bounce and largely uncapturable.
- **Universe.** Price > $3 with 3,000 names means a large share of any imbalance alpha comes from sub-$500mm names. Pre-register the top ~1,500 by dollar volume as primary.

---

## 9. Pre-registration thresholds are arbitrary and not decision-linked

MCC > 0.10, odds ratio > 1.3, 1.5bp realized spread — these aren't tied to anything that changes what we do. With billions of trades every one of them passes or fails on sample size. Replace Gate 1's criteria with a downstream quantity: the correlation between RLOIB and a credible retail imbalance measure must exceed some level at which RLOIB could plausibly carry incremental information. And $150mm capacity at 5% ADV across 1,500 names is far below what the participation constraint implies — the binding constraint here is alpha decay, not capacity. Re-derive it.

Finally, the multiple-testing section covers buckets × horizons × weightings but not the specification search across nine weeks of exploration. State the primary spec, and state that everything discovered after week one is exploratory.

---

## The cheaper version

Roughly two weeks, one analyst, no LOBSTER, no ten-year TAQ build, no RD.

**Days 1–2.** Sampled TAQ (say 200 stocks × 20 days × one month per year, 2018–2025). One chart: distribution of print sizes by venue and year, plus the share of BJZZ-classified retail volume that falls in each size bucket. This alone probably answers the question. If retail flow has migrated to odd and fractional sizes while 100-share prints are dominated by lit algo children, we're done.

**Days 3–7.** Build RLOIB and BJZZ retail imbalance on ~1,000 liquid names, 2022–2025, daily. Fama–MacBeth at 1/5/20 days, and the joint regression. The single number that matters: the t-stat on RLOIB conditional on BJZZ-OIB, prior-week return, and turnover. If it's under 2, stop.

**Days 8–10.** If it survives: turnover, borrow screen, cost break-even, and correlation with the existing STR book.

Kill criteria: RLOIB adds nothing over BJZZ-OIB; or the alpha is concentrated in hard-to-borrow or sub-$500mm names; or the sign is positive (follow, don't fade), in which case the honest write-up is a one-pager referencing BJZZ and Kaniel–Saar–Titman rather than a project.

Expand to the full plan — Gate 1 mechanism work, ITCH validation, regime analysis — only if the ten-day version comes back positive. At that point you'll be spending the four months to *defend* a result rather than to *look for* one, which is the right time to spend it.
