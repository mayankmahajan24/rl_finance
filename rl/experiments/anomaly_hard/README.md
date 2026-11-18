# anomaly_hard (prototype)

A harder version of anomaly_scoring, to test whether frontier models can be pushed below a useful score. It
is not a family yet: no manifest, CI, approval or Harbor packaging. Proposed, for Mayank to review. The
task is the same as anomaly_scoring: write a `score.py` that flags bad rows in a panel it never sees, without
foresight. The flags are whatever that script outputs, graded by running it, so model reasoning earns nothing.

## Which perturbations, and why

The data is one company read by four independent sources (count `ct`, dollars `amt`, so ticket size `amt/ct`).
Bad data is a problem in one source. A real event moves every source of the company together. A perturbation is
used only if it fits that, and only at a size a careful scorer can see above the real noise between sources.
Noise was measured on the bench control panels (log units, a source vs the median of its company's other sources):

| Signal | Typical | Worst series |
|---|---|---|
| Daily count | 0.13 | 0.26 |
| Daily ticket size | 0.135 | 0.27 |
| Ticket-size drift over 90 days (90th percentile) | 0.09 | 0.25 |
| Weekly profile, per 8 weeks | 0.12 | 0.23 |

Planted in one source (labelled bad data, every day it touches), per panel:

| Kind | Per panel | What it does | Size on its days, in noise units |
|---|---|---|---|
| `card_testing` | 2 | count x3-7, dollars +$0.50-2.00 a transaction | count 3-33, ticket size -7 to -18 |
| `whale` | 2 | dollars +80-200%, count unchanged | ticket size 4-11, count ~0 |
| `settlement_lag` | 2 | 50-90% of a day moves to the next day or two | low day 8-23; catch-up days 1-12 |
| `feed_dropout` | 2 | count and dollars x0.4-0.65 for 2-4 days; half backfilled the next day | 3-11 a day, ticket size normal |
| `duplicate_batch` | 2 | adds 60-100% of the same day, the day before or the week before | count 3.6-9, ticket size normal |
| `fragmentation` | 1 | count ramps to x1.3-1.5 over 30-60 days, holds, snaps back; dollars unchanged; 90-200 days | sustained 1.4-4.7 a day |

`fragmentation` (instalments, BNPL) is sized x1.3-1.5, not the x1.05-1.30 proposed. Below about x1.15 it is lost
in normal ticket-size drift, so it is labelled from the day the count is 15% high.

Planted in every source of one company (real events, decoys, labelled good data), one of each per panel and on the
controls: `pantry_loading` (+60%/+40% then a week-long hangover that sums to zero) and `holiday_settlement` (40-90% of
a day settles the next day in every source).

Not used:
- **Day-boundary shift (local to UTC):** tried at 30-75% bleed. It moves the weekly profile by 0.08-0.24
  against 8-week noise of 0.12. Its effect on day-to-day autocorrelation (-0.29 to +0.23) is inside the natural range
  (90th percentile 0.38). It isn't detectable in the 45 days the scoring allows, so labelling it would grade guessing.
  data_audit's `dst_shift` (a whole-day redate) is the detectable version.
- **Privacy censoring:** suppressed days become missing rows, and a scorer can only score rows that exist. Series this
  low are already left out of scoring.
- **Month-end subscription compression:** real behaviour that hits every source, and at
  (31 - days in month) x the recurring baseline it is too small to matter as a decoy.

## Scoring (`grade.py`)

As anomaly_scoring v2 with the best grader:
- reward = (0.5 x row F1 + 0.5 x event F1) x coverage x no-foresight gate;
- a regime's 7 days after it ends aren't scored, and known real source-level artifacts are unscored to the panel's end;
- event recall is the mean over the 6 kinds, so each kind weighs the same;
- a short event counts if any of its days is flagged; `fragmentation` counts in full if flagged within 14 days of its
  labelled start, falling to nothing at 45;
- `decoy_fp` counts flags on decoy days.

`grade.py` runs the scorer without the Harbor sandbox, so grade only code copied out of its run folder.
`solutions/oracle` flags the gold's rows: it scores 1.0 on planted tasks and on the control, which checks the grader.

## Run

```bash
python rl/experiments/anomaly_hard/build.py --n 4 --controls 1     # rl/tasks/proto/anomaly_hard/ (gitignored)
python rl/experiments/anomaly_hard/grade.py rl/tasks/proto/anomaly_hard/anomhard-001 path/to/solution
```

The tasks use the bench split's companies with their own seeds (300001-300004 planted, 390001 control), outside
every family's seed ranges.

## First results (2026-11-17)

Existing code graded on 4 planted tasks and a control: the anomaly_scoring reference, and the two `score.py` files
Opus wrote for anomaly_scoring v2 (A from its 001 run, B from its 002 run; neither was written for these problems).
First grader (v0) -> current grader (v1):

| Task | Reference | Opus A | Opus B |
|---|---|---|---|
| 001 | 0.599 -> 0.415 | 0.298 -> 0.438 | 0.412 -> 0.679 |
| 002 | 0.119 -> 0.179 | 0.292 -> 0.401 | 0.855 -> 0.664 |
| 003 | 0.493 -> 0.387 | 0.270 -> 0.407 | 0.442 -> 0.714 |
| 004 | 0.267 -> 0.286 | 0.109 -> 0.333 | 0.401 -> 0.639 |
| control-01 | 0.885 | 0.971 | 0.993 |

- **v0's row recall was a fragmentation score:** fragmentation was 561 of 639 labelled days, so every scorer's
  recall sat near 0.1. v1's day recall weighs each kind equally.
- **The reference raises 92-104 alerts a panel, 86-88% of them false** (alert precision 0.13-0.14). v0 hid this
  because the false runs are short. Opus B raises 12-18 alerts with 56-75% true.
- **Spread across tasks is smaller under v1:** Opus B goes from 0.40-0.86 to 0.64-0.71, so tasks rank scorers more
  consistently.
- **Weakest kinds for every scorer:** fragmentation (days held) and whale days.

### A fresh Opus run on this task (2026-11-17)

Opus 5.5, subscription CLI, `ANTHROPIC_API_KEY` unset, given anomhard-001's instruction and visible data only, in a
folder outside the repo. It finished on its own in 22 minutes, wrote `score.py` and the note, and read nothing
outside its folder. Its `score.py` graded on every task's hidden panel:

| Task | v0 | v1 | Precision | Alert precision | Day recall | Event recall |
|---|---|---|---|---|---|---|
| 001 | 0.708 | 0.657 | 0.71 | 0.45 (9/20) | 0.77 | 0.81 |
| 002 | 0.795 | 0.629 | 0.77 | 0.38 (8/21) | 0.74 | 0.75 |
| 003 | 0.475 | 0.489 | 0.32 | 0.37 (10/27) | 0.76 | 0.92 |
| 004 | 0.286 | 0.425 | 0.29 | 0.33 (8/24) | 0.67 | 0.67 |
| control-01 | 0.962 | 0.962 | flags 0.19% of rows | | | |

Mean 0.55 on the planted tasks, with no-foresight passing everywhere. Told what to look for, Opus finds most problems:
it holds fragmentation on three tasks (58-97% of its days) but misses it entirely on 004. What it can't do is
avoid false alarms: 55-67% of its alerts touch no planted problem, and on 003-004 two thirds of its flagged
rows are false. One run, so the spread is unmeasured. Next: check whether those false alerts are real
unlabelled problems in the panel (that would be a grader ceiling, not model failure) before calling this hard.

### Opus with the neutral instruction (2026-11-17)

The instruction no longer lists the kinds of error ("flag everything that is actually off"). Same setup: anomhard-001's
visible data only, subscription CLI, nothing read outside its folder. It finished on its own in 73 minutes.
Its `score.py` on every task's hidden panel (v1 grader, before any review of real problems):

| Task | Reward | Precision | Alert precision | Day recall | Event recall |
|---|---|---|---|---|---|
| 001 | 0.406 | 0.16 | 0.43 (9/21) | 0.59 | 0.83 |
| 002 | 0.607 | 0.80 | 0.42 (8/19) | 0.59 | 0.75 |
| 003 | 0.341 | 0.11 | 0.33 (10/30) | 0.70 | 0.90 |
| 004 | 0.681 | 0.82 | 0.50 (8/16) | 0.71 | 0.75 |
| control-01 | 0.977 | flags 0.11% of rows | | | |

Mean 0.51 on the planted tasks (0.55 with the hinted instruction). Its unexplained alerts and the hinted run's,
105 in all, merge into 47 review items (26 from this run only, 17 from the hinted run only, 4 from both) for review
of whether they are real problems in the source data.

### Option A: a lasting problem is a change (2026-11-18)

Feedback log #9. A persisting problem (planted `fragmentation`, or a long reviewed one) is scored as a time series
monitor sees it: its first 14 days are bad data (event: onset), the days up to 45 from its start are unscored while a
scorer decides whether the new level is normal, and after that the shifted level is the normal level, so flags there are
false alarms; the return is labelled the same way (event: return). `grade.label_rows` holds the rule; the review tool
uses it too. The instruction now says this, with one example (a one-day spike or drop) and no list of error kinds.

The neutral run re-graded (it was written for the earlier "bad until normal" instruction, so this is a lower bound):

| Task | Before | Option A |
|---|---|---|
| 001 | 0.406 | 0.514 |
| 002 | 0.607 | 0.401 |
| 003 | 0.341 | 0.283 |
| 004 | 0.681 | 0.459 |
| control-01 | 0.977 | 0.977 |

002 and 004 drop because it held the fragmentation flag for its whole 128-145 days; 003 because it flagged the
fragmentation's return for 315 days. The review page now leaves off flags around planted problems (the grader decides
those) and takes a "worth flagging, but flagged too long" verdict with the days that were bad.

