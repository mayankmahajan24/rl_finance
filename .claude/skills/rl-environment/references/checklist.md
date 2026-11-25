# RL-environment checklist

Every item has an id, what must be true, how to verify it in this repo, and what to do when it is
not. `rl-environment/scripts/audit.py --skill rl-environment` settles the items tagged **[auto]** and
lists every other one as `MANUAL`: those are yours to settle by reading and experiment. Items
tagged **[human]** end in a decision only a person may record; prepare the evidence and stop there.
**[optional]** items are worth doing only when the budget allows. Ids are stable and unique across
the three checklists, so a retired or moved item leaves a gap rather than renumbering the rest.

Statuses: `PASS` (with evidence from this session), `FAIL`, `WARN` (holds, but weakly or by
heuristic: read it), `BLOCKED` (needs Docker, API spend or a person: say which, give the command),
`N/A` (say why), `MANUAL` (not yet looked at; never a final status).

Paths are relative to `rl/`. `<f>` is the family id, `<s>` the split.

This list covers the integrity of the environment a task runs in: what the agent can see, reach
and remember, whether each trial is clean and reproducible, and the release gates. What the grader
pays for is on the `grader-design` checklist (D, E, F, G, M). Whether the tasks are real, solvable,
varied and calibrated is on the `task-generation` checklist (T and most of A, B, H, I, J). K5 and
K7 are the two items here that ask for those reviews.

## Contents

- A. Leaks in what the agent sees
- B. The reference inside the environment
- C. Isolation and cheat paths: airgap, tools, point in time, clean reset
- H. Harness and infrastructure
- J. Contamination and instrument approval
- K. Release gates

---

## A. Leaks in what the agent sees

### A4. Nothing the agent sees identifies the gold, the benchmark or a disguised company [auto]
*Verify:* `splits/check.py` check 8 (`leakcheck.py`); `leak_check` in `family.yaml` declares the gold
fields. A family with numeric or textual gold and no `gold_numbers`/`gold_text` entry is unchecked.
*Fix:* declare the fields; remove the leak at its source (generator, builder, data file).

### A5. Ids, file names and metadata say nothing about the answer
Task ids, data file names, column order, row order, mtimes and anything else visible carry no
signal: held-out ids are numbered; a control task is not recognisable from its files. (The
`-control-` in a task id is repo-side only: confirm the id is not in the image or instruction.)
*Verify:* diff the visible half (`instruction.md`, `environment/`, `prompt/`) of a planted task and
its control; the only differences should be the data itself.

### A8. Nothing in the world points at the answer or contradicts the grader
No index, summary, note or file name that singles out the few records that matter; no seeded text
(a message, a memo, a README) that tells the agent to do something the verifier then punishes. A
model must not lose reward for following directions it was given.
*Verify:* read everything under `environment/` of two train tasks as the agent, then read the
verifier; list each place the two disagree. Whoever built the world should not be the only one to
read it for leaks.
*Fix:* at the generator or the data file; a contradiction that is deliberate is stated in the `rubric_visibility` note (task-generation A3).

---

## B. The reference inside the environment

### B2. The reference passes inside the task's own image [BLOCKED without Docker]
*Verify:* `JUDGE=keyword python rl/harness/oracle_check.py` (the family's tasks in its `SAMPLE`), or
the Oracle workflow. The reward must equal the local one (`tests/expected_rewards.json`).
*Fix:* a package the image pins differently, a path only the container has.

### B3. The reference is clean-room [auto]
It imports only what the agent's image has and reads nothing grader-side (`/tests`, gold, seeds,
the generator). A reference that peeks proves nothing about solvability.
*Verify:* `splits/check.py` check 9.

---

## C. Isolation and cheat paths: airgap, tools, point in time, clean reset

### C1. Agent and environment phases have no network; the verifier reaches only what its judge needs [auto]
*Verify:* `splits/check.py` check 6; `task.toml` `[agent]` and `[environment]` are `no-network`,
`[verifier]` is `no-network` or an allowlist of exactly `harbor.VERIFIER_HOSTS`.

