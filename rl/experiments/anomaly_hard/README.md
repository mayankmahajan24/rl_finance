# anomaly_hard (prototype)

A hard anomaly-detection-and-repair task on card-transaction panels, built so frontier models do not saturate it.
Prototype: no manifest, CI, approval or Harbor packaging yet. Reviewer feedback, verbatim with what changed:
`rl/runs/anomaly_hard/reviews/feedback_log.md`. Earlier versions are in git history.

## The task (`instruction.md`)

A panel of companies, each reported by several independent sources (daily transaction count `ct` and dollars `amt`).
Write `score.py`: point-in-time code, no model or network calls at run time (it runs with the network off), that
outputs for every row

* `confidence` in [0, 1]: can this row be trusted? (below 0.5 = distrusted)
* `clean_ct`, `clean_amt`: a like-for-like cleaned series, what the source would have reported had it kept working
  normally; blank only for low-signal segments it discards,

plus a write-up. The instruction names the companies (name, ticker, industry) but no kinds of error and no patterns.
The script is graded on a hidden panel of **other companies** (industry-balanced), with their own disguised tickers,
dates and problems.

## The data (`build.py`, `background.py`, `perturb.py`)

**Semi-real background.** Each source = its company's real daily move (median of its sources) + the source's own
constant level + its weekday pattern + its real day-to-day noise (one-off glitches clipped at 3x its spread).
Seasonality, holidays, storms and company events stay real; every source-level oddity is planted, so the answer key
is exact. `truth_panel.csv.gz` is the hidden panel before the problems were planted.

| Planted per panel | What | Graded as |
|---|---|---|
| 2 each: volume spike, dropout, count flood, dollar spike | one source, 1-3 days (x2-5; to 1-5%; count x3-7; dollars x1.8-3) | untrustworthy; impute |
| 2 steps, 2 ramps (2-8 weeks) | one source's level moves (volume, count only, or dollars only), temporary or permanent | first 14 days untrustworthy; then rescale to the old level and trust |
| up to 2 slow ramps | one source moves x1.5-3 or x0.35-0.6 over 4-10 months, for good | cleaned series only (no datable onset) |
| 2 yearly closures | one source drops to 5-30% on the same date every year | normal: trust and keep (first year unscored) |
| 1 thin start | one source starts at 6-14 transactions a day for 450-700 days, then grows into coverage | low signal: must be dropped |
| 1 pull-forward wave, 1 company step | every source of one company | real events: trust and keep |

At most one lasting change per company, and no two level changes overlap on a company. Controls have no planted
problems (closures, thin start and real events only). 13 tasks: 5 bench (001-004, control-01) and 8 train
(train-001..006, two controls); seeds for held-out tasks live outside the repo.

## The grader (`grade.py`)

