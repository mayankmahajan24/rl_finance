# rl_finance

RL environments and evals for buy-side financial services, built for frontier labs.

| Folder | What it is |
|---|---|
| [`rl/`](rl/) | The environments: tasks by role and workflow, fund worlds, graders by mode, a model runner with Anthropic's financial-services skills. Start at [`rl/README.md`](rl/README.md). |
| [`engineering_brief.md`](engineering_brief.md) | Start here if you are an engineer joining: goal, vocabulary, what exists, invariants, next work. |

The first environment (research design) was built from the Finance Domain Research
Lead take-home. The data it needs is in `rl/data/research_design/`; the full take-home
(report, Parts 0–3, scripts, every raw model call) is in git history at commit
`a75441c`, under `case_study/`. Its summary deck stays published from the
`finance_collaborator` repo.
