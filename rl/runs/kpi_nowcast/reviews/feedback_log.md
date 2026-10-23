# kpi_nowcast grader feedback log

Your feedback on the tasks and grading, recorded verbatim with a date. Each entry gets a disposition once it's acted on. Nothing here changes the frozen reference run (`~/ual_passenger_revenue_eval/frozen_run_v1`), which stays read-only. Grader changes made from these entries go through the usual harness diff and re-approval.

Disposition values: `open`, `rubric change`, `new programmatic check`, `case/gold change`, `frozen-run note` (recorded about the reference run, no change), `no change` (with reason).

## Your feedback

| # | Date | Scope (case / rubric item / general) | Feedback (verbatim) | Disposition | Change made |
|---|---|---|---|---|---|
| 1 | 2026-10-18 | General, method (given on UAL 2018Q4 pilot output) | We should try some sort of regression technique in case the growth of the underlying data was correlated but similar to magnitude to the actuals. | open | |
| 2 | 2026-10-18 | General, method | We should check for seasonality in both the actuals and the data. For whichever series are seasonal, we should de-seasonalize both the actuals and the data and perform the prediction on the de-seasonalized data before adding that effect for a total effect. | open | |
| 3 | 2026-10-18 | General, actuals audit | The actuals need to also be audited for adjustments against their data to flag any periods where we expect expect actuals to be affected significantly by something we wouldn't capture in the data. As an example, if we know last year was temporarily boosted by one-time revenues (say some asset sale) and we apply the data's growth to that inflated base, we'd end up with an overestimate relative to what the data actually says. Another example is COVID, when the relationship between data and actuals likely changed due to a regime change in the market. | open | |
| 4 | 2026-10-18 | General, use of recent actuals | We're currently not using any actuals reported after a year ago into our prediction. We should be taking this | open (completed in 4a) | |
| 4a | 2026-10-18 | General, use of recent actuals (completes #4) | For point 4, we should be taking more recent actuals into account. at the very minimum we should calculate the implied q/q value vs. last quarter's actual and check that this is reasonable vs. prior quarters assuming seasonality holds. e.g. if Q3 to Q4 is normally a 5% step up and this quarter is a -5% drop, in spite of the underlying data trends being consistent in the full period, that would merit a second look. A more advanced technique would actually predict Q/Q changes after adjusting data and actuals for seasonality. | open | |
| 5 | 2026-10-18 | General, model selection | You should only test constructions that have an intuitive relationship with the actuals. The correlation should be positive and any regression coefficients should be significant. | open | |
| 6 | 2026-10-18 | General, robustness | We shouldn't anchor to a summary statistic over the full time series. One extreme quarter where the data was correct can have a large impact on coefficients or significance. The point is to come up with the most robust model that should generate accurate predictions moving forward. | open | |

## Open questions raised by Claude (not feedback, for your call)

| # | Question | Context |
|---|---|---|
| Q1 | Should dropping a broken sensor for a different stated reason count as handling it (C4)? | ALK 2017Q4: dropped Sensor 1 for "too few transactions", not its missing days or level shifts; judge failed C4 |
| Q2 | Should C7 (no look-ahead) and C10 (numbers match the JSON) be `na` rather than `pass` when there's no substantive write-up? | Judge test calls: an empty write-up still passes C7, putting a 0.1–0.2 floor under write-up scores |
| Q3 | On anonymized cases the judge's facts use real names (e.g. Virgin America). Accept unnamed descriptions? | A write-up can flag an acquisition-driven jump without naming it |
| Q4 | Frozen-run note: it used restated Q4 2017 ($8,587M) from the Jan 2019 earnings release, after its 2018-12-31 as-of date | Recorded only; the frozen run is not changed |
| Q5 | Frozen-run note: on UAL 2018Q4 the naive seasonal benchmark missed by 0.3%, against the frozen run's −2.0% (and the pilot's −3.4%) | Recorded only |
