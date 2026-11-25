# Grader checklist

Every item has an id, what must be true, how to verify it in this repo, and what to do when it is
not. `rl-environment/scripts/audit.py --skill grader-design` settles the items tagged **[auto]** and
lists every other one as `MANUAL`. Items tagged **[human]** end in a decision only a person may
record. **[optional]** items are worth doing only when the budget allows. Ids are stable: a retired
or moved item leaves a gap.

Statuses: `PASS` (with evidence from this session), `FAIL`, `WARN` (holds, but weakly: read it),
`BLOCKED` (needs Docker, API spend or a person: say which, give the command), `N/A` (say why),
`MANUAL` (not yet looked at; never a final status).

Paths are relative to `rl/`. `<f>` is the family id, `<s>` the split.

This list covers what the grader pays for. What the agent can reach (files, network, tools, the
future) is on the `rl-environment` checklist. Whether the tasks are real, solvable, varied and
calibrated is on the `task-generation` checklist. Ids are unique across the three.

## Contents

- D. Verifiers: world state, not claims
- E. Red-teaming the grader
- F. Rubrics and model judges (judged families only)
- G. Evaluator tests
- M. Score shape and measurement

---

## D. Verifiers: world state, not claims

### D1. The verifier grades what exists, never what the agent said
It reads files the agent left and the behaviour of code the agent submitted. It never reads the
final message, a self-reported metric, or a "done" flag. Where the answer contains its own evidence
(in-sample errors, a count), the verifier recomputes it. Where the task is an action, it checks the
resulting state, including the arguments and the follow-through, not that a call was made.
*Verify:* read the verifier: list every input it opens.

### D2. Any valid route to the right end state passes
Two properties. Extensional: an output equal in meaning to the expected one passes, so numbers
match within a stated tolerance, dates and case are normalised, lists are order-insensitive, ranges
match by interval, and no exact string is required where meaning is intended. Isomorphic: the
reward does not change under a transformation that should not change it (key order, an equivalent
label, a different but valid method, a reworded sentence). No check on which tools or commands were
used and no required intermediate files: grade the deliverable, not the steps, because a step you
punish may be one the model was right to skip.
A verifier that fails a valid alternative teaches one route.
*Verify:* write two correct answers that differ in form and one by a different method; grade all.
*Fix:* normalise in the verifier; add the pair to the tests (G1).

### D3. Ground truth comes from `tests/`, not from anything the agent could edit
The verifier never re-reads `/app/data` as truth and never imports from `/app`.
*Verify:* the `tamper` attack; read the verifier's paths.

### D4. Reward is between 0 and 1; a crash is an error; an unavailable judge is "not graded" [auto]
Never a silent 0 and never a default pass.
Grading also finishes inside `verifier_timeout_sec` on the largest task and on the `long` attack.
*Verify:* `malformed` and `long` attacks do not crash the verifier (audit.py); read the judge-down path.

### D5. The code-graded reward is deterministic [auto]
The same answer graded twice gets the same reward. Any randomness in the verifier is seeded from
the task, not the clock.
*Verify:* audit.py grades the reference twice.

