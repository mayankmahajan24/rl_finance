# Report notes — working file

Raw material for the ≤3-page report. Not a deliverable itself. Findings recorded as
they're established, with the numbers that back them.

---

## Note 1 — Output length: what the brief constrains, and where length actually hurts

**Date:** 2026-08-09
**Question that prompted it:** are the generated plans too long for the assignment?

### What the brief constrains

The only length cap in the take-home is on the report: "≤3 pages text + **unlimited
examples/tables**." Plans, critiques, and eval items are repo artifacts and appendix
material. They do not count against the cap. Nothing in the current repo violates the
instructions on length.

### Measured lengths

Part 1 (`part1/plans/`, `part1/critiques/`):

| | mean words | range |
|---|---|---|
| plans (S1–S10) | 2,380 | 1,966 – 2,716 |
| critiques (S1–S10) | 2,198 | 1,559 – 3,164 |

Part 2 (`part2/items/S*.json`):

| seed | plan_A | plan_B | asymmetry | A method | B method |
|---|---|---|---|---|---|
| S1 | 2,278 | 2,748 | +21% | M1 | M2 |
| S2 | 2,565 | 3,652 | **+42%** | M2 | M1 |
| S3 | 2,783 | 3,033 | +9% | M2 | M1 |
| S4 | 2,617 | 1,954 | −25% | M1 | M2 |
| S5 | 3,853 | 2,284 | **−41%** | M2 | M1 |
| S6 | 2,052 | 2,612 | +27% | M1 | M2 |
| S7 | 2,614 | 2,920 | +12% | M1 | M2 |
| S8 | 2,589 | 2,621 | +1% | M2 | M1 |
| S9 | 2,609 | 2,451 | −6% | M2 | M1 |
| S10 | 2,177 | 2,568 | +18% | M1 | M2 |

Means by methodology: **M1 = 2,578 w, M2 = 2,720 w.** No systematic methodology-length
confound — the generation setup is clean on that axis. The problem is *within-item*
asymmetry, which runs to ±42%.

### Verdict: Part 1 plans stay long

The brief asks for hypothesis, data, methodology, validation, known pitfalls — five
sections. ~2,400 words is what a genuinely executable plan costs. More importantly Part 1
is a *measurement of what Claude produces cold*: capping the length would characterize a
constrained Claude, not the real one, and would forfeit the claim that the sample is
representative.

### The framing this unlocks (→ goes in the Part 1 findings section)

Length is not a side issue — **it is the mechanism behind the headline result.**

A 2,400-word plan that enumerates every caveat makes "did it avoid the gold flaw?"
easy to score generously. Recall near ceiling (9 caught / 1 partial / 0 missed) is
partly an artifact of surface area. And the same surface area is what produces
**2.6 manufactured objections per critique**.

So recall-high and precision-low are not two findings. They are one:

> **Claude buys recall with volume.** It is not discriminating between issues that matter
> and issues that merely exist — it is emitting the union of everything plausibly relevant
> and letting coverage do the work. On a desk this reads as diligence; under a precision
> metric it reads as noise.

This directly answers the brief's "where does it break?" — the failure is not "doesn't know
the finance" (the domain content is largely right). It is **"doesn't know how research goes
wrong"**, specifically the triage step: a desk reviewer's skill is knowing which three of
twenty objections would actually change the trade.

Corollary worth stating: this makes the *critique* the weaker artifact of the two, not the
plan. A 2,200-word "desk review" is a category error — a real desk review is 5–8 bullets,
and its value is in what it leaves out.

### Verdict: Part 2 eval items are too long — fix before filling gold

~5,300 words of paired plans per item, ~53,000 words across the ten. Three concrete
problems, in order of severity:

1. **The planted flaw stops being the deciding difference.** At ~2,600 words per side, A
   and B differ in dozens of places. When the discriminator picks A, that choice cannot be
   attributed to the flaw that was planted. The item no longer measures what it was
   designed to measure, and `why_B_is_convincing` becomes unfalsifiable.
2. **Length bias contaminates the pairwise metric.** LLM judges systematically favor longer
   responses. A 42% within-item length gap (S2) is a free signal the discriminator can
   exploit without doing any finance reasoning. The M1/M2 balance above means this is
   per-item noise rather than a systematic bias — recoverable, but only by fixing it.
3. **It breaks the sense-check the brief hands us.** "Performance should scale with model
   intelligence (Haiku 4.5 < Sonnet 4.5 < Opus 4.5 < Opus 4.8)." Noisy long-form pairs
   compress that spread. If the gradient comes out flat we won't be able to distinguish
   "items are bad" from "items are noisy."

**Fix:** condense each eval plan to **400–700 words, matched within ~10% of its pair**, with
the planted flaw as the only substantive difference. Derive by *editing down* the existing
`part2/plans/raw/*.md` rather than regenerating short — this preserves the "Claude wrote it,
under isolation, seeing only its token" provenance in `part2/plans/_manifest.json` and
`part2/ISOLATION.md`, and lets us state exactly what was changed. The brief explicitly
permits it: "you may use Claude / edit / pick your methodology for generating these."

Record the edit step in `part2/ISOLATION.md` so the provenance chain stays auditable.

**Sequencing:** do this *before* filling `part2/gold/S*.json` — those are still stubs
(~10 words each), they are the human labels the entire eval rests on, and shortened plans
make them substantially faster to write.

### One-line version for the report

> Plan length is the finding, not a formatting choice: Claude achieves near-ceiling recall
> by emitting everything plausibly relevant, which is also why its critiques carry 2.6
> manufactured objections apiece. The eval in Part 2 therefore has to control for length
> explicitly, or it measures verbosity instead of judgment.

---

