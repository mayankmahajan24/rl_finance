---
name: task-generation
description: Go from source data plus a sound grader to a larger set of RL tasks in rl/ that is valuable as a group and can be licensed to a lab — design the coverage grid, grow tasks from an expert seed without losing what made the seed good, keep every answer computed, make each task real, clear and solvable without guessing, add no-action twins, screen and tune difficulty into the band a policy learns from, convert tasks that teach nothing, check the set for redundancy, conflicting lessons and shared loopholes, hold the splits, and clear provenance and licences. Use this whenever the user wants to generate, scale, extend, diversify or prune tasks or a family; asks how many tasks, which variants, how hard, what the pass rates mean, or whether a set is worth licensing; mentions the generator, builder, seeds, variants, controls, calibration, screening, splits, manifests, provenance or a datasheet — even if they don't say "task generation". How answers are scored belongs to the grader-design skill, and what the agent can reach when a task runs to the rl-environment skill.
---

# Task generation

A grader says whether one answer is good. A lab licenses a set. This skill takes source data and a
grader that already works to a set of tasks that is worth having as a group: each task is real
work with one defensible answer, the tasks differ in what they demand, their difficulty sits where
a policy learns from it, the splits hold, and the data behind them can be licensed.

## What this skill owns

Three skills take a family to lab-ready, usually in this order, and each checklist item lives in
exactly one:

- **`grader-design`: what the score pays for.** Do that first, on a handful of seed tasks.
  Generating at volume against a weak grader multiplies the weakness.
- **`task-generation` (here): which tasks exist.** The generator, the instruction template, the
  seed and its variants, solvability, difficulty, variety, splits, provenance and licences.
- **`rl-environment`: what the agent can reach when a task runs.** Leaks, network, tools,
  look-ahead, resets, harness, replay, and the release gate, which asks for this skill's report at
  the family's current version (its item K7).

A quick test: if the defect would still be there with a perfect sandbox and a perfect grader (the
task is ambiguous, too easy, a copy of its neighbour, or built on data nobody may license), it is
this skill's.

## Ground rules

- **Work on train tasks.** A bench or held-out case you read, ran or debugged against no longer
  measures anything (`rl/splits/README.md`). Never open held-out gold, and never run calibration
  on held-out tasks to tune anything. A case that had to be touched is listed under `retired:` in
  `rl/splits/<source>.yaml` with the reason.
- **A person signs; you prepare.** Gold review, pass thresholds, dropping a task, provenance
  approval and licences are human decisions the code records by name. Bring the evidence, a
  recommendation and the exact command.
- **Ask before spending.** Calibration calls a model. Get a budget first; the runners take
  `--budget`.
- **A status needs evidence from this session.** If a check cannot run here it is `BLOCKED` with
  the command, not assumed.
- **Follow any local `CLAUDE.md`.** During the pilot it rules out more tasks, new families and
  replacing tasks that fail calibration; this skill does not override that.

## Workflow

### 1. Scope

Settle the family, what the set is for (training data, a capability measure, a regression set),
and how the lab would train on it: the difficulty band in step 6 matters for group-relative
methods and less for single-rollout ones. Confirm the grading has a `grader-design` report at the
current version; if not, that comes first. Read `family.yaml`, the instruction template, the
builder and the source's README.

### 2. Design the grid before generating

Write down what varies across tasks (trap type, magnitude, which traps co-occur, typical against
edge against adversarial, action against no-action, data holes) and which cells the set should
fill (T1). Every later question about variety, redundancy or coverage is answered against this
grid. Start with twenty to fifty hand-checked tasks; volume comes after the grid holds.

### 3. Generate from the seed, with computed answers

- Each variant keeps the decision its seed turned on, not only the surface (T2).
- Gold is computed by the builder or taken from source data; a model may write text but never
  decides the right answer (T3).
- The standard for a good task is in the builder and `splits/check.py`, and a person reads a
  sample of every batch (T4).
- Every planted task has a matched twin where the right move is to do nothing, identical in
  everything visible (I3). Without twins the set teaches the model to intervene everywhere.

```sh
python rl/build.py <family> --split train --n 3 --controls 1   # panel families; others: python rl/build.py <family>
```

### 4. Run the mechanical items

