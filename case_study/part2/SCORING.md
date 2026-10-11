# How the discriminator is scored

> **Read with `GRADED.md`.** This document is the metric *design*, written before
> gold existed. Running it revised two of its claims, and both revisions are load-
> bearing:
>
> - **Axis 1 (error asymmetry) is broken as implemented.** The enum offers
>   `symmetric` while the prompt routes symmetric payoffs to `type_ii_dominant`;
>   all four models emitted `symmetric` 0 times in 80 calls. The axis is sound in
>   principle and unmeasurable with the current instrument.
> - **Axis 4 (context sensitivity) is unscored** — the four flip items have no gold.
> - **The precision design below is necessary but not sufficient.** Haiku satisfies
>   the three-bucket framing while producing 14.3 manufactured objections per
>   review. The reported pair should be **recall + manufactured-per-review**, and
>   **not F1**, whose bands fail to rank the bottom three models.

The brief notes that "does it match my critique" is too brittle for pointwise
scoring and asks for the right recall/precision framing. This is the answer, and
it comes out of the Part 1 finding: recall was at ceiling (9 caught / 1 partial /
0 missed) while precision was the weakness — 2.6 manufactured objections per
critique. **An eval measuring only recall would have scored every model
near-perfect and separated nothing.**

---

## What the evaluator returns

Two modes, both structured. The design principle is *one place per fact*: enum
verdicts for per-tenet judgments, a single `issues` list for findings. Earlier
drafts had parallel arrays (`missing_checkpoints`, `unfounded_claims`, and so on)
duplicating the issue list — that inflated format burden and broke precision,
since one finding could be counted twice.

| Mode | Fields | Shape |
|---|---|---|
| **Pairwise** | 9 | winner, confidence, frame (2), `decisive_tenets`, differentiator, rationale, issues with each |
| **Pointwise** | 18 | frame (5), design (5), execution (4), honesty (2), `issues`, `overall` |
| **Issue** | 6 | summary, severity, category, `why_it_applies_here`, what breaks, fix |

All but four pointwise fields are enums, so format cost is roughly one token each.

## Tenet → field map

`evaluator/TENETS.md` is the judging basis. Every tenet is reachable, most via a
`category` on an issue rather than a dedicated field.

| Tenet | Pairwise | Pointwise |
|---|---|---|
| **A — Frame** | | |
| 1 actual goal | `goal_type` | `goal_type` |
| 2 firm, sophistication, error asymmetry | `error_asymmetry` | `plan_implied_asker`, `fits_firm`, `method_sophistication_fit`, `error_asymmetry`, `error_posture_fit` |
| 3 variant view / edge | cat. `no_edge` | `edge_basis` |
| **B — Design** | | |
| 4 simplest first | cat. `unnecessary_complexity` | `effort_proportionate` |
| 5 target, and measure validity | cat. `proxy_substitution`, `measure_validity` | `target_vs_proxy`, cat. `measure_validity` |
| 6 horizon | cat. `horizon_mismatch` | `horizon_fit` |
| 7 evidence standard, hierarchy | cat. `evidence_standard`, `evidence_hierarchy` | `evidence_standard`, cat. `evidence_hierarchy` |
| 8 breadth, negative controls | cat. `breadth` | cat. `breadth` |
| **C — Execution** | | |
| 9 sequence for information | cat. `sequencing` | `front_loads_kill`, `adaptive_flow` |
| 10 AI execution, checkpoints | cat. `human_oversight` | `explainability_fit` |
| **D — Honesty** | | |
| 11 what would make it wrong | cat. `falsification` | `what_would_falsify`, `other_side_considered` |
| 12 no invented economics | cat. `invented_economics` | cat. `invented_economics` |
| **E — Review** | | |
| 13 objections must be earned | — | `why_it_applies_here` on every issue |

Group A is scored first: most later fields are **conditional on it**. A `breadth`
finding only means something once `goal_type` says breadth applies, and
`edge_basis` is `not_applicable` by design on a capability build.

---

## Pairwise

**Accuracy** — does `winner` match gold `preference`.

**Weighted by `preference_strength`.** Gold picks A or B but marks the call
`strong` or `weak`. Report three ways: overall, strong-only, weak-only.
Strong-only is the headline — disagreement on a weak item is a different failure
from missing a clear one, and on a fourteen-item eval a few coin-flips would
otherwise swamp the signal. Read against the model's `confidence` for calibration.

