# Lab-ready checklist

Every item has an id, what must be true, how to verify it in this repo, and what to do when it is
not. `scripts/audit.py` settles the items tagged **[auto]** and lists every other one as `MANUAL`:
those are yours to settle by reading and experiment. Items tagged **[human]** end in a decision
only a person may record; prepare the evidence and stop there.

Statuses: `PASS` (with evidence from this session), `FAIL`, `WARN` (holds, but weakly or by
heuristic: read it), `BLOCKED` (needs Docker, API spend or a person: say which, give the command),
`N/A` (say why), `MANUAL` (not yet looked at; never a final status).

Paths are relative to `rl/`. `<f>` is the family id, `<s>` the split.

## Contents

- A. Specification: what the agent is told
- B. Solvability and separation
- C. Isolation: airgap, point in time, clean reset
- D. Grading: world state, not claims
- E. Reward hacking
- F. Rubrics and model judges (judged families only)
- G. Evaluator tests
- H. Difficulty calibration
- I. Difficulty design
- J. Integrity, splits and contamination
- K. Release gates

---

## A. Specification: what the agent is told

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
*Verify:* audit.py flags long templates and coaching phrases (heuristic). Read the template and ask
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

### A6. The task is real work
It is something the `role` in its metadata does at a fund, with the inputs they would have, not a
puzzle built to be hard. In a judgment domain the gold holds what is not in the dataset: what the
expert finds non-obvious, what others miss, and the counterfactuals that would flip the call, not
only the final answer. A task is also not a job: real work runs through other people and several
steps, so the family's description claims the task it measures and no more.
*Verify:* the source's assignment and README; for research_design, gold records ruled-out objections.

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

---

## B. Solvability and separation

### B1. The reference solution passes every task, locally [auto]
A task whose own reference fails is a broken spec or grader, not a hard task.
*Verify:* `python rl/harness/run_solutions.py --split <s> --family <f>`; every reference
`status: ok` and at or above `calibration.pass`. Controls included.
*Fix:* find which of spec, reference, grader or threshold is wrong. Never lower a threshold to make
a reference pass without saying so in the report.

### B2. The reference passes inside the task's own image [BLOCKED without Docker]
*Verify:* `JUDGE=keyword python rl/harness/oracle_check.py` (the family's tasks in its `SAMPLE`), or
the Oracle workflow. The reward must equal the local one (`tests/expected_rewards.json`).
*Fix:* a package the image pins differently, a path only the container has.

### B3. The reference is clean-room [auto]
It imports only what the agent's image has and reads nothing grader-side (`/tests`, gold, seeds,
the generator). A reference that peeks proves nothing about solvability.
*Verify:* `splits/check.py` check 9.

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

---

## C. Isolation: airgap, point in time, clean reset

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

---

## D. Grading: world state, not claims

### D1. The verifier grades what exists, never what the agent said
It reads files the agent left and the behaviour of code the agent submitted. It never reads the
final message, a self-reported metric, or a "done" flag. Where the answer contains its own
evidence (in-sample errors, a count), the verifier recomputes it.
*Verify:* read the verifier: list every input it opens.

### D2. Any valid route to the right end state passes
No check on which tools or commands were used, no required intermediate files, no exact-string
match where equality of meaning is intended: numbers within a stated tolerance, dates and case
normalised, order-insensitive lists, an interval match for ranges.
A verifier that fails a valid alternative is a lazy verifier, and it teaches one route.
*Verify:* write two correct answers that differ in form (key order, date format, an equivalent
label, a different but valid method) and grade both.
*Fix:* normalise in the verifier; add the pair to the tests (G1).

### D3. Ground truth comes from `tests/`, not from anything the agent could edit
The verifier never re-reads `/app/data` as truth and never imports from `/app`.
*Verify:* the `tamper` attack; read the verifier's paths.

### D4. Reward is between 0 and 1; a crash is an error; an unavailable judge is "not graded" [auto]
Never a silent 0 and never a default pass.
*Verify:* `malformed` and `long` attacks do not crash the verifier (audit.py); read the judge-down path.

### D5. The code-graded reward is deterministic [auto]
The same answer graded twice gets the same reward. Any randomness in the verifier is seeded from
the task, not the clock.
*Verify:* audit.py grades the reference twice.