### C2. The airgap is proven in Docker, for this family [BLOCKED without Docker]
*Verify:* `python rl/harness/sandbox_probe.py <task>` (`--with-judge` for a judged family), and one
of the family's tasks is in `.github/workflows/sandbox.yml` so it stays proven. audit.py checks the
workflow lists one.
*Fix:* add a task to the workflow.

### C3. The image is reproducible and self-sufficient [auto]
Base image pinned by digest, every pip and apt package pinned, nothing fetched at run time. The
agent needs nothing that is not in the image (no `pip install` in the reference).
*Verify:* audit.py reads the built Dockerfile; check 9 covers the reference's imports.

### C4. A run opens only the hosts the agent's own harness needs
The model API (`--allow-agent-host`) and the installer's hosts (`--allow-environment-host`), nothing
else; the agent's web tools are off (`--ak disable_web_search=true`). A model API host is also a
channel: confirm the agent harness cannot be pointed at a tool that browses.
*Verify:* the `harbor run` arguments in `README.md`, `calibrate.py run` and `live-run.yml`.

### C5. A dated task cannot see past its as-of date [auto + Docker]
Clock pinned, mtimes pinned, no row after `as_of` in any visible file, and nothing in the image
(package release dates aside) dated later.
*Verify:* check 6; the sandbox probe's clock readings; grep the visible data for later dates.

### C6. Grader-only material is never in the image [auto]
Gold, `CANARY`, seeds, the generator, judge prompts and reference outputs live in `tests/` (uploaded
after the agent finishes) or nowhere. The Dockerfile copies `data/` only.
*Verify:* check 4 and 8; audit.py reads the Dockerfile's `COPY` lines.

### C7. Every trial starts clean
One container per trial from the image; nothing a previous trial or the build left behind: no
`.git`, no caches, no shell history, no `__pycache__`, no editor state under `environment/`; no
host mounts or shared volumes in `task.toml`; `JUDGE_CACHE` never mounted where the agent runs.
*Verify:* audit.py lists stray files under `environment/`; read `task.toml` for mounts.

### C8. The verifier does not trust the container the agent ran in [auto, reports the mode]
By default Harbor runs the verifier in the agent's container (`environment_mode = "shared"`), where
the agent was root. `test.sh` already deletes anything planted in `/tests` and clears `PYTHONPATH`,
but an agent can still patch the interpreter or an installed package the verifier imports, or leave
a process that rewrites `/app/output` or `/logs/verifier` during grading. Harbor 0.24 can run the
verifier in a dedicated container (`[verifier] environment_mode = "separate"`, with the agent's
outputs passed as declared artifacts), which closes all of these.
*Verify:* audit.py reports each task's mode. In shared mode, record the residual risk and check
that the `tamper` attack covers what it can.
*Fix:* the change belongs in `families/_shared/harbor.py` and touches every family's instrument:
propose it to the user with the Docker test plan; do not make it as a side effect of another fix.

### C9. The agent has no tool the task did not intend
Secret tool use is a cheat path even with the network closed: a web search or fetch tool in the
agent harness, a code-execution or retrieval tool served by the model provider, an MCP server, a
browser, memory carried between trials. The list of tools the agent may use is written down, the
run arguments switch everything else off, and the transcripts show no call outside the list.
*Verify:* the `harbor run` arguments (`--ak disable_web_search=true` and the like); then, in the
calibration job folders, list the distinct tool names called and compare with the allowlist.
The first half is readable now; the second is BLOCKED until a calibration run exists.
*Fix:* close the tool in the run arguments; discard runs that used it.

### C10. The sandbox cannot be left for the real thing
Nothing in the environment lets the agent finish the task somewhere other than the sandbox: no
credential, token, cloud metadata endpoint or hostname that reaches a live system, and no stand-in
for a real service that fails over to the real one. The task also has no cheap workaround that
solves it by going around the world it was given.
*Verify:* `sandbox_probe.py` (C2) covers the network; grep the image and data for keys, tokens and
URLs; ask whether the task could be done faster by ignoring the provided files.

