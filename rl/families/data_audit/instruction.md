# Data-validation audit of a transaction panel

{firm}

Before this dataset is used for research, audit it for data-quality problems, then repair it. A problem is a period
where a series is wrong because of how the data was collected. Recover as much of the underlying signal as you can;
where it can't be recovered, mark the day or period unrecoverable and null it out. Flag and change only data that is
wrong, and as narrowly as you can, so researchers keep as much of the good data as possible.

The sources are independent, so the number of sources that move tells a collection problem from real activity:

* A move confined to some of the sources is a data problem, however many companies it touches: one source can fail
  for every company at once.
* A move in every source of a company is real business activity (holidays, seasonality, promotions, a storm across an
  industry, genuine growth or decline), unless no business moves that way: every source going near-dark at once, or
  jumping several-fold overnight and staying there, points to a collection problem upstream of all of them.
* A move in every source of every company can't be settled from this data: it could be the economy or a broad
  collection failure. Don't flag it or change it, and say so in your note.

{schema}

{copy_note}

## What to deliver

1. `/app/output/issues.json`: a JSON list with one object per distinct problem you find:

```json
[{"type": "outage", "ticker": "TAB", "source_id": 3, "start": "2016-04-02", "end": "2016-05-10",
   "evidence": "optional: one line on how you know"}]
```

* `type` is one of:
  * `duplicate_rows`: the same (date, ticker, source) appears more than once
  * `swapped_columns`: `ct` and `amt` are swapped for a period
  * `unit_scale`: amounts switch to a different unit (e.g. cents) for a period
  * `amount_shift`: amounts step up or down while counts don't (e.g. fees and tax start being included, or another currency)
  * `date_shift`: a series' dates are offset (e.g. by a day) from some date onward
  * `dst_shift`: a series' dates are offset by a day only while clocks are on summer time (a fixed UTC cut-off
    labelled with the local date). Report each summer as its own period.
  * `series_swap`: two tickers' series are exchanged within a source (report one ticker; include the other as `other_ticker`)
  * `double_count`: a source counts some or all transactions twice for a period
  * `outage`: a source (or all sources of a ticker) stops reporting or goes near-dark. A source failing for every
    company is one outage per ticker.
  * `level_shift`: a source's level steps up or down persistently relative to the same ticker's other sources
  * `ticker_remap`: a ticker's data steps abruptly in every source at once (e.g. a merchant re-mapping)
* `source_id` is the affected source, or `null` if every source of the ticker is affected.
* `start` is the first affected date; `end` is the last affected date, or `null` if it continues to the end.

2. `/app/output/cleaned.csv`: the panel repaired, with the columns `date, ticker, source_id, ct, amt` and one row per
   (date, ticker, source):
   * repair what can be repaired: deduplicate, swap back, rescale, re-date, and fill in short gaps (up to 7 days)
     from the series' own pattern and its peers;
   * a longer gap, or a near-dark period, can't be recovered: keep a row for each of its days with `ct` and `amt`
     left empty;
   * leave every other row exactly as it came, including real business activity.

3. `/app/output/usability.json`: a verdict for every ticker-source series in the data, on whether it is usable once
   repaired:

```json
[{"ticker": "TAB", "source_id": 3, "usable": false, "reason": "dark for the last 7 weeks"}]
```

   A series is not usable if an unrecoverable gap (more than 7 days) reaches into its last 90 days, if it has 3 or
   more unrecoverable gaps, or if they cover more than 10% of its history. Otherwise it is usable.

4. `/app/output/writeup.md`: a note of one to three sentences, at most 120 words, for the researchers who will build
   on this data. It gives an overall view rather than every problem:
   * how many series are usable once repaired, and which are not;
   * the main kinds of problem, and how you told them apart from real business activity;
   * how you repaired them;
   * one thing you ruled out or could not check.

   Follow it with one chart, saved as `/app/output/figures/flags.png` and shown as `![what it shows](figures/flags.png)`:
   every ticker's sources over the whole panel, with each period you flagged highlighted and labelled by source and
   problem type. The highlighted periods should match `issues.json`. Python with pandas, numpy, scipy and matplotlib
   is available.

## How you are scored

Your score is 40% the problems you report, 40% your repairs and 20% your usability verdicts, then scaled by the note
and chart.

* **Problems.** Each reported problem on the right series and of the right kind earns credit for how well its dates
  match the real problem's. That is full credit for the same dates, less as they diverge, and negative credit if they
  don't overlap at all. Problems are scored on precision and recall against a hidden list of real problems, so every
  report that is not a real problem lowers your score. Some panels have few or no problems; there you are scored on
  how few false reports you make.
* **Repairs.** `cleaned.csv` is compared, day by day, with the true values of the series.
  * A repaired day counts if it is within 5% of the truth (20% for a day you had to fill in).
  * An unrecoverable day counts if it is left empty.
  * Every day you change or empty without cause lowers the repair score steeply, real business activity included.
* **Usability.** Verdicts are scored on the series that are not usable: finding them, and not condemning usable ones.
* **Note and chart.** They are graded on whether they state your findings and repairs clearly and match them. A
  missing or poor note can halve your score, and a note over three sentences or 120 words loses credit.
