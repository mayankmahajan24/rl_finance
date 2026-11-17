# Online anomaly scoring for transaction data

{firm}

Build a model that scores every datapoint for how likely it is to be *bad data*: a row where a source misreports
what the company actually sold that day. The sources are separate reads on the same companies, so real business
events (holidays, promotions, weekly cycles, storms that bring shoppers out early and then keep them home, a bank
holiday that pushes settlement to the next day, genuine growth) move every source of a company together and are
not anomalies. Bad data is a problem in one source. In this data it takes these forms:

* **Count and value come apart.** A flood of tiny test transactions (the count jumps, the dollars barely move); a
  day with a few unusually large tickets (the dollars jump, the count doesn't); or a change in how purchases are
  split into transactions, where the count drifts up over weeks while the dollars don't.
* **Volume lands on the wrong day.** Part of a day's batch settles late and turns up the next day or two; part of
  the feed misses the cutoff for a few days and is sometimes backfilled in one go; or a batch is loaded twice.

Every day a problem touches is bad data: the low day and the catch-up day, the missing days and the backfill day,
and every day of a problem that persists, from when it starts until the source is back to normal. A source does not
become correct by staying wrong.

{schema}

{copy_note}

## What to deliver

1. Create `/app/solution/score.py`, runnable as

```
python /app/solution/score.py --input IN.csv --output OUT.csv
```

`IN.csv` has the same columns as the data above. `OUT.csv` must contain `date, ticker, source_id, anomaly_score`
with one row per input row, where `anomaly_score` is in [0, 1] and higher means more likely to be bad data.
A score above 0.5 counts as a flag. The flags are whatever this script outputs: nothing else you write is graded.

2. Write `/app/output/writeup.md`: a note (under 500 words) for the researchers who will rely on these scores: what
   the model does and why, how you checked it, and what they should know before trusting it.

Requirements:
* **New data.** Your script is graded on a different panel of the same kind that you never see, with its own tickers,
  dates and problems. It has to work on any file in this format, so a table of scores for the data above is worth
  nothing.
* **No foresight.** The score for a row dated *t* may only depend on rows dated on or before *t*. This is checked
  by running your script on that panel truncated at hidden dates and comparing the scores with a run on the whole
  panel.
* Each run must finish within 20 minutes on 2 CPUs. Python with pandas, numpy and scipy is available.

How you are scored. A row is flagged if its score is above 0.5. The labelled rows are every day of each planted
problem; for a problem that persists, the first 7 days after it ends are not scored. Your score is the average of
two parts:
* **Row F1:** F1 of your flags against the labelled rows.
* **Event F1:** F1 of the same row precision against event recall. Each kind of problem above carries an equal share
  of event recall. A problem lasting a few days counts if any of its days is flagged. A problem that persists counts
  in full if flagged within 14 days of its labelled start, with the credit falling to nothing at 45 days.

That average is multiplied by the share of rows you score, and set to zero if the no-foresight check fails. Some
panels have nothing planted: on those, the score is 1 minus the share of rows you flag divided by 5%, floored at 0.
Known real problems in the source data are left out of scoring. The note is graded separately and does not
change that score.