### D6. Code the agent submits runs without access to the gold
Where the verifier executes agent code (anomaly_scoring's scorer), that code runs as an
unprivileged user, with a minimal environment, unable to read `tests/` or write under
`/logs/verifier`, and with a timeout. It is also run on inputs the agent never saw, so code that
special-cases the visible data does not score.
*Verify:* read how the verifier launches it; try a submission that opens `/tests/gold.json`, and
one that returns hard-coded answers for the visible rows.

### D8. The gold is right, and does not contradict itself
An incorrect verifier is worse than none: gold agrees with the instruction and with the data the
agent sees, no two gold items conflict, and where a planted item overlaps a natural one the gold
says which counts. Tolerances match what the instruction promises.
*Verify:* solve two train tasks by hand, or read the reference's misses one by one: each
disagreement is either the reference's error or the gold's.

### D9. Doing the right thing plus the wrong thing does not pay in full
A verifier that checks only for the wanted outcome is missing its other half. It also checks what
should not have happened: input data altered, files written outside the deliverables, an action
out of scope for the role, a step that failed but was counted because it was attempted, the right
record with the wrong field.
*Verify:* take a passing answer and add a harmful side effect the role would be blamed for (edit
`/app/data`, write a second contradictory deliverable, overwrite an input). The reward must fall
or the trial must be flagged.
*Fix:* a state check in the verifier, and the case as an attack.

### D10. What the agent tells the reader is checked against what it did
A write-up, summary or message that claims work that was not done, or numbers the artifacts do
not support, costs reward: a model must not learn that lying to the user is free. (kpi_nowcast's
C36 is the pattern: figures in the brief must match the forecast JSON and the errors recomputed
from it.)
*Verify:* keep a passing answer's artifacts and rewrite its prose to overclaim; grade it.

### D11. Code grades whatever the output holds direct evidence for
A code check is cheap, deterministic and runs on every answer after every change. The order is:
code on the artifacts; then a claim check against the source documents; then a model judge, and
only for what needs judgment. A judged line that code could settle is moved to code. The reverse
mistake is avoiding a judge altogether: most real work cannot be fully verified by code, a
deterministic check and a quality judgment are different bars (two answers can pass the same
checks and differ in quality), and a calibrated judge is how the second gets measured.
*Verify:* for each judged line ask what a script would need to decide it. Lines about a number, a
date, a count, the presence of a field or agreement between two deliverables belong in code.

### D12. The verifier was written to check the job, not to hit a pass rate
No tolerance, weight, threshold or dropped check was chosen because of where it put the pass rate.
Bending a verifier toward a difficulty band usually costs verifier quality, and the model then
learns the bend.
*Verify:* `git log` on the verifier, grader and `family.yaml` `reward`: each change's reason is
about correctness. Any change made after a calibration run is read twice.
*Fix:* restore the check; move difficulty with task design (task-generation, section I).

---

## E. Red-teaming the grader

A grader exploit is an answer that scores without being the work. It usually means the task or the
scoring was underspecified, so the easiest way to raise the score is not what the designer meant.
The aim is not to make hacking impossible; it is to make the honest path the easier one. Any working exploit is a blocker,
not a note: reward hacking learned here transfers to other domains.

### E1. The family is in the attack suite [auto]
It has an adapter in `harness/attacks.py` (`FORMATS`); a family without one is not attacked at all.
*Fix:* write the adapter (outputs, placeholder, random, extreme, with_text).

### E2. Every generic attack scores at least the margin below good answers [auto]
`python rl/harness/attacks.py --split <s> --family <f>`: empty, malformed, placeholder, copy_input,
random, extreme, tamper, long, injection; plus padding, hedging, restating and stuffing where prose
is graded.

### E3. No constant policy passes on average
"Always A", answer true to everything, flag everything, flag nothing, the base-rate answer, last
period's value. When false values are rare, all-true scores well against a grader that only counts
agreement. Compute each policy's mean reward over the whole split including controls: flag-nothing
rightly passes a control, so the test is the family mean, and that planted tasks fail it
individually.
*Verify:* `extreme` and `placeholder` cover some; write the missing ones as attacks.
*Fix:* score both error types (a balanced or cost-weighted measure, or a penalty per false flag),
not raw agreement.

### E4. A family-specific exploit hunt has been done and its findings are regression tests
Read the verifier as an adversary and list at least five ways to earn reward without doing the
work (the prompts are in SKILL.md). Try each. Every one that scores becomes a fix and every one
tried becomes an attack in `attacks.py`, so it stays closed.

### E5. Partial credit cannot be farmed
Cheap components (format valid, file present, length in range, sections present) do not sum to the
pass threshold, alone or together. Penalties can take a component below zero before the final
clamp, so spraying guesses costs more than it earns.
*Verify:* build the answer that collects every cheap point and nothing else; it must fail.

### E6. Passes are earned: transcripts have been read
For each calibration model, read at least three passing transcripts and three failing ones in
full, from more than one model family: a case one model never triggers in 8 rollouts another hits.
Every failure should look fair once read; every pass should have done the work. Look for: guessing
the generator, special-casing the verifier, timing out after the answer was already written, a
pass the rubric paid for form.
*Verify:* Harbor job folders under `runs/calibration/<s>/<run_id>/jobs/` (local, gitignored).
BLOCKED until a calibration run exists.

### E8. A grader exists that the training loop never sees
Any grader used for RL or best-of-n selection is eventually gamed. Keep a check outside the reward
that training cannot optimise against: the held-out split with its secret seeds, a diagnostic
metric that is never blended in, or a second grader run only at evaluation. Name it in the report,
and plan to tighten the graders as models improve: a grader that held for this year's models is
not finished.
*Verify:* which metric or split plays this role for the family; that nothing in `reward` depends on it.

### E9. Near-miss copies of the reference fail
The generic attacks are junk built from scratch. This one starts from the right answer: take the
reference's output and make it wrong in known ways (numbers scaled, small noise, NaN or infinite
values, zeros, a constant, rows shuffled, half the rows, one field dropped, one sign flipped) and
regrade each. Two controls run beside them: the untouched output passes and an emptied one fails.
It finds tolerances that are too loose and fields the instruction asks for but the verifier never
reads.
*Verify:* by hand with `harness/local.py`'s `grade` on a train task. Read each accepted mutant
against the instruction: a field can be scale-invariant or unused by design.
*Fix:* tighten the tolerance or read the field; add the mutant as an attack.

