Work out which of {company}'s reported metrics the transaction data can track most usefully, then nowcast it.

Attached:
- `transaction_panel.csv`: daily transaction counts (`ct`) and dollar amounts (`amt`) by ticker and data source, through {as_of}. {company} appears as {tickers}.
- `data_brief.md`: a description of the data and its known issues.
- `actuals.csv`: {company}'s reported income statement ({industry}, {fiscal_note}) from our data feed: every line, with its segment, product, geography or sales-channel splits where the company reports them (`split`). It holds every value reported on or before {as_of}, through {prior}, including figures re-reported in later filings, with the date each was reported. `report` says whether a row is the earliest filing of that line and quarter in the feed or a later one. `q4_derived_from_annual` marks a fourth quarter computed as the full year minus the first nine months; per-share and share-count lines are not derived that way, so their fourth quarter is missing unless the filing reported it. Line names are as the company labelled them and can change between filings. The feed begins with filings from early 2014, so earlier quarters show the date of a later filing, not their original report.

First choose the metric: the reported line, or split of a line, that the transaction data can track best and that the investment staff would most want tracked, and say why. Then nowcast it. Today, {as_of}, is the last day of transaction data. {target}, which ended on {target_end}, is the next quarter {company} will report, and it has not been reported yet. The target is the metric's figure as first reported, not any later restatement. Provide walk-forward estimates for prior quarters and an estimate, with a range, for {target}.

Write two documents.

**A methods note** for the fund's data scientists, saved as `/app/output/methods.md`: how you reached your estimate. Cover the metric you chose and the alternatives you considered, the checks you ran on the data and what you did about what they found, what you tried and why you kept or dropped it, and the model you landed on. State what you modelled on what (the variable you forecast and the variables you used to explain it, with any transformation or lag) before showing results, and give the fitted model's coefficients and their significance. Show your walk-forward error against the reported actuals, quarter by quarter, next to a simple benchmark (for example, the same quarter last year).

**A brief** for the investment staff, as your final message. They read it without the methods note, so it must stand on its own and agree with the note. Put the metric, the target quarter, your point estimate, your range, the units and the implied year-on-year growth at the top, before any discussion of method. Then give your method and your view in plain language, with your walk-forward accuracy next to the benchmark's so they can see what your method adds. Leave the reasons for your choice of metric to the methods note.

You may add up to 4 charts across the two documents where they help the reader. Save each as a PNG and show it as `![what it shows](figures/name.png)`.

End the brief with a fenced ```json block with exactly these fields:

```json
{"target_period": "{target}", "metric": "", "unit": "USD millions",
 "point": 0, "low": 0, "high": 0, "interval_level": 0.95,
 "metric_history": [{"period_end": "YYYY-MM-DD", "value": 0}],
 "in_sample": [{"period_end": "YYYY-MM-DD", "estimate": 0}],
 "vs_consensus": "no_consensus"}
```

`metric` names the line (and split, if any) as `actuals.csv` names it, or how you combined lines. `metric_history` gives the metric's reported value for each of the 4 most recent quarters before {target}, as the latest filing in `actuals.csv` reports it. `low` and `high` bound your 95% confidence range, so `interval_level` must be 0.95; `low` ≤ `point` ≤ `high` is required, and a forecast that breaks either rule is not scored. `in_sample` must cover at least the 8 most recent prior quarters. Each estimate must be walk-forward: made only from the transaction data and actuals available on the day before that quarter was first reported, as you are doing for {target}. `vs_consensus` stays `no_consensus`, because no consensus estimate is provided.