## Note 2 — Condensation applied, and what it exposed

**Date:** 2026-08-09
**Status:** Note 1's Part 2 fix is done. A separate problem surfaced during verification.

### Condensation: done

All 20 Part 2 plans edited down from `raw/` to `short/`, then items rebuilt.

| | before | after |
|---|---|---|
| total | 53,020w | 11,969w (4.4x) |
| per plan | 1,956–3,855w | 583–600w |
| max within-pair gap | 42% (S2) | **2.2%** (S10) |

Length bias is now controlled: every pair matches within ~2%, so a
length-driven judge gets no free signal. Condensing agents ran on Sonnet, scoped
as tightly as the generators (one file, "editing task not a review", forbidden
from adding caveats or fixing methodology), and never saw seed id, slot, pair,
or planted flaw. Recorded in `part2/ISOLATION.md`.

### The problem this exposed: generators repaired their own planted flaws

Verifying that the flaws survived condensation revealed they were often not
there to begin with. **8 of 10 intended-weaker plans reference their own core
flaw in the original `raw/` text.**

| seed | intended-weaker flaw | self-reference |
|---|---|---|
| S1 | denominator circularity | 2 hits — **and fixes it** |
| S2 | spurious trend / leaky holdout | 0 |
| S3 | circular internal validation | 0 |
| S4 | n=1, no base rate | 3 |
| S5 | crowded / surprise collinearity | 4 |
| S6 | tautology / mechanical denominator | 7 |
| S7 | published = consensus | 4 |
| S8 | proxy polarity unvalidated | 7 — **and partly fixes it** |
| S9 | backlog inflated / frame accepted | 7 |
| S10 | guardedness confounded at source | 8 |

S1_B states it explicitly — "DraftKings deposits sit in the denominator of the
regressor and are the outcome... a large negative coefficient even in a world
with zero behavioral substitution, purely from arithmetic" — then makes
baseline-deflated intensity the primary spec, repairing it. S8_A says round-lot
imbalance is "tested as a retail proxy, not assumed" and residualizes against a
sub-penny companion signal.

**Cause:** generators were instructed to "build the strongest possible version of
this approach." Asked for the strongest version of a flawed method, Claude
diagnoses and repairs the flaw. The instruction that was meant to prevent
strawmen also prevented the planted contrast.

### Why this is not purely bad news

A mention is not a repair, and the distinction decides the item:

- **names it and fixes it** -> contrast destroyed, item is broken
- **names it and proceeds anyway** -> contrast *intact*, and it is a **better**
  item than designed — it is exactly the Part 1 failure mode (Claude names a risk
  in its pitfalls section, then proceeds as if it had not), which is the sharpest
  thing a discriminator can be asked to catch

Grep cannot separate these. It needs adjudication per item.

### Implication for the report (-> Part 2 design section)

This is itself a finding about **generating** eval data, worth stating:

> You cannot reliably plant a methodological flaw in a Claude-written plan by
> specifying a flawed methodology. Told to build the strongest version, it
> repairs the flaw — 8 of 10 times here. Constructing convincingly-worse plans
> requires either constraining the model from self-correcting, or accepting a
> weaker contrast and letting the gold labeller find it.

Sequencing note: this must be resolved **before** gold, same as Note 1. Writing
gold against items whose contrast has silently collapsed wastes the most
expensive human input in the project.

### Resolution: the design never needed a planted flaw

Reframed. An item works if the two plans are **distinct strategies** for the same
question; there is no prior that one must carry a defect. Gold preference is the
human's judgment about which approach they would staff — a real decision, not the
recovery of a hidden answer.

Under that framing the self-repair is not a defect at all. It is Claude doing
good work inside its assigned approach, which is exactly what "build the
strongest version of this methodology" asked for. The pairs are better for it:
two strong, genuinely different approaches is a closer match to an actual desk
decision than good-versus-sabotaged.

**Distinctness verified across all 10 pairs** (method vocabulary of A and B is
non-overlapping in every case):

| seed | plan A | plan B |
|---|---|---|
| S1 | cohort-stacked DiD, matched never-adopters | within-user share regression, PPML |
| S2 | log-levels panel FE nowcast | billable-seat gate, growth space |
| S3 | HDBSCAN/UMAP clustering, silhouette | external anchor, institution holdout, abstain |
| S4 | base rate across comparables | single-name documents, expected-loss sizing |
| S5 | DeBERTa fine-tune, quintile portfolios | two-week triage, kill gate, replication |
| S6 | regime/over-reaction, event ordering | cross-sectional panel, industry elasticities |
| S7 | CAR + revision price-in gate | logo-to-ACV ramp, Monte Carlo |
| S8 | RLOIB signal, Fama-MacBeth, cost model | venue partition, proxy benchmark, kill gate |
| S9 | RPO forward-commitment model vs EV | historical LTA outcomes, take-or-pay terms |
| S10 | COGS sizing, sensitivity, switching costs | defensiveness index over transcripts |

No regeneration needed. `forks.json` and `gold/design-intent.json` reframed;
`design-intent.json` is now explicitly a record of prior intent, not an answer key.

### What survives as a report finding

The generalizable observation stands on its own, independent of whether we wanted
the flaw:

> Told to build the strongest version of a specified methodology, Claude
> diagnoses and repairs that methodology's weaknesses — in 8 of 10 cases here,
> including explicitly naming a circular regressor and re-specifying around it.
> This is a capability result, and it is also a practical constraint on eval
> construction: you cannot plant a methodological flaw by specifying a flawed
> method.

---

## Note 3 — Part 1 findings rewritten against the human verdicts

**Date:** 2026-08-09
**Trigger:** the `your_verdict` column got filled in, which changed the headline.