### E10. A right answer with a wrong addition scores below the right answer
Take a passing answer and add something subtly wrong that takes away from it: a second figure that
contradicts the first, a wrong reason for a right call, a caveat that reverses the conclusion, an
extra flagged item that is not a problem. A grader that only looks for the right content pays this
in full, and the model learns that adding claims is free.
*Verify:* grade the pair; the spoiled copy must score lower, by a margin that shows in the reward.
For judged prose this needs the real judge (API spend).
*Fix:* a line or check for the contradiction or the false extra (see D9, D10); add the pair to G1.

### E11. Every exploit fix was re-checked against the reference
After each patch the reference and a second correct answer still pass, by execution. Hardening
makes graders stricter, and stricter graders start rejecting correct work.
*Verify:* `run_solutions.py` after every fix; the D2 pair in the tests.

### E12. The agent learns nothing from a rejection it can use to try again [optional]
If the setup lets an agent resubmit, a failed attempt is rejected in one line, without the reasons
or the history. N/A where the agent gets one submission and never sees the verdict.

---

## F. Rubrics and model judges

N/A when no part of the reward or a reported metric comes from a model.

### F1. One atomic check per line, with an explicit bar and no judgment words [auto, heuristic]
No "appropriate", "adequate", "reasonable", "sufficient", "clear", "thorough", "well", "timely".
Each line names the observable thing that makes it pass. A line joined by "and" is two lines.
*Verify:* audit.py lints `judge.md` and `graders/*.md`; read every flagged line.

### F2. Whether a line applies is decided in code, not by the judge
"If the task has consensus, ..." is computed from gold and the line is dropped or included before
the judge sees the rubric.
*Verify:* grep the rubric for "if", "when applicable", "na"; check the verifier.

### F3. An answer written without reading the record fails
Write the best generic answer you can from the instruction alone (no data opened): fluent,
well-structured, all the right headings and caveats. Grade it with the real judge. It must land
well below the pass threshold on every task tried. This is the single most revealing rubric test.
*Verify:* needs the judge (API spend, a few cents per answer): BLOCKED without a key and budget.
The offline `padding`/`restating` attacks are a weaker stand-in.

### F4. Easy lines cannot sum to a pass
Mark each rubric line easy (met by the F3 answer) or hard. Easy-only must fall short of the
threshold. Where the write-up multiplies or adds to a code-graded score, it cannot earn the reward
alone.

