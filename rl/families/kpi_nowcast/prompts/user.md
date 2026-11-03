Predict {{company}}'s quarterly {{kpi}} from the transaction-sensor data.

Attached:
- `sensor_panel.csv`: daily transaction counts (`ct`) and dollar amounts (`amt`) by ticker and data source, through {{as_of}}. {{company}} appears as {{tickers}}.
- `data_brief.md`: the note that came with the data, describing the sensors.
- `actuals.csv`: {{company}}'s reported {{kpi}} ({{industry}}, {{fiscal_note}}), in USD millions, from our data feed. It holds every value reported on or before {{as_of}}: {{first_quarter}} through {{prior}}, including figures re-reported in later filings, with the date each was reported.

{{target}} ended on {{target_end}} and has not been reported yet. Provide in-sample estimates for the prior quarters and an out-of-sample estimate, with a range, for {{target}}.

The investment staff read every write-up the same way: put the target quarter, your point estimate, your range and the units at the top, before any discussion of method, and show your in-sample accuracy next to a simple benchmark (for example, the same quarter last year) so they can see what your method adds.

End your final message with:
1. A write-up for the investment staff, in markdown.
2. A fenced ```json block with exactly these fields:

```json
{"target_period": "{{target}}", "unit": "USD millions",
 "point": 0, "low": 0, "high": 0, "interval_level": 0.9,
 "in_sample": [{"period_end": "YYYY-MM-DD", "estimate": 0}],
 "vs_consensus": "no_consensus"}
```

`low` and `high` bound your range at `interval_level` confidence, which must be between 0 and 1; `low` ≤ `point` ≤ `high` is required, and a forecast that breaks either rule is not scored. `in_sample` lists your estimate for each prior quarter you modeled.