### Dodging the named flaw is a poor proxy for plan quality

The two readings answer different questions — the subagent asked "did this handle
the one flaw specified in advance", the human asked "is this good work". The
totals (7/10 avoided vs 4/10 acceptable) invite a harshness reading; the per-item
breakdown rules it out, because the disagreement runs **both ways**:

| | Count | Seeds |
|---|---|---|
| Avoided the named flaw, still bad | **5** | S2, S4, S6, S8, S10 |
| Partially handled it, still fine | **2** | S3, S5 |
| Agree | 3 | S1, S7, S9 |

The five failed for reasons the gold flaw never named — "overly complex and
disorganized" (S6), "poor assumptions on context and implementability" (S8), "too
anchored" (S4). The two carried a partial version of the flaw and were still
worth staffing.

> **A plan's quality is not reducible to whether it dodged one pre-named
> defect.** Flaw-based scoring measures something narrower than what a desk
> decides on.

Same caution on the critique numbers: 9/10 "caught the flaw" versus 10/10 with a
defect. Both true — catching the named flaw and being a good review are different
achievements, and the recall figure is not a quality score.

Consequences for Part 2: gold must be human (a flaw-matching standard would have
certified five plans the desk rejected), and the eval should not rest on planted
flaws — a design abandoned for a separate reason, independently condemned here.

### Headline reversed

Earlier draft (automated scoring only): *the failure is not "doesn't know the
finance" — the domain content is largely right — it is "doesn't know how research
goes wrong."*

Human verdicts invert this. Sorting the ten verdicts by what was missed versus
what was over-raised:

- **Misses are domain facts** — deposits ≠ active trading (S1); sales headcount
  correlated with visitors (S2); negative→positive earnings breaking a multiple
  and revenue- vs EBITDA-based valuation as a company matures (S6); round-lot
  profitability decaying in minutes not days (S8); renegotiation flow-through
  timing (S10); diffing a shortage against disclosure and consensus (S9).
- **Overreaches are method boilerplate** — tertiary confounders (S1);
  survivorship bias and a 12-name universe (S2); an impossible statistical
  analysis (S3); an inflated minimum event count (S9).

> **Claude over-applies generic research methodology and under-applies finance
> domain knowledge.** It knows the catalogue of ways research goes wrong and
> recites it whether or not the entries apply; what it misses is almost always an
> institutional or mechanical fact. The two are the same failure — reaching for
> the generic checklist is what a model does when the domain-specific insight
> isn't there.

### On the discretionary seeds

The brief asks whether the fundamental failures are "anchors on the narrative" or
"can't tell mechanism from correlation." Evidence supports **neither** as the
main story. Only S4 was judged *"too anchored"*; S9's plan explicitly refused the
management frame. The real discretionary failures were **context and
implementability** — S8 *"why would an asset manager care about this?"*, S9
*"underassumes firm's market data tooling."* Reasoning about mechanism is
competent; judging who the work is for is not.

### Self-critique

Holds up, and in one direction: the critique is the stronger artifact. Human
verdicts note "better simplification" (S6), "better scoped" (S10), "picked up on
the wrong construct and overengineering" (S3). On the obviously-flawed seeds the
plan proposed a kill once, the critique three times. Claude knows an idea is weak
while writing the plan and scopes the full project anyway.

---

## Note 4 — Haiku 4.5 sweep (baseline model)

**Date:** 2026-08-09
**Status:** 28 pairwise + 28 pointwise calls, 0 errors after retries. Gold not yet
written, so these are the diagnostics that do not require an answer key.

### Pairwise — works, with two real weaknesses

| Diagnostic | Result |
|---|---|
| Self-consistent across A/B and B/A | **11 / 14** (chance 50%) |
| Agreement with my design intent | **10 / 11** consistent items = 91% |
| `goal_type` stable across orderings | **8 / 14** |
| Slot-A rate | 61% |
| Mean confidence | 3.7 / 5 |

Three items (S1, S6, S7) flip when the plans are swapped — on those Haiku is
responding to presentation, not discriminating. `goal_type` instability is worse:
the same seed and plans are read as `mechanism_test` one way and
`single_name_kpi` the other on 6 of 14. Since every later tenet is conditional on
the goal read, that instability propagates.

**Construction flaw, recorded:** in all ten forks I made M1 the intended-stronger
methodology. Slot assignment is mixed 5/5 so nothing leaks to an evaluator (it
never sees M1/M2), but my prior was never varied. That is why "agreement with
design intent" is cleanly measurable here — and why it must not be mistaken for
accuracy.

**The 91% needs care.** The brief's sense-check says a 90% Haiku score means the
items are too easy. But this is 91% agreement with *my prior*, not with gold. In
Part 1 the human verdicts diverged sharply from automated scoring; if gold
diverges from my intent on even three items, real accuracy falls toward 65%.
**Gold decides whether this eval is too easy, and nothing else can.** It also
promotes the no-tenets control from optional to necessary: with 13 tenets in the
prompt, 91% may be rubric-following rather than judgment.

### Pointwise — Haiku cannot follow the precision instruction

| | |
|---|---|
| Issues per review | mean **26.3**, median 17, max **90** |
| Severity split | ~90% secondary |
| Truncations before retry | 7 / 28 at 32k; 2 still failed at 48k; cleared at 64k |
| `explainability_fit` "over-" value used | **0 times** |
| Top category | `measure_validity` raised **194 times** |

A desk review is 3–8 findings. Haiku produced a median of 17 and one review of
90 against a 600-word plan — a ~15x overshoot. It marks ~90% of them secondary,
so it partly knows they do not matter, and emits them anyway. This is the
exhaustiveness/Type I failure the error-asymmetry tenet exists to catch.

