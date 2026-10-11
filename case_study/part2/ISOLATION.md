# Isolation rules — what each agent is allowed to know

Three tiers. An agent in one tier must never receive a lower tier's inputs.
Violating this doesn't produce an error; it produces a good-looking number that
measures nothing.

| Tier | Agent | Receives | Must NEVER receive |
|---|---|---|---|
| 1 | **Generator** — writes a plan | The seed sentence; its own assigned methodology brief | The other methodology; that a competing plan exists; which approach is preferred; any repo file |
| 2 | **Evaluator** — the thing under test | The seed; one plan (pointwise) or two plans (pairwise) | Gold preference; gold critiques; `gold/design-intent.json`; the methodology briefs; Part 1 findings; any repo file |
| 3 | **Scorer** — grades the evaluator | The evaluator's output; the gold labels | Nothing to protect — scorers grade, they never generate or evaluate |

## Enforcement

- **Tier 1 and 2 get no repo read access.** Content is passed inline in the
  prompt. Where a file path is unavoidable, the prompt names exactly one path and
  forbids every other read.
- **`gold/` is quarantined.** It holds `design-intent.json` (my private read of
  which plan is stronger) and the human gold labels. Nothing in `gold/` may be
  quoted into a Tier 1 or Tier 2 prompt.
- **`forks.json` is Tier 1 material only.** It contains both methodologies side
  by side, so an evaluator that saw it would know the intended contrast. It no
  longer contains design intent — that moved to `gold/`.
- **Slot assignment is mixed 5/5.** The stronger methodology sits in slot A for
  five seeds and slot B for the other five, so an evaluator cannot score above
  chance by always picking a position.

## Condensation pass (length edit, provenance preserved)

The 20 generated plans averaged ~2,650 words, which made the pairs unusable as
eval items: at that length A and B differ in dozens of places, so a
discriminator's choice cannot be attributed to the planted contrast, and
within-item length gaps ran to 42% — free signal for a length-biased judge.

Each plan was therefore **edited down to 500–600 words** (`part2/plans/short/`),
not regenerated short. The originals remain in `part2/plans/raw/`. The brief
permits this: "you may use Claude / edit / pick your methodology for generating
these."

Condensing agents ran on Sonnet and were scoped as tightly as the generators:
each read exactly one token file, was told this is *an editing task, not a
review*, and was explicitly forbidden from adding caveats, improving the
methodology, or dropping a step it judged weak. They never saw the seed id, the
slot, or the paired plan. Result: all 20 within 500–600 words,
max within-pair gap **2.2%** against a 10% target, 4.4× total reduction.

`build_items.py` prefers `short/` and falls back to `raw/`.

## Known deviation, recorded rather than hidden

The first 11 plans (S1–S6) were generated with the output path and file header
carrying the slot label — `part2/plans/S1_A.md`, `# S1 · plan A`. The generating
agent therefore knew it was writing one of a labeled pair. It did **not** learn
what the alternative was, which was preferred, or that a preference would be
assigned, and the methodology was fully specified so it could not drift toward or
away from an unseen alternative.

This is minor but not zero. The fix for a clean run is to have generators write
to an opaque filename that is mapped to a slot afterwards. Whichever way this is
resolved, **all 20 plans must be produced under the same condition** — a mixed
set is worse than a uniformly-marked one, because it introduces a difference
between items that has nothing to do with the methodology being tested.

## Sampling configuration — a known confound in the model sweep

The fingerprints prove every model saw the same prompt and the same schema. They
do **not** cover sampling configuration, and one difference matters.

`run_eval.py` never passes `thinking`, so each model runs at its shipped default.
Measured directly (`messages.create`, inspect returned content-block types):

| model | thinking by default |
|---|---|
| claude-haiku-4-5 | off |
| claude-sonnet-5 | off |
| claude-opus-4-8 | off |
| **claude-opus-5** | **ON (adaptive)** |

So Opus 5 is the only model in the sweep that reasons before answering. Any Opus 5
vs Opus 4.8 difference is therefore **model + thinking**, not model alone, and must
not be read as a clean capability gap.

This is a defensible primary configuration — it is how each model behaves when
invoked as shipped, which is how a desk would actually use it — but it is a
configuration choice, not a neutral one, and the ordering it produces is not
evidence about model capability on its own.

The control that separates the two: re-run Opus 5 with `thinking` explicitly
disabled and compare against its default-on run. Until that exists, the sweep
supports "Haiku < Sonnet ≈ Opus 4.8" as a capability ordering and treats the
Opus 5 row as not-yet-attributable.