**Gates.** The task's reward is 0 if the output is malformed, the point-in-time check fails (outputs on truncated
panels must match the full run, all three columns), the code imports or calls a model or network client (parsed, so
prose that names one does not count), or the write-up is missing. A panel's reward is 0 if low signal is not dropped
(at least 90% of the thin start's rows distrusted and blank) or confidence is not a probability on a continuous scale
(rows scored strictly between 0.01 and 0.99 need at least 20 distinct values, none on more than half; stated in the
instruction since #96). The earlier detection gate (confidence at least 0.25) was removed: detecting nothing now
scores 0 on confidence by itself.

**Reward** (per panel) = 0.45 x confidence + 0.45 x cleaned series + 0.1 x stability; the task's data reward is the mean
over its three hidden panels (each with its own planted problems and disguise, so tuning to one does not pay).

| Part | How |
|---|---|
| Confidence | read as the probability that the row's cleaned value is right: within the source's own noise of the truth panel in count and ticket (right), beyond 2x in either (wrong), in between not scored. Brier in strata fixed before the outcome (each kind of planted problem: every row in its spans, right or wrong; and the fine rows outside every span), so a calibrated probability scores best; balanced skill (kinds averaged, then half and half with fine rows), floored at 0, times (0.5 + 0.5 x alert precision), an alert being true only if it touches a wrong row inside a problem's span. No timing windows (#89, #90). |
| Cleaned series | gain x intact x kept. Gain: per kind, the share of the raw log error (count and ticket, beyond the source's own noise) on problem rows that the cleaned series removes, mean over kinds. Intact: share of untouched rows left within the source's noise. Kept: share of rows to keep not left blank (blank counts as raw). |
| Stability | the code re-run on its own cleaned series (counts rounded, dollars to the cent, blanks dropped) and on the truth panel: 1 - (extra alerts on its own output) / (the panel's planted problems), floored at 0. |

**What is not scored** (no point-in-time code could know, or too ambiguous to grade): the one-year warm-up; series too
low-volume to grade; short windows around company-wide natural breaks in the underlying data; a source's thin
beginning (its own gate); a planted problem's days before it shows in the data (its trailing 7-day median deviation
reaches 3x the noise of a 7-day median of the source's relation to its sisters, `build.annotate_events`), and a problem
that never does. Everything else is scored by whether the cleaned value is right: a step is wrong until corrected, a
ramp while the correction lags, a return while the code still rescales; a company's real growth is never wrong.

**The report** multiplies the data reward by 0.5 + 0.5 x its score (`writeup.py`, `judge.md`: code items K1-K9 and a
model judge; 150-500 words; halved for a length outside that, a missing section or a missing chart). If the code fails
on the visible panel the report scores 0; only an unavailable judge leaves the data reward alone.

**Isolation.** The grader runs agent code as `nobody`, with no network, in its own mount namespace where every shared
writable folder is empty (no memory between its five runs), and the task's `tests/` folder is root-only. A source's
own noise (`own_noise`) is measured on usable days only (28-day median at least 20 a day, against peers that are too).

**Not scored:** series too low-volume to grade, short windows around company-wide natural breaks in the underlying
data, and a few days either side of the thin start's edges.

## Results (all 13 tasks, three hidden panels each, 2026-11-25)

> **Superseded.** Every number below was scored with the earlier confidence score (F1 of recall and alert precision)
> and the detection gate, before the changes of 2026-11-25/26 (#76-#87). They are kept for the record; current results
> are in notes.md (E34-E35) until this section is redone.

| Solution | What it is | All 13 | Held out (8) | Min |
|---|---|---|---|---|
| `oracle` | the answer key | 1.000 | 1.000 | 1.000 min |
| `ceiling_ideal` | the ceiling with exact imputation | 0.999 | 0.999 | 0.995 min |
| `ceiling` | gold-informed but realistic: a step caught on a 3-day median, ramps on a 14-day median, imputation with the source's own noise | 0.980 | | |
| **`reference`** | hand-built point-in-time scorer (`solutions/reference/writeup.md`) | **0.933** | **0.937** | 0.852 min |
| **`practitioner`** | a plain 258-line scorer, 12 knobs (`solutions/practitioner/writeup.md`): pairwise peer relation per weekday on the original basis, counting noise, spikes with one culprit, CUSUM changes confirmed on a 7-day median, yearly lookup, reason and adjustment columns (12 s a task) | **0.893** | **0.906** | 0.821 min |
| Opus runs (4, Nov 25, current instruction) | fresh airgapped model solutions, one per tuning task | 0.44 (0.14, 0.28, 0.66, 0.69) | 0.41 | 0.0 min |
| Opus runs (8, Nov 20 and 23, older instructions) | earlier model solutions | 0.26 (0.13-0.43) | | |
| `trust_all_ref` | the reference's cleaned series, every row trusted | 0.231 | 0.250 | 1.0 on the 3 controls (correct there), 0 elsewhere |
| `distrust_all_ref` | the reference's cleaned series, every row distrusted | 0.000 | 0.000 | 0.000 min |
| `distrust_all` | every row distrusted, the answer key's cleaned series | 0.000 | 0.000 | 0.000 min |
| `naive` | do nothing (trust all, clean = raw; fails the low-signal gate) | 0.000 | 0.000 | 0.000 min |
| `exploit_gold_read` | agent code that looks for the answer key on disk | 0.000 | 0.000 | 0.000 min |

The exploit probes `exploit_memory` (memory between the grader's runs) and `exploit_selfrun` (recognising the re-run on its own cleaned series) score exactly the reference: neither channel exists.

Reference per task (reward and its three components, means over the three panels) and the practitioner:

| Task | Reference | Conf. | Cleaned | Stab. | Practitioner |
|---|---|---|---|---|---|
| 001 * | 0.918 | 0.865 | 0.954 | 0.949 | 0.846 |
| 002 | 0.909 | 0.828 | 0.954 | 0.980 | 0.860 |
| 003 | 0.966 | 0.962 | 0.968 | 0.972 | 0.837 |
| 004 * | 0.867 | 0.882 | 0.849 | 0.873 | 0.850 |
| control-01 | 0.999 | 0.999 | 0.999 | 0.999 | 1.000 |
| train-001 * | 0.939 | 0.916 | 0.933 | 0.994 | 0.841 |
| train-002 * | 0.912 | 0.830 | 0.959 | 0.983 | 0.821 |
| train-003 | 0.908 | 0.846 | 0.930 | 0.988 | 0.878 |
| train-004 | 0.936 | 0.875 | 0.969 | 0.991 | 0.892 |
| train-005 | 0.927 | 0.875 | 0.949 | 0.988 | 0.884 |
| train-006 | 0.852 | 0.790 | 0.850 | 0.982 | 0.899 |
| train-control-01 * | 1.000 | 1.000 | 1.000 | 1.000 | 0.999 |
| train-control-02 | 0.999 | 0.999 | 0.999 | 0.999 | 0.999 |

\* tuning tasks; the other eight are held out. On 45 newly generated train tasks (scale check): answer key 1.0 on all, do-nothing 0, ceiling 0.971 (min 0.878), reference 0.904 on a sample of nine (min 0.725: false alerts). The reference's main loss is false alerts (2-6 a task, around real company events, a source's early growth and inside slow ramps). What separates the three is mostly confidence (mean over panels: tuned reference 0.89, practitioner 0.82, the
fresh Opus runs 0.32-0.53, with 2 to 29 of their 39 panels under the detection gate); the cleaned series is closer
(0.93, 0.93, 0.83-0.96). The practitioner keeps about five false alerts a panel against the reference's three. The ceiling's gap to 1.0 is imputation noise (a repaired value carries the source's own noise): with exact imputation it scores 0.999.

**Grader ablation (2026-11-25).** The cached outputs re-scored under six weaker graders (all 13 tasks, three panels):

| Variant | Reference | Practitioner | Opus (4 fresh runs) |
|---|---|---|---|
| current | 0.933 | 0.893 | 0.14 / 0.69 / 0.28 / 0.66 |
| no 14-day alert split | 0.933 | 0.894 | 0.42 / 0.73 / 0.76 / 0.68 |
| alerts joined across 7-day gaps | 0.933 | 0.892 | 0.14 / 0.71 / 0.28 / 0.66 |
| no stability (50/50) | 0.922 | 0.876 | 0.14 / 0.64 / 0.28 / 0.62 |
| confidence = mean(precision, recall) | 0.937 | 0.902 | 0.43 / 0.83 / 0.80 / 0.73 |
| no detection gate | 0.933 | 0.893 | 0.36 / 0.75 / 0.69 / 0.67 |
| noise tolerance x2 | 0.941 | 0.900 | 0.14 / 0.69 / 0.28 / 0.66 |

No part of the grader is dead weight that holds the practitioner back: the largest lift for it is +0.009. The alert
split, the F1 and the detection gate are what keep Opus low (the two weak runs distrust long stretches; 29 and 26 of
their 39 panels fail the gate). Keep the grader as it is.

**The report (2026-11-25).** The write-up is now graded: a 150-500-word report for the data scientists who use the
cleaned series, in six sections, with a chart of original vs cleaned series. Reward = data reward x (0.5 + 0.5 x report
score); code checks plus a model judge (`writeup.py`, `judge.md`, review in
`rl/runs/anomaly_hard/reviews/grader_2026-11-25.md`). The tables above are the data reward; the practitioner's
reference reports (`solutions/practitioner/reports/`) score 1.0 on train-001 and train-002.

**Run-to-run variance (2026-11-25).** Opus runs on the same instruction vary widely: 11 fully graded runs score
0.14 to 0.86 on the data reward (mean 0.44, standard deviation 0.26). Two runs on the same task and instruction
scored 0.17 and 0.82. The cause is how well each run flags, not how well it cleans. The cleaned-series score is 0.87
to 0.96 for every run, but the confidence score (alert precision and recall) ranges from 0.33 to 0.72 by run. Runs
near 0.35 raise many false alerts, and on more than half their panels confidence falls under the 0.25 detection
gate, so those panels score 0. Runs at 0.66 to 0.72 clear the gate on every panel. The gates make the gap look
sharper than it is, but they are not its main cause. Re-scoring the saved outputs shows this. A ramp instead of the
detection gate (x min(1, confidence / 0.4) per panel) lowers the spread only to 0.23. A gate on the task's average
confidence over its three panels leaves it at 0.26. Even removing the low-signal gate as well leaves 0.20. Neither
change was adopted (feedback #64). What the spread means:

- for training, attempts at the same task differ in quality, which gives a policy something to learn from;
- for evaluation, quote a mean over several runs per task with its spread, never one run.

## Run

```bash
python rl/experiments/anomaly_hard/build.py --n 4 --controls 1                 # bench tasks -> rl/tasks/proto/anomaly_hard/ (gitignored)
python rl/experiments/anomaly_hard/build.py --split train --n 6 --controls 2   # train tasks
python rl/experiments/anomaly_hard/grade.py rl/tasks/proto/anomaly_hard/anomhard-001 rl/experiments/anomaly_hard/solutions/reference
```

Model runs: `rl/experiments/anomaly_hard/runner/run.sh` (airgapped through `runner/offline.sh`).
