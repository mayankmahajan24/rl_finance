---
name: grader-design
description: Design, review and red-team the grading for an RL task or eval in rl/ — the verifier, rubric, model judge and reward — so the score pays for the work and nothing else. Covers turning a task and its deliverable into checks, writing rubric lines, choosing code versus a judge, building the probe answers that expose a weak grader (a right answer beside the same answer with a subtly wrong addition, near-miss copies of the reference, answer-true-to-everything and other constant policies, a fluent answer that never read the data, cheap-points-only), avoiding a rubric overfitted to its reference or tuning set, judge calibration against people, and grader regression tests. Use this whenever the user wants to write, change, tighten, test or sanity-check a verifier, grader, rubric, judge prompt, tolerance, weight or reward formula; asks how an answer should be scored, why something passed or failed, or whether a grader can be gamed; or mentions rubric lines, judge agreement, partial credit or grading feedback — even if they don't say "grader". Building out the task set (variety, difficulty, splits, licences) belongs to the task-generation skill, and what the agent can reach when a task runs (sandbox, leaks, tools, look-ahead, release) to the rl-environment skill.
---

# Grader design

A grader is sound when the reward goes up only because the work got better. This skill takes a
task and its deliverable to a verifier, rubric and judge that meet that bar, proves it with answers
built to break the grader, and leaves the proof behind as tests.

## What this skill owns

Three skills take a family to lab-ready, and each checklist item lives in exactly one. An
environment is a verifier, a world and a task set, built in that order, so the skills are used in
that order too, with the release gate last:

- **`grader-design` (here): what the score pays for.** Verifiers, rubrics, judges, reward shape,
  grader exploits, evaluator tests. The question is whether the grader paid for something that is
  not the work.
- **`rl-environment`: the world a task runs in.** Realism, leaks, network, tools, resets,
  harness, replay, and the release gate, which asks for this skill's report at the family's
  current version (its item K5) and does not re-check grading.
- **`task-generation`: which tasks exist.** Going from data and a sound grader to a set of tasks
  that are real, solvable, varied, calibrated, point-in-time, cleanly split and licensable.

## Ground rules

- **Work on train tasks.** A bench or held-out case you read, ran or debugged against while
  changing a grader no longer measures anything (`rl/splits/README.md`). Never open held-out gold.
- **A person signs; you prepare.** Mayank reviews verifiers, graders, gold and reference
  solutions himself. Pass thresholds, reward weights, what a task should measure, gold and
  instrument approval are his to record. Bring the evidence, a recommendation and the exact command.
- **Log grading feedback verbatim, the same turn.** Anything the expert says about a task, a
  rubric line or a grade goes into `rl/runs/<family>/reviews/feedback_log.md` word for word before
  you act on it.
- **Ask before spending.** The real judge and judge stability call a model. Get a budget first.
- **A status needs evidence from this session.** If a check cannot run here it is `BLOCKED` with
  the command, not assumed.

## Workflow

Steps 1 to 3 are for a new or redesigned grader. To review an existing one, read the verifier,
graders, `judge.md` and `family.yaml` `reward`, then start at step 4.

### 1. Say what good work is, before writing any check

Write, in a few lines: the deliverable (files, schema, units), the two to five decisions that
separate good work from bad on this task, and the failures that would disqualify the work outright.
A rubric built from decisions is short. A rubric built by listing everything in the reference is
long, pays for form, and fits one answer.

For judgment tasks the list comes from the expert, not from the data: what is non-obvious, what
others miss, which counterfactual would flip the call (checklist F14). Ask, and log the answer.

### 2. Put each requirement on the cheapest instrument that can decide it

1. **Code on the artifacts** for anything with direct evidence: a number, a date, a count, a
   field, agreement between two deliverables, a recomputed error.
2. **A claim check against the source data** for statements of fact in prose.
3. **A model judge** only for what needs judgment, one criterion per call.

Code is deterministic and free to re-run after every change; a judge is neither. Each judged line
you can move to code is one fewer line to calibrate (D11). Do not avoid the judge where judgment is
the point: passing every code check and being good work are different bars, and a calibrated judge
is how the second is measured.

### 3. Draft the rubric and the reward

- One observable check per line, pass or fail or unknown, with the bar written down and no
  judgment words (F1, F6). Split any line joined by "and".
- Decide in code whether a line applies; the judge never sees an inapplicable line (F2).
- Weight so the lines a generic answer can meet fall short of a pass, and pay dependent lines only
  when their prerequisite passed (F4, F5).
- Score both kinds of error where the answer is a set of flags or labels, so a constant answer
  does not win when one value is rare (E3).
- Keep pass/fail at the line and a gradient at the task. Zero the task only for a disqualifying
  failure, and say so in `reward` (M1).
- Justify every line by what the task demands. If a line exists because of how the reference
  phrased or solved something, rewrite it as the outcome (F11).

### 4. Build the probe set before tuning anything

