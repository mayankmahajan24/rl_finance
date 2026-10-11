# Part 2 — an eval for the discriminator

Given a plan (or a pair), can Claude score quality and explain why? This builds
the eval that measures it.

## The design decision, and why

Part 1 found recall at ceiling and **precision** as the real weakness — 2.6
manufactured objections per critique. So the pairs here are **both competent**.

> **The results inverted this premise.** Scored against gold, recall discriminates
> (29–62%) and precision does not. Part 1's recall was at ceiling because it was
> measured against *one pre-named flaw*; against 45 real desk objections it is the
> sharpest axis in the eval. The design decision below is still right — both plans
> must be competent — but the reason it is right changed. See `GRADED.md`.
Each seed forks into two genuinely different strategies, each built as the
strongest version of its own approach. An eval built on broken plans measures
recall only, and every model scores near-perfect.

**Neither plan carries a deliberate defect.** An item works if the two approaches
are genuinely distinct; the gold preference is a real judgment about which one
you'd staff for this firm and this goal. This is a deliberate deviation from the
brief's example format, which frames the second plan as "convincingly wrong" — we
found that construction does not survive contact with the generator. Told to
build the strongest version of a weak methodology, Claude diagnoses and
re-specifies around the weakness (8 of 10 cases, `REPORT-NOTES.md` Note 2). The
reframed design is closer to a real desk decision anyway: two credible approaches,
one of which fits better.

## Layout

```
forks.json              the two methodologies per seed, and which slot each landed in
plans/raw/<token>.md    the 20 plans as generated (opaque tokens — see below)
plans/short/<token>.md  the same plans edited to 500-600w — what items use
plans/_manifest.json    token -> (seed, slot)
items/S1..S10.json      assembled eval items: seed, plan_A, plan_B, gold
gold/                   QUARANTINED — your labels, plus my private design intent
  HOW-TO-FILL.md        instructions for the gold pass
evaluator/pairwise.md   the pairwise prompt (edit this — it's the thing you tune)
evaluator/pointwise.md  the pointwise prompt
runs/<model>/           evaluator outputs per model
ISOLATION.md            what each agent tier may and may not know
SCORING.md              the recall/precision framing and diagnostics
```

## Blind generation

Each of the 20 plans was written by an agent that received **only** the seed
sentence and its own methodology brief, wrote to an opaque token filename
(`febb35.md`, not `S1_A.md`), and had no repo access. It never learned that a
competing plan existed, what the alternative was, or which was preferred. Slots
are mixed 5/5 so the stronger methodology sits in A for half the items.

## Running it

```sh
python scripts/build_items.py                              # plans -> items
python scripts/run_eval.py --mode both --model claude-opus-5
python scripts/run_eval.py --mode both --model claude-haiku-4-5
```

Same items and same prompt text for every model — only `max_tokens` varies, and
it's recorded. Structured outputs force a common response shape so weaker models
aren't hand-tuned into parseability. If a model can't hold the format, that's a
result, not something to engineer around.

## Your part

1. Fill in `gold/S*.json` — see `gold/HOW-TO-FILL.md`. Judge blind; don't open
   `gold/design-intent.json` first.
2. Tweak `evaluator/pairwise.md` and `evaluator/pointwise.md`. They are the
   prompt, read directly by the runner.
3. Then the sweep, scored per `SCORING.md`.