### Opus on the Option A instruction (2026-11-18)

Same setup, the instruction as it stands now (no list of error kinds, one example, the change/new-normal rule, "every
flag costs a researcher time"). Finished on its own in 28 minutes, nothing read outside its folder.

| Task | Reward | Precision | Alert precision | Day recall | Event recall |
|---|---|---|---|---|---|
| 001 | 0.716 | 0.82 | 0.73 (8/11) | 0.67 | 0.67 |
| 002 | 0.661 | 0.86 | 0.67 (8/12) | 0.53 | 0.67 |
| 003 | 0.817 | 0.84 | 0.79 (11/14) | 0.74 | 0.92 |
| 004 | 0.814 | 0.81 | 0.79 (11/14) | 0.76 | 0.92 |
| control-01 | 0.996 | flags 0.02% of rows | | | |

Mean 0.75, up from 0.41 for the run written for the old instruction. Told plainly that flags cost time and that a
lasting change becomes the new normal, it raises 3-4 false rows a task. What it still misses: the gradual count
drift (fragmentation: 0-19 of 28 labelled days, onset caught on 2 of 4 tasks), one task's feed dropouts, and half
the dollars-only days. Its 4 unexplained alerts are on the review page; two of them were also flagged by the earlier
run in 3-4 tasks.
