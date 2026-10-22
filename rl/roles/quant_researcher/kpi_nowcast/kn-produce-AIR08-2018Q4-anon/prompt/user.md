Predict Airline AIR08's quarterly passenger revenue from the transaction-sensor data.

Attached:
- `sensor_panel.csv`: daily transaction counts (`ct`) and dollar amounts (`amt`) by ticker and data source, through 2018-12-31. Airline AIR08 appears as AIR08.
- `data_brief.md`: the note that came with the data, describing the sensors.
- `actuals.csv`: Airline AIR08's reported passenger revenue (US airline, calendar quarters), in USD millions, from our data feed. It holds every value reported on or before 2018-12-31: 2013Q1 through 2018Q3, including figures re-reported in later filings, with the date each was reported.

2018Q4 ended on 2018-12-31 and has not been reported yet. Provide in-sample estimates for the prior quarters and an out-of-sample estimate, with a range, for 2018Q4.

End your final message with:
1. A write-up for the investment staff, in markdown.
2. A fenced ```json block with exactly these fields:

```json
{"target_period": "2018Q4", "unit": "USD millions",
 "point": 0, "low": 0, "high": 0, "interval_level": 0.9,
 "in_sample": [{"period_end": "YYYY-MM-DD", "estimate": 0}],
 "vs_consensus": "no_consensus"}
```

`low` and `high` bound your range at `interval_level` confidence. `in_sample` lists your estimate for each prior quarter you modeled.
