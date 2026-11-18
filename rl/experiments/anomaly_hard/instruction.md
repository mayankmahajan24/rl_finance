# Trust scores and clean series for transaction data

{firm}

You have a daily panel of card transactions: several independent data sources (sensors) each report every company's
daily transaction count and dollar total. Sources sometimes misreport. Build code that says, for every row, whether
it can be trusted, and that produces a cleaned version of every series.

{schema}

{copy_note}

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
  Where a row is fine, it equals the raw value. You may leave them blank on rows you throw out as junk.

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
* **Junk data.** You may throw out data that carries no usable signal (for instance the leading portion of a source
  with very few transactions), as long as the rule is in the code so it would scale.
* **New data.** Your script is graded on a different panel of the same kind, with its own tickers, dates and
  problems. Each run must finish within 20 minutes on 2 CPUs.

## How you are scored

The grader knows which rows misreport (problems planted in the hidden panel, and real problems in the source data
that have been reviewed) and what each source would have reported had it been working normally.

* **Confidence (half).** Rows scored below 0.5 are compared with the rows that cannot be trusted: F1 of those rows
  (recall counted per problem, each kind of problem weighing the same), and F1 of alerts (a run of distrusted days on
  one source; correct if it touches an untrustworthy row) against problems caught, with credit falling the longer a
  problem goes uncaught.
* **Cleaned series (half).** On rows a problem affected, how much of the gap between the raw value and what the
  source should have reported your cleaned value closes (in log terms, count and dollars, each kind of problem
  weighing the same), multiplied by a penalty for changing rows that were fine.

That sum is set to zero if the outputs are malformed, if the point-in-time check fails, or if the write-up is missing.
Rows on thin stretches of a source (fewer than about ten transactions a day) and debatable rows are not scored. The
write-up is also graded on its own, separately from this score.
