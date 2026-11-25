# Task-generation checklist

Every item has an id, what must be true, how to verify it in this repo, and what to do when it is
not. `rl-environment/scripts/audit.py --skill task-generation` settles the items tagged **[auto]** and
lists every other one as `MANUAL`: those are yours to settle by reading and experiment. Items
tagged **[human]** end in a decision only a person may record; prepare the evidence and stop there.
**[optional]** items are worth doing only when the budget allows. Ids are stable and unique across
the three checklists, so a retired or moved item leaves a gap rather than renumbering the rest.

Statuses: `PASS` (with evidence from this session), `FAIL`, `WARN` (holds, but weakly or by
heuristic: read it), `BLOCKED` (needs Docker, API spend or a person: say which, give the command),
`N/A` (say why), `MANUAL` (not yet looked at; never a final status).

Paths are relative to `rl/`. `<f>` is the family id, `<s>` the split.

This list covers the tasks as a set: whether each one is real, clear and solvable, and whether
together they are varied, calibrated, cleanly split and licensable. What the grader pays for is on
the `grader-design` checklist (D, E, F, G, M). What the agent can reach when a task runs, and the
release gates, are on the `rl-environment` checklist.

## Contents

- T. Generating the set
- A. Specification and realism: what each task tells the agent
- B. Solvability and separation
- H. Difficulty calibration
- I. Difficulty design and variety
- J. Splits, provenance and licences

---

## T. Generating the set

