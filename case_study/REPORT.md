# Can Claude tell good research from bad?

**Mayank Mahajan · Finance Domain Research Lead take-home**

Repo: `github.com/mayankmahajan24/finance_collaborator` — seeds, scripts, eval items, gold labels, scoring, and every raw model call.

*Tables are in Appendix A, referenced by number. Part 0 is Appendix B; repo map is Appendix C.*

---

## Part 1 — Where Claude breaks as a research planner

Ten seed ideas, five quant and five fundamental, mixing obviously good, obviously flawed and subtly flawed. Claude wrote a plan for each, then critiqued it, seeing only the seed sentence. I scored each item myself, and separately against a flaw written in advance.

**Claude applies too much generic research methodology and too little finance knowledge.** It lists the standard ways research goes wrong whether or not they apply. What it misses is almost always a specific fact about the instrument, the data, or how the market prices information (**Table 1**). So this is closer to "doesn't know the finance" than "doesn't know how research goes wrong," and its fluent methodology hides that. Both columns of Table 1 are one problem: falling back on the standard checklist is what a model does when it lacks the specific insight. I found a real defect in **10 of 10 critiques**, at about 2.6 objections each that do not apply — the price of a 2,400-word plan that lists every possible caveat. It also makes work look rigorous with precise numbers it never derived: "stop below 0.5%" reads as discipline, but the number came from nowhere (**Table 3**).

**On the fundamental ideas, is it "anchors on the narrative" or "can't tell mechanism from correlation"?** Neither — only one plan was too anchored, and two rejected the conclusion their seed implied. The real failures were **context and feasibility**: a 40,000 firm-quarter panel proposed to a five-person Bloomberg-and-Excel shop, and public methods for identifying retail orders proposed to a market maker that already holds the real labels internally. Claude reasons about mechanism well and misjudges who it is working for.

**Does it catch its own mistakes?** The critique is better than the plan, but knowing the problem never changes the recommendation. One plan says in its own pitfalls section that the signal is already well known, then budgets eight weeks to test it. Another proposes a random 20% holdout and notes *in the same sentence* that random splits leak — the brief's own example, in the sharper form where the plan identifies the problem and keeps going.

**Avoiding a known flaw is a poor measure of plan quality.** Seven of ten plans avoided the flaw I wrote down; only four were good enough to staff, and the disagreement ran both ways (**Table 2**). That ruled out two options for Part 2: gold labels must be human, and the eval cannot rest on planted flaws.

## Part 2 — An eval for the discriminator

**How the items are built:** ten seeds, two genuinely different methodologies each, with blind generation, length matched within 2.2%, and a stated firm per item (**Table 4**). I expected the first methodology to win every pair; my blind labels chose it **5 of 10 times**, so my expectation did not reach the answer key.

### Result 1 — the average hides the result; the split shows it

My labels prefer plan A on 6 of 10 items, so always answering A scores 60% — and against that, three of four models fail to beat a coin flip. Splitting by **how confident I was** (**Table 5**) tells a different story. Where I was confident, accuracy rises with model quality (58% → 67% → 67% → 75%) and every model beats chance. Where I was torn, every model falls below its own 75% baseline and the order reverses.

**Noting how sure I was about each answer turned out to predict whether the item was any good.** On the items I was sure about, the better models scored better, and all four beat a coin flip. On the items I was unsure about, all four models did worse than a coin flip and the ranking fell apart. Those items measure nothing.

This is free to collect — the reviewer already knows how sure they are. Use it to decide which items count, and report accuracy on the sure items as the headline. Averaging the unsure ones back in drags the number toward chance and hides the result.

The brief warned that if Haiku scored 90%, the items would be too easy. **Haiku scored 55%**, so that is not the problem here. The opposite might be: the items I was unsure about may just be too hard to score.

One item is worth more than the average (**Table 6**): all four models picked the same plan under both orderings, against a preference I had marked *strong* the other way. Four models agreeing confidently and being wrong against a confident reviewer is a shared blind spot, not noise — the most informative item in the set.