**`decisive_tenets` replaces five free-text note fields** and is more scoreable
than they were: it says directly which tenets did the work, comparable against
gold's own list. A model reaching the right answer for the wrong reason is
visible here and nowhere else. Listing many tenets means nothing decided it.

**Score it as overlap with partial credit, never as set equality.** Gold lists
what drove the *preference*, not everything wrong with the two plans, and a tenet
can dominate a critique without being decisive. S8 is the clearest case: the
gold's `critique_A` opens on horizon — trading against retail flow is a
market-making activity at nanoseconds to seconds, and both plans build daily
signals — which is tenet 6 exactly, while `decisive_tenets` is `1, 2` because
goal identification and firm fit are what settled the choice. A model naming
tenet 6 there has found the sharpest issue in the item and would score zero under
exact match.

Across the ten base items gold uses tenet 2 five times, 7 four times, 1 and 5
three times each, and 3, 4, 8, 10, 11 once each. **Tenets 6, 9 and 12 are never
decisive, and 13 never appears by design** (it is scored through
`why_it_applies_here` on every issue). Their absence is a property of this item
set, not evidence that a model citing them is wrong — before scoring such an
answer as a miss, check whether the tenet appears in gold's critique prose.

Each pair runs **both ways** (A/B and B/A):

| Diagnostic | What it catches |
|---|---|
| **Consistency** | Same *plan* chosen under both orderings. An inconsistent evaluator is reacting to position, not discriminating |
| **Position bias** | Rate of picking slot A; 50% is unbiased |
| **Length correlation** | Plans match within 2.2%, so this should be near zero. If it isn't, something else is driving the choice |

## Pointwise

**Recall = blocking gold issues surfaced / total blocking gold issues.** Only
blocking counts. A model missing the fatal flaw but catching three minor ones
should not score well.

**Precision = real issues raised / total issues raised.** Three buckets:

| Bucket | Counts as | Definition |
|---|---|---|
| Matched | real | Semantically matches a gold issue |
| Real-but-unlisted | real | Not in gold, but adjudicated a legitimate concern |
| Manufactured | not real | Not in gold and not legitimate |

The middle bucket is why this isn't brittle matching. Part 1 produced findings
not in gold that were genuinely good — the sharpest derived that a plan's own IR
target couldn't clear its own t-statistic hurdle on any subsample. Scoring those
as false positives would punish the behaviour we want. Matching is semantic, done
by a scorer agent, never string comparison; anything it can't confidently bucket
escalates to the human.

**`why_it_applies_here` is the precision mechanism.** Required on every issue, it
makes tenet 13's failure self-revealing: a justification that would read
identically against any plan in the asset class is a misapplied objection, far
easier to detect than adjudicating the objection itself. **An issue with a
generic justification counts as manufactured even when the concern is real in the
abstract.**

This came from the Part 1 gold pass, where 4 of 10 verdicts named a misapplied
standard objection — *"wrongly rejects due to universe size of 12 and
survivorship bias, which are not concerns in this analysis"*, *"overstates
tertiary confounding variables"*, *"depends on statistical analysis that is not
possible"*, *"requirement on number of events much too high"*. The 2.6
manufactured objections per critique were not random noise; they were canonical
concerns recited without checking whether they bite.

---

## The axes that discriminate

Ordinary accuracy separates models weakly. These four separate them sharply,
because each traps a model that maximizes a single virtue.

**1. Error asymmetry — there is no fixed standard of rigor.** On a
`type_i_dominant` item a demanding plan is correct and `too_permissive` is the
failure; on a `type_ii_dominant` item the *same* plan becomes
`too_conservative`. A model preferring the thorough plan everywhere is right on
the first kind and wrong on the second. **Report `error_posture_fit` accuracy
split by the item's true asymmetry — the pattern is the finding, not the
aggregate.**

**Asymmetry is a property of the item, not of the firm**, and the gold proves
it: `event_desk` carries `type_i_dominant` on S4 (reading strategy into a
scheduled financing event) and `type_ii_dominant` on S7 (incrementally positive
news, so the exposure is missing the raise rather than being wrong in the name).
`midsize_ls` and `systematic` likewise split across items. This makes the axis
sharper than a firm-level mapping would: a model that infers the asymmetry from
the firm label is reasoning from a correlation that does not hold, and S4 against
S7 is the pair that catches it.

