# Online anomaly scoring for transaction data

{firm}

Build a model that scores every datapoint for how likely it is to be *bad data*: a row where a source misreports
what the company actually did that day. Flag everything that is actually off. Real business events (holidays,
promotions, weekly cycles, genuine growth) move every source of a company together and are not bad data. Every row a
problem touches is bad data, and a problem that persists is bad data on every day until the source is back to normal:
a source does not become correct by staying wrong.

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

How you are scored. A row is flagged if its score is above 0.5. The panel's bad data is known to the grader: problems
planted in it, and real problems in the source data that have been reviewed. Debatable rows are not scored, nor
the first 7 days after a persisting problem ends. Your score is the average of two parts:
* **Row F1:** precision of your flagged rows, against recall measured as the share of each problem's days you flag.
  Problems of each kind weigh equally, so a problem lasting months counts the same as a one-day one.
* **Event F1:** alert precision against event recall. An alert is a run of flagged days on one source (gaps of up
  to 2 days joined), and it is correct if it touches bad data. A problem lasting a few days is caught if any of its
  days is flagged; one that persists is caught in full if flagged within 14 days of its start, with the credit
  falling to nothing at 45 days. Each kind of problem carries an equal share of event recall.

That average is multiplied by the share of rows you score, and set to zero if the no-foresight check fails. Some
panels have no known bad data: on those, the score is 1 minus the share of rows you flag divided by 5%, floored at 0.
The note is graded separately and does not change that score.