### C11. The world does not announce that it is a test
Tells are found and removed: a clock that moves too evenly, a world too small to be real, a folder
layout that looks like a benchmark task, file or path names that mention grading, rubrics, gold,
tests or the task id, a canary string in view. Agents now often begin by looking for grader files,
and a model that knows it is being evaluated acts more cautiously, so its behaviour there is not
the behaviour a lab is buying.
*Verify:* list the image's file tree and environment variables as the agent sees them; read
calibration transcripts for the model remarking that this is an eval or a test.
*Fix:* rename, restructure, or enrich the world; do not treat cleaner behaviour under suspicion as
the true signal.

### C12. The model's own memory is not a look-ahead path
Pinning the clock stops the sandbox seeing the future; it does not stop a model that was trained
after the as-of date from remembering it. For a dated task, the outcome being forecast is either
later than the training cutoff of every model the task is meant for, or the company and period are
disguised well enough that the model cannot place them, and the probe says so.
*Verify:* `harness/memorisation.py` (named against disguised variants) and `canary_probe.py` (J5);
compare `as_of` with the cutoffs of the calibration models. Needs an API key: BLOCKED without one.
*Fix:* disguise, or restrict the task to models whose cutoff precedes the outcome and say so in
the datasheet.

### C13. Transcripts were read for access the agent should not have had
Listing `/tests` or `/logs/verifier`, reading repository or shell history, searching for the
generator or the gold, editing inputs, probing the network, looking up the company. Any hit is a
defect in the environment even when the attempt failed.
*Verify:* grep the calibration job folders for those paths and commands, across every model run.
BLOCKED until a calibration run exists.

---

## H. Harness and infrastructure

### H7. Errors are infrastructure, and rare
`errored` near 0; refusals, truncations and timeouts are scored 0 and counted separately; the agent
timeout is not what decides pass or fail.

### H13. The agent harness exercises the skill the task is for
A model is always measured together with its harness. The harness makes the agent do the thing
being trained (for a task about reading a chart, the image reaches the model), and a harness fault
(a timeout, a tool error, a truncated file read) is counted as an error (H7), not as the model
failing.
*Verify:* read three transcripts for how the inputs reached the model; confirm errored trials are
separated from failed ones in the run records.

---

## J. Contamination and instrument approval

### J5. The canary is in every task and nowhere visible; contamination probes are run [auto, partial]
`harness/canary_probe.py`; `harness/memorisation.py` for families with named and disguised variants.

### J7. The instrument is approved at its current hash [human]
`python rl/harness/approve.py --family <f> --show`. Any fix to an instrument file reopens this;
that is the system working. Never run `--approve` yourself.

---

## K. Release gates

### K1. `python rl/splits/check.py --release` passes [auto; expected to fail until J6 and J7 are done]

### K2. The sign-off steps in `review/SIGNOFF.md` are done in order [human]

### K4. What the family is, and what is left open, is written down
Anything left `WARN`, `BLOCKED` or accepted as a residual risk appears in the readiness report and,
where it outlives the session, in `rl/README.md` (Known limits). The family's `reward` text and
`release/CHANGELOG.md` describe it as it now is, including whether it is meant as a capability
measure, a regression set or training data. Rubric changes made after reading traces are logged in
`runs/<family>/reviews/feedback_log.md`.

### K5. Grading passed the grader-design review at this version
`runs/<f>/reviews/grader_<date>.md` exists for the family's current version with verdict sound (or
sound once signed, with the same open items listed here). A family whose verifier, grader, rubric
or `reward` changed since that report is not ready.
*Verify:* the report's version against `family.yaml`; `git log` on the grading files since its commit.
*Fix:* run the `grader-design` skill; do not re-do its checks here.

### K6. A run can be replayed and regraded
The commit, the image digest and every dependency are pinned (C3); nothing is fetched or called
live during a trial, or the call is served from a snapshot; and a saved answer can be graded again
later and gets the recorded reward. A lab that cannot reproduce a number will not trust it.
*Verify:* `tests/test_replay.py`; regrade one saved run record and compare the reward.

### K7. The task set passed the task-generation review at this version
`runs/<f>/reviews/task_set_<date>.md` exists for the family's current version with verdict ready
(or ready once signed, with the same open items listed here).
*Verify:* the report's version against `family.yaml`.
*Fix:* run the `task-generation` skill; do not re-do its checks here.
