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

**Gates** (reward 0 if any fails): output format; point in time (outputs on truncated panels must match the full run,
all three columns); no model or network client in the code; a write-up; low signal dropped (at least 90% of the thin
start's rows distrusted and blank); detects (a confidence score of at least 0.25, so repairing
the series without detecting its problems cannot pass).

**What is graded**, six things:

| # | Measures | How |
|---|---|---|
| 1 | Catch the problems | recall: share of problems with any untrustworthy day distrusted; per kind (one-day kinds pooled), mean over kinds |
| 2 | No false alarms | alert precision: runs of distrusted days on a source (gaps up to 2 days joined, split every 14 days) that touch a problem |
| 3 | Repair problem rows | gain: per kind, share of the raw log error beyond the source's own noise that the cleaned series removes (pooled over the kind's problems), mean over kinds |
| 4 | Don't damage good rows | intact: share of untouched rows left within the source's own noise of the truth |
| 5 | Keep the history | kept: share of rows that should be kept not left blank |
| 6 | Stability | the scorer re-run on its own cleaned series raises no more alarms than on clean data (excess scaled by the size of the task's problems) |

**Reward** = 0.4 x confidence + 0.4 x cleaned series + 0.2 x stability, where confidence = F1(1, 2) and cleaned
series = 3 x 4 x 5. An ordinary weighted average; the three components are in the detailed metrics (and the
geometric mean, the reward before feedback #45, as `reward_geometric`), so a lopsided solution is visible. The
detection gate keeps cleaning-only solutions from scoring: without it, the reference's cleaned series with every row
trusted or distrusted would score 0.67 and 0.59.

**Timing rules** (what a point-in-time scorer could know):
* Scoring starts after a one-year warm-up.
* A problem counts from the day it first shows (trailing 7-day median deviation at 3x the source's noise); one that
  never shows is unscored; one that takes over 45 days to show is a slow build-up (cleaned series only).
* A level change: first 14 days untrustworthy, unscored to day 45 while the code decides, then trusted. After a
  temporary change ends, 45 days unscored, then trusted.
* The first yearly closure is unscored; later ones must be trusted.

**Isolation.** The grader runs agent code as `nobody`, with no network, in its own mount namespace where every shared
writable folder is empty (no memory between its five runs), and the task's `tests/` folder is root-only. A source's
own noise (`own_noise`) is measured on usable days only (28-day median at least 20 a day, against peers that are too).

**Not scored:** series too low-volume to grade, short windows around company-wide natural breaks in the underlying
data, and a few days either side of the thin start's edges.

## Results (all 13 tasks, 2026-11-24)

| Solution | What it is | All 13 | Held out (8) | Min |
|---|---|---|---|---|
| `oracle` | the answer key | 1.000 | 1.000 | 1.000 min |
| `ceiling_ideal` | the ceiling with exact imputation | 0.999 | 0.999 | 0.995 min |
| `ceiling` | gold-informed but realistic: a step caught on a 3-day median, ramps on a 14-day median, imputation with the source's own noise | 0.981 | 0.980 | 0.960 min |
| **`reference`** | hand-built point-in-time scorer (`solutions/reference/writeup.md`) | **0.939** | **0.938** | 0.883 min |
| `practitioner` | a plain ~200-line scorer: pairwise peer z-scores per weekday, CUSUM with rescaling, thin-start rule, yearly lookup, reason and adjustment columns (12 s a task) | 0.704 | | |
| Opus runs (8, Nov 20 and 23, older instructions) | fresh model solutions | 0.28 (0.08-0.50) | | |
| `trust_all_ref` | the reference's cleaned series, every row trusted | 0.231 | 0.250 | 1.0 on the 3 controls (correct there), 0 elsewhere |
| `distrust_all_ref` | the reference's cleaned series, every row distrusted | 0.000 | 0.000 | 0.000 min |
| `distrust_all` | every row distrusted, the answer key's cleaned series | 0.000 | 0.000 | 0.000 min |
| `naive` | do nothing (trust all, clean = raw; fails the low-signal gate) | 0.000 | 0.000 | 0.000 min |
| `exploit_gold_read` | agent code that looks for the answer key on disk | 0.000 | 0.000 | 0.000 min |

The exploit probes `exploit_memory` (memory between the grader's runs) and `exploit_selfrun` (recognising the re-run on its own cleaned series) score exactly the reference: neither channel exists.

Reference per task (reward and its three components; the geometric mean for comparison; the ceiling):

| Task | Reward | Conf. | Cleaned | Stab. | Geometric | Ceiling |
|---|---|---|---|---|---|---|
| 001 * | 0.944 | 0.917 | 0.975 | 0.937 | 0.915 | 0.975 |
| 002 | 0.883 | 0.789 | 0.927 | 0.984 | 0.848 | 0.966 |
| 003 | 0.961 | 0.957 | 0.967 | 0.957 | 0.941 | 0.974 |
| 004 * | 0.920 | 0.900 | 0.980 | 0.839 | 0.860 | 0.975 |
| control-01 | 1.000 | 1.000 | 1.000 | 0.999 | 1.000 | 1.000 |
| train-001 * | 0.926 | 0.917 | 0.902 | 0.991 | 0.905 | 0.991 |
| train-002 * | 0.913 | 0.833 | 0.958 | 0.984 | 0.886 | 0.968 |
| train-003 | 0.892 | 0.863 | 0.882 | 0.971 | 0.860 | 0.981 |
| train-004 | 0.933 | 0.863 | 0.972 | 0.995 | 0.914 | 0.980 |
| train-005 | 0.920 | 0.857 | 0.948 | 0.988 | 0.896 | 0.979 |
| train-006 | 0.915 | 0.800 | 0.992 | 0.989 | 0.886 | 0.960 |
| train-control-01 * | 1.000 | 1.000 | 1.000 | 1.000 | 0.999 | 1.000 |
| train-control-02 | 0.999 | 0.999 | 0.999 | 1.000 | 0.999 | 1.000 |

\* tuning tasks; the other eight are held out. On 45 newly generated train tasks (scale check): answer key 1.0 on all, do-nothing 0, ceiling 0.971 (min 0.878), reference 0.904 on a sample of nine (min 0.725: false alerts). The reference's main loss is false alerts (2-6 a task, around real company events, a source's early growth and inside slow ramps). What separates the three: false alerts per task (tuned reference 3, practitioner 17, Opus 120;
alert precision 0.78, 0.37, 0.10) and the cleaned series (0.96, 0.69, 0.67). The gap from a plain, sound approach
(0.70) to the tuned reference (0.94) is false-alert tuning and careful rescaling. The ceiling's gap to 1.0 is imputation noise (a repaired value carries the source's own noise): with exact imputation it scores 0.999.

## Run

```bash
python rl/experiments/anomaly_hard/build.py --n 4 --controls 1                 # bench tasks -> rl/tasks/proto/anomaly_hard/ (gitignored)
python rl/experiments/anomaly_hard/build.py --split train --n 6 --controls 2   # train tasks
python rl/experiments/anomaly_hard/grade.py rl/tasks/proto/anomaly_hard/anomhard-001 rl/experiments/anomaly_hard/solutions/reference
```

Model runs: `rl/experiments/anomaly_hard/runner/run.sh` (airgapped through `runner/offline.sh`).
