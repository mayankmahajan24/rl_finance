# Online anomaly scoring for transaction data

{firm}

Build a model that scores every datapoint for how likely it is to be
*bad data*: a one-day spike or drop from a malfunctioning source, or a period in which a source's level has shifted
up or down relative to what it should read. A shifted source is bad data on every day of the shift, from the day it
moves until the day it returns to normal, however long that takes: it does not become correct by staying wrong. Once
it is back to normal, its rows are good data again.

{schema}

{copy_note}

## What to deliver

1. Create `/app/solution/score.py`, runnable as

```
python /app/solution/score.py --input IN.csv --output OUT.csv
```

`IN.csv` has the same columns as the data above. `OUT.csv` must contain `date, ticker, source_id, anomaly_score`
with one row per input row, where `anomaly_score` is in [0, 1] and higher means more likely to be bad data.
A score above 0.5 counts as a flag.

2. Write `/app/output/writeup.md`: a note (under 500 words) for the researchers who will rely on these scores: what
   the model does and why, how you checked it, and what they should know before trusting it.

Requirements:
* **New data.** Your script is graded on a different panel of the same kind that you never see, with its own tickers,
  dates and anomalies. It has to work on any file in this format, so a table of scores for the data above is worth nothing.
* **No foresight.** The score for a row dated *t* may only depend on rows dated on or before *t*. This is checked
  by running your script on that panel truncated at hidden dates and comparing the scores with a run on the whole panel.
* Real business events (holidays, Black Friday, weekly cycles, genuine growth) move every source of a company together
  and are not anomalies.
* Each run must finish within 20 minutes on 2 CPUs. Python with pandas, numpy and scipy is available.

How you are scored. A row is flagged if its score is above 0.5. The labelled anomalies are the planted one-day
spikes and drops, and every day of each planted level shift; the first 7 days after a shift ends are not scored.
Your score is the average of two parts:
* **Row F1:** F1 of your flags against the labelled rows. Shift days are most of them, so this mostly rewards
  flagging a shifted source for as long as it stays shifted, and not flagging it once it has recovered.
* **Event F1:** F1 of the same row precision against event recall. Spikes and drops carry half of event recall, and
  count if their day is flagged. Shifts carry the other half: a shift counts in full if flagged within 7 days of its
  start, with the credit falling to nothing at 30 days.

That average is multiplied by the share of rows you score, and set to zero if the no-foresight check fails. Some
panels have nothing planted: on those, the score is 1 minus the share of rows you flag divided by 5%, floored at 0.
The note is graded separately and does not change that score.