```sh
python .claude/skills/rl-environment/scripts/audit.py --family <family> --skill task-generation --out <scratch>/task_set.md
```

Offline and free: the split check, reference and naive solvers, ablation, twin counts, duplicate
fingerprints, and calibration stats where a run exists. `FAIL` is a defect, `WARN` a weak pass to
read, `MANUAL` the real work, `BLOCKED` names what is missing.

### 5. Work the manual items

Open `references/checklist.md` and settle every `MANUAL` item, T to J. The three that most often
find something:

**Solve it cold (B7, A7).** Give the instruction and data, without the gold, to a clean-room
solver and compare with the gold. Every disagreement is ambiguity in the instruction, a value the
agent could only guess, or wrong gold. A task that can only be scored by guessing teaches
confident guessing.

**Read the instruction as the colleague who got the assignment (A2, A3).** Delete anything a
professional would not be told: step lists, the trap described, "make sure to check". Then list
every graded requirement and find the sentence that states it.

**Look at the set, not the task (I5, I7).** Tabulate trap types and right answers over the split.
Look for the same idea taught many times, a behaviour rewarded in one task and punished in another
with nothing visible to tell them apart, and any grader exploit that works across the whole split.

### 6. Screen and tune difficulty

Difficulty is moved by task design only, never by the grader.

- Screen with k = 2, then 4, then 8, stopping on a task once it is clearly too easy (2/2, 3/4,
  4+/8). Re-run the 2/2 and 0/2 tasks at k = 2 on a cheaper second model family before deciding:
  a task at 0/8 for one family can be above half for another.
- Audit every 0/k for a harness, instruction or grading bug before calling it hard (H5). Look at
  the interval, not the count: 0/4 is consistent with a 1-in-8 task about six times in ten.
- Convert 0/k and k/k tasks before authoring new ones (T5).
- Move difficulty with two or three non-fatal decisions and matched twins, never with length,
  clutter, planted contradictions, hints or a single fatal gate (I1).
- For group-relative training aim for 1/8 to 3/8 on the model being trained; report the pass-rate
  curve either way, not only pass@1 (H4, H11).

### 7. Clear the data

Every gold input has a provenance entry, the source's licence allows the intended use, and
person-level data was checked for quasi-identifiers (J6, J8, J9). These end in a person's
decision: prepare `python rl/review/review.py review --reviewer <name>` and the licence status,
and stop.

### 8. Report

Write to `rl/runs/<family>/reviews/task_set_<YYYY-MM-DD>.md`:

```markdown
# Task set: <family> (<version>, commit <sha>)

**Verdict:** ready | ready once signed (list) | not ready (list the FAILs)

## The set                   (counts by split and grid cell, twins, pass-rate distribution, cost per rollout)
## What was fixed            <change> — <evidence it worked> — <version bump>
## Open: needs a fix
## Open: needs a person      (the decision, the evidence, the exact command)
## Open: needs budget        (the command and what it will show)
## Residual risks accepted
## Scorecard                 (every item T1–J9: status and one line of evidence)
```

No item may be left `MANUAL`. The report goes in git: no gold, no model answers, no real company
behind an anonymised task.

## Changing a family

All three skills use this when a fix touches a family. One change at a time:

1. Write down which pinned rewards and attack scores should move, and which way, before
   re-running. Anything else that moves is a bug in the fix.
2. Make the change at its source (template, generator, data, verifier, grader, rubric, adapter).
   Built tasks under `rl/tasks/` are outputs; never edit them.
3. Bump `version` in `family.yaml` in the same change: major if the reward now means something
   different, minor if what the model sees or the sandbox changed, patch for metadata only.
4. Rebuild (`python rl/build.py <family>`, and the train size the manifests record), which ends
   with the split check. Re-record pins only for the flips you predicted
   (`UPDATE_EXPECTED=1 pytest rl/tests/test_verifiers.py -m slow`).
5. Add the regression: an attack, a test case, or an ablation hook.
6. `pytest -m "not slow"` and `ruff check`; re-run the audit.

Fixing the instrument reopens its approval. That is the system working: report it, do not route
around it.

## Reference

- `references/checklist.md` — the full list, T1–J9. Read it in step 5.
- `../rl-environment/scripts/audit.py --skill task-generation` — the mechanical items and the
  scorecard.
