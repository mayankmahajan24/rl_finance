Predict {{company}}'s quarterly {{kpi}} from the transaction-sensor data.

Attached:
- `sensor_panel.csv`: daily transaction counts (`ct`) and dollar amounts (`amt`) by ticker and data source, through {{as_of}}. {{company}} appears as {{tickers}}.
- `data_brief.md`: the note that came with the data, describing the sensors.
- `actuals.csv`: {{company}}'s reported {{kpi}} ({{industry}}, {{fiscal_note}}), in USD millions, from our data feed. It holds every value reported on or before {{as_of}}: {{first_quarter}} through {{prior}}, including figures re-reported in later filings, with the date each was reported.

{{target}} ended on {{target_end}} and has not been reported yet. Provide in-sample estimates for the prior quarters and an out-of-sample estimate, with a range, for {{target}}.

End your final message with:
1. A write-up for the investment staff, in markdown.
2. A fenced ```json block with exactly these fields:

```json
{"target_period": "{{target}}", "unit": "USD millions",
 "point": 0, "low": 0, "high": 0, "interval_level": 0.9,
 "in_sample": [{"period_end": "YYYY-MM-DD", "estimate": 0}],
 "vs_consensus": "no_consensus"}
```

`low` and `high` bound your range at `interval_level` confidence. `in_sample` lists your estimate for each prior quarter you modeled.