### Result 2 — the right recall and precision framing is not F1

I split my critiques into **45 blocking issues** (the recall denominator), 7 secondary, 4 that were praise, and 4 **anti-objections** — places where I say explicitly that a criticism does not apply. Matching is by meaning, with three precision buckets so valid issues I never wrote still count as real.

**The results reversed the assumption behind the design** (**Table 7**). Part 1 suggested recall would be near its ceiling and precision would separate the models. The opposite holds, because Part 1 measured recall against a *single* flaw named in advance (9 of 10) while Part 2 measures it against *45 real review objections* (62% at best). Recall does not rise with model quality either: Haiku beats both mid-tier models by raising 28.6 issues per review, enough volume to cover half the answer key by chance.

**So F1 is the wrong summary statistic.** Haiku's F1 range overlaps both mid-tier models, because F1 is a ratio and ignores how much noise was produced to get that recall. The raw count does not: **14.3 objections per review that don't apply, versus 0.1** — roughly 100x, and the cleanest separation in the eval. **So report recall alongside invalid-objections-per-review, and don't report F1.** That pair answers what a reviewer cares about: did you find what mattered, and how much noise did I read to get there.

Five caveats apply to all of this (**Table 12**), most seriously that Opus 5 graded its own reviews.

## Part 3 — Collecting more of this data at scale

**The proposal.** Run each item through three stages (**Table 10**). The expert first writes the blocking issues alone, with no model output in front of them, plus which plan they prefer and how confident they are. Only then do they see 20-30 model-generated candidates and mark each keep, strike, or duplicate. A model merges the two passes; the expert reviews only conflicts.

**Generate those candidates with a high-recall, low-precision model — Haiku, not Opus.** This is the counterintuitive part, and it is the main recommendation. Four safeguards keep the labels clean (**Table 13**) and five metrics catch it if they fail (**Table 11**); the one that generalises beyond this proposal is **never generate suggestions with a model you are evaluating.**

Part 2 happened to run both halves of this question already — I wrote gold labels by hand for twenty plan reviews, and four models produced issue lists for the same plans — so the reasoning below is measured.

**Why the expert still writes first.** Strike-out alone caps recall (**Table 8**): the labels can only contain what the model proposed, and the best model covers just **62%** of the blocking issues I wrote by hand. Writing by hand has the opposite gap — models raised 46 to 236 valid issues I never wrote. Neither wins, so both stages are needed.

**Why the noisy model.** Suggestion quality decides the label mix, and good suggestions ruin it (**Table 9**). An expert reviewing Opus 5's suggestions strikes out 3 of 133 and spends the session agreeing — 98% positive labels, useless for evaluating a discriminator. **The strikes are the valuable output, not the discarded part.** Each is an anti-objection, the label type Part 2 found most useful and the one hand-writing produces least: 4 across twenty reviews, against **286** from Haiku's suggestions on the same reviews. Haiku is right here for exactly the reason it was the worst discriminator.

**What to do with the data.** Fix the prompt before training anything: the dominant error is objections that don't apply, and that is an instruction problem before it is a weights problem. Then the labels have three uses. The preference pairs, with confidence attached, are directly usable as preference data — train only on the items I was sure about, since the rest are noise. The struck candidates are labelled false positives of exactly the failure mode, which is the signal that is otherwise almost impossible to collect. And the confident items held out become the benchmark, scored on recall and invalid-objections-per-review rather than on a single number. One constraint carries over from Part 2: never train on labels a model helped produce about its own output.

**Hire a second reviewer before writing more items.** All labels come from one person, which limits every number above — and this cost argument counts steps rather than timing them, so time stage 1 against stage 2 in the first session.

# Appendix A — Figures and tables

### Table 1 — Part 1: what Claude misses vs. what it over-raises

