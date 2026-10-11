# Part 3 — collecting discriminator data at scale

The brief asks whether it is cheaper to have the expert **write** the gold issue
list or to have Claude **propose ~8 candidates and the expert strike out** the
wrong ones, and what the second approach does to the label distribution.

Part 2 accidentally ran both halves of that experiment. The expert wrote gold
free-hand for twenty plan-critiques, and four models independently produced issue
lists for the same twenty plans, every issue of which was then adjudicated. So
the trade-off can be answered with measurements instead of intuition.

---

## What the Part 2 data already settles

**1. Strike-out imposes a hard recall ceiling, and it is low.** Gold can only ever
contain what the candidate generator proposed. Measured against the 45 blocking
issues the expert wrote free-hand:

| Candidate generator | Recall ceiling on gold |
|---|---|
| Sonnet 5 | 29% |
| Opus 4.8 | 33% |
| Haiku 4.5 | 53% |
| **Opus 5** | **62%** |

Even the best generator would have lost **38% of the expert's own blocking
issues** — they never appear as a candidate, so there is nothing to keep. Pure
strike-out cannot reproduce free-hand gold. This is not a tuning problem; it is
the ceiling of the method.

**2. But free-hand writing has its own recall problem, in the other direction.**
The models raised legitimate issues the expert did *not* write: 47 (Sonnet), 46
(Opus 4.8), **97 (Opus 5)**, 236 (Haiku). The expert was not being lazy — nobody
writing prose claims to be exhaustive. Neither method dominates, which is the
actual argument for a hybrid rather than a preference for one.

**3. Candidate quality controls the label distribution — and good candidates
break it.** This is the direct answer to the brief's question, and it is the
opposite of what "use the best model" would suggest:

| Candidate generator | Candidates | Expert keeps | Expert strikes | Label balance |
|---|---|---|---|---|
| Sonnet 5 | 66 | 64 | **2** | 97% positive |
| Opus 4.8 | 72 | 66 | 6 | 92% positive |
| Opus 5 | 133 | 130 | **3** | 98% positive |
| **Haiku 4.5** | 572 | 286 | **286** | **50/50** |

**A high-precision generator produces a degenerate, nearly all-positive label
set.** An expert reviewing Opus 5's candidates strikes 3 things out of 133 and
spends the session agreeing. You have bought expert time to confirm what the
model already believed — the most expensive way possible to learn nothing, and a
label set no discriminator can be trained or evaluated on because it has almost
no negatives.

## The result that reframes the question

**The strikes are the product, not the waste.**

Part 2's sharpest single finding was that *anti-objections* — cases where the
expert explicitly rules an objection out — are the cleanest available signal.
They are gold-certified false positives: checkable without adjudicating anything,
and they measure the exact failure mode that separates a usable reviewer from an
unusable one (Haiku, 14.3 manufactured objections per review, versus 0.1 for
Sonnet).

Free-hand prose produced **4 of them across twenty critiques**, and only
incidentally — the expert happened to pre-empt an objection they expected.

**Every strike is an anti-objection label.** Striking a candidate is exactly the
statement "this objection does not apply to this plan," produced deliberately
rather than by luck. Against Haiku candidates, the same twenty critiques would
yield **286** of them.

So the question is not "is strike-out cheaper than writing." It is that
**strike-out and writing produce different label types**, and the type strike-out
produces is the one Part 2 found most discriminating and free-hand writing
produces least.

This inverts the natural instinct about which model to use for candidates. **Use
a high-recall, low-precision generator.** Its noise is not a defect to be
minimized; it is the negative-label supply. Haiku is the right tool here for
precisely the reason it was the worst discriminator.

---

## Proposed process

Three stages per item, ordered so that the expensive, anchoring-prone judgment
happens before the model can contaminate it.

### Stage 1 — write-first, un-anchored (expert, short)
The expert sees context, seed, and plan. Before any model output, they write:
- the **blocking** issues only, in one clause each — not prose
- **preference** and **strength** if this is a pair

This preserves the 38% of blocking issues no generator proposes, and it is the
only stage that must be un-anchored. Capping it at blocking-only is what makes it
short; Part 2's gold spent effort on `secondary` (7) and `praise` (4) paragraphs
that contributed nothing to any metric.