**Consequence for scoring:** against a gold list of ~4 blocking issues, a
90-issue review scores near-zero precision by construction. The metric would
measure verbosity, not judgment.

**Partly the prompt's fault, and worth saying so.** The pointwise prompt is
~2,600 words over 13 tenets, most with sub-checks. A literal-minded model reads
it as a checklist and emits one issue per checkpoint. `measure_validity` at 194
mentions — the newest and most narrowly scoped tenet — supports that reading.

**What did work:** `why_it_applies_here` was never left generic (0 of 585 issues
had a justification under 80 characters). Forcing per-issue justification
produces real reasoning even when the model over-produces.

### Open decision before running Sonnet / Opus

Cap `issues` with `maxItems` (~12) so the model must *select* rather than
enumerate. This fixes truncation, makes precision meaningful, and matches what a
desk review actually is. It changes the instrument, so it must be decided before
the other models run — and the Haiku data would need re-running to stay
comparable.

---

# Note 5 — the four-model sweep, gold-free

All four models completed 28 pairwise + 28 pointwise calls, zero errors, matching
prompt and schema fingerprints. Opus 5 required two credit top-ups and a merge
retry; `retry_eval.py` preserved the 17 calls that had already succeeded.

| | Haiku 4.5 | Sonnet 5 | Opus 4.8 | Opus 5 |
|---|---|---|---|---|
| Self-consistent (AB vs BA) | 11/14 | 11/14 | 12/14 | **13/14** |
| Frame stable (`goal_type`) | 8/14 | 11/14 | 10/14 | **13/14** |
| Slot-A rate (50% = unbiased) | 61% | **46%** | **50%** | 54% |
| Issues per pointwise review | **26.3** | 3.9 | 3.9 | 6.6 |
| `goal_type` categories used | 3/5 | 4/5 | **5/5** | **5/5** |
| Preference moved on a context flip | 0/4 | 0/1 | 1/3 | **2/3** |

## Finding: no single metric orders all four models

This is the practical result of the sweep, and it is a design finding rather than
a model finding.

- **Issues per review** separates Haiku (26.3, max 90) from everything else, then
  goes non-monotone — Opus 5 raises *more* than Sonnet and Opus 4.8 (6.6 vs 3.9).
  Verbosity resolves the bottom band only.
- **`goal_type` coverage** is monotone but saturates: 3 → 4 → 5 → 5. It cannot
  separate the top two.
- **`explainability_fit = over_demanded`** fires 9 times for Opus 4.8 and 0–1 for
  everyone else including Opus 5. This looked like a top-band discriminator on
  three models; the fourth shows it is an Opus 4.8 idiosyncrasy. **One model can
  invent a trend across three points.**
- **Stability metrics** (self-consistency, frame stability) are the only ones that
  are monotone *and* still separating at the top — and they are exactly the
  metrics the thinking confound below contaminates.

**Consequence:** the eval needs a metric panel, and the panel must be read by
band. Reporting a single headline number would have picked a metric that resolves
one band and flattens the rest.

## The context-flip result inverts a metric that looks like a win

`flip_test.py` reports two things per model: whether preference moves when only
the firm changes, and whether the model's reading of *the plan* drifts (it should
not — the plan is byte-identical).

| | Haiku 4.5 | Sonnet 5 | Opus 4.8 | Opus 5 |
|---|---|---|---|---|
| Implied-asker drift (lower better) | **0/8** | **0/8** | 3/8 | 2/8 |
| Preference moved (capability) | 0/4 | 0/1 | 1/3 | **2/3** |

Read alone, the drift row says Haiku and Sonnet are the disciplined readers. The
second row says why: **they never moved anything.** Zero drift is free if the
model is scoring plans in the abstract and ignoring the stated firm entirely —
which is a tenet-2 failure, not a success.

Neither row is interpretable without the other. A stability metric only counts as
a virtue when paired with evidence the model *can* move.

## Confound: Opus 5 is the only model that thinks

Measured directly rather than assumed — inspect the returned content-block types:

| model | thinking by default |
|---|---|
| haiku-4-5, sonnet-5, opus-4-8 | off |
| **opus-5** | **ON (adaptive)** |

`run_eval.py` never passes `thinking`, so every model runs as shipped. The
fingerprints cover prompt and schema, **not sampling configuration**, so this
difference was invisible in the comparability check that otherwise guards this
sweep.

Opus 5 leads on precisely the two metrics extended reasoning would be expected to
improve — self-consistency and frame stability. So its lead is **model + thinking**
and is not attributable to capability on this data.

Running each model as shipped is a defensible primary configuration; it is how a
desk would actually invoke them. But it is a choice, and the ordering it produces
is not on its own evidence about capability. The separating control is Opus 5 with
thinking explicitly disabled, versus its default-on run. Until that exists this
sweep supports **Haiku < Sonnet ≈ Opus 4.8** as a capability ordering and holds
the Opus 5 row as not-yet-attributable.

## What still gates the headline claim

Everything above is gold-free. The assignment's sense-check — *scores should scale
with model intelligence; if Haiku gets 90% the items are too easy* — is an
**accuracy** claim, and accuracy needs gold, which is still empty. The diagnostics
show Haiku is clearly separated on process; they cannot yet show it is separated
on being right.

---

# Note 6 — What the gold pass exposed about the plans

**Date:** 2026-08-09
**Produced by:** labelling `part2/gold/S1..S10` item by item against `TENETS.md`.

Part 1 measured Claude critiquing itself. This note is different evidence: a human
reading twenty plans closely enough to pick between them and say why. The failure
modes below recur across items, slots and methodologies, so they are properties of
how Claude plans research — not of any one seed.

