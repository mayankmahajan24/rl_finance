# rl_finance

RL environments and evals for buy-side financial services, built for frontier labs.

| Folder | What it is |
|---|---|
| [`rl/`](rl/) | The environments: tasks by role and workflow, fund worlds, graders by mode, a model runner with Anthropic's financial-services skills. Start at [`rl/README.md`](rl/README.md). |
| [`engineering_brief.md`](engineering_brief.md) | Start here if you are an engineer joining: goal, vocabulary, what exists, invariants, next work. |
| [`finrl_eval/`](finrl_eval/) | Suite registry, earnings fixtures, and the fixed-income feed. `finrl-eval list` and `finrl-eval runnable` read it. Scoring is not in this change. |
| [`case_study/`](case_study/) | The Finance Domain Research Lead take-home the first environment is built from: report, Parts 0–3, scripts, every raw model call. `rl/build_from_case_study.py` reads it. |

## Task suites

Earnings recaps and fixed income are live suites. Quantitative signal research and dataset valuation are planned names only.

```bash
uv sync
uv run finrl-eval list
uv run finrl-eval runnable
uv run python scripts/generate_earnings_fixtures.py
make format-tasks
```

`make format-tasks` writes one FORMAT folder per sample under `rl/roles/`. Those tasks are `needs_rubric`. They carry synthetic gold (`provenance.kind: synthetic_pipeline`) and do not name a grader module. The 10 `rd-produce-*` tasks stay `needs_rubric`. `rl/build_from_case_study.py` rebuilds only `research_design` and `research_funding`.

The case study's summary deck is not here; it stays published from the
`finance_collaborator` repo.
