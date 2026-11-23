# anomaly_hard (prototype)

A harder successor to anomaly_scoring, to find a task frontier models can't saturate. It is not a family yet: no
manifest, CI, approval or Harbor packaging. Proposed, for Mayank to review; his feedback is in
`rl/runs/anomaly_hard/reviews/feedback_log.md`.

## The task (`instruction.md`)

From one company panel (several sources, each reporting daily count `ct` and dollars `amt`), write point-in-time code
(`score.py`, no model or network calls at run time) that outputs, for every row:

* `confidence` in [0, 1]: can this row be trusted (does it carry usable signal, raw or adjusted)?
* `clean_ct`, `clean_amt`: a like-for-like cleaned series, what the source would have reported had it kept working
  normally, with untrusted rows imputed (only junk rows may be blank);

plus a write-up of how both are built, the packages used and why, and how they were checked. The instruction names
no kinds of error (one example: a one-day spike or drop) and does not say how a lasting change is scored: deciding
when a changed level is the new normal is left to the model.

## The data (`perturb.py`, `build.py`)

Bench companies, disguised (`build_panel`), with seeds outside every family's ranges. Each task has a visible panel,
a hidden panel from another random stream, the hidden panel before problems were planted (`truth_panel.csv.gz`: what
each source should have reported) and the gold. Only data moving up or down is planted; nothing shifts volume across
days.

| In one source (untrustworthy) | Per panel |
|---|---|
| Volume spike, x2-5 for 1-3 days | 2 |
| Dropout to 1-5% of normal for 1-3 days (the panel has no zero rows) | 2 |
| Count flood: count x3-7, dollars up $0.50-2.00 a transaction | 2 |
| Dollar spike: dollars x1.8-3, count flat | 2 |
| Level shift, immediate (step): volume x0.55-0.75 or x1.4-1.8, count only x1.3-1.6, or dollars only x0.6-0.75; temporary (60-240 days) or permanent | 2 |
| The same, over 2-8 weeks (ramp) | 2 |

| In every source of one company (real events: trusted, kept in the cleaned series) | Per panel |
|---|---|
| Pull-forward wave: +60%/+40%, then a trough that gives it back | 1 |
| Company step: stores opening or closing, x0.8-0.9 or x1.15-1.3 for good | 1 |

Sizes are set against the panel's measured noise (a source vs the median of its company's other sources, log units:
daily count 0.13, daily ticket size 0.135, 90-day ticket drift 0.09 at the 90th percentile). Real problems confirmed in
review (`reviewed.yaml`, original coordinates) are mapped into every task as untrustworthy rows.

Left out, from the list of effects considered: cross-channel cannibalisation (real behaviour between companies),
distribution-shape effects (daily totals show them only as the ticket-size shifts above), return waves, authorisation
mismatches and trade-down (company-wide or too small), and every timing or calendar effect (day-of-week shifts, payday
cycles, holiday shifts, quarter-end surges, settlement lags).

## The grader (`grade.py`)

Gates, reward 0 if any fails: output format, the point-in-time check on all three columns, no model or network
client in the code (import scan; the runs have no network), the write-up present. Then, in three parts:

* **Confidence (40%):** rows below 0.5 are distrusted. Untrustworthy rows: every day of a point anomaly or reviewed
  real problem, and a level shift's first 14 days; the following days up to 45 are unscored while the code settles on
  the new level, after which the new level is trusted. When a temporary shift ends the data is right again: the next
  45 days are unscored, then the source must be trusted. 0.5 x row F1 (precision vs per-problem day recall) + 0.5 x
  event F1 (alert precision vs problems caught).
* **Self-consistency (20%):** `score.py` run again on its own cleaned series and on the truth panel. Fixed (share of
  planted untrustworthy rows the first run distrusted and the run on the cleaned series trusts) x (0.5 x no new alarms
  (falls to zero when the cleaned series is distrusted on 1 point more of rows than the truth panel) + 0.5 x
  idempotent (falls to zero when re-cleaning moves the cleaned series 5% on average)).
