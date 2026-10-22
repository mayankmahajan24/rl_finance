Predict Retailer RET03's quarterly total net sales from the transaction-sensor data.

Attached:
- `sensor_panel.csv`: daily transaction counts (`ct`) and dollar amounts (`amt`) by ticker and data source, through 2017-10-28. Retailer RET03 appears as RET03.
- `data_brief.md`: the note that came with the data, describing the sensors.
- `actuals.csv`: Retailer RET03's reported total net sales (US department store / off-price retailer, fiscal quarters (fiscal year ends late January / early February)), in USD millions, from our data feed. It holds every value reported on or before 2017-10-28: FY2012 Q1 through FY2017 Q2, including figures re-reported in later filings, with the date each was reported.

FY2017 Q3 ended on 2017-10-28 and has not been reported yet. Provide in-sample estimates for the prior quarters and an out-of-sample estimate, with a range, for FY2017 Q3.

End your final message with:
1. A write-up for the investment staff, in markdown.
2. A fenced ```json block with exactly these fields:

```json
{"target_period": "FY2017 Q3", "unit": "USD millions",
 "point": 0, "low": 0, "high": 0, "interval_level": 0.9,
 "in_sample": [{"period_end": "YYYY-MM-DD", "estimate": 0}],
 "vs_consensus": "no_consensus"}
```

`low` and `high` bound your range at `interval_level` confidence. `in_sample` lists your estimate for each prior quarter you modeled.
