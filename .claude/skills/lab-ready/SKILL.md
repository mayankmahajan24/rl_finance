---
name: lab-ready
description: Take an RL task family (or one task) in rl/ from "it builds" to production-grade and ready to hand to a lab — audit it against the full lab-ready checklist (solvable, airgapped, clean reset, grades world state, resistant to reward hacking, sound rubrics and judges, tested evaluators, calibrated difficulty, integrity and release gates), fix what is off, and write the readiness report. Use this whenever the user asks to harden, productionise, audit, review or sign off a family or task; asks whether a family is ready to ship, release or train on; worries about reward hacking, leaks, the sandbox, a rubric or judge, or pass rates; or has just added or changed a family, verifier, grader, rubric or instruction — even if they don't say "lab-ready".
---

# Lab-ready

A family is lab-ready when a lab can train or evaluate on it and trust every reward: each task is
solvable, the agent can't look the answer up or reach outside, the grader pays for the work and
nothing else, difficulty sits where a policy learns from it, and all of that is recorded so someone
else can check it. This skill runs the family through the checklist that establishes that, fixes
what it can, and reports what is left and who has to decide it.

Most of the machinery already exists in `rl/` (`FORMAT.md`, `families/README.md`,
`review/SIGNOFF.md`, `harness/`). The skill is the order to use it in, the checks no script can
do, and the discipline around fixing.

## Ground rules

These come from how the repo treats measurement; breaking one quietly invalidates results.

- **Work on train tasks.** A bench or held-out case that was read, run or debugged against while
  fixing a grader no longer measures anything (`rl/splits/README.md`). Audit and experiment on
  `--split train`. Never open held-out gold. If a fix really did need a bench case, list that case
  under `retired:` in `rl/splits/<source>.yaml` with the reason and say so in the report.
- **A person signs; you prepare.** Gold review (`review.py`), instrument approval
  (`approve.py --approve`), licences, pass thresholds and dropping a task are human decisions the
  code records by name. Assemble the evidence and the exact command; don't run it.
- **Ask before spending.** Calibration, the real judge, the canary probe and judge stability call
  a model. Get a budget from the user first; the runners take `--budget`.
- **A status needs evidence from this session.** `PASS` means you ran or read the thing now. If a
  check can't run here (no Docker, no key), it is `BLOCKED` with the command, not assumed.
- **Fixing the instrument reopens its approval.** That is the system working. Bump the version,
  rebuild, and report it; don't route around it.
- **Follow any local `CLAUDE.md`** (pilot scope rules live there, out of git).

## Workflow

### 1. Scope

Settle which family (or task) and what the user wants it ready for: RL training (difficulty band
and volume matter most), a published bench (contamination and release gates matter most), or
both. Read the family's `family.yaml`, instruction template, verifier, graders, `judge.md` and
reference solution before running anything: most real findings come from reading the verifier.

For a single task, audit its family: nearly every property is the family's.

### 2. Run the audit

Needs the repo's pinned environment (Python 3.14, `pip install -e ".[dev]"`) and built tasks:

```sh
python rl/build.py <family> --split train --n 3 --controls 1   # panel families; others: python rl/build.py <family>
python .claude/skills/lab-ready/scripts/audit.py --family <family> --out <scratch>/audit.md --json <scratch>/audit.json
```

`--split train` and two planted tasks plus one control are the defaults; `--full` runs every task,
`--static` needs no built tasks. Families with no train split (research_design builds into `eval`)
take `--split eval`. It runs offline and spends nothing: the split check, reference and naive
solvers, the attack suite, ablation, and static reads of the Dockerfiles, task configs, rubric and
tests. It prints the whole checklist with a status per item.

Read the scorecard as a to-do list. `FAIL` is a defect to fix. `WARN` is a heuristic or a weak
pass: read the thing it points at. `MANUAL` is the bulk of the real work (step 3). `BLOCKED` names
what is missing: Docker, a budget, or a person.

### 3. Work the manual items

Open `references/checklist.md` and settle every `MANUAL` item in order, A to K. Each says what must
be true, how to verify it here, and the fix. Don't skim this step: the script covers what is
mechanical, and the failures that reach a lab are the ones that aren't. The three that most often
find something:

