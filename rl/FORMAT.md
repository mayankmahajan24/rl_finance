# Task format

Every task is a folder at `roles/<role>/<workflow>/<task_id>/`. The folder has two
halves that must never mix: what the model sees, and what only the grader sees.

```
<task_id>/
  task.yaml          harness-only metadata — never shown to the model
  prompt/            MODEL-VISIBLE
    system.md        rendered system message
    user.md          rendered user message (compare tasks: user.AB.md, user.BA.md)
    inputs.json      the raw fields the user message was rendered from
  grader/            GRADER-ONLY
    gold.json        human labels (graded tasks)
    draft_rubric.json  rubric in progress (needs_rubric tasks)
    reference/       reference outputs with their human verdicts
```

`build_from_case_study.py` refuses to write the tree if any gold text appears
anywhere under `prompt/` (the leak check).

## task.yaml

| Field | Meaning |
|---|---|
| `id` | Stable id: `<workflow-abbrev>-<mode>-<source id>[-<slot>]`. Says nothing about the answer. |
| `role` | Who does this work at a fund: `fundamental_analyst`, `quant_researcher`, `pm`, `risk` |
| `workflow` | The job within the role, e.g. `research_design`, `research_funding`, `earnings_recap` |
| `mode` | `produce` (do the work), `review` (find what is wrong with given work), `compare` (choose between two pieces of work), `revise` (fix work given a critique) |
| `world` | The fund this task runs inside; see `worlds/<id>/world.yaml` |
| `status` | `graded` (gold exists, grader runs), `ungraded` (gold missing), `needs_rubric` (no grader yet) |
| `split` | `eval` for now. When there are enough worlds, hold out whole worlds, never single tasks: tasks in one world share context and leak into each other. |
| `prompt.template` / `prompt.fingerprint` | The template the prompt was rendered from and a hash of its exact text. Two runs are comparable only if fingerprints match. |
| `output_schema` | JSON schema the response must satisfy |
| `grader` | Grader type, module and per-task parameters |
| `sources` | Where every piece of the task came from |
| `meta` | Grader-side facts about the task (seed, slot, style, flip). Never shown to the model. |

## Graders are organized by mode, tasks by role

The same grader serves every topic in a mode:

| Mode | Grader | Reward |
|---|---|---|
| review | `graders/review_issues.py` | blocking-issue recall − 0.1 × manufactured − 0.2 × contradicts-gold, clamped to [0, 1] |
| compare | `graders/pairwise_pick.py` | 1 if the pick matches gold, averaged over both orderings |
| produce | rubric grader (not built yet) | weighted pass/fail rubric items + code-checked facts |

## Worlds

A world is a simulated fund. Today each world is only a firm brief
(`status: brief_only`). A full world adds mandate, holdings, theses, past memos and
a point-in-time data snapshot, and many tasks across roles run inside it. The list
of what is missing is in each `world.yaml`.
