# Online anomaly scoring for sensor data

{firm}

Build a model that scores every datapoint for how likely it is to be
*bad data*: a one-day spike or drop from a malfunctioning sensor, or a period in which a sensor's level has shifted
up or down relative to what it should read.

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
* Real business events (holidays, Black Friday, weekly cycles, genuine growth) move every sensor of a company together
  and are not anomalies.
* Each run must finish within 20 minutes on 2 CPUs. Python with pandas, numpy and scipy is available.

You are scored on F1 against hidden labelled anomalies (one-day anomalies, and the first weeks of level shifts),
multiplied by the share of rows you score, and set to zero if the no-foresight check fails. Some panels have nothing
planted: on those, the F1 is replaced by 1 minus the share of rows you flag divided by 5%, floored at 0. The note is graded
separately and does not change that score.
