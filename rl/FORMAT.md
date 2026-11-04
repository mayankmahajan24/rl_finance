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
                        reference outputs, provenance.json (who produced each gold input, and its
                        review state). Harbor copies it in only after the agent finishes
  solution/             reference solution for Harbor's oracle agent, where one exists
  checksums.sha256      sha256 of every other file in the task; `sha256sum -c checksums.sha256` verifies it
```

Two halves must never mix: what the model sees (`instruction.md`, `environment/`, `prompt/`) and
what only the grader sees (`tests/`). One shared check (`leakcheck.py`) runs at the end of every
build and in `splits/check.py`. It fails a task when anything the agent sees contains its declared
gold fields (`leak_check` in `family.yaml`), identifying text (repo, source or upstream names, URLs,
SEC accession numbers, task ids, benchmark framing; `identity_allowlist` in `source.yaml` allows a
phrase, with the reason), a real company name, ticker or series id in an anonymised task, or the
release canary. `splits/check.py` also fails if a grader-only file sits where the agent can see it.

**Contamination.** Every task's grader-only `tests/CANARY` holds the release's canary
(`canary.txt`, replaced with each release), and the export's datasheet prints it.
`python rl/harness/canary_probe.py --model <m>` asks a model to complete it.
`python rl/harness/memorisation.py <results.jsonl>` compares a model's scores on the named and
anonymised variants of the same kpi_nowcast case: a named-variant advantage suggests memory of the
real company.

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
| That the instrument is the approved one | `family.yaml` lists the family's `instrument` files (prompts, schemas, graders, judge rubric, verifier, builder or generator, the shared writer); `families/<family>/approval.yaml` records the approved hash over them, who approved it, when and at which commit (`instrument.py`). Live API runs refuse to start and `check.py --release` fails while the current hash isn't the approved one. `python rl/harness/approve.py --family <f> --show` prints the diff since approval |
| When and from what it was built | `[metadata.build]`: UTC `built_at`, `repo_commit`, `repo_dirty` (uncommitted changes to tracked files), `builder`, Python and library versions, `source` and `source_sha256` (every file of `sources/<source>/`), `base_image` |
| That no file changed since | `checksums.sha256` |
| That it is the task the repo recorded | its `content_sha256` (every file but `task.toml` and `checksums.sha256`, plus the parsed `task.toml` without `[metadata.build]`) equals the one in `splits/manifests/<family>.json`. Identical across rebuilds of the same content |
| That the environment is reproducible | base image pinned by digest, every pip and apt package pinned; packages only the verifier needs (the LLM judge's client) are installed by `tests/test.sh`, not in the agent's image |
| That the agent can't look the answer up | Point in time, below |

`python rl/splits/check.py` checks all of this for every built task. Before handing tasks to
anyone, run `python rl/splits/check.py --release`: it also requires every task to come from one
commit with no uncommitted changes, and every bench and held-out task's gold to be approved (Gold
provenance, below). Commit first, then rebuild, then check.

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

## Every part counts

`splits/check.py` (check 7) fails a task when:
- a `/app/data` file the instruction names isn't in the image
- an output the instruction asks for is never read by the verifier
- the reference solution imports a package the agent's image lacks
- the reference refers to grader-side files (`/tests`, ground truth, gold, seeds, the generator)
- its `params.json` gives a value the instruction doesn't state

`python rl/harness/ablation.py` checks two things. First, dropping any one planted item from a
gold-derived answer lowers the reward (pytest runs this on a task per generated family). Second,
turning off a reference step loses reward wherever that step's trap is planted (data_audit's six
checks).

## Reward hacking

`python rl/harness/attacks.py --split <split>` attacks every verifier the way a gaming agent would:
empty, malformed, placeholder, copied-input, random, extreme, over-long and prompt-injection
outputs, edits to `/app/data`, modules planted in `/tests` before the grader is uploaded, and, for
prose graded by a judge or keyword grader, padding, hedging, restating the brief and keyword
stuffing. Each family's mean must stay a margin below good answers (reference solution, gold
forecast, gold pick); pytest runs it on one bench task per family. Because Harbor uploads `tests/`
by merging into whatever is at `/tests`, every task ships `tests/FILES`, and `test.sh` deletes
anything else there and clears `PYTHONPATH` before running the verifier.

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
| `provenance` | the review state of the family's gold inputs: `status` (`approved` only when every one is approved and unchanged since review), `files`, and the `unapproved` ones. Details per file in `tests/provenance.json` (Gold provenance, below) |
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

Every model-graded verifier (growth_thesis memo, research_design review scorer, kpi_nowcast write-up)
calls the shared judge, `families/_shared/judge.py`, copied into `tests/` with `tests/judge.json`:
the family's pinned judge (`judge` in `family.yaml`: model, effort, votes, max tokens). It retries
with backoff, never falls back to another model, and records the requested and served model and
the judge prompt's fingerprint in `details.json`. With `JUDGE_CACHE=<dir>`, judgments are cached by
the exact request, so re-grading a saved answer is free and returns the same reward. Without
`ANTHROPIC_API_KEY`, or when the judge fails, judged metrics are reported as not graded (kpi_nowcast
keeps its accuracy metrics); `JUDGE=keyword` explicitly opts growth_thesis into its keyword grader.
`python rl/harness/judge_stability.py` re-judges saved answers to measure per-item agreement.

## Gold provenance

Every file a family's gold comes from (gold labels, rubrics, grader facts, annotations, the
generators whose output is ground truth) is listed in its `family.yaml` under `gold_inputs`, and
has an entry in a provenance index, `provenance.yaml` in its source's or family's folder
(`provenance.py`): who or what produced it (a person, a model and prompt fingerprint, or code and
a commit), when, and its review (`draft`, `approved`, `rejected`, by whom, why). An approval binds
to the file's content hash, so a file edited after review counts as unreviewed. Review entries with
`python rl/review/review.py review --reviewer <name> --batch 10`: highest value first, evidence
beside each item, one key per decision, blind-first labels where an entry asks for one. Decisions
go to `review/decisions.jsonl`; edits and rejections also to `review/examples.jsonl`.

`splits/check.py` fails when a gold input has no entry or a task claims approved gold that no longer
is; `--release` (and so the export) also fails every bench or held-out task whose gold is not all
approved. Rebuild after a review session so tasks record the new state.

## Worlds

A world is a simulated fund. Today each world is only a firm brief
(`status: brief_only`). A full world adds mandate, holdings, theses, past memos and
a point-in-time data snapshot, and many tasks across roles run inside it. The list
of what is missing is in each `world.yaml`. research_design tasks stay one `eval` set until there
are enough worlds to hold out whole worlds, never single tasks: tasks in one world share context
and leak into each other.
