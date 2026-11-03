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
  checksums.sha256      sha256 of every other file in the task; `sha256sum -c checksums.sha256` verifies it
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

## Integrity

Every task can be checked on its own, without the repo:

| What | Where |
|---|---|
| Who made it, which version | `[task] authors`, `[task] version` (from `family.yaml`; bump the version when a family's tasks change in a way results can't be compared across) |
| When and from what it was built | `[metadata.build]`: UTC `built_at`, `repo_commit`, `repo_dirty` (uncommitted changes to tracked files), `builder`, Python and library versions, `source` and `source_sha256` (every file of `sources/<source>/`), `base_image` |
| That no file changed since | `checksums.sha256` |
| That it is the task the repo recorded | its `content_sha256` (every file but `task.toml` and `checksums.sha256`, plus the parsed `task.toml` without `[metadata.build]`) equals the one in `splits/manifests/<family>.json`. Identical across rebuilds of the same content |
| That the environment is reproducible | base image pinned by digest, every pip and apt package pinned; packages only the verifier needs (the LLM judge's client) are installed by `tests/test.sh`, not in the agent's image |
| That the agent can't look the answer up | Point in time, below |

`python rl/splits/check.py` checks all of this for every built task. Before handing tasks to
anyone, run `python rl/splits/check.py --release`: it also requires every task to come from one
commit with no uncommitted changes. Commit first, then rebuild, then check.

## Point in time

A task is valid only if the agent can't look the answer up, so every task's `task.toml` sets an
explicit network policy for each phase (Harbor's `network_mode`):

| Phase | Policy | Why |
|---|---|---|
| `[agent]` | `no-network` | the agent works from the files it is given |
| `[environment]` (between phases, agent setup) | `no-network` | a process the agent leaves running can't fetch anything after the agent phase ends |
| `[verifier]` | `allowlist` of `api.anthropic.com`, `pypi.org`, `files.pythonhosted.org` when the verifier calls a judge; `no-network` otherwise | the judge's API, and the index `test.sh` installs its client from |

Hosts an agent needs come from the run, never the task: its model API with
`harbor run --allow-agent-host api.anthropic.com`, and whatever its install fetches with
`--allow-environment-host` (Claude Code's installer uses `deb.debian.org` and `downloads.claude.ai`).
The oracle and the probe below need neither.

A **dated** task (a family with `dated: true` in `family.yaml`; today kpi_nowcast) records its
`as_of` and its image pins the clock to it: libfaketime starts `python` and `date` at noon UTC on
the as-of date, `$TASK_AS_OF` holds it, and the data files carry it as their mtime. Only those
commands are faked, so the agent's own process (node, a CLI) keeps the real clock its TLS needs;
`test.sh` drops the fake clock before the verifier runs. research_design and the generated panel
families have no as-of date: their data carries no "today" for a model to exploit.

`[metadata.environment]` records the policy (`internet = false`, `verifier_hosts`), and
`splits/check.py` fails when a task's policy is missing, isn't `no-network` for the agent, or
disagrees with that record, and when a dated task lacks `as_of` or its pinned clock.
`python rl/harness/sandbox_probe.py <task>...` runs tasks in Docker with an agent that only tries
to reach public hosts and read the clock; it fails if any request gets a response (`--judge` also
checks that a judged verifier still reaches its API). Harbor's Docker egress control answers DNS
from the container's resolver even with no network, so a name still resolves; nothing beyond it
connects.

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
| `as_of` | The date the task is set on (dated families): nothing after it is in the data, and the container's clock reads it |
| `environment` | `internet` (always false) and `verifier_hosts`, the network policy `task.toml` enforces (Point in time, above). kpi_nowcast adds the API runner's `tools` |
| `seed`, `control` | Generator seed and whether nothing was planted (generated families; held-out tasks record no seed) |
| `fingerprint` or `prompt.fingerprint` | Hash of exactly what the model sees. Two runs are comparable only if fingerprints match |
| `prompt.template` | The template the prompt was rendered from |
| `output_schema`, `grader`, `sources`, `meta` | Response schema, grader type and parameters, where every piece came from, grader-side facts about the task |
| `build` | the build record (Integrity, above) |

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