| The **misses** are domain facts | The **overreaches** are method boilerplate |
|---|---|
| deposits ≠ active trading (S1) | tertiary confounding variables (S1) |
| sales headcount correlates with visitors (S2) | survivorship bias on a 12-name universe (S2) |
| negative→positive earnings break a multiple; revenue- vs EBITDA-based valuation as a company matures (S6) | a statistical analysis that is not possible (S3) |
| round-lot profitability decays in **minutes**, not days (S8) | minimum event count set far too high (S9) |
| renegotiation flow-through timing to margins (S10) | scope expanded to irrelevant analyses, e.g. scale estimation (S1) |
| the shortage must be diffed against existing disclosure and buy-side consensus (S9) | |

### Table 2 — Part 1: flaw-dodging disagrees with desk quality, in both directions

| | Count | Seeds |
|---|---|---|
| Avoided the named flaw, still **bad** | **5** | S2, S4, S6, S8, S10 |
| Only *partially* handled it, still **fine** | **2** | S3, S5 |
| Agree | 3 | S1, S7, S9 |

*7/10 avoided the pre-written flaw; 4/10 were acceptable to me. The totals invite a "harsher reviewer" reading; the per-item split rules it out.*

### Table 3 — Manufactured precision: invented thresholds carrying real decisions

| Item | The numbers | What rests on them |
|---|---|---|
| S4_A | prior of 20:1–30:1 against; ~25x likelihood ratio required | The entire evidence bar — the denominator was invented |
| S7_A | >0.5% priced / <0.2% dismissed; CAR under 1 SD | The stop-go gate before any fundamental work |
| S7_B | ≥75bp above midpoint; ≥50bp above consensus; move ≥1.2x implied | Whether the trade goes on at all |
| S8_B | lift ≥2.0x, recall ≥35%, signing ≥70%, r ≥0.40, t ≥3 | Five conjunctive kills on labels with no ground truth |
| S9_A | tier haircuts 90–95 / 70 / 25–35% | The coverage math and the verdict |
| S10_A | under 25bp makes tone moot; over 75bp forces a call | The materiality frame |

### Table 4 — Part 2: eval construction

| Property | Choice | Why |
|---|---|---|
| Plans per seed | 2 distinct methodologies | Precision is only measurable when both sides are competent |
| Generation | Opus 5, blind `sha256` token | Generator never knew a sibling plan existed → no strawman |
| Length | 500–600 w, matched within **2.2%** | LLM judges favour length; uncontrolled, it is free signal |
| Context | 5 firm profiles, stated per item | A plan is good or bad *for someone* (tenet 2) |
| Judging basis | 13 tenets + precedence rules | Explicit, inspectable, and scoreable |
| Ordering | every pair run A/B **and** B/A | Separates judgment from position bias |
| Gold | human, written blind | Part 1 showed flaw-matching certifies plans a desk rejects |
| Planted flaws | **none** | Generators repaired them; and Table 2 condemns the metric |

### Table 5 — Part 2 pairwise: accuracy against a per-split baseline

| | Haiku 4.5 | Sonnet 5 | Opus 4.8 | Opus 5 | baseline |
|---|---|---|---|---|---|
| All calls (n=20) | 55% | 55% | 50% | 65% | **60%** |
| **Strong-preference items** (n=12) | 58% | 67% | 67% | **75%** | **50%** |
| **Weak-preference items** (n=8) | 50% | 38% | 25% | 50% | **75%** |
| Agreed with gold under **both** orderings | 40% | 50% | 40% | **60%** | — |

### Table 6 — Part 2: per-item agreement (the items worth more than the aggregate)

| Item | Gold | Models correct (of 4) |
|---|---|---|
| S4, S10 | B strong / A weak | **4** |
| S1, S7 | A strong | 3 |
| S6 | B strong | 2 |
| S2, S8, S9 | B strong / A weak / B weak | 1 |
| **S3, S5** | A weak / **A strong** | **0** |

