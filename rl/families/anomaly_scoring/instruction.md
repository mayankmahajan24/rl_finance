# Online anomaly scoring for sensor data

{firm}

Build a model that scores every datapoint for how likely it is to be
*bad data*: a one-day spike or drop from a malfunctioning sensor, or a period in which a sensor's level has shifted
up or down relative to what it should read.

{schema}

## What to deliver

Create `/app/solution/score.py`, runnable as

```
python /app/solution/score.py --input IN.csv --output OUT.csv
```

`IN.csv` has the same columns as the data above. `OUT.csv` must contain `date, ticker, source_id, anomaly_score`
with one row per input row, where `anomaly_score` is in [0, 1] and higher means more likely to be bad data.
A score above 0.5 counts as a flag.

Requirements:
* **No foresight.** The score for a row dated *t* may only depend on rows dated on or before *t*. This is checked
  by re-running your script on the same data truncated at hidden dates and comparing the scores.
* Real business events (holidays, Black Friday, weekly cycles, genuine growth) move every sensor of a company together
  and are not anomalies.
* Each run must finish within 20 minutes on 2 CPUs. Python with pandas, numpy and scipy is available.

You are scored on F1 against hidden labelled anomalies (one-day anomalies, and the first weeks of level shifts),
multiplied by the share of rows you score, and set to zero if the no-foresight check fails.
