# Reference solution: method note

One model per channel (log count, log ticket size), all of a company's sources walked forward together one day at a
time: x[s,t] = m[t] + L[s] + w[s, weekday] + noise. m is the company's move (median of the other usable sources, each
less its own level; peers that are outliers today left out), L the source's level (trailing median of its cleaned
relation to the company), w its weekday pattern. Residuals are in the source's own noise (trailing robust spread).

* Bad point (|z| > 4.5): distrusted, imputed with the expectation.
* Level change (more than 3 outlier days of one sign, or a CUSUM at k=1, h=7): an episode with offset delta; rows are
  raw - delta (the source's old basis), delta follows a 14-day running median, and the episode closes when the
  source is back within 40% of the largest offset it reached. Distrusted for 30 days from the start, then trusted.
* Safeguards: a change must beat 0.15 and 2x the noise of a median over its days; the source must have moved against
  most of its peers one by one; at most half a company's sources in an episode at once (more is company-wide: reset);
  no episode opens on upheaval days (the company's move against recent same weekdays over 1 log unit); a jump back to
  a relation held in the past year, after being well away from it, re-anchors the baseline instead of opening one; a
  source back after 60 days without usable data starts its warm-up again.
* Recurring: an outlier where the same source moved the same way a year or two earlier is trusted and kept.
* Low signal: before a source is established (28-day median at 20 or more for 90 days running) it is dropped while
  thin, with hysteresis (kept from 25, dropped again under 16); a source that dips later is kept.

Checks: point in time by construction, confirmed by the grader's truncation check; re-run on its own output it moves
the series 0.1-0.2% and raises no new alarms. Tuned on tasks 001-002, reported on 003, 004 and the control. Packages:
numpy and pandas only.

Known gaps: slow ramps are caught late or not at all; a planted count-only step can be missed when the ticket channel
absorbs it; small real one-day problems inside a source's noise are missed; with three usable sources, one genuinely
broken, a healthy source can still pick up a wrong offset.