**The exploit hunt (E4).** Read the verifier as an agent that wants the reward without the work,
and write down at least five concrete attempts before judging any of them. Prompts:

- What does the verifier read that I can write? (`/app/data`, `/tests` before upload, the
  interpreter and installed packages in a shared container, `/logs/verifier`)
- What does it trust that I report? (my own error metrics, counts, a "done" flag)
- Which answer is right most often without looking? (always A, flag nothing, flag everything, last
  period's value, the base rate) What does that policy average over the split, controls included?
- Which cheap parts pay? (valid format, right sections, length, keywords, hedged claims that are
  never wrong) Do they sum to a pass?
- What does the visible half give away? (file names, row order, mtimes, ids, float precision or
  rounding that marks planted values, generator regularities across tasks)
- If it runs my code, what can that code open?
- If a judge reads my text, can the text talk to it, bury it, or flatter the rubric?

Try each on a train task with `harness/local.py`'s `grade`. Every attempt, successful or not,
becomes an attack in `rl/harness/attacks.py` so it stays closed.

**The never-read-the-record answer (F3, judged families).** Write the best answer you can from the
instruction alone, with no data opened: fluent, structured, every expected caveat. Grade it with
the real judge. If it passes or comes close, the rubric is paying for form; fix the rubric before
anything else is measured with it.

**Two right answers and a wrong one (D2, G1).** Write a correct answer, a second correct answer in
a different form or by a different method, and the first with its key claim negated. The grader
must pass both and fail the third. Add them to `rl/tests/`.

### 4. Fix what is off

Fix defects in the family as you find them; that is the point of the run. One change at a time:

1. Write down which pinned rewards and attack scores should move, and which way, **before**
   re-running. Anything else that moves is a bug in the fix.
2. Make the change at its source (template, generator, verifier, grader, rubric, adapter). Built
   tasks under `rl/tasks/` are outputs; never edit them.
3. Bump `version` in `family.yaml` in the same change: major if the reward now means something
   different, minor if what the model sees or the sandbox changed, patch for metadata only.
4. Rebuild (`python rl/build.py <family>`, and the train size the manifests record), which ends
   with the split check. Re-record pins only for the flips you predicted
   (`UPDATE_EXPECTED=1 pytest rl/tests/test_verifiers.py -m slow`).
5. Add the regression: an attack, a test case, or an ablation hook.
6. `pytest -m "not slow"` and `ruff check`; re-run the audit.

Stop and ask instead of fixing when the change is a judgment the owner should make: what the task
should measure, a pass threshold, reward weights, whether to drop or retire a task, or anything in
shared code that changes every family at once (`families/_shared/harbor.py`, `judge.py`). For
those, bring the evidence and a recommendation.

Difficulty fixes follow `references/checklist.md` sections H and I. In short: audit every 0/k for a
harness or rubric bug before calling it hard; convert 0/k and k/k tasks before authoring new ones;
move difficulty with two or three non-fatal decisions and matched no-action twins, never with
length, clutter, a single fatal gate or hints.

### 5. Report

Re-run the audit, merge in your manual findings, and write the readiness report to
`rl/runs/<family>/reviews/lab_ready_<YYYY-MM-DD>.md`:

```markdown
# Lab-ready: <family> (<version>, commit <sha>)

**Verdict:** ready | ready once signed (list) | not ready (list the FAILs)

## What was fixed
<change> — <evidence it worked> — <version bump>

## Open: needs a fix
## Open: needs a person      (the decision, the evidence, the exact command)
## Open: needs Docker or budget   (the command and what it will show)
## Residual risks accepted
## Scorecard                 (every item A1–K4: status and one line of evidence)
```

No item may be left `MANUAL`. The report goes in git, so it follows the run-records rule: no gold,
no model answers, no real company behind an anonymised task.

Tell the user the verdict first, then the FAILs fixed, then what is waiting on them. Commit the
fixes, the rebuilt manifests and the report together only when the user asks for a commit.

## Reference

- `references/checklist.md` — the full checklist, A1–K4. Read it in step 3; it is the skill's
  substance.
- `scripts/audit.py` — the mechanical items and the scorecard. It parses the checklist for its
  items, so a new item added there appears in the scorecard as `MANUAL` until the script learns it.
