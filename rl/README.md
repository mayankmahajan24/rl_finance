# rl/ — buy-side RL environments, MVP

Tasks are built from **sources** (a dataset plus the assignment it came with) by **families** (one
kind of task each), and assigned to **splits** (train, bench, heldout) by company. Every task is a
folder in Harbor's layout; [`FORMAT.md`](FORMAT.md) is the spec. This file owns the commands.

| Folder | What it holds |
|---|---|
| [`sources/`](sources/) | `txn_panel` (transaction panel + description of its known data issues) and `research_design_case` (the research-design case study) |
| [`families/`](families/) | one folder per kind of task: builder or generator, instruction, verifier and graders, baseline solutions |
| [`splits/`](splits/) | company and seed assignment per split, retired cases, `manifests/<family>.json` (the committed index of every task), `check.py` |
| `tasks/` | every built task at `tasks/<split>/<task_id>/`. Gitignored; `build.py` rebuilds it |
| [`harness/`](harness/) | `run_api.py` (any model on any family through the API, graded by the task's verifier), `run_solutions.py` (reference vs naive, no Docker), `local.py` (the local grader both use), `oracle_check.py` (Harbor's oracle in Docker vs the local reference), `calibrate.py` (Harbor calibration jobs: pass@k, noise floor, keep/drop per task), `sandbox_probe.py` (an agent that tries to get out of the sandbox; Docker), `records.py` and `report.py` (one run-record schema; leaderboards that never mix instruments), `approve.py` (instrument approval), `ablation.py`, `attacks.py`, `canary_probe.py`, `memorisation.py`, `judge_stability.py` |
| [`review/`](review/) | the gold review queue (`review.py`) and the release sign-off steps ([`SIGNOFF.md`](review/SIGNOFF.md)) |
| `skills/`, [`runs/`](runs/) | financial-services skills for API runs, run records |

| Family | Tasks | Splits |
|---|---|---|
| research_design | 30 (20 review, 10 compare) | eval |
| kpi_nowcast | 102 | 54 train, 24 bench, 22 heldout, 2 retired |
| data_audit, anomaly_scoring, growth_thesis | generated: 12 bench and 12 heldout each; train on demand | train, bench, heldout |

## Commands

```sh
python rl/build.py                                     # build every family (bench and heldout), then the split check
python rl/build.py panel --split train --n 3 --controls 1   # the train size the committed manifests record
python rl/build.py data_audit --split train --n 200 --controls 20
python rl/splits/check.py                              # splits, checksums, manifests, leaks, provenance
python rl/splits/check.py --release                    # also: one clean commit, approved instruments and gold
python rl/harness/approve.py                           # which families' instruments are approved; --family X --show for the diff
python rl/review/review.py review --reviewer "<name>" --batch 10   # review gold provenance, highest value first
python rl/families/research_design/replay.py           # case-study baselines must reproduce
python rl/harness/run_solutions.py --split bench       # reference should beat naive in every family
python rl/harness/run_solutions.py --split eval --family research_design
python rl/harness/ablation.py --split bench            # every planted item, and every reference step, must earn reward
python rl/harness/attacks.py --split bench             # every reward-hacking attack must score well below good answers
python rl/harness/run_api.py --split bench --model claude-opus-5-5 --dry-run            # print one request, no API call
python rl/harness/run_api.py --split bench --model claude-opus-5-5 --budget 20 --k 3    # live; needs approved instruments
python rl/harness/report.py --split bench              # leaderboard over the run records
python rl/harness/calibrate.py run --split bench --model <m1> --model <m2> --k 5   # Harbor; resumes; needs approved instruments
JUDGE=keyword python rl/harness/oracle_check.py         # oracle in Docker on a bench sample = local reference rewards
python rl/harness/sandbox_probe.py --with-judge rl/tasks/bench/kn-produce-AIR02-2017Q4-anon   # no internet for the agent; clock at as_of
```

Every human sign-off, in order, from merged code to a releasable sample: [`review/SIGNOFF.md`](review/SIGNOFF.md).

**Skills.** `run_api.py --skills default` gives Anthropic models the `buy_side_core` profile from
`skills/config.yaml` (18 of the financial-services repo's 63 skills; the API caps a request at 20,
and the config says why every other skill is out). Runs are skills-off unless they ask. Skills
attach through the code-execution container and apply to the model under test only, never the
judge. Every run record carries its skills condition, so the two conditions never mix in a report.

```sh
python rl/skills/manage.py fetch    # pinned checkout of anthropics/financial-services
python rl/skills/manage.py sync     # upload the profile's skills to your API workspace (once)
python rl/harness/run_api.py --split eval --family research_design --model claude-opus-5-5 --skills default --budget 5
```