*S5 is the sharpest item in the set: gold is **strong** for A and all four models chose B under both orderings — unanimous and confident against a confident human is a shared blind spot, not noise. Separately, Haiku is the **only** model correct on S2 and S9 while missing S1 and S7: it is differently wrong, not uniformly worse, which no single-scalar leaderboard can show.*

### Table 7 — Part 2 pointwise: recall, precision, and why F1 fails

| | Haiku 4.5 | Sonnet 5 | Opus 4.8 | Opus 5 |
|---|---|---|---|---|
| **Recall** (of 45 blocking) | 53% | 29% | 33% | **62%** |
| **Precision band** | 31–50% | 68–97% | 71–92% | **90–98%** |
| **F1 band** | 0.39–0.52 | 0.41–0.45 | 0.45–0.49 | 0.74–0.76 |
| Issues raised per review | **28.6** | 3.3 | 3.6 | 6.7 |
| **Manufactured objections per review** | **14.3** | **0.1** | **0.3** | **0.2** |
| Hit an anti-objection (gold ruled it out) | 7 | 0 | 3 | 2 |

*Precision is a band, not a point: the scorer was told to choose "real but unlisted" over "manufactured" when genuinely torn and flag it. The upper bound counts those as real, the lower as manufactured. Quoting 97% would quote the tie-breaking rule rather than the model. Note the F1 bands for the bottom three models overlap — F1 does not rank them.*

### Table 8 — Part 3: strike-out's recall ceiling on gold

| Candidate generator | Ceiling on gold | Legitimate issues it found that I did *not* write |
|---|---|---|
| Sonnet 5 | 29% | 47 |
| Opus 4.8 | 33% | 46 |
| Haiku 4.5 | 53% | 236 |
| **Opus 5** | **62%** | 97 |

*Even the best generator loses 38% of my own blocking issues — they never appear as a candidate, so there is nothing to keep. This is the ceiling of the method, not a tuning problem. The right-hand column is the mirror-image gap in free-hand writing.*

### Table 9 — Part 3: candidate quality controls the label distribution

| Candidate generator | Expert keeps | Expert strikes | Label balance |
|---|---|---|---|
| Opus 5 | 130 | **3** | 98% positive |
| Sonnet 5 | 64 | 2 | 97% positive |
| Opus 4.8 | 66 | 6 | 92% positive |
| **Haiku 4.5** | 286 | **286** | **50 / 50** |

*Free-hand prose produced **4** anti-objections across the same twenty critiques, and only incidentally. Strike-out against a noisy generator produces 286, deliberately.*

### Table 10 — Part 3: proposed three-stage collection

| Stage | Who | What they see | What it produces |
|---|---|---|---|
| **1. Write-first, un-anchored** | Expert (short) | Context, seed, plan — **no model output** | Blocking issues only, one clause each; preference + strength. Recovers the 38% no generator proposes |
| **2. Strike-out** | Expert (fast) | ~20–30 noisy candidates | keep / strike / duplicate. Every strike is an anti-objection; balanced labels |
| **3. Merge** | Model, expert on conflicts only | Both prior stages | Final gold + a free recall measurement of the generator |

### Table 11 — Part 3: what to measure to know it is working

| Metric | Why | Failure signal |
|---|---|---|
| Keep-rate per session | Label balance | Trends toward 100% |
| Stage-1 issues no candidate proposed | Is stage 1 earning its cost | Goes to ~0 → drop stage 1 |
| Write-only vs strike-out gold composition | Anchoring | Systematic divergence |
| Preference-strength distribution | Item difficulty mix | Mostly weak → items not discriminating |
| Inter-expert agreement on a shared subset | Is gold reproducible | Low → the eval measures one desk |

### Table 12 — Limitations that bound every number in this report

