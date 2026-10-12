# rl_finance

RL environments and evals for buy-side financial services, built for frontier labs.

The repo has two layers that share one catalog and one scoring path:

| Folder | What it is |
|---|---|
| [`rl/`](rl/) | FORMAT task tree: 100 tasks by role and workflow, fund worlds, graders by mode, Anthropic runner with financial-services skills. Start at [`rl/README.md`](rl/README.md). |
| [`finrl_eval/`](finrl_eval/) | Multi-provider package for mock, Anthropic, and OpenAI, plus rubric scorers and the `finrl-eval` CLI. Earnings and fixed-income suites live here. FORMAT copies of those suites are generated under `rl/roles/`. |
| [`engineering_brief.md`](engineering_brief.md) | Start here if you are an engineer joining: goal, vocabulary, what exists, invariants, next work. |
| [`case_study/`](case_study/) | The Finance Domain Research Lead take-home the first environment is built from. `rl/build_from_case_study.py` reads it. Do not duplicate its graders or gold. |

The case study's summary deck is not here; it stays published from the
`finance_collaborator` repo.

## What was already here

52 FORMAT tasks in 6 worlds (`research_design`, `research_funding`), human gold,
`review_issues` / `pairwise_pick` graders, `rl/replay_case_study.py`, the Anthropic
runner (`rl/run.py`), and the skills manager. That tree is kept. The case-study
rebuild no longer wipes other workflows under `rl/roles/`.

## What `finrl_eval` adds

- Providers: deterministic `mock` (oracle / noisy / broken), Anthropic, OpenAI.
- Rubric produce grader in `rl/graders/rubric.py`, called by `rl/run.py` for graded
  produce tasks. It calls the suite rubric. Scores are not re-derived.
- FORMAT mirrors: one produce task per sample of each live suite
  (`earnings_recap`, `fixed_income`), gold marked `provenance.kind: synthetic_pipeline`.
- Packaging (`pyproject.toml` / `uv.lock`), Dockerfile / compose, GitHub Actions CI.
- CLI: `finrl-eval list | runnable | run | report`.

Quant Signal Research and Dataset Valuation remain extension-point stubs.

## Quick start

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python rl/replay_case_study.py          # offline case-study regression
uv run finrl-eval list                         # suites, FORMAT mirrors, providers
uv run finrl-eval runnable                     # live suite names, one per line
uv run finrl-eval run --suite earnings --provider mock
uv run finrl-eval run --suite fixed_income --provider mock
uv run finrl-eval report runs/<run_id>
make check                                     # ruff, mypy, pytest, replay
```

Rebuild FORMAT mirrors after changing a suite (does not touch case-study tasks):

```bash
uv run python scripts/build_instrumentation_suites.py
```

Against a real model (keys from the environment, never from files):

```bash
export ANTHROPIC_API_KEY=...   # or OPENAI_API_KEY
uv run finrl-eval run --suite fixed_income --provider anthropic
python rl/run.py --model claude-opus-5-5 --dry-run
```

### Mock provider modes

| `--model` | Behaviour |
|---|---|
| `mock-noisy` (default) | ~58% correct; the rest split across numeric slips, GAAP/non-GAAP swaps, unit errors, dropped fields and prose-only answers. |
| `mock-oracle` | Always the ground truth. Tests assert every rubric awards 1.0. |
| `mock-broken` | Always an unparseable prose answer. Tests assert the rubric floor. |

## Run outputs (`finrl-eval run`)

Each run writes `runs/<timestamp>-<suite>-<provider>/` with `config.json`,
`rubric.json`, `samples.jsonl`, `summary.json`, `report.md`, `failure_modes.md`,
and `rewards.jsonl`, one reward record per sample. Live Anthropic sweeps from
`rl/run.py` still write `rl/runs/<tag>/`.

## Docker

```bash
make docker-build
make docker-eval          # both suites, mock provider; results in ./runs
make docker-pipeline      # tests + both suites in one container
```

CI lints, type-checks, runs pytest + replay, builds the image, re-runs tests
inside it, and runs both mock-provider suites.

## Invariants

- Never edit human gold. Instrumentation gold is synthetic and labelled as such.
- `rl/build_from_case_study.py` owns `research_design` and `research_funding` only.
- Graders for review/compare stay `rl/graders/review_issues.py` and
  `pairwise_pick.py`. Do not re-derive those metrics.
- Produce scoring for instrumentation reuses `finrl_eval` suite rubrics.
- Two runs are comparable only if prompt fingerprints match.
