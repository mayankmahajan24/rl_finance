# Data-validation audit of a transaction panel

{firm}

Before this licensed dataset is used for research, audit it for
data-quality problems that would make any series misleading.

{schema}

## What to deliver

Write `/app/output/issues.json`: a JSON list with one object per distinct problem you find:

```json
[{"type": "outage", "ticker": "TAB", "source_id": 3, "start": "2016-04-02", "end": "2016-05-10",
   "evidence": "one line on how you know"}]
```

* `type` is one of:
  * `duplicate_rows`: the same (date, ticker, source) appears more than once
  * `swapped_columns`: `ct` and `amt` are swapped for a period
  * `unit_scale`: amounts switch to a different unit (e.g. cents)
  * `date_shift`: a series' dates are offset (e.g. by a day) from some date onward
  * `series_swap`: two tickers' series are exchanged within a source (report one ticker; include the other as `other_ticker`)
  * `double_count`: a sensor reports every transaction twice for a period
  * `outage`: a sensor (or all sensors of a ticker) stops reporting or goes near-dark
  * `level_shift`: a sensor's level steps up or down persistently relative to the truth
  * `ticker_remap`: a ticker's data steps abruptly in every sensor at once (e.g. a merchant re-mapping)
* `source_id` is the affected sensor, or `null` if every sensor of the ticker is affected.
* `start` is the first affected date; `end` is the last affected date, or `null` if it continues to the end.

Real business events (holidays, seasonality, genuine growth) are not data problems. You are scored on precision and
recall against a hidden list of real problems; reporting things that are not problems lowers your score, and some
datasets contain few or no planted problems.
