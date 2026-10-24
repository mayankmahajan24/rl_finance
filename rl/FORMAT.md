# Task format

Every task in the repo is a folder in [Harbor](https://github.com/laude-institute/harbor)'s layout
at `tasks/<split>/<task_id>/`, written by one shared writer (`families/_shared/harbor.py`). Built
tasks are gitignored and rebuilt by their family's builder; what was built is recorded, with
hashes, in `splits/manifests/<family>.json`.

```
<task_id>/
  instruction.md        what a Harbor agent is given
  task.toml             Harbor config; [metadata] is the repo's task metadata (below). Never shown to the model
  environment/          MODEL-VISIBLE: Dockerfile + data/ (mounted at /app/data; .gz files unpacked in the image)
  prompt/               MODEL-VISIBLE: the exact messages the repo's API runners send (system.md,
                        user.md or user.AB.md + user.BA.md, inputs.json). Families with an API runner only
  tests/                GRADER-ONLY: test.sh, the verifier and graders, gold (gold.json or ground_truth.json),
                        reference outputs. Harbor copies it in only after the agent finishes
  solution/             reference solution for Harbor's oracle agent, where one exists
```

Two halves must never mix: what the model sees (`instruction.md`, `environment/`, `prompt/`) and
what only the grader sees (`tests/`). Every builder runs a leak check before it finishes, and
`splits/check.py` fails if a grader-only file sits where the agent can see it.

**Two ways to run a task.** Harbor runs the agent in the container from `instruction.md`; the
verifier writes `reward.txt`, or `reward.json` when a family reports several named metrics
(kpi_nowcast) or has no grader yet (empty). The repo's API runners (`families/<family>/run.py`)
send `prompt/` through the Messages API and grade with the same graders. For research_design and
kpi_nowcast, `instruction.md` is the system and user message plus a note on where the files are
and where to write the answer; the fingerprint covers the API messages, so a Harbor run and an API
run of the same task are comparable only up to that note.

## [metadata]

| Field | Meaning |
|---|---|
| `id` | Stable id; says nothing about the answer. Panel families' held-out ids are numbered, never seeded |
| `family` | The family that built it (`families/<family>/`) |
| `source` | The source it was built from (`sources/<source>/`) |
| `role` | Who does this work at a fund: `fundamental_analyst`, `quant_researcher`, `pm`, `risk` |
| `workflow` | The job within the role, e.g. `research_design`, `kpi_nowcast`, `data_audit` |
| `mode` | `produce` (do the work), `review` (find what is wrong with given work), `compare` (choose between two pieces of work), `revise` (fix work given a critique) |
| `world` | The fund this task runs inside; see `worlds/<id>/world.yaml` |
| `status` | `graded` (gold exists, grader runs), `ungraded` (gold missing), `needs_rubric` (no grader yet) |
| `split` | `train`, `bench`, `heldout`; `eval` for a source with no split assignment; `retired` for a retired case (`splits/README.md`). Always the folder the task is in |
| `companies` | Companies whose data the task contains (sources with a company split) |
| `seed`, `control` | Generator seed and whether nothing was planted (generated families; held-out tasks record no seed) |
| `fingerprint` or `prompt.fingerprint` | Hash of exactly what the model sees. Two runs are comparable only if fingerprints match |
| `prompt.template` | The template the prompt was rendered from |
| `output_schema`, `grader`, `sources`, `meta` | Response schema, grader type and parameters, where every piece came from, grader-side facts about the task |

TOML has no null: a field with no value is absent.

## Graders

| Family | Mode | Grader | Reward |
|---|---|---|---|
| research_design | review | `graders/review_issues.py` | blocking-issue recall − 0.1 × manufactured − 0.2 × contradicts-gold, clamped to [0, 1] |
| research_design | compare | `graders/pairwise_pick.py` | 1 if the pick matches gold, averaged over both orderings (a Harbor run sees AB only) |
| research_design | produce | none yet | an expert rubric is needed |
| kpi_nowcast | produce | `grader.py` + `judge.md` | named metrics: forecast accuracy (code) and C1–C12 write-up rubric (LLM judge) |
| data_audit, anomaly_scoring, growth_thesis | review / produce | `verifier/*.py` | see each `family.yaml` |

## Worlds

A world is a simulated fund. Today each world is only a firm brief
(`status: brief_only`). A full world adds mandate, holdings, theses, past memos and
a point-in-time data snapshot, and many tasks across roles run inside it. The list
of what is missing is in each `world.yaml`. research_design tasks stay one `eval` set until there
are enough worlds to hold out whole worlds, never single tasks: tasks in one world share context
and leak into each other.