### F5. Partial credit climbs a dependency ladder
A line that only makes sense once an earlier one passes (the interpretation of a number that is
wrong) pays only if its prerequisite did. No floor that pays for showing up.

### F6. Verdicts are binary, with a way to say "cannot tell" [auto]
pass/fail per line, never a 1–5 scale; the schema offers an unknown/na verdict so the judge is not
forced to guess, and the code decides what unknown scores.

### F7. The judge is pinned, separate from the model under test, and no dearer than it needs to be [auto, partial]
Model, effort, votes and max tokens in `family.yaml` (`judge`), part of the instrument; no
fallback model; the anti-injection preamble on every call. The judge should come from a different
model family than the one being scored, since judges favour their own family; where both are
Anthropic models say so in the report as a limit and lean on F9 and F10. Among judges that clear
the catch-rate and false-fail bar in F10, the cheapest is the right one.

### F8. Order, length and self-preference are neutralised
Comparisons are shown in both orders and score only when consistent (a flip counts as a tie);
lists of items shown to the judge do not put gold first; a longer answer does not score higher for
its length (the `padding` attack); a clean answer beats its subtly broken copy (E10).

### F9. The judge agrees with itself [BLOCKED without a key]
`python rl/harness/judge_stability.py --k 3 <task>=<output_dir> ...` on saved answers. Lines that
flip are rewritten (F1), not out-voted: re-asking helps only up to three to five votes.

### F10. The judge agrees with people [human]
Hand-label 10 to 20 real traces to align the rubric with what the expert means; 50 to 100 expert
labels before trusting the judge's scores at scale; re-label when the agent or the rubric changes.
To measure the judge itself, label 30 to 50 good and 30 to 50 bad examples: with 40 examples a
measured 90% catch rate could sit anywhere from about 81% to 99%.
Report, per line, the catch rate (bad outputs the judge fails), the false-fail rate (good outputs
it fails) and kappa. Raw agreement hides both errors when most answers pass. Expert agreement is
the ceiling: experts regrade their own work differently some of the time, so the target is the
experts' combined verdict, not a higher number than they reach.
Until a second expert labels the same tasks this is a stated limit, not a pass.

### F11. The rubric is not fitted to the reference or to the answers it was tuned on
Each line is justified by what the task demands, not by a phrase or a method in the reference. A
second correct answer by a different method passes (D2). Answers used to revise the rubric are
kept apart from the answers used to say it works: revise on one set, then grade a set the rubric
has never been changed against, and report that number.
*Verify:* for each line, name the instruction sentence or practitioner habit behind it. Count how
many lines quote the reference. Grade the held-apart answers once, at the end.
*Fix:* rewrite the line in terms of the outcome; never add a line to fail one specific answer.

### F12. The judge is asked one criterion per call [partial]
Judges lose accuracy when one call scores four or five criteria. Each call names one failure, asks
for the evidence, and returns pass, fail or unknown.
*Verify:* read how `families/_shared/judge.py` batches lines. Where lines are batched for cost,
compare batched and one-per-call verdicts on saved answers and record the disagreement as a limit.
*Fix:* a change to shared judge code touches every family: propose it, do not make it in passing.

### F13. The judge sees the evidence and cites it
The judge is given what it needs to decide (the deliverables, the relevant source data, the gold
for that line) and points to the file, row or sentence that justifies each verdict. A verdict with
no citation is a guess, and a failure blamed on the model is sometimes a broken task.
*Verify:* read ten saved verdicts: each names where it looked.

### F14. The expert was asked what the dataset does not show, before the rubric was written [human]
What is non-obvious, what others miss, and which counterfactual would change the call. The gold
and rubric record those, not only the final answer. Every answer from the expert goes verbatim
into `runs/<f>/reviews/feedback_log.md` the same turn.
*Verify:* the feedback log has the elicitation; rubric lines trace to it.

