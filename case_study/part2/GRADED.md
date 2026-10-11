# Part 2 — graded against human gold

Ten base items (S1–S10) have gold and are scored here. The four context-flip
items are not yet filled and are excluded by name in the output rather than
silently dropped: `scripts/score.py`, full run in `graded-output.txt`.

The design-intent check passes first. `forks.json` was built with M1 as the
intended-stronger methodology on all ten seeds. **Gold preferred M1 on 5 of 10** —
the construction prior is fully washed out of the answer key, so the eval is not
scoring models against my own generation bias.

---

## Headline — accuracy is only interpretable against a per-split baseline

Gold prefers A on 6 of 10 items, so *always answer A* scores 60% while
discriminating nothing. The strong and weak splits have very different baselines,
and reporting a single aggregate hides the entire result.

| | Haiku 4.5 | Sonnet 5 | Opus 4.8 | Opus 5 | baseline |
|---|---|---|---|---|---|
| All calls (n=20) | 55% | 55% | 50% | **65%** | 60% |
| **Strong items** (n=12) | 58% | 67% | 67% | **75%** | **50%** |
| **Weak items** (n=8) | 50% | 38% | 25% | 50% | **75%** |
| Both orderings agree with gold | 40% | 50% | 40% | **60%** | — |

**On the aggregate, three of four models fail to beat a coin that always says A.**
That is the number a careless writeup would report, and it is close to meaningless.

**On strong items the capability ladder is clean and monotone:** 58 → 67 → 67 → 75
against a 50% baseline. Where the human reviewer was confident, the models track
model quality in the expected order, and every one of them beats chance.

**On weak items every model is far below its 75% baseline**, and the ordering
roughly inverts — Opus 4.8 is worst at 25%. Where gold itself was torn, more
capable models are not better and the whole panel does worse than answering
blind. Eight calls, so treat the ordering as noise; the *level* is not noise, and
it is consistent across all four models.

This is the answer to the brief's sense-check. The worry was *"if Haiku scores
90%, the items are too easy."* Haiku scored 55%, below the trivial baseline.
The items are not too easy. The open question is now the opposite one — whether
the weak items are discriminating at all, or are simply items where one
reviewer's call is not recoverable from the plans.

**Recommendation: report strong-item accuracy as the headline metric** and carry
weak items as a separate diagnostic, not folded into one number.

## Where the models agree with each other and not with gold

| Item | Gold | Models correct |
|---|---|---|
| S4, S10 | B strong / A weak | **4/4** |
| S1, S7 | A strong | 3/4 |
| S6 | B strong | 2/4 |
| S2, S8, S9 | B strong / A weak / B weak | 1/4 |
| **S3, S5** | A weak / **A strong** | **0/4** |

**S5 is the sharpest item in the set.** Gold is *strong* for A; all four models
chose B under both orderings. Unanimous, confident, and wrong against a confident
human — that is a shared blind spot rather than model noise, and it is worth more
than any aggregate here. S3 is the same shape at weak strength.

The inverse case is also informative: Haiku is the *only* model correct on S2 and
S9, while being wrong on S1 and S7 where the other three are right. Its 55% is
not a weak version of the others' behaviour — it is differently wrong. Aggregate
accuracy cannot see that.

---

## Two instrument defects found by the gold pass — these invalidate two metrics

Both were caught by scoring, not by inspection, and both mean a number that looks
like a model failure is actually a defect in my own instrument. Neither
`goal_type` nor `error_asymmetry` accuracy is reportable as model capability.

**1. `error_asymmetry`: the schema offers a value the prompt forbids.**
The enum is `type_i_dominant / type_ii_dominant / symmetric`. Gold uses
`symmetric` on 3 of 10 items. But the prompt says:

> *"Capped downside with unbounded upside (venture), or **a symmetric payoff run
> with breadth** (most quant), makes **Type II** the expensive error."*

The only place the guidance mentions symmetric payoffs, it routes them to
`type_ii_dominant`. Nothing anywhere states when to return `symmetric`. Result:

