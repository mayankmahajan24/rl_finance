# Reference solution: method note (work in progress)

Each source is compared with the median of its company's other sources, in log count and log ticket size, after
putting the peers on a common level (their trailing one-year relation to the company average). Company-wide moves
cancel. Residuals are measured in the source's own noise (trailing robust spread, net of its weekday pattern).

* Bad points (beyond 5 noise units, up to 3 days): distrusted, imputed from the peers.
* Level changes (persistent outliers, or a CUSUM at k=1, h=10): pending (distrusted, cleaned to the old level), then
  cancelled if the source comes back, or committed after 21 days if it moved against most peers one by one. A
  committed change is trusted from 30 days after its start and removed from the cleaned series while it lasts.
* Recurring moves (same dates a year or two earlier): trusted, kept.
* Low signal (trailing 28-day median under 20 transactions): confidence 0, blank.
* Two passes per company, the second against peers corrected by the first.

Checks: point in time by construction (a forward walk), confirmed by the grader's truncation check; tuned on tasks
001-002 only, reported on 003, 004 and the control. Packages: numpy and pandas (medians and a CUSUM are enough).

Known gaps: slow ramps are often missed, and a missed temporary ramp's return is then taken for a change; a company
with three usable sources, one of them genuinely broken (DDS), can still have a healthy source blamed.