| Limitation | Effect |
|---|---|
| **Opus 5 scored its own reviews** in the pointwise pass | It posts the best recall *and* precision under its own judge — exactly what self-preference produces. Treat its margin as an upper bound. Does **not** touch the Haiku result (a 100x gap, not a 4-point one) |
| **Opus 5 is the only evaluated model with thinking on** by default | The runner passes no `thinking` parameter, so each model runs as shipped. Opus 5's lead is model + thinking, and is not attributable to capability alone |
| **All gold is one reviewer** | "The model is wrong" and "the model disagrees with this desk" are not separable anywhere in this work |
| **Ten items, n=1 per call, no re-rolls** | Run-to-run variance is unmeasured; treat any single-item difference as noise |
| The gold-issue classifier is **non-deterministic** | Returned 43 then 45 blocking issues on identical input, so recall denominators carry ~±2 of slack |

### Table 13 — Part 3: controls against poisoning the labels

| Control | What it prevents | Measurable? |
|---|---|---|
| **Write-first ordering** — un-anchored issues recorded before any candidate is shown | Anchoring overwriting the expert's own judgment | Structural |
| **15% write-only control arm** — no candidates ever shown | Makes drift *detectable*; without it anchoring is unmeasurable, not merely unmeasured | **Yes** |
| **Never generate candidates with a model under evaluation** | Self-preference contamination — Part 2 hit exactly this | **Yes** |
| **Keep-rate as a live health metric** | Distinguishes "generator improved" from "expert stopped reading" — only separable against the control arm | **Yes** |

# Appendix B — Part 0: two ideas, written before touching Claude

Both written without model assistance and not revised afterward. They are deliberately the **same shape** — third-party panel data used to infer a company's reported financials. One works, one doesn't. The point isn't "alt data good/bad"; it's whether the panel observes the thing that drives the reported number.

## B1 — Well-posed: does Kalshi adoption cannibalize DraftKings?

The readout is: among users already active on DraftKings, does a first Kalshi transaction coincide with lower subsequent DraftKings retention, spend, or transaction frequency versus DraftKings users who never use Kalshi? The primary pair is DraftKings-to-Kalshi; use DraftKings-to-FanDuel only as the switching benchmark.

Use transaction-level credit card and bank deposit data mapped to DraftKings, Kalshi, and FanDuel activity. Start cohorts in 2021, aggregate each user's activity to monthly and weekly periods, and produce separate credit-card, bank-deposit, and combined source cuts. For Kalshi, use a 3-month forward window because history is short and adoption ramped recently.

Compare two groups of DraftKings users around the month or week when the first group tries Kalshi for the first time. The first group is users who were active on DraftKings and then made their first Kalshi transaction. The comparison group is DraftKings-active users from the same time period who never used Kalshi; use a stable 5% sample of those users so the analysis is repeatable and not too expensive to run. Track DraftKings activity before and after the Kalshi start date, including whether users remain active, how much they spend or deposit, and how often they transact. Show the raw paths, the gap between Kalshi adopters and non-adopters, and the percent gap versus the comparison group. Adjust for any average pre-Kalshi gap between the two groups so the post-Kalshi change is easier to read.

Before interpreting results, confirm the merchant mapping for each product, check that the Kalshi adopter sample is large enough, and make sure adopters and non-adopters looked reasonably similar before the first Kalshi transaction. Compare credit-card, bank-deposit, and combined results for the same directional message, and use weekly versus monthly views to understand timing. Treat the output as directional evidence, not proof of causality, because Kalshi adopters may be different types of users, observed deposits/spend are not the same as betting handle, and Kalshi's short history may leave limited post-adoption data.

## B2 — Plausible, but dies at desk review: portal MAU → seat-based SaaS ARR

The readout is: among US-listed SaaS companies that price per seat, does the level of monthly active users on the client-facing portal explain reported ARR one to two quarters later, closely enough to call the number before the company prints it? The primary relationship is portal MAU to ending ARR; use subscription revenue run-rate only as a secondary read for names that do not disclose ARR directly.

Use third-party web and mobile panel data mapped to each company's client-facing portal domain and app. Start in 2021, aggregate panel traffic to monthly and quarterly periods, and produce separate web, mobile, and combined source cuts. Pull ARR, subscription revenue, and consensus estimates point-in-time from filings and press releases so restated figures do not leak into the fit. Screening for seat-based pricing and quarterly ARR disclosure gives roughly 35 to 50 names.

