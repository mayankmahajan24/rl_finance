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
client in the code (import scan; the run has no network), the write-up present. Then:

* **Confidence (half):** rows below 0.5 are distrusted. Untrustworthy rows: every day of a point anomaly or reviewed
  real problem; for a level shift, its first 14 days and the first 14 after a temporary one ends; the following days
  up to 45 are unscored while the code settles on the new level, after which the new level is trusted.
  0.5 x row F1 (precision vs per-problem day recall) + 0.5 x event F1 (alert precision vs problems caught).
* **Cleaned series (half):** for each planted problem, the share of the raw value's log error (vs the truth panel)
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

Review loop: `review_items.py` collects distrusted runs the gold can't explain, `explain.py` describes them,
`review_page.py` writes the verdict page; verdicts go to `reviewed.yaml`.

## History

* v2-style anomaly flags, kinds listed in the instruction: Opus 0.55, then 0.51 with the kinds removed.
* Lasting problems scored as changes (Option A) and a precision-minded instruction: Opus 0.75, 0.80 after the first
  review of its false alarms. Too easy; the task was redesigned to the current outputs (2026-11-18).
