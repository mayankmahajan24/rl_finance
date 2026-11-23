# Reference solution: method note

**Provenance.** Started from the best fresh Opus run on this task (written on anomhard-001's visible data, 2026-11-20;
strict 0.51 under the current grader), then improved by hand. The earlier hand-built references are in git history.

**Model.** Per company, per channel (log count, log ticket size), all sources walked forward together one day at a
time: each source = the company's daily move (median of the sources, each less its own level) + its own level
(trailing median of its cleaned relation to the company) + noise (trailing robust spread). One-day outliers
(robust |z| > 4.5) are imputed from the other sources; persistent shifts (CUSUM, k = 1, h = 7) open an episode whose
offset (running 14-day median) is removed, keeping the source on its old basis. Safeguards from the original: at most
half the usable sources in an episode at once (more is a company-wide move); episodes frozen and noise widened on
upheaval days (holidays, closures); a jump back to a level held in the past year re-anchors the baseline instead of
opening an episode; an episode closes when the source is back near its old basis.

**What changed from the Opus run, and why.**
1. A level change is distrusted for 25 days after it is detected, then trusted as the new normal (still rescaled):
   the reviewer's rule for lasting changes. The original distrusted every day of an episode (confidence precision
   0.15-0.21; this alone took the reward from about 0.49 to 0.72).
2. Thin data: only a source's thin beginning is discarded (until its median has held 20 a day for 90 days, with
   hysteresis: kept from 25, dropped again under 16); a source that thins later is kept (reviewer's rule).
3. One-day problems are also judged against the source's own history (beyond 5x its own spread, and beyond 2.5x
   against its peers so real company moves stay trusted): catches ticket spikes on sources whose ticket is noisy
   against peers.
4. One-day problems are judged and imputed against the other sources only (leave one out): with three usable sources
   the median includes the source itself and halves its own spike.
Tried and dropped (no consistent gain across tasks): a lagged level baseline for ramps; leave-one-out offsets inside
episodes; leave-one-out everywhere (noisier drift detection, more false episodes).

**Checks.** Point in time by construction (forward walk), confirmed by the grader's truncation check. Re-run on its own
output it moves the series 0.1-0.5% and raises no new alarms. Tuned on tasks 001-002; 003, 004 and the control held
out (they score as well or better). numpy and pandas only.

**Known gaps.** Slow ramps are caught late (gain 0.2-0.65); a single-measure step on a source whose ticket is noisy
against its peers can be missed; small reviewed real problems inside a source's noise are missed (recall 0.55-0.7).