Line up each company's quarterly portal MAU against its reported ARR and fit the relationship in logs across the panel, with company effects to absorb persistent differences in panel coverage and price level, and quarter effects to absorb common macro. Test MAU lagged zero, one, and two quarters and carry forward whichever lag fits best. Where a company has enough quarters, fit it on its own so the coefficient reflects that name rather than the pooled average; otherwise fall back to the pooled coefficient. Cluster standard errors by company. Hold out a random 20% of company-quarters, fit on the rest, and report out-of-sample R² and average percentage error against reported ARR. Treat the relationship as usable if average error is under 3% and the MAU coefficient is positive and significant in most of the per-company fits. Then, two weeks ahead of each print, generate a predicted ARR, and compare it to consensus.

Before interpreting results, confirm the domain and app mapping for each company, check that the panel covers each name densely enough to be stable, and look for level shifts where the vendor has re-baselined its methodology. Use a point-in-time universe that includes delisted names so the fit is not run only on survivors. Compare web, mobile, and combined cuts for the same directional message, and report all three lags rather than only the one that fit best. Treat the output as directional rather than exact, because some names have fewer than twelve quarters of history, the universe is small enough that a handful of large companies drive the pooled fit, and panel coverage of any single company can change without notice.

### Why B2 dies

**It dies on the billing mechanic.** Seat-based ARR bills on seats *contracted*, not seats used — so shelfware lets ARR compound while MAU is flat, and free viewer tiers let MAU climb on seats that bill nothing. Even where the two co-move, ARR is seats × price and MAU is silent on the price/mix half, which carries most of the growth in a mature seat model. The panel makes this worse rather than better: enterprise traffic behind SSO and VPN is largely invisible to third-party measurement, so coverage skews toward exactly the small accounts contributing least to ARR. A level regression across SaaS names will still print a high R² because both series trend up — which is precisely what makes the result convincing and wrong.

Every step in B2 is individually standard practice. The caveats it *does* raise — survivorship, thin samples, concentration — are real and responsible, and **none of them is what kills it.** It succeeds on its own terms, which is what makes it the right shape for a subtly-flawed eval seed. It became **S2**.

# Appendix C — Repo map

| Path | Contents |
|---|---|
| `ideas.md`, `seeds.json` | 14 candidate seeds, the working 10, buckets and cut rationale |
| `part0/` | The two ideas above, plus where B2's flaws are loaded |
| `part1/` | Plans, critiques, per-item human verdicts, `FINDINGS.md`, provenance |
| `part2/evaluator/` | `TENETS.md` (13 tenets + precedence rules), pairwise & pointwise prompts |
| `part2/plans/` | 20 plans, raw and condensed, with the blind-token manifest |
| `part2/items/`, `part2/gold/` | 14 eval items; gold + the classified issue denominator |
| `part2/runs/` | Every raw model call — four models, both modes, plus issue scores |
| `part2/GRADED.md`, `SCORING.md`, `ISOLATION.md` | Results, metric design, isolation guarantees |
| `part3/README.md` | Collection proposal |
| `scripts/` | Generation, eval runner, retry/merge, scoring, comparison, flip test |
| `REPORT-NOTES.md` | Working notes 1–7, including decisions reversed and why |

**To extend it:** add seeds to `seeds.json`, generate plans via `scripts/generate.py` (blind tokens), build items with `build_items.py`, then `run_eval.py --model X`. Scoring is `score.py` (deterministic) and `score_issues.py` (semantic). Prompt and schema fingerprints are stored per run and re-checked on merge, so a changed instrument refuses to mix with old results rather than silently corrupting a comparison.

**Not done, and why it matters:** the four context-flip items (same seed, same plans, different firm) have no gold, so the one axis that holds the plan fixed and varies the brief is measured only gold-free. That is the first thing I would finish.