### T1. Cases were designed from dimensions before any were generated
A written grid of what varies (trap type, magnitude, which traps co-occur, typical against edge
against adversarial, action against no-action, data holes) and which cells the set fills. A batch
of near-duplicate queries is not a set. Twenty to fifty hand-checked tasks are enough to start;
volume comes after the grid holds.
*Verify:* the grid exists (in the family's README or `family.yaml` notes) and every built task
maps to a cell; list the empty cells and say which are deliberate.
*Fix:* add generator parameters for a missing dimension; do not pad a filled cell.

### T2. Variants keep what made the seed task good
Where the family grows from a small expert-written seed, each generated variant keeps the seed's
reasoning, constraints and edge cases, not only its surface, and the expert's notes on what is
non-obvious still apply to it. A variant that changes the numbers but drops the trap is a
different, easier task.
*Verify:* for three variants, name the seed, the decision the seed turned on, and where that
decision sits in the variant.

### T3. Every generated answer is computed, not written by a model
Gold comes out of the generator's own arithmetic or from the source data, and the reference
solution passes each generated task (B1). A model may write task text; it does not decide what the
right answer is.
*Verify:* read where the builder writes `gold_file`; `run_solutions.py` on the generated split.

### T4. The standard was written down before generating at volume
What a good task is, in the family's own terms, is fixed first and enforced by the builder and
`splits/check.py`, and a person reads a sample of every generated batch. Models write tasks more
easily than they judge whether those tasks are fair, so an unread batch is unreviewed.
*Verify:* the family README states the standard; the report names who read which tasks of the
batch.

### T5. Tasks that teach nothing are converted before new ones are written
A task every model always passes or always fails adds cost and no signal. Each goes to a
conversion queue (change the decisions it turns on, add its no-action twin, fix what made it
impossible) before any new task is authored: conversion is several times cheaper than screening
fresh tasks.
*Verify:* from the latest calibration stats, list the 0/k and k/k tasks and what was done with each.
BLOCKED until a calibration run exists.

### T6. The set is described as a set
What a licensee gets is written down: task counts by split and by grid cell, the share of
no-action twins, the pass-rate distribution per calibration model, cost per rollout, what is held
out and stays secret, and what the set is meant for (training data, a capability measure, a
regression set).
*Verify:* the family's entry in the datasheet or `release/` notes has each of these, with numbers
from this version.

---

## A. Specification and realism: what each task tells the agent

### A1. The instruction states the goal, the inputs, the deliverables and the constraints [auto, partial]
An agent that reads only `instruction.md` knows what to produce, where (`/app/output/...`), in what
format, from which files, and in broad terms what it is scored on.
*Verify:* `splits/check.py` check 9 (every `/app/data` file named exists; every output asked for is
read by the verifier; `params.json` gives nothing unstated). Then read two rendered train
instructions end to end as if you were the agent.
*Fix:* the template (`families/<f>/instruction.md` or `prompts/`). Minor version bump.

### A2. The instruction does not coach the solution
It names the goal, not the method: no step lists, no description of the planted traps, no mid-task
hints, no "make sure to check X". Data holes are stated plainly ("no consensus exists for this
quarter") without the rule for handling them. Coaching turns a judgment task into instruction
following, and what the model then learns is to follow coaching.
*Verify:* audit.py flags templates over 900 words; the rest is reading. Read the template and ask
of each sentence: does a professional given this assignment by a colleague get told this?
*Fix:* delete the sentence; if a grader depended on it, the requirement moves to A3.

### A3. Nothing is graded that the agent could not know to do
Every graded requirement is either stated in the instruction or is what a careful practitioner
does unprompted, and the second kind is a recorded, deliberate choice (`rubric_visibility` in
`family.yaml`). Output-format requirements (file names, schema, units, word limits) are always
stated: a format miss teaches nothing.
*Verify:* list every check in the verifier, grader and `judge.md`; map each to an instruction
sentence or to the `rubric_visibility` note.
*Fix:* state it, or drop the check, or record it as deliberate.

### A6. The task is real work
It is something the `role` in its metadata does at a fund, with the inputs they would have, not a
puzzle built to be hard, and a better score on it would matter to someone doing that job. The
environment mirrors the setup the work is done in: the files, tools and state the role would have.
*Verify:* the source's assignment and README; ask what decision a higher score would change.

### A7. No task can only be scored by guessing
If the instruction leaves a rule, a value or a convention unstated and the data does not settle
it, a model can only score by guessing, and RL then teaches it to guess with confidence in
production. Everything the gold depends on is either stated, derivable from the visible files, or
genuinely unknowable, and in the last case the right answer is to say so and the grader pays for
that, not for a lucky guess.
*Verify:* for each gold field, name the visible evidence that determines it. Take a train task's
passing answer and ask which of its choices the agent could not have justified from what it saw.
*Fix:* state the convention (A3), put the evidence in the data, or make "cannot be determined" a
scored answer.

### A9. Generated data does not read as generated
Synthetic records carry the texture of real ones: uneven formatting, human-like errors,
company-specific habits, gaps. Templated text, concatenated or implausible documents and values on
a clean grid tell the model it is in a test, and it then behaves differently (rl-environment C11).
*Verify:* show a sample of the visible data, with no context, to a model or a person and ask which
rows are synthetic and why; fix what gives them away and repeat until nothing is singled out.
Families built on real panels: N/A for the real rows, still applies to anything planted.

### A10. Rules sit where they would at work [optional]
At work a rule lives in a document, a record or a colleague's message, not in the request. A task
can be built in two versions: full (every rule in the prompt) and realistic (the agent has to find
the rule). Models break a rule more often when it sits in a document than when the user states it.
*Verify:* where a family has both, run both and read the traces where the full version passed and
the realistic one failed. N/A for families whose instruction is the whole assignment.

---

## B. Solvability and separation

### B1. The reference solution passes every task, locally [auto]
A task whose own reference fails is a broken spec or grader, not a hard task.
*Verify:* `python rl/harness/run_solutions.py --split <s> --family <f>`; every reference
`status: ok` and at or above `calibration.pass`. Controls included.
*Fix:* find which of spec, reference, grader or threshold is wrong. Never lower a threshold to make
a reference pass without saying so in the report.

### B4. A naive solution fails, by a margin [auto]
`solutions/naive` scores below the pass threshold and at least 0.3 below the reference on planted
tasks. If both score alike the task measures nothing.
*Verify:* `run_solutions.py`; `tests/test_verifiers.py` pins the gap.

### B5. Doing nothing scores zero, and is distinguishable from deciding nothing is needed [auto, partial]
No output scores 0 (not an error, not partial credit). On a no-action twin (I3) the correct answer
is an explicit one (an empty list written to the output file, a "hold" decision), so absent output
still scores 0 there.
*Verify:* the `empty` attack on a planted task and on a control; audit.py reports both.

### B6. Every planted item and every step of the reference earns reward [auto where the family has a hook]
*Verify:* `python rl/harness/ablation.py --split <s> --family <f>` (families in `ablation.CREDIT`).
A family without a hook: drop one gold item from a gold-derived answer by hand and confirm the
reward falls.
*Fix:* add the family to `CREDIT`; fix a verifier that ignores an item.

### B7. Two experts would independently reach the same pass or fail
The task has one defensible answer, or the gold records every defensible one. A task that is 0%
across many trials is usually broken, not hard: an unstated output path, a convention only the
author knew.
*Verify:* give the instruction and data, without the gold, to a second solver (a person, or a
clean-room model run) and compare with the gold; each disagreement is ambiguity or an error.
*Fix:* the instruction (A3, A7) or the gold (grader-design D8).

### B8. The reference was checked by someone other than its author
A model-written reference is fine when it was verified independently, the graders were not fitted
to it, and a simpler solution a person would write also passes. If only the generated reference
earns credit the task teaches one path.
*Verify:* the gold review record (`review/review.py`); a second, plainer solution graded on two
train tasks (grader-design D2 holds the test).

---

## H. Difficulty calibration

Needs approved instruments and API budget: everything here is BLOCKED until the user gives a
budget. Never run calibration on held-out tasks to tune anything.

### H1. The pass threshold is confirmed, not proposed [human]
`calibration.pass` in `family.yaml`, with what it means in the task's terms.

### H2. At least two model families, one of them weaker, through the real agent harness
The model and its harness are tested together. A strong model reads through harness and API bugs
that a weaker one exposes. `calibrate.py run --model <strong> --model <weak>`. Where a second
agent harness is available (`--agent`), run it too: a result that holds in one harness only is a
harness result.

### H4. Tasks sit in the mixed-outcome band [auto, when stats exist]
For the model being trained, target 1/8 to 3/8. 0/8 and 8/8 groups give zero advantage under
GRPO/RLOO. audit.py reads the latest `runs/calibration/<s>/*/stats.json` and reports the share of
tasks at 0, in band, above band and at k/k.
The band is a property of group-relative training (GRPO, RLOO), where an all-pass or all-fail
group teaches nothing. A lab that trains from single rollouts does not need it: ask which they use
and report the pass-rate curve either way, not only pass@1.

### H5. Every 0/k was audited for a harness or rubric bug before being called hard
Read the transcripts. Typical causes: an output path the agent could not have known, a timeout, a
tolerance, a judge line nobody could pass, wrong gold (grader-design D8). A task at 0/k for every model with no
bug needs supervised data first, not on-policy RL: say so rather than keep it. But don't write a
hard task off on a small k: a sparse pass rate is noisy (0/4 is consistent with a 1-in-8 task
about 6 times in 10), and some hard tasks are learned slowly. Look at the interval, not the count.

### H8. The reward is not a cliff, and models separate
The per-task score distribution is not just {0, 1} for a family meant to give gradient; the noise
floor is below the gap between models (`report.md`, Model separation).

### H9. Cost per rollout is known, and the family is judged on signal per dollar
Tokens, wall time and judge cost per attempt from the run records. A dearer task with mixed
outcomes beats a cheap one at 0/8.

### H11. Reliability and cost are reported, not only pass@1
pass^k (all k attempts pass) beside pass@k, both with bootstrap intervals (`calibrate.py report`
gives these), and cost per correct outcome (spend divided by passing attempts) from the run
records. Capability improves faster than reliability, and identical runs can differ many times
over in cost, so the spread of cost per attempt is reported too.

### H12. The result survives a reworded instruction [optional]
A paraphrase of the instruction with the same content (reordered, different wording, same
deliverables) gives a pass rate inside the noise of the original. A drop means the task was
measuring the phrasing.
Costs a second calibration run; worth it for long hand-written instructions, rarely for a short
generated template.
*Verify:* build two or three train tasks with a paraphrased template into a scratch folder and
run the same k; do not commit the variant.

---

## I. Difficulty design and variety

### I1. Difficulty comes from decisions, not from a gate or from clutter
What makes the task hard is two or three non-fatal sizing or calibration decisions, each moving
the score part of the way. A single must-pass line used as the hardness dial turns pass rates into
a cliff (0/8 or 8/8); what a zeroing gate may be used for is grader-design M1.
Difficulty does not come from length, clutter, planted contradictions or hints either: frontier
models read through all of these, and they raise cost, not signal.
A penalty for inefficiency (tokens, steps, time), if there is one, is bounded and small next to
the outcome: its effect on behaviour is not linear in its size.
*Verify:* name the decisions that separate a 0.4 answer from a 0.8 answer on a train task; if the
only one is a gate, the difficulty is in the wrong place.

### I3. Matched no-action twins exist in every split [auto]
For planted tasks there are controls where the right move is to do nothing, matched in everything
visible. Report their share and the over-intervention rate from calibration.
*Verify:* audit.py counts `control = true` tasks per split (or the family's own twin marker).

### I5. Tasks in the family differ in what they demand
Not one solution replayed with new numbers: trap types, magnitudes and which ones co-occur vary;
fingerprints are unique; train can be generated at volume without repeats
(`python rl/build.py <f> --split train --n 200 --controls 20`, then count distinct fingerprints).

### I7. The family was checked as a set, not only task by task
A task can be good alone and poor beside its siblings: many tasks teaching the same idea, two
tasks rewarding opposite behaviour, a loophole shared by every task (which is far worse than one in
a single task), a lesson that only holds in this narrow setting.
*Verify:* for the split, tabulate trap types and which answer is right; look for a behaviour that
is rewarded in one task and punished in another with nothing visible to tell them apart; run each
grader exploit found on one task (grader-design E4) across the whole split.

---

## J. Splits, provenance and licences

### J1. `splits/check.py` passes for the family [auto]

### J2. A rebuild reproduces the committed manifest [auto]
`python rl/build.py <f>` then `git diff --exit-code -- rl/splits/manifests`.

### J3. The version was bumped for every change made in this session
major: the reward means something different; minor: what the model sees or the sandbox changed;
patch: metadata only (`families/README.md`, Versions).

### J4. Splits hold by company and by seed; nothing tuned on bench or held-out
A bench or held-out case you read, ran or debugged against while fixing a grader no longer
measures anything: list it under `retired:` in `splits/<source>.yaml` with the reason. Work on
train tasks so this does not come up.

### J6. Every gold input has a provenance entry, and all are approved [human]
`python rl/review/review.py review --reviewer <name>`.

### J8. The source's licence allows the intended use [human]
`licence.status` in `sources/<source>/source.yaml`.

### J9. Real data carries no personal information
Where a source holds records about people, de-identification was checked for quasi-identifiers
(dates, locations, rare combinations), not only for names. N/A for sources with no person-level
rows: say which sources were checked.