## The headline: manufactured precision

Part 1's finding was that **Claude buys recall with volume**. The gold pass found
the same instinct in a second register: **Claude buys credibility with precision.**
It reaches for exact-looking numbers that were never derived from anything, and the
numbers then carry decisions.

**Arbitrary numeric thresholds — flagged on five of ten items, in both slots:**

| Item | The numbers | What rests on them |
|---|---|---|
| S4_A | prior of 20:1–30:1 against, ~25x likelihood ratio required, "leverage-driven one to three in fifty" | The entire evidence bar. The denominator was invented |
| S7_A | >0.5% priced / <0.2% dismissed, CAR under 1 SD, straddle under 1.2x trailing median | The stop-go gate before any fundamental work |
| S7_B | ≥75bp above midpoint, ≥50bp above consensus, raise >1.5x median, move ≥1.2x implied | Whether the trade goes on at all |
| S8_B | lift ≥2.0x, recall ≥35%, signing ≥70%, r ≥0.40, t ≥3 | Five conjunctive kills on labels with no ground truth |
| S9_A | tier haircuts 90–95 / 70 / 25–35%, six constructive conditions | The coverage math and the verdict |
| S10_A | under 25bp makes tone moot, over 75bp forces a call | The materiality frame |

Human verdict, recurring verbatim: *"the explicit numeric thresholds seem
arbitrary"*, *"the thresholds for both are a bit arbitrary."* This is distinct from
a missed issue. A plan that says "we will stop if the effect is small" is honest; a
plan that says "we will stop below 0.5%" has produced an unearned decision rule and
made it load-bearing. It reads as discipline and functions as decoration.

## Recurring failure modes, with citations

**1. Horizon set by data availability, not by the phenomenon (tenet 6).** S6_A
proposed a TAQ tick-data check for a question about multiple re-rating — *"the time
horizon for a multiple rerating is months to years NOT milliseconds."* S8: both
plans built daily signals with next-day entry when fading retail order flow is a
market-making activity at nanoseconds to seconds. Claude reaches for the highest
resolution available rather than the resolution the phenomenon lives at.

**2. Plans that don't scale to the asker (tenet 2).** S6_A wanted TAQ at a firm
with no tick data. S9_B assumed a subscription stack — TrendForce, Fastmarkets,
UxC, Argus/ICIS, Drewry/Xeneta, Panjiva, PACER, SEMI — at a five-person Bloomberg
shop; the human's fix was that *"the firm would need to cobble together data points
individually using their analysts."* S10_B proposed a 40,000 firm-quarter panel
with embeddings and a pinned LLM at that same shop: *"you can't do a 40,000
firm-quarter panel in excel, nor would that firm be interested in that kind of
analysis even if it is stronger statistically."*

**3. Reasoning like an outsider when the asker has better data.** S8: both plans
triangulated public retail-identification labels — Rule 605 reports, RLP flags,
sub-penny classification — at a firm that *internalizes retail flow* and therefore
holds real labels in its own systems. Neither considered it. Claude imports the
data constraints of an academic researcher into firms that don't have them.

**4. Fixing the mechanics by breaking the measure (tenet 5).** S6_A killed the
circularity correctly, then adopted a trailing LTM multiple — *"an alternate
valuation metric that doesn't reflect how assets are priced in public markets
(mostly on forward earnings not prior earnings)."* One error traded for a worse one.

**5. Naming a leak and keeping it anyway.** S2_A headlines a random 20%
company-quarter holdout and states *in the same sentence* that random splits leak,
demoting rolling-origin to a gate. Claude can identify the contamination and still
report the contaminated number. This is the brief's own named failure — "propose
validation that leaks" — in a form where the plan diagnoses itself and does not act.

**6. Generalizing what shouldn't be generalized.** S4_A coded 40–60 comparable
guarantor releases as draws from a common distribution: *"tries to generalize
something that should not be generalized."*

**7. Kitchen-sink fitting over hypothesis-led subsetting.** S5_A: *"it's better to
start with strong priors / subsets of the data and market you think the signal will
work on and test that."* Related, same item: the custom domain-adapted transformer
may be unnecessary if *"finbert or some time series z score with a standard scoring
model works well"* — Claude reaches for the most capable method rather than
establishing what the cheap one delivers first.

**8. No commercial baseline.** S5_A never sets a licensed vendor score as the
hurdle a custom build must clear. Claude benchmarks against academic baselines and
factor models; it does not ask whether you could simply buy the signal.

**9. Human-fatigue caveats under AI execution (tenet 10).** S4_B warns that *"after
300 pages every clause looks intentional."* The volume of reading is not a cost
when an AI reads it; the missing content is a rule for separating genuinely salient
clauses from precedent boilerplate.

**10. Gating on evidence the setting cannot produce (tenet 7).** S8_B stakes five
conjunctive kills on labels with no ground truth, so a label-quality failure reads
as a signal failure. S3_B manufactures ground truth with a consented survey of 500
respondents per country — *"it should not have required any survey work."*

**11. Screening out the interesting observations.** S6: both plans screen away
negative and near-zero EBITDA denominators. *"The negative denominator multiples
can be handled by switching to a revenue multiple instead of EBITDA multiple"* —
the cases dropped are the ones where re-rating is most violent.

