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
| 3 | 2026-11-17 | Case DAL-2-2016-04-08 (verdict: real) | It's good that the model flagged the right errant days, but it continues to flag days after the errant period is fixed. I would not include prior flagged errant days in my baseline to flag new errant days, e.g. if there is a 3 day spike and then it coems back to normal (vs. history) then we should catch that pretty fast. | no change | The days after a planted problem are already good data, so flags there count as false alarms; the card follows a planted problem and is left off the review |
| 4 | 2026-11-17 | Case DAL-2-2016-09-26 (verdict: real) | This is clearly wrong, the model does not adjust to the new regime and continues to flag every data point. It should have flagged the dates when the model started changing regimes but should ahve figured out the new normal and benchmarked vs. taht | rubric change | Option A (#9): a lasting problem is scored as a change and a return; the card is now graded by the grader (it follows a planted problem) and left off the review |
| 5 | 2026-11-17 | Case DAL-2-2016-12-17 (verdict: real) | I think this is real but the rule seems overly complicated - we could have just flagged on the weekly dip in counts not showing up this week. | case/gold change | In reviewed.yaml as real |
| 6 | 2026-11-17 | Case DAL-2-2017-09-21 (verdict: not real) | Way too many flagged days.Visually not much seems wrong here. | case/gold change | In reviewed.yaml as not real |
| 7 | 2026-11-17 | Case DAL-2-2017-10-06 (verdict: not real) | Way too many flagged days. Too much indexing to other sources IMO, the counts and ticket sources feels totally in-line so the alert day doesn't feel wrong to me. | case/gold change | In reviewed.yaml as not real |
| 8 | 2026-11-17 | Case DAL-2-2017-10-16 (verdict: not real) | Not real to me, the raw time series look ok, except maybe a small shift down in the second half of the alert period. I think comparing to other time series only really makes sense for large moves, this one feels too sensitive. | case/gold change | In reviewed.yaml as not real |
| 9 | 2026-11-18 | General (grader, instruction) | decision one - go with option A, it's on the model to figure out when a new normal has been established. think about this from a time series peerspetive. | rubric change | grade.label_rows: a lasting problem's first 14 days and the 14 days after it ends are bad data, days up to 45 from each are unscored, the settled level after that is normal; instruction says the same |
| 10 | 2026-11-18 | General (review) | Decision two - i need a way to denote that there was a change worth flagging but the days flagged were too many , and if the model had alerted on a smaller set and gone back to normal quicker that would be ok but you are alerting too much. go figure out how best to show this and thne we can regrade the neutral tasks | new programmatic check | Review page verdict "Worth flagging, but flagged too long" with a picker for the bad days (click the chart); only those days become bad data, flags outside stay false alarms |
| 11 | 2026-11-20 | General (grader, data) | for a couple of these the one day ticket size flag is too sensitive IMO, it's not like 50%+ different for somethign that can be more volatile (accounting for day of week / day of year seasonality). | case/gold change, new programmatic check | Those cards marked false alarms; planted one-day problems now clear 6x the source's own weekday-adjusted noise (single-measure level shifts 3x); triage groups one-day ticket moves under 6x own noise for a single verdict |
| 12 | 2026-11-20 | General (grader) | In others i find this year flagging but the same thing happened last year so feels like a real effect if it's recurring. understandably we might have flagged it the first time we saw it but the next year we should have more confidence it seems normal. and the cleaned series would leave them as is. | rubric change | New verdict "recurring": the first year a pattern appears in the data is unscored, later years must be trusted and left as they are; triage groups alerts that match a move a year earlier |
| 13 | 2026-11-20 | General (review) | can we enact the feedback we have so far from the cards? and think of the best way to provide feedback in the most efficient way instead of having to look at 60 charts | new programmatic check | Card verdicts in reviewed.yaml; triage.py sorts alerts into patterns (recurring, one-day ticket within noise, small vs own history, review) and the page takes one verdict per pattern with exclusions |
| 14 | 2026-11-20 | General (grader) | so whats the most efficeint way to notify on both false negatives and false positives in the best way to enhance the grader | new programmatic check | Detector pool over the real data (pool.py), Series Review page labelling each series once (series_page.py, apply_reviews.py), strict and lenient rewards for unjudged flags |
| 15 | 2026-11-20 | General | you can push these commits to the remote worktree branch. then let's kick off refining this with the goal of creating the best overall grader most efficienty | open | Push refused: no GitHub access from this session; grader refinement started (#14) |

Verdicts without a note, 2026-11-20 (in reviewed.yaml): DAL-3 2015-10-19 to 10-28 not real; DAL-3 2016-12-30 to 2017-01-05
not real; DAL-3 2017-04-12 to 04-13 not real; DAL-3 2017-12-30 real; DAL-3 2018-01-05 not real; DAL-4 2017-12-19 real;
DDS-1 2016-04-05 real; DDS-1 2017-01-24 to 01-27 real; M_M-1 2015-07-05 real; M_M-1 2017-03-21 to 03-22 real (alert was
03-23 to 03-24, not real); M_M-4 2018-02-01 real; M_M-4 2018-12-18 not real. Possible conflicts with #12, to confirm:
M_M-1 Christmas 2015 and 2016 both real; DAL-3 year end 2016-17 not real but 2017-12-30 real.

Verdicts without a note, 2026-11-18 (latest run's cards, all in reviewed.yaml): M_M-1-2015-08-04 real; M_M-1-2015-12-25
real; M_M-1-2016-12-25 real; M_M-4-2018-08-28 not real.

Verdicts without a note (page): DAL-2-2016-12-04 not real; DAL-2-2017-07-23 not real; DAL-2-2017-01-29 not real (a
hinted-run card, no longer on the page, not used).
