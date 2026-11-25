---
name: rl-environment
description: Make the RL environment a task runs in sound enough to sell to a frontier lab, and run the final release gate — audit every way the agent could get the answer or an unfair edge without the grader being wrong (gold or tests in the image, leaked ids and metadata, network access, secret tool use such as web search or provider-side tools, look-ahead past the as-of date, outcomes the model memorised in training, sandbox escape to a live system, state left by a previous trial, a verifier sharing the agent's container, eval tells), plus harness faults, contamination canaries, reproducible images and replayable runs, then fix what is off and write the readiness report. Use this whenever the user asks to build, harden, audit or sign off an environment, sandbox, image or harness; asks whether a family is ready to ship, release, sell or train on; worries about cheating, leaks, the airgap, tools, point-in-time or look-ahead safety, contamination or reproducibility; or has just changed a Dockerfile, task config, harness or run arguments — even if they don't say "environment". How answers are scored belongs to the grader-design skill, and which tasks exist and how hard they are to the task-generation skill; this skill checks those reviews exist and does not repeat them.
---

# RL environment

An environment is sound when the only way to earn the reward is to do the work with what the task
intended the agent to have. This skill audits everything a run can see, reach and remember, fixes
what it can, and runs the release gate that says a family is ready for a lab.

Most of the machinery already exists in `rl/` (`FORMAT.md`, `families/README.md`,
`review/SIGNOFF.md`, `harness/`). The skill is the order to use it in, the checks no script can
do, and the discipline around fixing.

## What this skill owns

Three skills take a family to lab-ready, usually in this order, and each checklist item lives in
exactly one:

- **`grader-design`: what the score pays for.** Verifiers, rubrics, judges, grader exploits.
- **`task-generation`: which tasks exist.** Real, solvable, varied, calibrated, split, licensable.
- **`rl-environment` (here): what the agent can reach when a task runs**, and the release gate.

Reward hacking has two halves. If the agent had something it should not have had (a file, a tool,
the internet, the future, a hint in a file name), the hole is here. If the grader paid for
something that is not the work, it is `grader-design`'s. The release gate asks for the other two
reports at the family's current version (K5, K7) and never re-does their checks: if one is missing
or stale, run that skill and come back.

## Ground rules

- **Work on train tasks.** A bench or held-out case that was read, run or debugged against no
  longer measures anything (`rl/splits/README.md`). Never open held-out gold. A case that had to
  be touched is listed under `retired:` in `rl/splits/<source>.yaml` with the reason.
- **A person signs; you prepare.** Instrument approval (`approve.py --approve`) and the sign-off
  steps are human decisions the code records by name. Assemble the evidence and the exact command;
  don't run it.
- **Ask before spending.** The canary and memorisation probes and any calibration run call a
  model. Get a budget first.
- **A status needs evidence from this session.** `PASS` means you ran or read the thing now. If a
  check can't run here (no Docker, no key), it is `BLOCKED` with the command, not assumed.
- **Follow any local `CLAUDE.md`** (pilot scope rules live there, out of git).

## Workflow

### 1. Scope

Settle which family and what it is being readied for: RL training, a published bench
(contamination and release gates matter most), or both. Read the built task layout
(`instruction.md`, `environment/`, `tests/`, `task.toml`), the Dockerfile, the shared Harbor
config and the run arguments in `README.md` and `calibrate.py` before running anything.

### 2. Run the audit

```sh
python rl/build.py <family> --split train --n 3 --controls 1   # panel families; others: python rl/build.py <family>
python .claude/skills/rl-environment/scripts/audit.py --family <family> --skill rl-environment --out <scratch>/env.md --json <scratch>/env.json
```

`--full` runs every task, `--static` needs no built tasks, and without `--skill` it prints all
three skills' items. It is offline and free: the split check's leak and network checks, static
reads of the Dockerfiles and task configs, stray files, the verifier's container mode, the canary.
The Docker proofs (`sandbox_probe.py`, `oracle_check.py`) are `BLOCKED` without a daemon.

`FAIL` is a defect to fix. `WARN` is a weak pass: read what it points at. `MANUAL` is the real
work. `BLOCKED` names what is missing: Docker, a budget, or a person.

### 3. Be the reviewer who wants to reject it

Open `references/checklist.md` and settle every `MANUAL` item, A to K. Before judging anything,
write down at least five concrete ways this environment could hand the agent the answer or an
unfair edge:

- What can I read that I should not? (`/tests`, `/logs/verifier`, gold in the image, git or shell
  history, a previous trial's files)
- What can I reach? (the network, a metadata endpoint, a credential, a live system the sandbox
  stands in for)
- Which tools do I have that the task did not intend? (web search, a provider-side code or
  retrieval tool, an MCP server, memory between trials)
- What do I already know? (the outcome of a dated task, the company behind a disguise, the
  benchmark this was built from)
- What does the visible half give away? (file names, row order, mtimes, ids, float precision or
  rounding that marks planted values, an index that points at the records that matter)
- What can I change that the verifier trusts? (the interpreter, an installed package, a process
  left running, files under `/app/data`)
- What tells me this is a test? (a tidy clock, a tiny world, a task-shaped folder, the word
  "gold" in a path)

Try each on a train task. Each maps to an item in A or C, and a hit is a defect even when the
attempt would not have scored: a model that learns to look will find the next one.

Two more that often find something:

**Diff a planted task against its control (A5, A8).** Everything visible. The only differences
should be the data itself.

**Read transcripts for reaching, once a calibration run exists (C9, C13).** List the distinct
tools called and grep for `/tests`, history, the generator and network probes, across every model.

### 4. Fix what is off

Follow "Changing a family" in the `task-generation` skill for the mechanics (predict the flips,
change the source, bump the version, rebuild, add the regression, re-run). Environment fixes are
usually in the Dockerfile template, the task config, the shared Harbor adapter or the run
arguments; the regression is a line in the sandbox probe or a check in `splits/check.py`.

Stop and ask instead of fixing when the change touches every family at once
(`families/_shared/harbor.py`, the verifier's container mode in C8): bring the evidence, a
recommendation and the Docker test plan.

### 5. Release gate and report

The gate is section K: both other reviews exist at this version (K5, K7), the release check and
sign-off steps are done in order, runs can be replayed and regraded, and what is left open is
written down. Then write the readiness report to
`rl/runs/<family>/reviews/lab_ready_<YYYY-MM-DD>.md`:

```markdown
# Lab-ready: <family> (<version>, commit <sha>)

**Verdict:** ready | ready once signed (list) | not ready (list the FAILs)

## Reviews this relies on    (grader-design and task-generation reports: path, version, verdict)
## What was fixed            <change> — <evidence it worked> — <version bump>
## Open: needs a fix
## Open: needs a person      (the decision, the evidence, the exact command)
## Open: needs Docker or budget   (the command and what it will show)
## Residual risks accepted
## Scorecard                 (every item A4–K7: status and one line of evidence)
```

No item may be left `MANUAL`. The report goes in git, so it follows the run-records rule: no gold,
no model answers, no real company behind an anonymised task.

Tell the user the verdict first, then the FAILs fixed, then what is waiting on them. Commit the
fixes, the rebuilt manifests and the report together only when the user asks for a commit.

## Reference

- `references/checklist.md` — the full list, A4–K7. Read it in step 3.
- `scripts/audit.py` — the mechanical items and the scorecard, for all three skills. It parses the
  three checklists for their items, so a new item added to any of them appears as `MANUAL` until
  the script learns it.