Write these answers for two train tasks, and write the score each **should** get before grading
any of them. This is where most weak graders show, and it is cheap.

| Probe | Should score | Checks |
|---|---|---|
| The reference | pass | baseline (task-generation B1) |
| A second correct answer, different form or method | pass | D2, F11 |
| The reference with its key claim negated | fail | G1 |
| The reference plus a subtly wrong addition | below the reference | E10, D9, D10 |
| Near-miss copies: scaled, noisy, one field dropped, half the rows | fail | E9 |
| A fluent answer written without opening the data | well below pass | F3 |
| Each constant policy: all true, flag nothing, base rate, last value | fail on average | E3 |
| Every cheap point and nothing else | fail | E5, F4 |
| Passing artifacts with prose that overclaims | below the reference | D10 |
| Empty, malformed, very long, an injection aimed at the judge | 0, no crash | E2, D4 |

Then hunt for the family's own exploits (E4). An exploit usually means the task or the scoring was
underspecified; the aim is to make the honest path easier than the hack, not to make hacking
impossible. Read the verifier as an agent that wants the reward
without the work and write at least five concrete attempts before judging any:

- What does the verifier trust that I report? (my own error metrics, counts, a "done" flag)
- Which answer is right most often without looking? What does it average over the split, controls
  included?
- Which cheap parts pay? Do they sum to a pass?
- If it runs my code, can that code special-case the inputs it will be graded on?
- What can I add besides the answer that nobody checks?
- Where does the gold depend on something I could only guess?
- If a judge reads my text, can the text talk to it, bury it, or flatter the rubric?

Grade with `rl/harness/local.py`'s `grade`. Run the code-graded probes first, offline and free;
spend on the real judge only once those hold.

### 5. Run the mechanical items

```sh
python rl/build.py <family> --split train --n 3 --controls 1   # panel families; others: python rl/build.py <family>
python .claude/skills/rl-environment/scripts/audit.py --family <family> --skill grader-design --out <scratch>/grader.md
```

It runs offline and spends nothing: the attack suite, determinism, the rubric lint, and static
reads of the tests. Then open `references/checklist.md` and settle every `MANUAL` item, D to M.

### 6. Fix, without fitting

One change at a time:

1. Write down which probes, pinned rewards and attack scores should move, and which way, before
   re-running. Anything else that moves is a bug in the fix (M4).
2. Change the source (verifier, grader, rubric, `reward`), never a built task.
3. Lock it in with two tests: the disputed case now grades correctly, and a near-identical bad
   answer still fails (G5). Every probe and exploit tried becomes an attack in
   `rl/harness/attacks.py` or a case in `rl/tests/`.
4. Re-run the reference and the second correct answer. Hardening that rejects correct work is a
   new defect (E11).
5. Follow the version, rebuild and pin mechanics in `task-generation` ("Changing a family"): a
   grader change reopens the instrument's approval, and that is the system working.

Three habits keep the grader from being fitted to its own examples:

- **Hold answers apart.** Revise against one set of answers; report the result on a set the rubric
  was never changed against (F11).
- **Never add a line to fail one answer.** Find the property that makes the answer wrong and check
  that.
- **Never move a tolerance, weight or threshold to move a pass rate** (D12). Get the grader right,
  then see where difficulty lands; difficulty is changed by task design, in `task-generation`.

Stop and ask instead of fixing when the change is the owner's call: what the task measures, a pass
threshold, reward weights, or anything in shared code (`families/_shared/judge.py`, `harbor.py`).

### 7. Calibrate the judge against people

Judged families only, and it ends in a human step. Prepare: saved answers to label (a random
sample, good and bad), the per-line catch rate and false-fail rate once labels exist, judge
stability at k = 3, and the corrected pass rate (F9, F10, F15). Until labels exist these are
stated limits, not passes.

### 8. Report

Write to `rl/runs/<family>/reviews/grader_<YYYY-MM-DD>.md`:

```markdown
# Grader review: <family> (<version>, commit <sha>)

**Verdict:** sound | sound once signed (list) | not sound (list the FAILs)

## What good work is         (the decisions from step 1)
## Probe results             (the step 4 table: expected, got)
## What was fixed            <change> — predicted flips — result — the two tests
## Open: needs a fix
## Open: needs a person      (the decision, the evidence, the exact command)
## Open: needs budget        (the command and what it will show)
## Residual risks accepted
## Scorecard                 (every item D1–M6: status and one line of evidence)
```

No item may be left `MANUAL`. The report goes in git: no gold, no model answers, no real company
behind an anonymised task.

## Reference

- `references/checklist.md` — the full list, D1–M6. Read it in step 5.
- `../rl-environment/scripts/audit.py --skill grader-design` — the mechanical items and the scorecard.

Left out on purpose: metagraders, production A/B tests and continuously refreshed eval suites.
Nothing in this repo is deployed or graded at a volume that needs them.
