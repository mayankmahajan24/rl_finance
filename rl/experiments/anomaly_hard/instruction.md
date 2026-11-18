# Online anomaly scoring for transaction data

{firm}

Build a model that scores every datapoint for how likely it is to be *bad data*: a row where a source misreports
what the company actually did that day, such as a one-day spike or drop in one source. Flag everything that is
actually off, and nothing that isn't: researchers look into every flag. Real business events (holidays,
promotions, weekly cycles, genuine growth) move every source of a company together and are not bad data.

A problem that lasts is a change in a source's level. The change is bad data, and so is the source's return to its
old level. Once a changed level has held long enough to be the source's new normal, judge the source against that
new normal: deciding when that is, from the data so far, is part of the job.

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
planted in it, and real problems in the source data that have been reviewed. A problem that lasts is labelled as a
change: its first 14 days are bad data, the days after that up to 45 days from its start are not scored, and after
that its level is the normal level, so flags there are false alarms; its return is labelled the same way (the first
14 days after it ends are bad data, then not scored up to 45 days after it ends). Debatable rows are not scored. Your
score is the average of two parts:
* **Row F1:** precision of your flagged rows, against recall measured as the share of each problem's labelled days
  you flag. Problems of each kind weigh equally.
* **Event F1:** alert precision against event recall. An alert is a run of flagged days on one source (gaps of up
  to 2 days joined), and it is correct if it touches bad data. A short problem is caught if any of its days is
  flagged; a change or a return is caught in full if flagged within 14 days, with the credit falling to nothing at
  45 days. Each kind of problem carries an equal share of event recall.

That average is multiplied by the share of rows you score, and set to zero if the no-foresight check fails. Some
panels have no known bad data: on those, the score is 1 minus the share of rows you flag divided by 5%, floored at 0.
The note is graded separately and does not change that score.