* **Cleaned series (40%):** for each planted problem (and each reviewed real problem, against a hindsight reference from the full series), the share of the raw value's log error (vs the truth panel)
  that the cleaned value closes, averaged within and then across kinds; times a damage penalty that reaches zero when
  rows no problem touched move 5% on average.
* Unscored: before the warm-up ends, low-volume series, thin stretches (truth count's 28-day median under 10), near
  known natural artifacts. The write-up is judged separately.

Checks: `solutions/oracle` (the gold) scores 1.0 on all five tasks; `solutions/naive` (trust everything, clean = raw)
scores 0; a model import, a cleaned series that looks ahead, a 3% nudge to every value and blank imputations are each
caught.

## Run

```bash
python rl/experiments/anomaly_hard/build.py --n 4 --controls 1     # rl/tasks/proto/anomaly_hard/ (gitignored)
python rl/experiments/anomaly_hard/grade.py rl/tasks/proto/anomaly_hard/anomhard-001 path/to/solution
```

Review loop: `review_items.py` collects distrusted runs the gold can't explain; `trace_scorer.py` re-runs the scorer
instrumented and gives each card the scorer's own workings over the full history it had seen when it set the alert
(expected vs actual, residuals against the one-day line, drift evidence against the alarm, confidence, shift runs and
accepted new normals) and a reason from that state (`explain.py` is the fallback for scorers it doesn't understand);
`review_page.py` writes the verdict page; verdicts go to `reviewed.yaml`.

## History

* v2-style anomaly flags, kinds listed in the instruction: Opus 0.55, then 0.51 with the kinds removed.
* Lasting problems scored as changes (Option A) and a precision-minded instruction: Opus 0.75, 0.80 after the first
  review of its false alarms. Too easy; the task was redesigned to the current outputs (2026-11-18).

## Opus on the current task (2026-11-18)

anomhard-001's instruction and visible data only, subscription CLI, nothing read outside its folder; finished on its
own in 21 minutes and passed every gate. Its `score.py` on every task's hidden panel (before reviewing its alerts):

| Task | Reward | Confidence | Cleaned series | Precision | Alerts true | Clean gain | Damage penalty |
|---|---|---|---|---|---|---|---|
| 001 | 0.382 | 0.378 | 0.385 | 0.18 | 15/47 | 0.71 | 0.55 |
| 002 | 0.425 | 0.398 | 0.452 | 0.27 | 13/47 | 0.54 | 0.84 |
| 003 | 0.495 | 0.488 | 0.501 | 0.31 | 15/38 | 0.69 | 0.72 |
| 004 | 0.450 | 0.314 | 0.586 | 0.14 | 14/53 | 0.67 | 0.87 |
| control-01 | 0.511 | 0.044 | 0.978 | | | | |

Mean 0.44. It catches and imputes every point anomaly well (cleaned gain 0.84-0.99, except count floods on two tasks).
It fails at level shifts: it distrusts a shifted source for months after the change (most of its false rows, 54-296
days a task, sit around planted shifts) and does not rescale a shifted stretch back to the old basis (ramp gain 0.0-0.6,
step gain 0.0-0.7), and imputing its false alarms moves good rows 0.6-2.3% on average. The real-event decoys are left
alone (0-7 days). The 60 unexplained alerts are on the review page, recurring ones first.

Self-consistency added (2026-11-19): the same Opus scorer, re-graded: 0.412, 0.349, 0.443, 0.430 (mean 0.41;
control 0.609). On its own cleaned series it distrusts fewer rows than on the truth panel (0.04-0.09% vs 0.19-0.31%)
and re-cleaning moves it 0.01-0.02%, so its consistency score (0.24-0.67) is set by "fixed": the level-shift onsets
it never caught. Confidence fell (0.25-0.39) because distrusting a return to normal no longer earns credit.

Feedback #11-13 applied (2026-11-20): 13 more card verdicts in reviewed.yaml; planted one-day problems at least 6x the
source's own weekday-adjusted noise and single-measure shifts 3x; a `recurring` verdict (first year unscored, later
years trusted). The same Opus scorer re-graded: 0.549, 0.491, 0.453, 0.493 (mean 0.50; control 0.688), oracle 1.0.
Review is now by pattern (`triage.py`): of its 48 unexplained alerts, 8 recur a year earlier, 8 are one-day ticket
moves within the source's own noise, 31 are small against the source's own history, 1 (a sustained move) needs a card.

## Labelling the real data once (2026-11-20)

Reviewing one model's alerts only ever finds what that model flagged. Instead the real data (the bench companies'
20 series, original coordinates) is labelled once and every task inherits it:

1. `pool.py` pools independent detectors over the raw panel: three simple baselines (one-day move against the source's
   own history, one-day move against the other sources, slow drift against them) and any scorers given: only the
   latest task's solutions (now the current Opus scorer). It found 221 candidate stretches: 165 raised by one
   detector, 56 by two or more.
2. `series_page.py` writes the Series Review page: per series, its whole history, a strip per detector, the verdicts
   already made, the candidates with a suggestion from the standing rules (sustained -> look; recurs a year earlier ->
   recurring; one detector and under 6x own noise -> fine), free marking on the chart, and a "reviewed end to end"
   tick. Verdicts: bad, level change (scored like a planted shift: onset untrustworthy, then the new normal),
   fine, recurs yearly, unsure.
3. `apply_reviews.py` merges the page's verdicts into reviewed.yaml; `build.py` maps them into every task.
4. The grader reports two rewards: `reward` counts distrusted rows on unjudged real data as false alarms;
   `reward_lenient` leaves them unscored. Known rows: planted changes, real events, judged stretches, series reviewed
   end to end, and runs of flags that touch any of those.

The current Opus scorer: strict 0.549, 0.491, 0.453, 0.493 (mean 0.50); lenient 0.577, 0.535, 0.530, 0.545 (mean
0.55). Missing labels move its score by about 0.05: the task is not hard because the answer key is incomplete.