### F15. A reported pass rate is corrected for the judge's own errors
A judge is a classifier. If it passes good work with probability s and fails bad work with
probability f, a reported pass rate p stands for a true rate of (p + f − 1) / (s + f − 1). A judge
that passes 95% of good work and catches 60% of bad work reports 80% when the truth is 73%. The
labels behind s and f must be a random sample (F10) or the correction is wrong.
*Verify:* the report gives s and f per rubric and both the raw and corrected rate, or says the
labels do not exist yet.

---

## G. Evaluator tests

### G1. Every evaluator has the four cases [auto, partial]
A known pass, a known fail, a paraphrase of each (same meaning, different form), and a negation
(the pass with its key claim reversed) in `tests/test_verifiers.py` or `tests/test_judge.py`.
audit.py only checks the family appears in the tests; read them for the four cases.

### G2. Reference and naive rewards are pinned [auto]
A sample of the family's tasks in `tests/expected_rewards.json`.

### G4. The suite is green [auto]
`pytest -m "not slow"` and `ruff check`; the full `pytest` before a release.

### G5. Every grader fix is locked in by two tests
The disputed case is now graded correctly, and a near-identical bad example still fails. The
second test stops a fix from simply making the grader more lenient.
*Verify:* each grader change in this session has both, in `tests/` or `attacks.py`.

---

## M. Score shape and measurement

### M1. The task score separates partial work; a hard zero is for disqualifying failures only
60% of the job and 80% of the job get different scores even when neither is a full pass.
Pass/fail lives at the rubric line (F6), not at the task. A gate that zeroes the task is reserved
for failures that disqualify the work (a fabricated figure in the final output, foresight,
look-ahead, a contradiction between deliverables), is recorded as such in `reward`, and is never
the thing that makes the task hard.
*Verify:* read `reward` in `family.yaml`; over the attack and solution rows, how often is the
reward exactly 0 for an answer that did real work?

### M2. The reward does not teach guessing (was I6)
Right-or-wrong scoring pays a guess more than "I do not know". Where the deliverable carries a
range, a probability or a confidence, a proper scoring rule on it reaches the reward (or the
report states why it is a diagnostic only), an over-narrow interval costs more than an honest wide
one, a confident error costs more than an abstention, and "not enough evidence" can be the
best-scoring answer on the tasks where it is true.
*Verify:* grade the reference with its interval collapsed to the point, and with it widened
tenfold; grade a confident wrong answer beside an abstention; see what moves.

### M3. A grader change is judged on the same answers, with an interval
Two grader versions are compared by regrading the same saved answers, not two fresh samples, and a
difference whose interval includes zero is noise. Scale matters: an 80% score on 500 binary
questions has a 95% interval of about 76.5% to 83.5%, and detecting a 5-point change at a 50% pass
rate takes about 1,570 independent tasks per version unless the comparison is paired.
*Verify:* the regrade command and the paired difference are in the report for any grader change
that was claimed to help.

### M4. One change at a time, with the flips written down first
Before re-running, write which pinned rewards, attack scores and saved verdicts should move and
which way. Anything else that moves is a bug in the change. Regressions are read before
improvements.
*Verify:* the report's "What was fixed" lists the prediction beside the result.

### M5. Several rewards on one task can all be met by one perfect answer
Where a task carries more than one reward, each is a binary function, none contradicts another,
and the reference meets all of them. Observed rewards are expected to be a little noisy; the
design does not depend on any single one being exact.
*Verify:* the reference's score on each component; look for two components that pull opposite ways.

### M6. What eval awareness does to the score was looked at
A model that believes it is being tested behaves more cautiously, so its score here is not its
behaviour in use, and training environments look like evals often enough that awareness should be
assumed likely. Transcripts where the model remarks that this is a test are counted and compared
with the rest; cleaner behaviour under suspicion is not reported as the true signal.
*Verify:* grep calibration transcripts for the model saying it is in an eval, test or benchmark;
report the share and whether scores differ. BLOCKED until a calibration run exists. Removing the
tells themselves is rl-environment C11.