| | Haiku | Sonnet | Opus 4.8 | Opus 5 |
|---|---|---|---|---|
| `symmetric` emitted, 20 calls each | **0** | **0** | **0** | **0** |

Zero in 80 calls. The 0/6 score on gold's symmetric items is **compliance with
the prompt**, not a failure of judgment. SCORING.md calls error asymmetry the
first of four discriminating axes; that axis is currently broken.

**2. `goal_type`: none of the five labels is defined anywhere.**
`grep` for each of `single_name_kpi`, `broad_market_effect`, `mechanism_test`,
`blind_fit_oos`, `capability_build` across `pointwise.md`, `pairwise.md` and
`TENETS.md` returns **zero occurrences of all five**. The schema property carries
no `description` either. Models received a bare enum of five snake_case strings
and had to infer my private semantics from the identifiers.

Measured accuracy was 15–45% against a 40% baseline. That is a measurement of
label-guessing, not of framing ability. `blind_fit_oos` — gold's label on 3 of 10
items — was emitted 0 times by Haiku and Sonnet.

This defect is worse than it looks, because SCORING.md makes Group A conditional:
*"most later fields are conditional on it… a `breadth` finding only means
something once `goal_type` says breadth applies."* The conditioning field was
undefined.

**Fix before any re-run:** write a one-line definition of each `goal_type` into
the schema `description`, and either define when `symmetric` applies or remove it
from the enum and from gold. Both change the instrument, so both invalidate
cross-run comparability and require re-running all four models.

## What survives

| Metric | Status |
|---|---|
| Pairwise preference accuracy | **valid** — no definitional dependency |
| Self-consistency, position bias | **valid** — gold-free |
| `decisive_tenets` overlap | **partly** — categories are defined; tenets 1 and 13 have no category, so it is a lower bound |
| `goal_type` accuracy | **invalid** — labels undefined |
| `error_asymmetry` accuracy | **invalid** — prompt contradicts the enum |

`decisive_tenets`, on the lower-bound reading: Haiku 60%, Sonnet 50%,
Opus 4.8 55%, Opus 5 65% hit at least one of gold's stated deciding tenets. The
spread is narrow and this does not separate models.

## Still outstanding

The four context-flip items (`S2F`, `S5F`, `S8F`, `S9F`) have no gold, so the
context-sensitivity axis — the only one that holds the plan fixed and varies the
firm — is unscored. `flip_test.py` reports it gold-free in the meantime.

---

# Pointwise — recall and precision

`split_gold.py` classifies gold's prose into scoreable issues; `score_issues.py`
does the semantic matching. Scorer is Opus 5, blind to which model wrote the
review. Haiku is **not scored** — credits ran out 17 reviews in.

Building the denominator changed it twice, and both changes matter:

| | count | |
|---|---|---|
| **blocking** | **45** | the recall denominator |
| secondary | 7 | real, but not decisive |
| **anti_objection** | **4** | gold *explicitly rules the objection out* |
| praise | 4 | not a criticism; a model cannot "surface" it |

Splitting prose on paragraphs alone would have put 8 non-criticisms into a
60-item denominator and depressed every recall number by ~13%.

The **anti_objection** category was not in the original design and is the more
useful find. Gold contains sentences like *"the objection that twenty to thirty
episodes across ten industries is too few does not apply"* (S9B) and *"the
thinness of the seat-disclosing gate sample is not an objection here"* (S2B).
These are **gold-certified false positives**: a reviewer bothered to write down
that a specific canonical objection does not bite. A model raising it anyway is
committing the exact Part 1 failure, and it is checkable without adjudicating
anything. Four traps exist across the ten items.

## Results

