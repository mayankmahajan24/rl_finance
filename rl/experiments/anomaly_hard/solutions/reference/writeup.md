# Reference solution

**Model.** Per company and per channel (log count, log ticket size), all sources are walked forward one day at a time.
Each source is the company's daily move (median of the sources, each less its own level) plus its own level
(trailing median of its cleaned relation to the company, leaving out the latest 14 observations so a ramp cannot drag
it along) plus noise (trailing robust spread). Everything for day t uses only days up to t.

**Confidence.**
- *One-day problems*: a day more than 5.5 robust sigmas off, judged against the other sources only (leave one out),
  is distrusted and imputed from them. A day far outside the source's own history (5x its spread) that also stands
  out against its peers (2.5x) is distrusted too. A move the same source made within 3 days of the same date a year
  or two earlier is a yearly pattern (a closure): trusted and kept.
- *Level changes*: a CUSUM (k = 1, h = 7) on the clipped z opens an episode. It is distrusted for 14 days after
  detection, then trusted as the new normal while the cleaned series keeps rescaling it to the old basis.
- *Safeguards against false alarms*: at most half a company's sources can open an episode within 90 days (more is a
  company-wide move, such as a real store change); noise is widened and episodes frozen on days the whole company
  moves abnormally (holidays); a jump back to a level held in the past year re-anchors instead of opening an episode;
  a change must be at least 3x the source's usual month-to-month wander; a drift alarm on dates where the source
  alarmed a year earlier is seasonal; a peer far off on a day is left out of that day's company move.
- *Settling in*: a source in its first 120 days of a kept stretch (including after it comes back from being dropped)
  raises no alarms and does not help set the company's move, so growth out of a thin start is not read as a shift.

**Cleaned series.** Imputed values come from the other sources; an episode's offset (running 14-day median) is
removed so the source stays on its old basis. Slow drift is checked weekly: the last 28 observations against those
180-365 back, judged against the noise of the two medians; if the source moved at least 3x that, on two checks running
and against most of its peers one by one, it is rescaled to the old basis but not distrusted (its onset is long past).

**Low signal.** A source's thin beginning is discarded (distrusted, blank) until its trailing 28-day median count has
held 20 for 90 days, with hysteresis (kept from 20, dropped again under 16). A source that thins after it is
established is kept.

**Checks.** Point in time by construction, confirmed by the grader's truncation check. Re-run on its own output it
raises almost no new alarms (stability 0.87-1.0). Tuned on tasks 001, 004, train-001, train-002 and
train-control-01; the other eight held out. Reward 0.939 on all 13 tasks, 0.938 on the held-out ones (2026-11-24).
numpy and pandas only.

**Known gaps.** False alerts remain the main loss (2-6 a task, around real company events, a source's early growth
and inside slow ramps). A small single-measure step on a source whose ticket is noisy against its peers can be
missed. Slow ramps are rescaled late.
