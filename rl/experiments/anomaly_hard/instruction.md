# Trust scores and clean series for transaction data

{firm}

You have a daily panel of card transactions: several independent data sources (sensors) each report every company's
daily transaction count and dollar total. Sources sometimes misreport. Build code that says, for every row, whether
it can be trusted, and that produces a cleaned version of every series.

The point is a usable, like-for-like series for every source with as much of its history as possible. Some segments
of the data carry too little signal to be worth keeping, and those may be discarded; everything else should be kept,
repaired where it needs repair.

{schema}

{copy_note}

{companies}

## What to deliver

1. **`/app/solution/score.py`**, runnable as

```
python /app/solution/score.py --input IN.csv --output OUT.csv
```

`IN.csv` has the same columns as the data above. `OUT.csv` has one row per input row, with columns
`date, ticker, source_id, confidence, clean_ct, clean_amt`:

* `confidence`, in [0, 1]: does this row carry usable signal about what the company actually did that day, as
  reported or after your adjustment? High means trust it; below 0.5 means do not.
* `clean_ct`, `clean_amt`: a cleaned series for the row's ticker and source that is comparable like for like with
  that source's own history: what the source would have reported had it kept working the way it normally does.
  Where a row is fine, it equals the raw value. Where a row cannot be trusted, impute it. Leave a row blank only when
  it belongs to a segment you discard for low signal (and give it low confidence).

2. **`/app/output/writeup.md`** (under 600 words): how the confidence score and the cleaned series are built and why,
   how you checked them, which open-source packages you used and why (or that you used none), and what a researcher
   should know before relying on them.

## Requirements

* **Code, point in time.** Every output for a row dated *t* may use only rows dated on or before *t*. This is
  checked for all three columns by running your script on the hidden panel truncated at hidden dates and comparing
  with a run on the whole panel.
* **No AI at run time.** You may use any tools to develop the code, but `score.py` must not call a model or any
  network service. It runs with the network off.
* **Built to scale.** Imagine running this on hundreds more sources and companies: the bar is to catch the
  obviously wrong datapoints automatically. Encode every judgment in the code, not in a list of dates or tickers.
* **Simple is fine.** Use complexity only where it clearly helps. Python with pandas, numpy, scipy, statsmodels and
  scikit-learn is available; use any of them, or none.
* **Low-signal data.** Segments that carry no usable signal (for instance a stretch where a source has too few
  transactions for its daily numbers to mean much) may be discarded, as long as the rule is in the code so it would
  scale. Discard as little as you can: history is valuable.
* **New data.** Your script is graded on a different panel of the same kind, with its own tickers, dates and
  problems. Each run must finish within 20 minutes on 2 CPUs.
* **Your own output as input.** The script must also run on a file of its own cleaned series in the input format.

## How you are scored

The grader knows which rows misreport (problems planted in the hidden panel, and real problems in the source data:
reviewed ones and known quirks of individual sources) and what each source would have reported had it been working
normally.

* **Confidence (half).** Rows scored below 0.5 are compared with the rows that cannot be trusted: F1 of those rows,
  with recall counted per problem (each kind of problem weighing the same), so a problem caught late loses the days
  it went uncaught.
* **Cleaned series (half).** On rows a problem affected, how much of the gap between the raw value and what the
  source should have reported your cleaned value closes (in log terms, count and dollars, each kind of problem
  weighing the same), multiplied by the share of rows that were fine and that your cleaned series leaves within the
  source's own noise, by the share of rows that should be kept and that you did not leave blank, and by a stability
  check: your script is run again on its own cleaned series (same columns; counts may not be whole numbers) and on
  clean data, and the cleaned series should not be distrusted more often than clean data (extra alarms count against
  you in proportion to the size of the real problems in the panel). A blank cleaned value on a row with a problem counts as the raw value, so a row left blank where it
  should have been imputed earns nothing.

The total is set to zero if the outputs are malformed, if the point-in-time check fails, if the code imports or shells
out to a model or network client, if the write-up is missing, or if low-signal data is not dropped: a source that
reports fewer than about twenty transactions a day before it has built up steady coverage (its early history, or all
of it) must be distrusted and left blank there (at least 90% of those rows). A source that dips that low after it was
established is kept: those rows count in the cleaned-series score, so blanking them costs history. Rows near the
twenty-a-day line, the two weeks either side of a low-signal stretch's edges, and other debatable rows are not scored.
The write-up is also graded on its own, separately from this score.