### D6. Code the agent submits runs without access to the gold
Where the verifier executes agent code (anomaly_scoring's scorer), that code runs as an
unprivileged user, with a minimal environment, unable to read `tests/` or write under
`/logs/verifier`, and with a timeout.
*Verify:* read how the verifier launches it; try a submission that opens `/tests/gold.json`.

### D7. Grading finishes inside its timeout on the largest task
*Verify:* time the verifier on the biggest input and on the `long` attack against
`verifier_timeout_sec`.

### D8. The gold is right, and does not contradict itself
An incorrect verifier is worse than none: gold agrees with the instruction and with the data the
agent sees, no two gold items conflict, and where a planted item overlaps a natural one the gold
says which counts. Tolerances match what the instruction promises.
*Verify:* solve two train tasks by hand, or read the reference's misses one by one: each
disagreement is either the reference's error or the gold's. Read every 0/k task with this in mind (H5).

### D9. Doing the right thing plus the wrong thing does not pay in full
A verifier that checks only for the wanted outcome is missing its other half. It also checks what
should not have happened: input data altered, files written outside the deliverables, an action
out of scope for the role, a step that failed but was counted because it was attempted, the right
record with the wrong field. Check resulting state, not that a call was made.
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

---

## E. Reward hacking

### E1. The family is in the attack suite [auto]
It has an adapter in `harness/attacks.py` (`FORMATS`); a family without one is not attacked at all.
*Fix:* write the adapter (outputs, placeholder, random, extreme, with_text).

### E2. Every generic attack scores at least the margin below good answers [auto]
`python rl/harness/attacks.py --split <s> --family <f>`: empty, malformed, placeholder, copy_input,
random, extreme, tamper, long, injection; plus padding, hedging, restating and stuffing where prose
is graded.

### E3. No constant policy passes on average
"Always A", flag everything, flag nothing, the base-rate answer, last period's value. Compute each
one's mean reward over the whole split including controls: flag-nothing rightly passes a control,
so the test is the family mean, and that planted tasks fail it individually.
*Verify:* `extreme` and `placeholder` cover some; write the missing ones as attacks.

### E4. A family-specific exploit hunt has been done and its findings are regression tests
Read the verifier as an adversary and list at least five ways to earn reward without doing the
work (see the list in SKILL.md). Try each. Every one that scores becomes a fix and every one tried
becomes an attack in `attacks.py`, so it stays closed.

### E5. Partial credit cannot be farmed
Cheap components (format valid, file present, length in range, sections present) do not sum to the
pass threshold, alone or together. Penalties can take a component below zero before the final
clamp, so spraying guesses costs more than it earns.
*Verify:* build the answer that collects every cheap point and nothing else; it must fail.

### E6. Passes are earned: transcripts have been read
For each calibration model, read at least three passing transcripts and three failing ones in
full. Every failure should look fair once read; every pass should have done the work. Look for:
guessing the generator, reading files it should not have, special-casing the verifier, timing out
after the answer was already written.
*Verify:* Harbor job folders under `runs/calibration/<s>/<run_id>/jobs/` (local, gitignored).
BLOCKED until a calibration run exists.

### E7. A loophole is a blocker, never a known limit
Reward hacking learned on one task transfers: a finance task with an exploitable grader can
degrade a model's behaviour in unrelated domains. Any attack that scores above the margin is fixed
or the affected tasks are withheld from training; it is not shipped with a note.

### E8. A grader exists that the training loop never sees, and shortcuts are watched for
Any grader used for RL or best-of-n selection is eventually gamed. Keep a check outside the reward
that training cannot optimise against: the held-out split with its secret seeds, a diagnostic
metric that is never blended in, or a second grader run only at evaluation. Name it in the report.
Alongside it, look in transcripts for shortcut behaviour (reading history or metadata, probing
`/tests`, editing inputs, searching for the generator) and plan to tighten the graders as models
improve: a grader that held for this year's models is not finished.
*Verify:* which metric or split plays this role for the family; that nothing in `reward` depends on it.

---

## F. Rubrics and model judges

N/A when no part of the reward or a reported metric comes from a model.

### F1. One atomic check per line, with an explicit bar and no judgment words [auto, heuristic]
No "appropriate", "adequate", "reasonable", "sufficient", "clear", "thorough", "well". Each line
names the observable thing that makes it pass. A line joined by "and" is two lines.
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

### F7. The judge is pinned and separate from the model under test [auto, partial]
Model, effort, votes and max tokens in `family.yaml` (`judge`), part of the instrument; no
fallback model; the anti-injection preamble on every call. The judge should come from a different
model family than the one being scored; where both are Anthropic models say so in the report as a
limit and lean on F9 and F10.

### F8. Order effects are neutralised
Comparisons are shown in both orders and score only when consistent; lists of items shown to the
judge do not put gold first.

### F9. The judge agrees with itself [BLOCKED without a key]
`python rl/harness/judge_stability.py --k 3 <task>=<output_dir> ...` on saved answers. Lines that
flip are rewritten (F1), not out-voted.

### F10. The judge agrees with people [human]
Hand-label 10 to 20 real traces to align the rubric with what the expert means; 50 to 100 expert
labels before trusting the judge's scores at scale; re-label when the agent or the rubric changes.
Report, per line, the catch rate (bad outputs the judge fails), the false-fail rate (good outputs
it fails) and kappa. Raw agreement hides both errors when most answers pass.
Until a second expert labels the same tasks this is a stated limit, not a pass.

### F11. Every rubric and any cheaper judge was tested vote by vote before paying for rollouts
The F3 answer, a known pass and a known fail, per line, before any calibration run.

### F12. The rubric has been through its rounds of drift, and they are logged
Reading traces changes what the criteria mean; expect two or three rounds before a rubric settles.
Each round is recorded (what was read, which lines changed and why:
`runs/<family>/reviews/feedback_log.md`), and labels made under an older wording are redone or dropped.

### F13. The quality rubric and the training reward are kept apart
A rich, judged quality measure is for understanding a model; the reward a policy climbs is
low-variance and hard to argue with. Where a judged score enters the reward, its weight is
bounded and stated (F4), and the full rubric is still reported separately as a diagnostic.

---

## G. Evaluator tests

### G1. Every evaluator has the four cases [auto, partial]
A known pass, a known fail, a paraphrase of each (same meaning, different form), and a negation
(the pass with its key claim reversed) in `tests/test_verifiers.py` or `tests/test_judge.py`.
audit.py only checks the family appears in the tests; read them for the four cases.

### G2. Reference and naive rewards are pinned [auto]
A sample of the family's tasks in `tests/expected_rewards.json`.

### G3. Changes are made one at a time, with the expected flips written down first
Before re-running after a grader or rubric change, list which pinned rewards and which attack
scores should move and which way. Anything else that moves is a bug. `UPDATE_EXPECTED=1` only for
the flips you predicted.

### G4. The suite is green [auto]
`pytest -m "not slow"` and `ruff check`; the full `pytest` before a release.

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

### H3. Screening is a ladder, not a flat k
k = 2, then 4, then 8, stopping early on a task at 2/2, 3/4 or 4+/8: it is too easy for on-policy
RL at that point and more rollouts are wasted.

### H4. Tasks sit in the mixed-outcome band [auto, when stats exist]
For the model being trained, target 1/8 to 3/8. 0/8 and 8/8 groups give zero advantage under
GRPO/RLOO. audit.py reads the latest `runs/calibration/<s>/*/stats.json` and reports the share of
tasks at 0, in band, above band and at k/k.

### H5. Every 0/k was audited for a harness or rubric bug before being called hard
Read the transcripts. Typical causes: an output path the agent could not have known, a timeout, a
tolerance, a judge line nobody could pass, wrong gold (D8). A task at 0/k for every model with no
bug needs supervised data first, not on-policy RL: say so rather than keep it. But don't write a
hard task off on a small k: a sparse pass rate is noisy (0/4 is consistent with a 1-in-8 task
about 6 times in 10), and some hard tasks are learned slowly. Look at the interval, not the count.

### H6. 0/k and k/k tasks are converted before new ones are authored
Move a too-easy task with the dials in section I; a too-hard one by fixing what H5 found.

### H7. Errors are infrastructure, and rare
`errored` near 0; refusals, truncations and timeouts are scored 0 and counted separately; the agent
timeout is not what decides pass or fail.

### H8. The reward is not a cliff, and models separate
The per-task score distribution is not just {0, 1} for a family meant to give gradient; the noise
floor is below the gap between models (`report.md`, Model separation).

### H9. Cost per rollout is known, and the family is judged on signal per dollar
Tokens, wall time and judge cost per attempt from the run records. A dearer task with mixed
outcomes beats a cheap one at 0/8.

### H10. The band was reached by changing tasks, never by bending the verifier
Write the right verifier first; then see where difficulty lands. Loosening a tolerance, dropping a
check or re-weighting the reward to pull a task into the band makes the number fit and the
measurement wrong. Every verifier or threshold change in this session has a correctness reason
stated in the report, independent of any pass rate.

### H11. Reliability and cost are reported, not only pass@1
pass^k (all k attempts pass) beside pass@k, both with bootstrap intervals (`calibrate.py report`
gives these), and cost per correct outcome (spend divided by passing attempts) from the run
records. Capability improves faster than reliability, and identical runs can differ many times
over in cost, so the spread of cost per attempt is reported too.

### H12. The result survives a reworded instruction
A paraphrase of the instruction with the same content (reordered, different wording, same
deliverables) gives a pass rate inside the noise of the original. A drop means the task was
measuring the phrasing.
*Verify:* build two or three train tasks with a paraphrased template into a scratch folder and
run the same k; do not commit the variant.

---

## I. Difficulty design

### I1. No single fatal gate decides the reward
The score comes from two or three non-fatal sizing or calibration decisions, each moving it part
of the way. A gate that zeroes the reward is there for integrity (foresight, look-ahead, a
contradiction between deliverables), never as the difficulty, and is recorded as such in `reward`.
A penalty for inefficiency (tokens, steps, time), if there is one, is bounded and small next to
the outcome: its effect on behaviour is not linear in its size.
*Verify:* read `reward` in `family.yaml`; over the attack and solution rows, how often is the
reward exactly 0 for an answer that did real work?

### I2. Difficulty does not come from length, clutter, planted contradictions or hints
Frontier models read through all of these; they raise cost, not signal.

### I3. Matched no-action twins exist in every split [auto]
For planted tasks there are controls where the right move is to do nothing, matched in everything
visible. Report their share and the over-intervention rate from calibration.
*Verify:* audit.py counts `control = true` tasks per split (or the family's own twin marker).

### I4. Positive and negative cases are balanced
Across the split, the correct answer is not predictable from base rates (E3).

### I5. Tasks in the family differ in what they demand
Not one solution replayed with new numbers: trap types, magnitudes and which ones co-occur vary;
fingerprints are unique; train can be generated at volume without repeats
(`python rl/build.py <f> --split train --n 200 --controls 20`, then count distinct fingerprints).

### I6. Where the job is pricing uncertainty, the reward prices it too
A reward that pays only for the point answer teaches overconfidence. If the deliverable carries a
range, a probability or a confidence, a proper scoring rule on it reaches the reward (or the
report states why it is a diagnostic only), an over-narrow interval costs more than an honest wide
one, and "not enough evidence" can be the best-scoring answer on the tasks where it is true.
*Verify:* grade the reference with its interval collapsed to the point, and with it widened tenfold;
see what moves.

---

## J. Integrity, splits and contamination

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
### J5. The canary is in every task and nowhere visible; contamination probes are run [auto, partial]
`harness/canary_probe.py`; `harness/memorisation.py` for families with named and disguised variants.
### J6. Every gold input has a provenance entry, and all are approved [human]
`python rl/review/review.py review --reviewer <name>`.
### J7. The instrument is approved at its current hash [human]
`python rl/harness/approve.py --family <f> --show`. Any fix to an instrument file reopens this;
that is the system working. Never run `--approve` yourself.
### J8. The source's licence allows the intended use [human]
`licence.status` in `sources/<source>/source.yaml`.
### J9. Only run records are committed
No transcripts, answers, gold, grading breakdowns, or an anonymised task's real company in git.

---

## K. Release gates

### K1. `python rl/splits/check.py --release` passes [auto; expected to fail until J6 and J7 are done]
### K2. The sign-off steps in `review/SIGNOFF.md` are done in order [human]
### K3. `release/CHANGELOG.md` and the family's `reward` text describe the family as it now is
### K4. Known limits are written down
Anything left `WARN`, `BLOCKED` or accepted as a residual risk appears in the readiness report and,
where it outlives the session, in `rl/README.md` (Known limits).

### K5. The family says what kind of measurement it is
Capability (can a model do this at all: hard, mixed outcomes), reliability or regression (does it
keep doing it: near-saturated, tracked with pass^k), or training. A task that saturates as a
capability measure moves to the regression set rather than being deleted. Passing a task in
isolation is not evidence for the workflow around it: say which of capability, reliability and
checkability of the output the family speaks to, in `rl/README.md`.