| | Haiku 4.5 | Sonnet 5 | Opus 4.8 | Opus 5 |
|---|---|---|---|---|
| **Recall** (of 45 blocking) | 53% | 29% | 33% | **62%** |
| **Precision band** | 31–50% | 68–97% | 71–92% | **90–98%** |
| **F1 band** | 0.39–0.52 | 0.41–0.45 | 0.45–0.49 | **0.74–0.76** |
| Issues raised | 572 | 66 | 72 | 133 |
| Per review | **28.6** | 3.3 | 3.6 | 6.7 |
| Matched / real-unlisted / manufactured | 50/236/279 | 17/47/2 | 20/46/3 | 33/97/1 |
| **Manufactured per review** | **14.3** | **0.1** | **0.3** | **0.2** |
| Contradicts gold | 7 | 0 | 3 | 2 |

**Precision is a band, not a point.** The scorer was told to choose
`real_unlisted` over `manufactured` when genuinely torn and to flag `uncertain`;
the upper bound counts those as real, the lower bound as manufactured. Sonnet's
spread is 29 points on 19 uncertain calls out of 66. Quoting 97% would be quoting
the tie-breaking rule rather than the model.

## Finding 1 — recall discriminates, precision does not, and neither alone ranks the models

**This inverts the Part 1 prediction the Part 2 design was built on**: that recall
would sit at ceiling and precision would be the weakness worth measuring.

Recall separates far more sharply than precision — but **it is not monotone in
model capability**. Haiku (53%) beats both Sonnet (29%) and Opus 4.8 (33%). It
gets there by raising 28.6 issues per review against their ~3.5: a shotgun wide
enough to cover half the answer key by volume.

The reason Part 1 and Part 2 disagree is that they measured recall against
different objects. Part 1 asked *"did the critique catch the one flaw named in
advance?"* — 9/10, a ceiling. Part 2 asks *"did the review surface what a desk
actually raised?"* against 45 human blocking issues, and the best model reaches
62%. **Recall against a planted flaw is a ceiling metric; recall against a real
desk critique discriminates.** That is independent support for abandoning planted
flaws, reached by contradicting the design intent rather than confirming it.

## Finding 2 — F1 is the wrong summary, and this eval shows why

F1 is the obvious way to combine recall and precision. On this data it **fails to
rank the bottom three models**, because the bands overlap:

| | F1 band |
|---|---|
| Haiku 4.5 | 0.39 – **0.52** |
| Sonnet 5 | **0.41** – 0.45 |
| Opus 4.8 | 0.45 – 0.49 |
| Opus 5 | **0.74 – 0.76** |

Haiku's band spans both mid-tier models. A shotgun review is *competitive on F1*
with careful ones, because F1 is a ratio and normalises away how much noise was
produced to buy the recall.

What a desk actually cares about is not normalised. In absolute terms:

**Haiku produces 14.3 manufactured objections per review. Sonnet produces 0.1.**

That is a ~100x difference, and it is the cleanest separation anywhere in this
eval — sharper than accuracy, recall, precision or F1. A reviewer who raises
fourteen unearned objections per plan is unusable no matter what fraction of the
answer key they also happen to cover, because the reader cannot tell which
fourteen to ignore.

**Recommendation: report recall and manufactured-per-review as a pair, and do not
report F1.** The pair is interpretable in the terms a desk uses — did you find
what mattered, and how much noise did I have to read to get it. This is the
answer to the brief's question about the right recall/precision framing, and it
is a stronger answer than the three-bucket precision design alone, which the
Haiku column shows can be satisfied while still being unusable.

The anti-objection traps corroborate it: Haiku hit 7, versus 0–3 for the others.

## Limitation: the scorer is grading its own homework

Opus 5 scored all four models, including Opus 5. The scorer never sees which
model produced a review, but blinding does not remove self-preference — a model
can recognise its own style and reasoning idiom. Opus 5 posts the best recall
*and* the best precision under an Opus 5 judge, which is exactly the pattern
self-preference would produce.

This is not resolvable by inspection. The check is to re-score a subsample with a
different judge and compare, and until that exists **Opus 5's margin should be
treated as an upper bound**. Sonnet vs Opus 4.8 is unaffected — neither is the
judge — and those two are separated by 4 points, i.e. not separated.

The thinking confound from Note 5 applies here too: Opus 5 is the only evaluated
model reasoning before it answers.