Thin bar raised to 20 transactions a day (feedback #18): 8% of rows unscored. Opus: strict 0.576, 0.513, 0.473, 0.511
(mean 0.52), lenient mean 0.57; oracle 1.0.

SAVE Series Review verdicts merged (10 spans; SAVE-2, -3, -4 reviewed end to end; 5 of 20 series now done): 56
reviewed entries. Opus strict unchanged (0.576, 0.513, 0.473, 0.511), lenient mean 0.56; control strict 0.786; oracle 1.0.

Reviewed real problems in the cleaned-series score (feedback #19): against a hindsight reference from the full hidden
series (`hindsight_ref`: the source's relation to its company's other sources, from 56 days either side of the
problem, or the 56 days before a lasting change; errors within the source's own noise in that relation not counted).
Oracle 1.0. Opus strict 0.560, 0.507, 0.473, 0.511 (mean 0.51), lenient mean 0.55; control strict 0.566 (was 0.786):
on the control the real problems are the only ones, and Opus leaves several (M_M-1's Christmas dropouts, 3-4
transactions against about 17 and 59 expected) unrepaired. DAL-1's level change sits inside the known-artifact
exclusion (from 2016-05-04), so it is not scored.

Feedback #20: reviewed series (end to end, or with a level change) are no longer dropped by the shared panel's
known-artifact list, so DAL-1's level change is graded (Opus's cleaned series closes about 0.83 of its error); M_M-1
Christmas is a recurring pattern. Oracle 1.0. Opus strict 0.557, 0.522, 0.465, 0.510 (mean 0.51), lenient mean 0.55;
control strict 0.670.

Thin stretches graded (feedback #21): under 16 transactions a day (28-day median of the truth count) a source must be
distrusted and left blank; 16-25 a day and two weeks either side of a thin stretch's edges are not scored. Opus trusts
and imputes nearly every thin day (day recall 0-1%, none left blank). Oracle 1.0, naive 0.0 on all five tasks. Opus
strict 0.523, 0.492, 0.436, 0.486 (mean 0.48), lenient mean 0.51; control strict 0.410.

Feedback #22: the instruction states the goal (a usable like-for-like series, maximum history; low-signal segments
may be discarded). Cleaned-series score x history kept (`BLANK_TOL` 5% of rows that should be kept left blank).
Opus blanks nothing, so its scores are unchanged (strict mean 0.48); oracle 1.0, naive 0.0; the oracle with every
10th day blanked scores 0.19.

## Reference solution and fresh Opus runs (2026-11-20, work in progress)

`solutions/reference/` is an honest scorer (reads only its input) built from the reviewer's rules; tuned on tasks
001-002, reported on 003, 004 and the control. Strict: 001 0.601, 002 0.493 (tuning); 003 0.475, 004 0.318,
control 0.582 (held out). Its weak points: slow ramps, a missed temporary ramp's return taken for a change, and DDS
(three usable sources, one genuinely halved for years and not reviewed) where a healthy source gets blamed (004:
damage 9.7%, cleaned-series score 0).

Fresh Opus runs on the current instruction (subscription CLI, each from one task's instruction and visible data),
graded on all five tasks, strict: run on 001: 0.594, 0.581, 0.666, 0.582, control 0.721; run on 004: 0.572, 0.567,
0.610, 0.515, control 0.585. Both discard and blank every thin stretch and barely touch good rows (damage under
0.1%). Neither honest solution passes about 0.67: the ceiling for point-in-time code is well under 1.0.

All four fresh Opus runs (2026-11-23; each written on one task, graded on all four planted tasks), strict mean:
0.606, 0.506, 0.518, 0.566 (overall 0.55; lenient 0.57); controls 0.48-0.72. Every gate passed. Confidence 0.40-0.67,
cleaned series 0.53-0.73, self-consistency 0.43-0.60.

Feedback #23: DDS-3's fall from 2015-10-16 is a reviewed lasting level change (scored like DAL-1). Thin data must be
dropped only before a source is established (median at 20 or more for 90 days running) or when it never is; a source
that thins later is kept (cleaned series scored, confidence not).
Re-graded after #23 (oracle 1.0, naive 0.0 on all five): Opus runs strict mean 0.583, 0.490, 0.504, 0.560 (overall
0.53), controls 0.47-0.68; reference 0.469, control 0.579.

## Ceiling: the best a point-in-time scorer could plausibly do (2026-11-23)

`solutions/ceiling` reads the gold like the oracle but acts only as an excellent past-only detector could: a row is
judged by its deviation from what it should read, in units of the source's own noise against its peers; one-day
problems are caught on the day only above 3 sigma; level changes once their trailing 3-day median passes 2 sigma
(ramps late), then rescaled; a temporary shift's end is missed for 3 days; imputed values carry the source's own noise
(`solutions/ceiling_ideal`: exact imputation). Strict reward on the planted tasks: 0.751, 0.720, 0.765, 0.812 (mean
0.76), control 0.806; ideal 0.828, 0.783, 0.830, 0.876 (mean 0.83), control 0.829.

So the reachable range is about 0.76-0.83, not 1.0: Opus (0.53) is at about 70% of it and the reference (0.47) at 62%.
What still caps the ceiling: event F1's alert precision (every short false alert counts as much as a true one), the
consistency score's "fixed" (a missed problem also fails "fixed", so misses count twice), and ramps caught late.

Feedback #24: alert precision weights each alert by min(1, days / 7). Strict planted means: ceiling 0.81 (control
0.86), Opus runs 0.588, 0.508, 0.520, 0.573 (0.55), oracle 1.0, naive 0.0. Reference rebuilt (one model per channel,
the safeguards Opus's write-up described, plus the peer vote): 0.590, 0.493 (tuning), 0.440, 0.491 (held out),
control 0.574; mean 0.50, up from 0.47. Its losses: damage from wrong offsets (penalty 0.36-0.98), "fixed" 0.39-0.45,
slow ramps.

## What the task is for, and the simplified grader (2026-11-23)

The point: can a model write production-grade, point-in-time code that turns a noisy multi-source panel into
something a researcher can rely on, generalising to data it has not seen? Two deliverables carry that: (1) the rows
that cannot be trusted are flagged, and nothing else; (2) a cleaned series that is right, like for like, keeps as much
history as possible, and is stable when the code is run on its own output. The rest (gates, Option A for lasting
changes, hindsight references for reviewed real problems, the thin-data rule) is what makes those two measurable.

Over-specified metrics removed from the reward (still reported in the details): event F1 (restates row F1: day
recall is counted per problem, so a late catch already loses the days it went uncaught; alert precision restates
row precision), the consistency score's "fixed" (a missed problem penalised a second time) and its separate 20%
weight (stability is a property of the cleaned series). Reward = 0.5 x confidence (row F1) + 0.5 x cleaned series
(gain x damage penalty x history kept x stability), stability = 0.5 x no new alarms + 0.5 x idempotent.

| Strict reward | 001 | 002 | 003 | 004 | planted mean | control |
|---|---|---|---|---|---|---|
| oracle | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| ceiling (best plausible point-in-time) | 0.853 | 0.848 | 0.867 | 0.889 | 0.864 | 0.887 |
| reference (from the best Opus run, improved) | 0.762 | 0.745 | 0.803 | 0.769 | 0.770 | 0.790 |
| Opus run on 001 | 0.508 | 0.469 | 0.547 | 0.518 | 0.510 | 0.520 |
| Opus run on 002 | 0.496 | 0.320 | 0.404 | 0.377 | 0.399 | 0.478 |
| Opus run on 003 | 0.459 | 0.424 | 0.525 | 0.490 | 0.475 | 0.341 |
| naive | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

The reference is tuned on 001-002 and scores as well on the held-out tasks: 89% of the ceiling. Opus is at 46-59% of
it. The reference's write-up says what was changed from the Opus run and why; the biggest single change is the
reviewer's lasting-change rule (trust a settled new level), which Opus missed.

## Across more companies: the train split (2026-11-23)

`build.py --split train` builds from the 8 train companies (AAL, ALGT, HA, LUV, UAL, JWN, ROST, TJX; each task draws 8
of their 10 series groups); 6 planted tasks and 2 controls, about 56,000 rows each. None of their real data has been
reviewed, so strict counts flags on real problems as false alarms (lenient leaves them unscored) and no real problem's
cleaned values are scored. Held-out companies are not used.

| Strict reward, train split | 001 | 002 | 003 | 004 | 005 | 006 | mean | lenient | controls |
|---|---|---|---|---|---|---|---|---|---|
| oracle | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | | 1.0, 1.0 |
| ceiling | 0.800 | 0.875 | 0.873 | 0.863 | 0.852 | 0.852 | 0.853 | | 1.0, 1.0 |
| reference | 0.848 | 0.768 | 0.852 | 0.779 | 0.835 | 0.868 | 0.825 | 0.839 | 0.905, 0.951 |
| Opus run on 001 | 0.586 | 0.544 | 0.723 | 0.690 | 0.754 | 0.782 | 0.680 | 0.688 | 0.974, 0.989 |
| Opus run on 004 | 0.630 | 0.531 | 0.746 | 0.556 | 0.729 | 0.599 | 0.632 | 0.643 | 0.964, 0.977 |
| Opus run on 002 | 0.320 | 0.416 | 0.327 | 0.572 | 0.513 | 0.694 | 0.474 | 0.528 | 0.673, 0.810 |
| Opus run on 003 | 0.365 | 0.130 | 0.140 | 0.547 | 0.240 | 0.553 | 0.329 | 0.379 | 0.351, 0.774 |
| naive | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0, 0 |

The reference, tuned only on bench tasks 001-002, scores 0.825 on companies it never saw (97% of the ceiling; on two
tasks it beats the ceiling, which is a plausible best, not a bound: its imputation carries the source's own noise).
Opus's runs spread from 0.33 to 0.68. Fixed on the way: a task with no reviewed real problems gave the hindsight
reference an untyped empty table, which broke the oracle's merge.
