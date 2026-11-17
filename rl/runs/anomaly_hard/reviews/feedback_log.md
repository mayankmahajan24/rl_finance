# anomaly_hard grader feedback log

Your feedback on the anomaly_hard prototype (`rl/experiments/anomaly_hard/`), recorded verbatim with a date. Each entry
gets a disposition once it's acted on. Card verdicts and notes come from the flag review page (one entry per card
with a note); a card id is ticker-source-first flagged day, in original coordinates.

Disposition values: `open`, `rubric change`, `new programmatic check`, `case/gold change`, `reference change`, `no change` (with reason).

## Your feedback

| # | Date | Scope (case / rubric item / general) | Feedback (verbatim) | Disposition | Change made |
|---|---|---|---|---|---|
| 1 | 2026-11-17 | General (instruction) | the model shouldnt be told about the source of any errors, it should flag everything that's actually off. our grader should take this into account, i can manually grade this myself given the output to see if the remaining flagged items are real or fake (and if any were missed) and then we can add those back to the grader | instruction change, case/gold change | Instruction no longer lists error kinds; reviewed.yaml and the flag review page add reviewed real problems to the grader |
| 2 | 2026-11-17 | General (instruction) | the eventual task description will not have any hints on what the types of issues are so we dont need to look at those task runs. it may have a few examples (e.g. spikes) but is not going to list out the types of ways the data could be wrong. | no change | Review page shows only the neutral-instruction run |
| 3 | 2026-11-17 | Case DAL-2-2016-04-08 (verdict: real) | It's good that the model flagged the right errant days, but it continues to flag days after the errant period is fixed. I would not include prior flagged errant days in my baseline to flag new errant days, e.g. if there is a 3 day spike and then it coems back to normal (vs. history) then we should catch that pretty fast. | open | |
| 4 | 2026-11-17 | Case DAL-2-2016-09-26 (verdict: real) | This is clearly wrong, the model does not adjust to the new regime and continues to flag every data point. It should have flagged the dates when the model started changing regimes but should ahve figured out the new normal and benchmarked vs. taht | open | |
| 5 | 2026-11-17 | Case DAL-2-2016-12-17 (verdict: real) | I think this is real but the rule seems overly complicated - we could have just flagged on the weekly dip in counts not showing up this week. | open | |
| 6 | 2026-11-17 | Case DAL-2-2017-09-21 (verdict: not real) | Way too many flagged days.Visually not much seems wrong here. | open | |
| 7 | 2026-11-17 | Case DAL-2-2017-10-06 (verdict: not real) | Way too many flagged days. Too much indexing to other sources IMO, the counts and ticket sources feels totally in-line so the alert day doesn't feel wrong to me. | open | |
| 8 | 2026-11-17 | Case DAL-2-2017-10-16 (verdict: not real) | Not real to me, the raw time series look ok, except maybe a small shift down in the second half of the alert period. I think comparing to other time series only really makes sense for large moves, this one feels too sensitive. | open | |

Verdicts without a note (page): DAL-2-2016-12-04 not real; DAL-2-2017-07-23 not real; DAL-2-2017-01-29 not real (a
hinted-run card, no longer on the page, not used).