**12. Not questioning the primitive.** S8 fixes round lots at 100 shares
(A explicitly holds it fixed against the SEC's own tiered redefinition). *"100
shares can be a lot, we should also consider 1, 5, 10, 20 shares as round."*

**13. Delivering the framework instead of the answer.** S9_B ends at *"a
probability-weighted haircut, not a verdict"*; S3_A's primary output is country
plus archetype, which is not a tradable name. The work stops one step short of the
decision it was commissioned for.

## What the plans got right

Recording these because precision is only measurable against sound work.

- **Both plans on S4 and S7 refused the seed's embedded conclusion.** S4 enumerated
  five mundane nulls before the strategic reading; S7 gated on whether the checks
  were already priced. Anchoring on the question's framing — a Part 1 failure — did
  not recur here.
- **Circularity was caught unprompted on S6 by both plans**, and on S1_B, which
  states the denominator problem explicitly and builds a permutation null against it.
- **Self-diagnosis is strong even where self-correction is not.** S2_A names its own
  leak; S3_A states "cohesion isn't correctness"; S8_A concedes a one-day sign would
  be liquidity provision. In each case the plan sees the problem and proceeds anyway
  — which is a more specific and more actionable finding than "misses the flaw."

## Findings about the eval itself

- **`goal_type` is not always single-valued.** On S8 three of five categories were
  judged partially right. Exact-match scoring on that field overstates its precision.
  Written into `SCORING.md`.
- **Error asymmetry is a property of the item, not the firm.** `event_desk` came
  back `type_i_dominant` on S4 and `type_ii_dominant` on S7. The original scoring
  design asserted a firm-to-asymmetry mapping; the gold disproves it, and S4 vs S7
  is now the pair that catches a model inferring asymmetry from the firm label.
- **`decisive_tenets` is not the same as critique content.** S8's sharpest issue is
  horizon (tenet 6) while its decisive tenets are 1 and 2. Scored as set equality,
  a model naming tenet 6 there would be marked wrong for finding the best objection
  in the item. Now scored as overlap with partial credit.
- **Tenets 6, 9 and 12 are never decisive** across the ten items; 13 never appears
  by design. Their absence is an item-set property, not a model error.
- **The pairs are unbiased by construction.** The winning plan came from methodology
  M1 five times and M2 five times, with plans matched within ~2% on length. The
  pairwise metric is measuring judgment, not generation style or verbosity.
- **Issue count does not track preference.** S1's gold carries three issues against
  the winner and one against the loser. A discriminator scoring by defect tally gets
  that item exactly backwards, which is the property that makes it worth including.
- **Context is load-bearing and was wrong twice.** S3 and S8 both needed their firm
  reassigned once the seed's natural asker became clear — S8 to a market maker,
  because the horizon critique was otherwise punishing a model for correctly
  following the stated brief. Seeds carry an implied asker, and the assignment has
  to match it or the item tests the wrong thing.
- **"Say when an objection doesn't apply" was exercised repeatedly** — the thin gate
  sample on S2, the event-count and heterogeneity objections on S9, the reading
  volume on S4. These are the precision anchors: without them a model manufacturing
  plausible objections scores well on recall and its noise stays invisible.

---

# Note 7 — the graded results, and what to put in the report

Everything below is scored against human gold on the ten base items. Detail and
method live in `part2/GRADED.md`; this is the report-facing synthesis. Raw output
is `part2/graded-output.txt` (pairwise) and `part2/issue-scores-output.txt`
(pointwise).

## The six results worth reporting

**1. The aggregate is a trap; the split is the result.** Pairwise accuracy is
50–65% against a 60% always-answer-A baseline, which reads as "models cannot
discriminate research plans." Split by gold's own confidence it says the opposite:

| | Haiku 4.5 | Sonnet 5 | Opus 4.8 | Opus 5 | baseline |
|---|---|---|---|---|---|
| Strong items (n=12) | 58% | 67% | 67% | **75%** | **50%** |
| Weak items (n=8) | 50% | 38% | 25% | 50% | **75%** |

Same twenty calls per model. Where the reviewer was confident, accuracy is
monotone in model capability and everything beats chance; where the reviewer was
torn, everything is below chance and the ordering inverts. **Report strong-item
accuracy as the headline and carry weak items separately** — that is forced by
the data, not a stylistic choice.

**2. Preference strength turns out to be a difficulty label.** This is the
reusable design point: gold confidence predicts whether an item discriminates at
all, and it costs nothing to collect because the reviewer is already writing it.
It should gate which items count, not merely how they are reported.

**3. The sense-check passes, in the direction the brief was not worried about.**
The concern was *"if Haiku gets 90%, the items are too easy."* Haiku scored 55%,
below the trivial baseline. The live risk is the opposite one.

**4. Recall discriminates; precision does not; neither alone ranks the models.**

| | Haiku 4.5 | Sonnet 5 | Opus 4.8 | Opus 5 |
|---|---|---|---|---|
| Recall (of 45 blocking) | 53% | 29% | 33% | **62%** |
| Precision band | 31–50% | 68–97% | 71–92% | **90–98%** |
| Manufactured per review | **14.3** | 0.1 | 0.3 | 0.2 |

**This inverts the Part 1 prediction the Part 2 design was built on** — that
recall would be at ceiling and precision the weakness. And recall is not monotone
in capability: Haiku beats both mid-tier models by raising 28.6 issues per review
against their ~3.5. The two parts measured recall against different objects: one
pre-named flaw (9/10, a ceiling) versus 45 human blocking issues (62% at best).
**Recall against a planted flaw is a ceiling metric; recall against a real desk
critique discriminates.**

**5. F1 is the wrong summary, and this data shows why.** Haiku's F1 band
(0.39–0.52) spans both mid-tier models, because F1 is a ratio and normalises away
how much noise was produced to buy the recall. The absolute count does not:
**14.3 manufactured objections per review versus 0.1.** A ~100x gap, and the
cleanest separation anywhere in this eval. **Report recall and
manufactured-per-review as a pair; do not report F1.** That pair is the answer to
the brief's recall/precision question, and it is stronger than the three-bucket
precision design alone — which the Haiku column shows can be satisfied while the
reviewer is still unusable.

**6. The gold pass audited the instrument, and the instrument lost.** Two defects
surfaced only when real labels met the schema, and **neither was visible in the
gold-free diagnostics that looked clean across three prior model sweeps**:
`symmetric` is offered in the `error_asymmetry` enum while the prompt routes
symmetric payoffs to `type_ii_dominant` (0 emissions in 80 calls), and none of the
five `goal_type` labels is defined anywhere in the instrument. Both metrics are
therefore unreportable as capability. The transferable lesson is that **gold-free
process metrics cannot validate an instrument** — only real labels can.

## Two items worth more than any aggregate

**S5.** Gold is *strong* for A; all four models chose B under both orderings.
Unanimous and confident against a confident human is a shared blind spot, not
noise, and it is the single most informative item in the set. S3 is the same shape
at weak strength.

**Haiku is differently wrong, not uniformly worse.** It is the only model correct
on S2 and S9 while missing S1 and S7, where the other three are right. Any
single-scalar leaderboard erases this.

## What the anti-objection category bought

Not in the original design, and the highest-value thing found while building the
denominator. Gold contains sentences that rule an objection *out* — *"the
objection that twenty to thirty episodes is too few does not apply"* (S9B). Those
are gold-certified false positives: checkable without adjudicating anything, and
they measure the exact Part 1 failure. Four traps across ten items; Haiku hit 7,
the others 0–3. **Cheap to collect and worth designing for deliberately** — a
carry into Part 3.

## Caveats that must travel with these numbers

- **Opus 5 scored itself.** It posts the best recall *and* the best precision
  under an Opus 5 judge, which is what self-preference looks like. Blinding the
  scorer to model identity does not remove it. Treat its margin as an upper
  bound. Unaffected: Sonnet vs Opus 4.8 (neither is the judge, and they are 4
  points apart, i.e. not separated), and the Haiku manufactured-rate finding,
  which is a 100x gap rather than a 4-point one.
- **Opus 5 is the only evaluated model that thinks** (Note 5). Its lead is
  model + thinking.
- **Precision is a band** because the scorer was told to prefer `real_unlisted`
  when torn. The point estimate quotes the tie-breaking rule.
- **Ten items, one reviewer, n=1 per call.** Where a model disagrees with gold the
  honest reading is "disagrees with this desk," not "wrong."
- **The classifier that built the denominator is not deterministic** — it returned
  43 then 45 blocking issues on two runs of the same input. Recall denominators
  carry roughly ±2 of slack.

---

# Note 8 — Part 3: collecting expert judgment at scale

**Date:** 2026-08-10
**Produced by:** four parallel design explorations, then verification of every load-bearing
number against `part2/runs/` and `part2/gold/` directly. Numbers marked **[measured]** were
recomputed from repo files; those marked **[estimated]** come from the design analyses and
have not been validated against a stopwatch.

## What Note 7 already settles

The recall / precision / F1 results and the recall-is-not-monotone-in-capability finding
live in **Note 7 §§ 4–5** and are not restated here. Note 7's framing is the one to use:
report recall and manufactured-per-review as a pair, and do not report F1. The two facts
from it that this section builds on:

- Haiku raises **28.6 issues per review at 50.0% precision**, against ~3.5 at 92–97% for the
  mid-tier models and 6.7 at 97.7% for Opus 5.
- Opus 5 was the adjudicating scorer for every model's issues.

**One [measured] result Note 7 does not cover, and Part 3 turns on it: the frame is where
models fail hardest.** Agreement with gold across 20 order-swapped pairwise calls each is
13/20 (Opus 5), 11/20 (Sonnet), 11/20 (Haiku), 10/20 (Opus 4.8) — barely above the 10/20
coin flip. `goal_type` agreement is **3–6 of 20 for every model**. Frame fields are also the
cheapest thing an expert can produce, because they follow from the seed and the firm context
without reading either plan closely. **The label models get most wrong is the label that
costs least to collect**, and no protocol in the design space was built around that.

## What this does to the brief's Part 3 question

The brief asks whether it is cheaper for the expert to write the gold issue list, or for
Claude to propose eight candidates and the expert to **strike out the wrong ones** — and what
the second approach does to the label distribution.

**[measured]** The answer is generator-dependent, and the dependence is enormous:

| Generator | candidates/review | share not real | escalations needing human |
|---|---|---|---|
| Opus 5 | 6.7 | **2.3%** | 16 / 133 |
| Sonnet 5 | 3.3 | 3.0% | 20 / 66 |
| Opus 4.8 | 3.6 | 8.3% | 19 / 72 |
| Haiku 4.5 | 28.6 | **50.0%** | 172 / 572 |

With a strong generator the brief's premise is close to empty: 97.7% of what Opus 5 raises is
defensible, so **the expert is not a truth filter, they are a materiality filter.** Against
~6.6 available candidates the human raised 2.6 — they surface 39% of what is true. Instructed
as the brief words it ("strike the wrong ones") the expert strikes almost nothing and gold
issue counts inflate roughly 2.5x. Reworded as "strike what you would not raise at a desk
review," the same mechanic yields ~11 labelled negatives per critique against the 0.2 the
expert produces spontaneously.

**So the instruction wording is worth more than the candidate count**, and the honest answer
to the brief's question is that its framing applies to Haiku and not to Opus 5.

**On the self-scoring exposure Note 7 flags:** it is narrower than it looks for the purpose
of *choosing a generator*. Opus 5 rates Sonnet at 97.0% against its own 97.7% — a 0.7pp gap,
no self-flattery — and the 50% it assigns Haiku is a large real spread. Generator selection
turns on that spread, not on the contested middle.

## Four designs, compared

| | **A · Strike-out triage** | **B · Disagreement routing** | **C · Interview capture** | **D · Gold by construction** |
|---|---|---|---|---|
| Expert min/item **[est]** | 27, or 41 as a 2nd pass | 10.1 blended | 17.4 | 11 → ~2.4 amortized |
| vs. free-hand (~27–32) | ~1.2x | 2.5x | 1.6x | 2.4x → 10x |
| Produces best | ~11 negatives per critique | frame labels at ~1.8 min each | idiosyncratic findings, anti-objections | volume; single-tenet counterfactuals |
| Cannot produce | recall denominator (capped at generator recall, 62%) | precision anchors (~45 min each) | clean provenance | omission and frame issues; **no `weak` items at all** |
| Poisoning mechanism | supply constraint; generator fingerprint enters gold | correlated blind spots invisible by construction | ~86% of gold words model-authored | model detects the seam, not the defect |
| Pairwise headline | survives if preference elicited before candidates | survives | survives — enums captured before any prose | n/a — cannot make close calls |

Three cross-cutting results:

**1. The cheapest label is the one models get most wrong, and no design was built for it.**
Frame fields are derivable from seed plus context alone, so a ~2.5-minute label is as good as
a 25-minute one. The value spread **[est]** is ~1.8 expert-minutes per frame correction, ~9
per preference resolution, ~45 per anti-objection — 25x, sitting unexploited.

**2. Disagreement routing fails its own kill criterion on this data. [measured]** Of the four
items where all eight votes agreed, the ensemble is right on two; on S5 — a gold *strong*
item — all four models in both orders picked wrong. Minority share on strong items (0.167) is
indistinguishable from weak (0.156). It is justified for frame labels and for item QA, not as
difficulty triage.

**3. Construction cannot make the items half of this gold consists of. [measured]** Four of
ten base items are `weak` — genuine close calls between two defensible approaches, and a
constructed item has a right answer by definition. Only ~25 of the 45 blocking gold issues are
span-injectable; the missing 20 are domain-knowledge omissions (Robinhood-routed users, the
half-penny regime break, the firm's own internalized flow) and whole-document frame failures,
which is where tenets 1 and 2 live — 8 of the 20 decisive slots.

## The recommended pipeline

Four stages, each doing only what it is uniquely best at. Costs **[estimated]**.

| Stage | Scope | Min/item | Yields |
|---|---|---|---|
| **Frame pass** | every item | 2.5 | `goal_type`, `error_asymmetry` — the fields models fail hardest |
| **Judgment pass** | every item | 17 | preference, critiques, rationale, anti-objections |
| **Precision pass** | items that already have gold | 9 | ~11 labelled negatives per critique |
| **Volume layer** | separate slice, never aggregated | ~2.4 | per-tenet sensitivity curves |

The judgment pass is interview capture: the expert talks, a model structures, with a
**verbatim spine** (the first sentence of every critique stays the expert's words), a
provenance sidecar, and a **trichotomy confirm** — keep / cut / *true but not mine*. That third
bucket is the sharpest mechanism the exploration produced: partial agreement routes to
`secondary`, never `blocking`, so a half-held objection can help a model's precision score and
can never hurt its recall. Non-response defaults to **cut**, so acquiescence removes model
content instead of ratifying it.

The precision pass runs **second, never first** — showing candidates only for items whose gold
already exists, minus anything already matched, asking only "would you raise this?" The recall
denominator is fixed before any candidate exists, so the supply constraint cannot bite.

Rough cost for 100 items: ~250 min frame + ~28 h judgment + ~15 h precision ≈ **48 expert-hours**,
against ~45 h for 100 free-hand items carrying no negatives, no frame verification and no
per-tenet resolution.

## The stream the Haiku data unlocks: harvest negatives, don't elicit them

**[measured]** This gold contains **4 anti-objections in 60 issues** — the scarcest and, at an
estimated ~45 expert-minutes each, the most expensive label in the system. `SCORING.md` calls
them the precision anchors: without them a model manufacturing plausible objections scores well
on recall and its noise stays invisible.

Haiku produced **286 manufactured objections, 227 of them adjudicated with no uncertainty
flag**, each carrying a written reason:

> *"Canonical look-ahead objection misapplied: the OLS slope over −6..−1 uses only pre-period
> data, so there is no look-ahead."*
>
> *"Overfitting objection rests on an invented sample size for a licensed card-and-bank panel."*

That is exactly the class the Part 1 gold caught four times by hand — canonical concerns
recited without checking whether they bite. **So run a weak model deliberately and adjudicate
its output.** It is the one place in the system where a cheap model is the right instrument
rather than a compromise: 227 labelled precision failures at roughly two orders of magnitude
less expert time than eliciting them, with 79% of the adjudication already free.

Two cautions. The adjudicator was Opus 5, so a harvested corpus inherits one model's judgment
of what counts as unearned — the 59 uncertain cases are where a human should look first. And
harvested negatives describe *Haiku's* error distribution; they are training and evaluation
material for recognizing recited objections, not a general model of how discriminators fail.

## Open

- The Sonnet / Opus 4.8 precision inversion (97.0 vs 91.7) is the one place the scorer's
  identity could be moving the ranking. Rescoring that pair with a non-Claude adjudicator, or
  with Opus 4.8 as scorer, would settle it cheaply.
- Every expert-minute figure above is an estimate. The one real data point is this session:
  10 items in roughly a 3-hour block, ~18 min/item, which is close to the interview-capture
  estimate of 17.4 and is the only number here with any observational basis.
- The four flip items remain unlabelled, so the context-sensitivity axis has no gold.
