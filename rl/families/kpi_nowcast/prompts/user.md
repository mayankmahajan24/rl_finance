Predict {company}'s quarterly {kpi} from the transaction-sensor data.

Attached:
- `sensor_panel.csv`: daily transaction counts (`ct`) and dollar amounts (`amt`) by ticker and data source, through {as_of}. {company} appears as {tickers}.
- `data_brief.md`: a description of the data and its known issues.
- `actuals.csv`: {company}'s reported {kpi} ({industry}, {fiscal_note}), in USD millions, from our data feed. It holds every value reported on or before {as_of}: {first_quarter} through {prior}, including figures re-reported in later filings, with the date each was reported. `report` says whether a row is the earliest filing of that quarter in the feed or a later one. `q4_derived_from_annual` marks a fourth quarter computed as the full year minus the first nine months. The feed begins with filings from March 2014, so earlier quarters show the date of a later filing, not their original report.

{target} ended on {target_end} and has not been reported yet. The target is the figure as first reported, not any later restatement. Provide walk-forward estimates for prior quarters and an estimate, with a range, for {target}.

The investment staff read every write-up the same way: put the target quarter, your point estimate, your range and the units at the top, before any discussion of method, and show your walk-forward accuracy next to a simple benchmark (for example, the same quarter last year) so they can see what your method adds.

You may add up to 4 charts where they help the reader. Save each as a PNG and show it in the write-up as `![what it shows](figures/name.png)`.

End your final message with:
1. A write-up for the investment staff, in markdown.
2. A fenced ```json block with exactly these fields:

```json
{"target_period": "{target}", "unit": "USD millions",
 "point": 0, "low": 0, "high": 0, "interval_level": 0.95,
 "in_sample": [{"period_end": "YYYY-MM-DD", "estimate": 0}],
 "vs_consensus": "no_consensus"}
```

`low` and `high` bound your 95% confidence range, so `interval_level` must be 0.95; `low` ≤ `point` ≤ `high` is required, and a forecast that breaks either rule is not scored. `in_sample` must cover at least the 8 most recent prior quarters. Each estimate must be walk-forward: made only from sensor data through that quarter's end and actuals reported before it, as you are doing for {target}. `vs_consensus` stays `no_consensus`, because no consensus estimate is provided.
