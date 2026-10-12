# rl_finance

RL environments and evals for buy-side financial services, built for frontier labs.

| Folder | What it is |
|---|---|
| [`rl/`](rl/) | The environments: tasks by role and workflow, fund worlds, graders by mode, a model runner with Anthropic's financial-services skills. Start at [`rl/README.md`](rl/README.md). |
| [`engineering_brief.md`](engineering_brief.md) | Start here if you are an engineer joining: goal, vocabulary, what exists, invariants, next work. |
| [`finrl_eval/`](finrl_eval/) | Suite registry, rubric scorers, and the mock, Anthropic, and OpenAI providers. `finrl-eval run` scores a live suite. FORMAT copies under `rl/roles/` stay `needs_rubric`. |
| [`case_study/`](case_study/) | The Finance Domain Research Lead take-home the first environment is built from: report, Parts 0–3, scripts, every raw model call. `rl/build_from_case_study.py` reads it. |

## Task suites

Earnings recaps and fixed income are live suites. Quantitative signal research and dataset valuation are planned names only.

```bash
uv sync
uv run finrl-eval list
uv run finrl-eval runnable
uv run finrl-eval run --suite earnings --provider mock
uv run finrl-eval run --suite fixed_income --provider mock
make format-tasks
```

`finrl-eval run` scores the live suite and writes `summary.json`, `rewards.jsonl`, and `failure_modes.md` under `runs/`. It does not call `rl/run.py`.

`make format-tasks` writes one FORMAT folder per sample under `rl/roles/`. Those tasks stay `needs_rubric`. They carry synthetic gold (`provenance.kind: synthetic_pipeline`) and do not name a grader module. The 10 `rd-produce-*` tasks stay `needs_rubric`. `rl/build_from_case_study.py` rebuilds only `research_design` and `research_funding`.

`make eval` loops `finrl-eval runnable` and runs each suite with the mock provider.

The case study's summary deck is not here; it stays published from the
`finance_collaborator` repo.