**Running Claude Code through Harbor on a Claude subscription** instead of API credit: run
`./setup_oauth.sh` once (it runs `claude setup-token` and saves the token to `.oauth.env`, which is
git-ignored), then

```sh
set -a; . ./.oauth.env; set +a; export CLAUDE_FORCE_OAUTH=1
harbor run -p rl/tasks/bench -a claude-code -m claude-opus-5-5 --ak max_budget_usd=5 --ak disable_web_search=true \
  --allow-agent-host api.anthropic.com \
  --allow-environment-host deb.debian.org --allow-environment-host downloads.claude.ai
harbor check rl/tasks/bench -a claude-code -m claude-sonnet-5-5   # Harbor's task-quality rubric
```

Harbor's network control doesn't work on Docker Desktop, so on a Mac it refuses these tasks. Run on
Linux instead, or use the manual **Live run** workflow (`.github/workflows/live-run.yml`), which needs
the `CLAUDE_CODE_OAUTH_TOKEN` repo secret.

Tasks give the agent no network ([`FORMAT.md`](FORMAT.md), Point in time): the run adds the model
API for the agent phase and the installer's hosts for setup. Those host lists are not yet validated
against a live Claude Code run. `CLAUDE_FORCE_OAUTH=1` makes Harbor drop `ANTHROPIC_API_KEY` for the
agent. The subscription covers the Claude Code agent only: judged verifiers (growth_thesis memo,
research_design review scorer, kpi_nowcast write-up) and `run_api.py` still use `ANTHROPIC_API_KEY`.

**Tests** (`rl/tests/`; `.github/workflows/ci.yml` runs them on every PR after a ~7 min rebuild that
must reproduce the committed manifests). `pip install -r requirements-dev.txt`, build the tasks as
CI does, then

```sh
pytest                                   # everything (~10 min; needs built bench and eval tasks)
pytest -m "not slow"                     # skip the end-to-end solver runs (~47 s)
UPDATE_EXPECTED=1 pytest rl/tests/test_verifiers.py -m slow   # re-record rewards after an intended change
```

Tests that need a built task skip when it is missing, and fail instead when `CI` is set.

Dependencies: `pip install -e ".[dev]"` from the repo root installs the pinned versions
(`../requirements.txt`, `../requirements-dev.txt`) and puts `rl-build`, `rl-check` and `rl-export` on
PATH, the same as `python rl/build.py`, `python rl/splits/check.py` and `python rl/export.py` from any
directory.

The **oracle workflow** (`.github/workflows/oracle.yml`, nightly and on demand) runs Harbor's oracle
on a bench sample of the generated families in Docker, and fails if a reward differs from the local
reference reward pinned in `tests/expected_rewards.json`.

## research_design

Built from the research-design case study ([`sources/research_design_case/`](sources/research_design_case/),
which also lists what was left out and why). Review tasks: a model reviews one research plan for a
named firm; gold is the human critique split into 45 blocking issues, plus secondary issues, praise
and 4 objections the expert ruled out. Compare tasks: a PM picks which of two plans to fund, shown
in both orders; gold is the human preference and its strength.

`families/research_design/replay.py` re-grades all four models' saved case-study runs with the
task verifiers' graders, without API calls. Prompt fingerprints match the runs, and every headline
number in `sources/research_design_case/baseline_runs/GRADED.md` reproduces:

| | Haiku 4.5 | Sonnet 5 | Opus 4.8 | Opus 5 |
|---|---|---|---|---|
| Compare accuracy, strong items | 58% | 67% | 67% | 75% |
| Review recall (45 blocking) | 53% | 29% | 33% | 62% |
| Manufactured objections per review | 14.3 | 0.1 | 0.3 | 0.15 |
| **Review reward** | **0.21** | **0.34** | **0.34** | **0.63** |

The review reward penalizes objections that do not apply, so Haiku's high recall from 28.6 issues
per review does not pay. Per-task records for every model are in
`runs/research_design/baseline/<model>.records.jsonl` and serve as baseline difficulty.

## Known limits

- One expert labelled everything. Grader–expert agreement can't be measured until a second and third expert grade the same tasks.
- Review penalty weights (0.1, 0.2) are v0: they reproduce the case-study model order but are uncalibrated.
- Each firm brief holds 1–3 case-study items: too few to hold out whole firms, so research_design is one eval set.
- The review grader's matching step calls a scorer model (Opus 5). Replay uses its cached decisions; grading a new run needs an API key.
- research_design's produce tasks and the 4 unlabelled context-flip items are not built until an expert rubric and labels exist.
