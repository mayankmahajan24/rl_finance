# Finance Domain Research Lead — take-home

Can Claude turn a half-formed investment research idea into an executable plan,
and can it tell a good plan from a bad one? Part 1 measures the first. Part 2
builds an eval for the second and runs four models against human gold. Part 3
proposes how to collect that gold at scale.

**→ `REPORT.md` is the deliverable.** Everything below is the working repo.

## Read these first

| | |
|---|---|
| **`REPORT.md`** | The report. Body + 12 numbered tables in Appendix A; Part 0 in Appendix B. |
| **`part1/FINDINGS.md`** | Part 1 qualitative read: Claude over-applies generic research methodology and under-applies finance domain knowledge. |
| **`part2/GRADED.md`** | Part 2 scored against human gold — pairwise accuracy, recall/precision, and two defects the gold pass found in my own instrument. |
| **`part2/evaluator/TENETS.md`** | The 13 judging tenets, grouped by when in a review they apply, with precedence rules for conflicts. |
| **`part2/SCORING.md`** | Metric design. Read with `GRADED.md` — the results revised two of its four proposed axes. |
| **`part3/README.md`** | Collection-at-scale proposal, argued from the Part 2 measurements. |
| **`REPORT-NOTES.md`** | Working notes 1–7, including decisions that were reversed and why. |

## Headline results

| | Haiku 4.5 | Sonnet 5 | Opus 4.8 | Opus 5 |
|---|---|---|---|---|
| Pairwise accuracy, strong-preference items (baseline 50%) | 58% | 67% | 67% | **75%** |
| Pointwise recall (of 45 blocking gold issues) | 53% | 29% | 33% | **62%** |
| **Manufactured objections per review** | **14.3** | **0.1** | **0.3** | **0.2** |

Recall is *not* monotone in capability — Haiku beats both mid-tier models by
firing 28.6 issues per review. F1 does not rank the bottom three. The metric that
separates cleanly is manufactured-objections-per-review, and the recommended
reporting pair is **recall + manufactured-per-review, not F1**. See `GRADED.md`.

## Layout

```
ideas.md                seed catalog — 14 candidates, the working 10, why each was kept or cut
seeds.json              the 10 seeds as data (`text` is the only field a model ever sees)
REPORT.md               the deliverable
REPORT-NOTES.md         working notes 1-7, with the numbers behind each finding

part0/                  my own two ideas, written before touching Claude
part1/                  plans, critiques, per-seed scores, findings table, qualitative read
part2/
  forks.json            the two methodologies per seed
  contexts.json         firm context per item, and the four context-flip items
  plans/raw/            the 20 generated plans (opaque token filenames)
  plans/short/          the same plans edited to 500-600w — what items use
  plans/_manifest.json  token -> (seed, slot) map, written before generation
  items/S1..S10,*F      assembled eval items: context, seed, plan_A, plan_B
  gold/S*.json          human labels — 10 base items filled, 4 flip items empty
  gold/_issues.json     gold prose classified into blocking / secondary / anti-objection / praise
  gold/design-intent.json   QUARANTINED — my private construction intent, never an input
  evaluator/            TENETS.md and the two prompts (pairwise, pointwise)
  runs/<model>/         every raw call, both modes, with prompt + schema fingerprints
  runs/_issue_scores.json   every issue-bucketing decision with the scorer's reasoning
  GRADED.md             results against gold
  SCORING.md            metric design and known limitations
  ISOLATION.md          what each agent tier may and may not know
part3/README.md         collection-at-scale proposal
scripts/                generation, assembly, eval runner, scoring, diagnostics
```

## Running it

Run from `case_study/`. The summary deck is published from the `finance_collaborator`
repo, not this one.

```sh
cd case_study
export ANTHROPIC_API_KEY=...

# Part 1 — seed -> plan -> critique, fresh context per call
python scripts/generate.py
python scripts/collect.py               # -> part1/raw.json
python scripts/summarize.py             # -> part1/scorecard.md
python scripts/render_part1.py          # -> part1/findings-table.md

# Part 2 — assemble items, then sweep models
python scripts/build_items.py
python scripts/run_eval.py --mode both --model claude-opus-5
python scripts/retry_eval.py --model claude-opus-5 --mode both --failed   # merges, never overwrites

# Part 2 — score
python scripts/split_gold.py            # gold prose -> classified issues (--review to sign off)
python scripts/score.py                 # deterministic: accuracy vs gold, with baselines
python scripts/score_issues.py          # semantic: recall / precision   (--report to re-print free)

# Diagnostics that need no gold
python scripts/compare_runs.py          # consistency, position bias, verbosity
python scripts/flip_test.py             # context sensitivity on the flip items
```

Same items and same prompt text for every model. Prompt and schema
**fingerprints** (`sha256[:12]`) are stored per run and re-checked on merge, so a
changed instrument refuses to mix with old results rather than silently
corrupting a comparison. Structured outputs force a common response shape, so
weaker models are not hand-tuned into parseability.

## Extending it

Add seeds to `seeds.json` → generate plans with `scripts/generate.py` (blind
tokens) → `build_items.py` → `run_eval.py --model X` → `score.py` /
`score_issues.py`.

Two things to know before changing the instrument. Editing a prompt or schema
changes its fingerprint, which invalidates cross-run comparability and requires
re-running every model. And `score.py` scores only items whose gold is filled,
naming the excluded ones in its output — partial gold shrinks the denominator
loudly rather than quietly.

## The methodological commitment

Every plan and critique here was produced by a model that saw **only the seed
sentence** and, in Part 2, its own assigned methodology — never the known flaw,
the bucket label, a sibling seed, the paired plan, or any repo file. Part 2 plans
were generated against opaque `sha256` tokens so a generator could not know a
paired plan existed. `part2/ISOLATION.md` sets out the three agent tiers and what
each may know.

## Status and known gaps

Parts 0–3 and the report are complete. Four models swept, 28 pairwise + 28
pointwise calls each, zero errors. Stated plainly because they bound every number
above:

- **The four context-flip items have no gold.** The one axis that holds the plan
  fixed and varies the firm is measured gold-free only (`flip_test.py`).
- **Opus 5 scored its own reviews** in `score_issues.py` and posts the best recall
  *and* precision under its own judge. Treat its margin as an upper bound.
- **Opus 5 is the only evaluated model with thinking on by default** — the runner
  passes no `thinking` parameter, so each model runs as shipped (`ISOLATION.md`).
- **All gold is one reviewer**, so "wrong" and "disagrees with this desk" are not
  separable anywhere in this repo.
- **`goal_type` and `error_asymmetry` accuracy are not reportable** as model
  capability — the gold pass found both fields defective in my instrument
  (`GRADED.md`).