It also constrains the evaluator's own behaviour, checkably: on
`type_ii_dominant` items a long issue list has inflated the reviewer's own Type I
rate in the setting that punishes it. Cross-read issue count against
`error_asymmetry`.

**2. Both-directions fields.** `evidence_standard`, `explainability_fit`,
`method_sophistication_fit` and `error_posture_fit` each have an over- and an
under- failure. A model that only ever returns the "under" value is applying a
checklist, not judging fit. **S3 is the probe**: a low-N capability build where
demanding a p-value is itself the error.

**3. Edge is a gate.** `edge_basis: none_established` is blocking — a plan can be
flawless and worth nothing if everyone already knows the answer. Two exemptions
are themselves scoreable: a capability build returns `not_applicable`, and
`speed` is a legitimate edge, so a model recognizing only `variant_view` will
wrongly penalize an arbitrage-shaped plan.

**4. Context sensitivity — the flip items.** `S2F`, `S5F`, `S8F`, `S9F` are the
same seed and plans under a different firm. Where gold preference changes, the
evaluator should change; where gold holds, an evaluator that flips is
over-reading. **A model that never changes across a flip is not applying tenet 2
at all**, whatever its raw accuracy. Cross-check: `plan_implied_asker` should
stay the same across a flip — the plan didn't change — while `fits_firm` moves.
Drift there means the model is reading the context into the plan.

This is the only axis that holds the plan fixed and varies the brief, so it is
the one place where firm-fit is measured rather than inferred. Without the flips
the substitute is comparing `fits_firm` across the five firms in the base items,
which confounds firm with seed.

## Conflicts are scored, not averaged

`TENETS.md` § Resolving conflicts gives precedence for the nine places tenets
pull apart — including specific-evidence versus breadth, where tenets 7 and 8
point opposite ways and the goal decides which wins. Report those items as their own slice. A model resolving every
conflict toward "more rigor" or "always faster" is not exercising judgment,
whatever its aggregate score.

## Reporting

Stratify by seed bucket (`seeds.json`: good / obviously flawed / subtly flawed)
rather than aggregating. A model clearing the obvious tier and failing the subtle
one is a more useful readout than one number.

The brief's sense-check applies to the subtly-flawed tier: scores should rise
Haiku 4.5 → Sonnet 5 → Opus 4.8 → Opus 5.

## Known limitations

- **Tenets 7 and 10 are pointwise-only.** No plan states a low-N conviction
  design (20/20) or names an inspectable checkpoint (19/20), because generation
  predated the tenets. Pointwise still works — the test becomes whether the model
  notices a *universal* absence, and empty findings across all 14 items is a
  visible failure. Pairwise cannot use them. **Empty is a property of the item
  set, not a model error.** We deliberately did not build probe pairs: making a
  plan that *has* checkpoints means instructing a generator to include them,
  which is the circularity removed everywhere else.
- **The evaluator is given the tenets**, so this measures applying a stated
  standard, not latent judgment. That matches how a production discriminator is
  prompted and the brief does not require otherwise — but a high Haiku score is
  then ambiguous between "items too easy" and "rubric too explicit." If Haiku
  scores near the top, run a no-tenets control on 3–4 items before concluding
  anything about difficulty.
- **`goal_type` is not always single-valued.** On S8 the gold labeller judged
  `mechanism_test`, `blind_fit_oos` and `broad_market_effect` all partially
  right, and picked `blind_fit_oos` as primary only because the field needs one
  value to score. Exact-match accuracy on `goal_type` therefore overstates its
  own precision: a model answering `mechanism_test` on S8 is marked wrong for a
  distinction the human could not make cleanly either. Read `goal_type` accuracy
  as a floor, and where a model's `goal_type` differs from gold, check whether
  its downstream judgments are coherent *with its own answer* before scoring it
  as an error.
- **Gold is one reviewer**, and the tenets come from the same person. This
  measures agreement with a stated desk standard, not objective plan quality.
- **n = 1 per call.** No re-rolls; run-to-run variance unmeasured.
- **Fourteen items.** A 7-point accuracy difference is one item. Treat small gaps
  between adjacent models as noise unless the pointwise metrics agree. This is
  the binding limitation on the whole eval: with A/B order swaps there are 28
  pairwise judgments per model, and the model-intelligence gradient the brief
  asks for has to be visible against that. Replicates are cheap (see the cost
  note in REPORT-NOTES.md) — run several and report the spread, or the gradient
  is unreadable.
