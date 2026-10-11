# rl/ — buy-side RL environments, MVP

The case study (`case_study/part1/`, `case_study/part2/`) converted into environment tasks: organized by
fund role, run inside fund worlds, graded by mode. Format spec: `FORMAT.md`.

```sh
python rl/build_from_case_study.py   # regenerate worlds/, roles/, catalog.json from the case study
python rl/replay_case_study.py       # grade the case-study model runs with the rl/ graders
```

## Running models, with or without financial-services skills

```sh
python rl/skills/manage.py fetch    # pinned checkout of anthropics/financial-services
python rl/skills/manage.py sync     # upload the profile's skills to your API workspace (once)
python rl/run.py --model claude-opus-5-5                  # skills on (default for claude-*)
python rl/run.py --model claude-opus-5-5 --skills off     # same tasks, no skills
```

Anthropic models get the `buy_side_core` profile from `skills/config.yaml` by
default: 18 of the repo's 63 skills (equity research, modeling, two PE skills). The
API caps a request at 20 skills, so profiles are curated; the config lists why
every other skill is out. Skills attach through the code-execution container and
apply to output generation only — the review scorer never gets them. Every run
record carries its skills condition (profile, repo commit, pinned skill versions),
and output files are named `<model>__skills-<profile>.jsonl` or `__skills-off`, so
the two conditions never mix.

The case-study baselines below are all skills-off.

## What is here

52 tasks in 6 worlds.

| Role | Workflow | Mode | Graded | Not yet graded |
|---|---|---|---|---|
| quant_researcher | research_design | review | 10 | 6 (context flips, no gold) |
| fundamental_analyst | research_design | review | 10 | 2 (context flips, no gold) |
| pm | research_funding | compare | 10 | 4 (context flips, no gold) |
| quant_researcher | research_design | produce | — | 5 (need a rubric) |
| fundamental_analyst | research_design | produce | — | 5 (need a rubric) |

**30 graded tasks.** Review tasks: a model reviews one research plan for a named
firm; gold is the human critique split into 45 blocking issues, plus secondary
issues, praise, and 4 objections the expert ruled out. Compare tasks: a PM picks
which of two plans to fund; gold is the human preference and its strength.

**22 tasks waiting on labels.** The 4 context-flip items reuse a pair under a
different firm and were never labelled. The 10 produce tasks (seed + firm → plan)
have one human-written must-hit item each (the flaw written before generation),
the human verdict on Claude's Part 1 plan, and Claude's Part 1 plan and critique
as reference outputs.

## Verified against the case study

`replay_case_study.py` re-grades all four models' saved runs with the new graders.
Prompt fingerprints match the runs, and every headline number in
`case_study/part2/GRADED.md` reproduces:

| | Haiku 4.5 | Sonnet 5 | Opus 4.8 | Opus 5 |
|---|---|---|---|---|
| Compare accuracy, strong items | 58% | 67% | 67% | 75% |
| Review recall (45 blocking) | 53% | 29% | 33% | 62% |
| Manufactured objections per review | 14.3 | 0.1 | 0.3 | 0.15 |
| **Review reward (new)** | **0.21** | **0.34** | **0.34** | **0.63** |

The review reward penalizes objections that do not apply, so Haiku's high recall
from 28.6 issues per review does not pay. Per-task records for every model are in
`runs/case_study/<model>.jsonl` and serve as baseline difficulty.

## Not copied, on purpose

| | Why |
|---|---|
| `case_study/part2/gold/design-intent.json` | The author's construction intent, not a gold label (`case_study/part2/ISOLATION.md`) |
| `case_study/part2/forks.json` | Generator-tier methodology briefs |
| `case_study/part1/scores/` | Scored by a model; gold must be human |

## Known limits

- One expert labelled everything. Grader–expert agreement can't be measured until a second and third expert grade the same tasks.
- Review penalty weights (0.1, 0.2) are v0: they reproduce the case-study model order but are uncalibrated.
- Worlds are firm briefs only, and most hold 1–3 source items. Too few to hold out whole worlds yet.
- The review grader's matching step calls a scorer model (Opus 5). Replay uses its cached decisions; grading a new run needs an API key.
- Every task is a single prompt and response. No tools, no files, no multi-step agent work yet.

## Next

The full plan, with who owns what and done criteria, is in
`../engineering_brief.md` section 6. In order:

1. Smoke test with skills on and off; invariants as CI tests.
2. Provenance on generated files and a review queue for expert sign-off.
3. Inspect exporter.
4. Gaming test for the review grader.
5. Labels from a 2nd and 3rd expert, with agreement numbers.
6. Earnings recap built from EDGAR: an agent with tools, in AI-drafted, expert-approved fund worlds.

Mayank meanwhile writes the earnings-recap judgment spec and fund world #1, and labels the 4 flip items.
