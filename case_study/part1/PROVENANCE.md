# How the Part 1 outputs were generated

Outputs live in a single flat layout — `part1/plans/<id>.md` and
`part1/critiques/<id>.md`. Two harnesses produced them, because the API credit
balance ran out six seeds into the run. Both received the **same seed sentence
and the same instructions** and produced comparable output, so they are treated
as one set. Each file's own header line records which harness wrote it, and
`raw.json` carries a `source` field, so the split stays auditable without
fragmenting the directory tree.

| Harness | Seeds | Mechanism |
|---|---|---|
| `api` | S1, S3, S4, S5, S6, S8 | `scripts/generate.py` — bare `claude-opus-5` API contexts, neutral system prompt, no tools |
| `subagent` | S2, S7, S9, S10 | Claude Code subagents, same prompt text, tool access present but restricted by instruction |

### Measured harness effect: none detectable

| harness | n | recall caught | plan avoided flaw | manufactured (mean, range) |
|---|---|---|---|---|
| api | 6 | 6/6 | 4/6 | 2.7 (1–4) |
| subagent | 4 | 3/4 | 3/4 | 2.5 (2–4) |

Indistinguishable on every axis, and the small differences run the reassuring
way: the only sub-ceiling recall result in the run (S2, `partial`) is a subagent
seed, so the subagent path is not inflating the subtly-flawed tier it dominates.
Plan lengths overlap too — 13.4k–17.9k chars via API, 14.7k–17.6k via subagent.
No headline claim in `FINDINGS.md` depends on the split; recall-near-ceiling and
precision-as-the-weak-axis both hold within each harness separately.

## Isolation

The point of both harnesses is that the generating model **never saw the answer**.

- The **plan** call received only the seed sentence and a generic "turn this into
  an executable research plan" instruction.
- The **critique** call received only the seed sentence and the plan.
- Neither received the bucket label, the gold flaw, `ideas.md`, `seeds.json`, or
  any sibling seed. Subagents were explicitly instructed not to read those files.

This matters because the flaws in these seeds were enumerated in conversation
before generation. A plan written by a model that has already been told where the
flaw is is not a sample of what Claude produces cold, and measuring it tells you
nothing.

## Remaining limitations

**Mixed harness.** The four subagent seeds are three of the four subtly-flawed
items (S2, S9, S10) plus one obviously-flawed (S7). Subagents carry a Claude Code
system prompt and have tool access, so they are not a strictly identical
condition to the bare API calls — the API path is the more faithful measurement
of how Claude serves an investment researcher. The table above shows no
detectable effect, but if you want a single-harness run, re-generate those four
once API credits allow: `python scripts/generate.py --seeds S2 S7 S9 S10`.

**n = 1 per seed.** Every plan and critique here is a single sample, so
run-to-run variance is unmeasured; a seed scored `caught` might score `partial`
on a re-roll. This is a larger limitation than the harness split, and the cheaper
place to spend generation budget if more rigor is wanted.

## Scoring

`part1/scores/<id>.json` — one independent subagent per seed, each given only
that seed's plan, its critique, and the gold flaw. No scorer saw another seed or
another scorer's verdict, so the reads do not anchor on each other.