### Stage 2 — strike-out against a noisy generator (expert, fast)
Now show ~20–30 candidates from a high-recall/low-precision model. The expert
marks each **keep / strike / duplicate-of-my-own**. Every strike is stored as an
anti-objection with the plan it was struck against.

This is the throughput stage: judging a written candidate is a recognition task,
writing one is a generation task, and recognition is much the faster of the two
per unit of label. It also produces the balanced label distribution that stage 1
alone cannot.

### Stage 3 — reconcile (model, then expert spot-check)
A scorer model merges stage 1 and 2 — deduping the expert's own issues against
kept candidates. The expert reviews only the merge conflicts.

**Output per item:** blocking gold (written + confirmed), a large set of
adjudicated negatives, preference + strength, and — free — a recall measurement
of the candidate generator against un-anchored human gold.

## Not poisoning the labels

The failure mode is anchoring: an expert shown eight plausible candidates accepts
some they would never have written, and gold drifts toward what models already
say. Four controls, three of them measurable:

1. **Write-first ordering** (above). The un-anchored issues exist before any
   candidate is seen, so the anchoring-prone stage cannot overwrite them.
2. **A write-only control arm.** Keep ~15% of items free-hand, no candidates ever
   shown. If strike-out gold and write-only gold diverge in composition, anchoring
   is measurable rather than assumed. Without this arm you cannot detect drift at
   all.
3. **Never generate candidates with a model under evaluation.** Part 2 hit this
   directly: Opus 5 scored its own reviews and posted the best recall *and*
   precision under its own judge. The same contamination applies to candidate
   generation, and it compounds silently.
4. **Track keep-rate as a live health metric.** A keep-rate drifting toward 100%
   means either the generator got good or the expert stopped reading. Both need
   intervention, and the two are distinguishable by the control arm.

## What to measure to know it is working

| Metric | Why | Failure signal |
|---|---|---|
| Keep-rate per session | label balance | trends to 100% |
| Blocking issues written in stage 1 that no candidate proposed | is stage 1 earning its cost | goes to ~0 → drop stage 1 |
| Write-only vs strike-out gold composition | anchoring | systematic divergence |
| Strength distribution | item difficulty mix | mostly weak → items not discriminating |
| Inter-expert agreement on a shared subset | is gold reproducible | low → the eval measures one desk |

The last one is the most important thing Part 2 could not do. **All of its gold is
one reviewer**, so "the model is wrong" and "the model disagrees with this desk"
are indistinguishable throughout. A second expert on a shared subset is the first
thing to buy at scale, ahead of more items.

## Two levers that make expert time go further

**Collect preference strength, always.** It costs one keystroke and Part 2 showed
it is a *difficulty label*: on strong items accuracy was monotone in model
capability (58→67→67→75 against a 50% baseline), and on weak items every model
fell below its 75% baseline with the ordering inverted. Weak items were not
discriminating. Strength lets you spend expert time only where items separate
models, which is a compounding saving.

**Do not collect what nothing scores.** Of the 60 paragraphs of free-hand gold,
45 were blocking (the only thing recall uses) and 4 were anti-objections (the
sharpest precision signal). The remaining 11 — secondary issues and praise — cost
writing time and fed no metric.

## Honest limits of this proposal

- **The economics are argued in operations, not measured hours.** Nobody timed
  the Part 2 gold pass, so "recognition is faster than generation" is a
  well-supported claim about the task type, not a measurement from this repo.
  Stage-1-vs-stage-2 minutes should be timed in the first real session.
- **The candidate counts come from four models on ten items.** Haiku's 50/50
  keep-rate is one generator on one item set; it is the shape of the argument that
  is robust, not the exact ratio.
- **28.6 candidates per plan may exceed what an expert will actually read.** The
  right number is an empirical question, and reading fatigue would show up as a
  rising keep-rate — which control 4 already watches for.
- **This optimizes for the metrics Part 2 found discriminating.** If the eval's
  headline metrics change, the collection design should be re-derived rather than
  inherited.
