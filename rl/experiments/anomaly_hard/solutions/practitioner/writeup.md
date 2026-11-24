# Practitioner reference

**Approach.** Plain rules a data scientist would write for a downstream model, kept few and explained. Per company,
each source is compared with each sister source in log count and log ticket size: the day's difference minus that
pair's level for the weekday, set over the pair's first 112 days once both sources are established. The median over
sisters is the source's relation to the company on its original basis; company-wide moves, weekday patterns and one
sister's own problem drop out. Its noise is its robust day-to-day spread, widened on days when few transactions are
expected (counting noise).

**Confidence and cleaning.**
- *Low signal*: before a source has held 20 transactions a day (28-day median) for 90 days, days under 20 are
  discarded (distrusted, blank). A source that thins later is kept.
- *One-day problems*: more than 6 sigmas off: distrusted and imputed from the sisters at the source's own level. Not
  if the same source made a spike-sized move the same way near the same date a year or two earlier (a yearly
  pattern, left as reported). When several sources spike on one day, only the one furthest off is the problem.
- *Level changes*: a spike that lasts more than 3 days, or a CUSUM alarm confirmed by the last week's median, opens
  a change (unless it recurs at the same date each year). Distrusted for 14 days, then trusted as the source's new
  normal; the cleaned series keeps rescaling it to the original basis until it returns.
- Two passes: the second compares each source with its sisters' cleaned values, so one source's problem does not
  leak into the others.

**For the analyst.** Extra columns: `reason` (ok, low_signal, spike, level_change, rescaled, yearly_pattern) and
`adj_ct`, `adj_ticket` (the log adjustment applied). `--report` writes one line per change: source, channel, start,
end, size.

**Knobs.** Twelve, each with a meaning: the low-signal bar (20, 16, 90 days), warm-up and noise windows (56, 120
days), anchor length (112 days), spike bar (6 sigmas, as long as 3 days), change alarm and confirmation (12, 2
sigmas), distrust window (14 days), yearly slack (3 days).

**Checks.** Point in time by construction, confirmed by the grader's truncation check. Developed on the five tuning
tasks' 15 panels (0.630 to 0.871, one general rule at a time); on the 24 held-out panels, never used while
developing it, 0.906. About 12 seconds a task. numpy and pandas only.

**Known gaps.** About five false alerts a panel remain (the tuned reference has three), mostly change alarms on a
sister of a source that really shifted. Small dollar spikes on a source whose ticket is noisy against its sisters
are missed.
