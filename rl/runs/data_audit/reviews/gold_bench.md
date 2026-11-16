# data_audit bench gold

Every bench task's `tests/gold.json`, built 2026-11-10 on `ad99c16` plus the uncommitted review changes, with the problems and real events of feedback log #24-#31. Seeds come from `splits/seeds.yaml`. Held-out gold is left out: its seeds are secret.

- **required**: scored for precision and recall: planted problems, plus real breaks from the raw panel (`natural`). Each match earns the generalized intersection over union of its dates.
- **optional**: real but debatable; a report on that ticker and source inside the window is neither rewarded nor penalised.
- **ignore**: series with median volume under 10 transactions a day; reports on them are ignored.
- **not usable**: series the usability rule condemns; every other scored series is usable.
- **real event**: a decoy planted in every source (an industry shock or a promotion). It is in the clean panel too: a report on it is false, and changing it is damage.

Every task also ships `clean.csv.gz` (the panel before any problem) and `given.csv.gz` (the panel as given), hidden in `tests/`, for the repair score.

"all" means every source of the ticker. Planted problems come from `families/data_audit/generate.py` and `_shared/panel_perturb.py`; natural and optional ones from `sources/txn_panel/annotations/data_artifacts.yaml`, mapped into each task's disguise.

## audit-bench-001

| List | Type | Ticker | Source | Start | End | Note |
|---|---|---|---|---|---|---|
| required | unit_scale | TSE | 3 | 2014-05-05 | 2014-07-13 | planted, note amount reported in cents |
| required | duplicate_rows | TYN | 1 | 2013-06-19 | 2013-07-19 | planted |
| required | date_shift | TEB | 4 | 2014-03-15 | end | planted, note dates off by -1 day |
| required | dst_shift | TNR | 4 | 2014-03-08 | 2014-11-01 | planted, note summer dates off by -1 day |
| required | dst_shift | TNR | 4 | 2015-03-07 | 2015-10-31 | planted, note summer dates off by -1 day |
| required | outage | TEB | 3 | 2013-07-10 | 2013-07-19 | planted, note source-wide |
| required | outage | TMS | 3 | 2013-07-10 | 2013-07-19 | planted, note source-wide |
| required | outage | TNR | 3 | 2013-07-10 | 2013-07-19 | planted, note source-wide |
| required | outage | TSE | 3 | 2013-07-10 | 2013-07-19 | planted, note source-wide |
| required | outage | TYN | 3 | 2013-07-10 | 2013-07-19 | planted, note source-wide |
| required | outage | TYN | 2 | 2011-09-23 | 2011-10-18 | planted |
| required | outage | TYN | 2 | 2012-11-19 | 2012-12-01 | planted |
| required | outage | TYN | 2 | 2014-05-14 | 2014-06-12 | planted |
| required | outage | TMS | all | 2015-03-08 | 2015-03-24 | natural, note every sensor at 5-10% of normal |
| optional | — | TYN | 1 | 2013-05-05 | 2014-02-04 | start window |
| optional | — | TEB | 1 | 2013-05-05 | 2014-02-04 | start window |
| optional | — | TMS | 3 | 2012-09-18 | 2013-02-18 | start window |
| optional | — | TNR | 3 | 2012-09-18 | 2013-02-18 | start window |
| optional | — | TSE | 3 | 2012-09-18 | 2013-02-18 | start window |
| optional | — | TMS | all | 2015-02-19 | 2015-04-19 | start window |
| optional | — | TYN | 1 | 2015-07-14 | 2015-08-02 | start window |
| optional | — | TNR | 1 | 2015-07-14 | 2015-08-02 | start window |
| optional | — | TEB | 1 | 2015-07-14 | 2015-08-02 | start window |
| ignore | — | TNR | 1 | | | low volume |
| not usable | — | TYN | 2 | | | |
| real event | recurring promotion | TYN | all | 2011-07-25 | 2015-08-03 | 5 period(s), counts x1.35, ticket x0.82 |

## audit-bench-002

| List | Type | Ticker | Source | Start | End | Note |
|---|---|---|---|---|---|---|
| required | amount_shift | TIY | 3 | 2012-10-31 | 2013-08-01 | planted, note amounts include tax or fees, mult 1.39 |
| required | date_shift | TFY | 1 | 2013-04-05 | end | planted, note dates off by -1 day |
| required | unit_scale | TBC | 4 | 2013-02-03 | 2013-06-30 | planted, note amount reported in cents |
| required | level_shift | TFY | 1 | 2013-11-02 | end | planted, mult 0.7 |
| required | outage | TFY | 4 | 2015-10-04 | end | planted |
| required | outage | TIE | 3 | 2011-08-09 | 2011-08-27 | planted |
| required | outage | TIE | 3 | 2013-03-05 | 2013-03-24 | planted |
| required | outage | TIE | 3 | 2014-07-26 | 2014-08-22 | planted |
| required | outage | TLR | all | 2015-03-08 | 2015-03-24 | natural, note every sensor at 5-10% of normal |
| optional | — | TIE | 3 | 2013-05-05 | 2014-02-04 | start window |
| optional | — | TFY | 3 | 2013-05-05 | 2014-02-04 | start window |
| optional | — | TLR | 2 | 2012-09-18 | 2013-02-18 | start window |
| optional | — | TBC | 2 | 2012-09-18 | 2013-02-18 | start window |
| optional | — | TIY | 2 | 2012-09-18 | 2013-02-18 | start window |
| optional | — | TLR | all | 2015-02-19 | 2015-04-19 | start window |
| optional | — | TIE | 3 | 2015-07-14 | 2015-08-02 | start window |
| optional | — | TBC | 3 | 2015-07-14 | 2015-08-02 | start window |
| optional | — | TFY | 3 | 2015-07-14 | 2015-08-02 | start window |
| not usable | — | TFY | 4 | | | |
| not usable | — | TIE | 3 | | | |
| real event | promotion | TIY | all | 2014-05-30 | 2014-06-03 | 1 period(s), counts x1.5, ticket x0.84 |

## audit-bench-003

| List | Type | Ticker | Source | Start | End | Note |
|---|---|---|---|---|---|---|
| required | amount_shift | TNX | 3 | 2018-08-10 | 2019-05-27 | planted, note amounts include tax or fees, mult 1.3 |
| required | series_swap | TOJ | 3 | 2020-07-20 | end | planted, with TNI |
| required | unit_scale | TDB | 3 | 2019-07-06 | 2019-09-27 | planted, note amount reported in cents |
| required | level_shift | TDB | 3 | 2018-12-31 | 2019-04-12 | planted, mult 1.56 |
| required | outage | TCK | 4 | 2020-03-18 | 2020-04-07 | planted, note source-wide |
| required | outage | TDB | 4 | 2020-03-18 | 2020-04-07 | planted, note source-wide |
| required | outage | TNI | 4 | 2020-03-18 | 2020-04-07 | planted, note source-wide |
| required | outage | TNX | 4 | 2020-03-18 | 2020-04-07 | planted, note source-wide |
| required | outage | TOJ | 4 | 2020-03-18 | 2020-04-07 | planted, note source-wide |
| required | outage | TOJ | 1 | 2021-09-21 | end | planted |
| required | outage | TNX | 2 | 2017-07-07 | 2017-08-02 | planted |
| required | outage | TNX | 2 | 2019-05-24 | 2019-06-09 | planted |
| required | outage | TNX | 2 | 2020-03-16 | 2020-04-08 | planted |
| required | outage | TCK | all | 2021-02-28 | 2021-03-16 | natural, note every sensor at 5-10% of normal |
| optional | — | TOJ | 1 | 2019-04-28 | 2020-01-28 | start window |
| optional | — | TDB | 1 | 2019-04-28 | 2020-01-28 | start window |
| optional | — | TCK | 3 | 2018-09-11 | 2019-02-11 | start window |
| optional | — | TNI | 3 | 2018-09-11 | 2019-02-11 | start window |
| optional | — | TNX | 3 | 2018-09-11 | 2019-02-11 | start window |
| optional | — | TCK | all | 2021-02-11 | 2021-04-11 | start window |
| optional | — | TOJ | 1 | 2021-07-06 | 2021-07-25 | start window |
| optional | — | TNI | 1 | 2021-07-06 | 2021-07-25 | start window |
| optional | — | TDB | 1 | 2021-07-06 | 2021-07-25 | start window |
| ignore | — | TNI | 1 | | | low volume |
| not usable | — | TNX | 2 | | | |
| not usable | — | TOJ | 1 | | | |
| real event | promotion | TOJ | all | 2019-09-27 | 2019-10-01 | 1 period(s), counts x1.69, ticket x0.88 |

## audit-bench-004

| List | Type | Ticker | Source | Start | End | Note |
|---|---|---|---|---|---|---|
| required | date_shift | TCR | 1 | 2012-10-14 | end | planted, note dates off by -1 day |
| required | swapped_columns | TZP | 4 | 2014-09-07 | 2014-09-15 | planted |
| required | unit_scale | TRC | 2 | 2012-07-28 | 2012-12-05 | planted, note amount reported in cents |
| required | outage | TRC | 3 | 2011-10-23 | 2011-11-14 | planted |
| required | outage | TRC | 3 | 2013-05-09 | 2013-05-22 | planted |
| required | outage | TRC | 3 | 2014-01-28 | 2014-02-25 | planted |
| required | outage | TBN | all | 2015-03-08 | 2015-03-24 | natural, note every sensor at 5-10% of normal |
| optional | — | TUM | 2 | 2013-05-05 | 2014-02-04 | start window |
| optional | — | TCR | 2 | 2013-05-05 | 2014-02-04 | start window |
| optional | — | TBN | 1 | 2012-09-18 | 2013-02-18 | start window |
| optional | — | TZP | 1 | 2012-09-18 | 2013-02-18 | start window |
| optional | — | TRC | 1 | 2012-09-18 | 2013-02-18 | start window |
| optional | — | TBN | all | 2015-02-19 | 2015-04-19 | start window |
| optional | — | TUM | 2 | 2015-07-14 | 2015-08-02 | start window |
| optional | — | TZP | 2 | 2015-07-14 | 2015-08-02 | start window |
| optional | — | TCR | 2 | 2015-07-14 | 2015-08-02 | start window |
| not usable | — | TRC | 3 | | | |
| real event | recurring promotion | TCR | all | 2011-08-12 | 2015-08-19 | 5 period(s), counts x1.31, ticket x0.81 |
| real event | industry shock x0.58 | TBN, TRC, TZP | all | 2012-10-24 | 2012-10-25 | department stores |

## audit-bench-005

| List | Type | Ticker | Source | Start | End | Note |
|---|---|---|---|---|---|---|
| required | duplicate_rows | TUJ | 1 | 2014-10-09 | 2014-10-19 | planted |
| required | date_shift | TWX | 2 | 2014-12-17 | end | planted, note dates off by -1 day |
| required | swapped_columns | TZX | 2 | 2015-05-04 | 2015-05-25 | planted |
| required | level_shift | TWX | 2 | 2016-04-17 | 2016-09-29 | planted, mult 0.7 |
| required | outage | TJH | 3 | 2015-06-19 | 2015-07-16 | planted, note source-wide |
| required | outage | TUJ | 3 | 2015-06-19 | 2015-07-16 | planted, note source-wide |
| required | outage | TUU | 3 | 2015-06-19 | 2015-07-16 | planted, note source-wide |
| required | outage | TZX | 3 | 2015-06-19 | 2015-07-16 | planted, note source-wide |
| required | outage | TJH | 4 | 2017-11-09 | end | planted |
| required | outage | TUU | all | 2017-03-05 | 2017-03-21 | natural, note every sensor at 5-10% of normal |
| optional | — | TJH | 3 | 2015-05-03 | 2016-02-02 | start window |
| optional | — | TUJ | 3 | 2015-05-03 | 2016-02-02 | start window |
| optional | — | TUU | 1 | 2014-09-16 | 2015-02-16 | start window |
| optional | — | TWX | 1 | 2014-09-16 | 2015-02-16 | start window |
| optional | — | TZX | 1 | 2014-09-16 | 2015-02-16 | start window |
| optional | — | TUU | all | 2017-02-16 | 2017-04-16 | start window |
| optional | — | TJH | 3 | 2017-07-11 | 2017-07-30 | start window |
| optional | — | TWX | 3 | 2017-07-11 | 2017-07-30 | start window |
| optional | — | TUJ | 3 | 2017-07-11 | 2017-07-30 | start window |
| ignore | — | TWX | 3 | | | low volume |
| not usable | — | TJH | 4 | | | |
| real event | recurring promotion | TJH | all | 2013-09-07 | 2017-09-11 | 5 period(s), counts x1.43, ticket x0.9 |

## audit-bench-006

| List | Type | Ticker | Source | Start | End | Note |
|---|---|---|---|---|---|---|
| required | dst_shift | TMF | 3 | 2021-03-13 | 2021-11-06 | planted, note summer dates off by -1 day |
| required | dst_shift | TMF | 3 | 2022-03-12 | 2022-11-05 | planted, note summer dates off by -1 day |
| required | unit_scale | TOD | 3 | 2021-08-09 | 2021-11-02 | planted, note amount reported in cents |
| required | date_shift | TSH | 3 | 2020-03-01 | end | planted, note dates off by +1 day |
| required | level_shift | TMF | 3 | 2020-12-24 | end | planted, mult 0.67 |
| required | outage | TJA | 4 | 2019-07-04 | 2019-07-29 | planted, note source-wide |
| required | outage | TMF | 4 | 2019-07-04 | 2019-07-29 | planted, note source-wide |
| required | outage | TOD | 4 | 2019-07-04 | 2019-07-29 | planted, note source-wide |
| required | outage | TSH | 4 | 2019-07-04 | 2019-07-29 | planted, note source-wide |
| required | outage | TZF | 4 | 2019-07-04 | 2019-07-29 | planted, note source-wide |
| required | outage | TSH | 1 | 2022-10-21 | end | planted |
| required | outage | TZF | all | 2022-02-27 | 2022-03-15 | natural, note every sensor at 5-10% of normal |
| optional | — | TOD | 4 | 2020-04-26 | 2021-01-26 | start window |
| optional | — | TSH | 4 | 2020-04-26 | 2021-01-26 | start window |
| optional | — | TZF | 3 | 2019-09-10 | 2020-02-10 | start window |
| optional | — | TJA | 3 | 2019-09-10 | 2020-02-10 | start window |
| optional | — | TMF | 3 | 2019-09-10 | 2020-02-10 | start window |
| optional | — | TZF | all | 2022-02-10 | 2022-04-10 | start window |
| optional | — | TOD | 4 | 2022-07-05 | 2022-07-24 | start window |
| optional | — | TJA | 4 | 2022-07-05 | 2022-07-24 | start window |
| optional | — | TSH | 4 | 2022-07-05 | 2022-07-24 | start window |
| not usable | — | TSH | 1 | | | |
| real event | industry shock x0.72 | TJA, TMF, TZF | all | 2020-01-07 | 2020-01-08 | department stores |

## audit-bench-007

| List | Type | Ticker | Source | Start | End | Note |
|---|---|---|---|---|---|---|
| required | amount_shift | TNV | 4 | 2017-08-10 | 2018-01-28 | planted, note amounts include tax or fees, mult 1.32 |
| required | dst_shift | TQM | 2 | 2018-03-11 | 2018-11-04 | planted, note summer dates off by +1 day |
| required | dst_shift | TQM | 2 | 2019-03-10 | 2019-11-03 | planted, note summer dates off by +1 day |
| required | level_shift | TGT | 1 | 2018-05-14 | end | planted, mult 1.49 |
| required | outage | TFX | 3 | 2017-03-04 | 2017-03-27 | planted, note source-wide |
| required | outage | TGT | 3 | 2017-03-04 | 2017-03-27 | planted, note source-wide |
| required | outage | TNV | 3 | 2017-03-04 | 2017-03-27 | planted, note source-wide |
| required | outage | TQM | 3 | 2017-03-04 | 2017-03-27 | planted, note source-wide |
| required | outage | TTR | 3 | 2017-03-04 | 2017-03-27 | planted, note source-wide |
| required | outage | TNV | 1 | 2016-03-25 | 2016-04-16 | planted |
| required | outage | TNV | 1 | 2017-01-19 | 2017-02-06 | planted |
| required | outage | TNV | 1 | 2018-07-09 | 2018-07-29 | planted |
| required | outage | TTR | all | 2019-03-03 | 2019-03-19 | natural, note every sensor at 5-10% of normal |
| optional | — | TNV | 4 | 2017-04-30 | 2018-01-30 | start window |
| optional | — | TQM | 4 | 2017-04-30 | 2018-01-30 | start window |
| optional | — | TTR | 2 | 2016-09-13 | 2017-02-13 | start window |
| optional | — | TFX | 2 | 2016-09-13 | 2017-02-13 | start window |
| optional | — | TGT | 2 | 2016-09-13 | 2017-02-13 | start window |
| optional | — | TTR | all | 2019-02-14 | 2019-04-14 | start window |
| optional | — | TNV | 4 | 2019-07-09 | 2019-07-28 | start window |
| optional | — | TFX | 4 | 2019-07-09 | 2019-07-28 | start window |
| optional | — | TQM | 4 | 2019-07-09 | 2019-07-28 | start window |
| not usable | — | TNV | 1 | | | |
| real event | recurring promotion | TQM | all | 2015-01-10 | 2019-01-16 | 5 period(s), counts x1.78, ticket x0.87 |

## audit-bench-008

| List | Type | Ticker | Source | Start | End | Note |
|---|---|---|---|---|---|---|
| required | dst_shift | TXN | 1 | 2016-03-12 | 2016-11-05 | planted, note summer dates off by -1 day |
| required | dst_shift | TXN | 1 | 2017-03-11 | 2017-11-04 | planted, note summer dates off by -1 day |
| required | swapped_columns | TQZ | 1 | 2015-05-01 | 2015-05-16 | planted |
| required | level_shift | TLY | 1 | 2016-08-08 | 2016-10-19 | planted, mult 1.59 |
| required | outage | TVZ | 3 | 2016-05-08 | 2016-06-07 | planted |
| required | outage | TVZ | 1 | 2017-11-18 | end | planted |
| required | outage | TLY | 2 | 2013-10-29 | 2013-11-10 | planted |
| required | outage | TLY | 2 | 2014-12-10 | 2015-01-07 | planted |
| required | outage | TLY | 2 | 2016-02-27 | 2016-03-14 | planted |
| required | outage | TLD | all | 2017-03-05 | 2017-03-21 | natural, note every sensor at 5-10% of normal |
| optional | — | TVZ | 3 | 2015-05-03 | 2016-02-02 | start window |
| optional | — | TXN | 3 | 2015-05-03 | 2016-02-02 | start window |
| optional | — | TLD | 2 | 2014-09-16 | 2015-02-16 | start window |
| optional | — | TQZ | 2 | 2014-09-16 | 2015-02-16 | start window |
| optional | — | TLY | 2 | 2014-09-16 | 2015-02-16 | start window |
| optional | — | TLD | all | 2017-02-16 | 2017-04-16 | start window |
| optional | — | TVZ | 3 | 2017-07-11 | 2017-07-30 | start window |
| optional | — | TQZ | 3 | 2017-07-11 | 2017-07-30 | start window |
| optional | — | TXN | 3 | 2017-07-11 | 2017-07-30 | start window |
| not usable | — | TLY | 2 | | | |
| not usable | — | TVZ | 1 | | | |
| real event | recurring promotion | TXN | all | 2013-04-21 | 2017-04-29 | 5 period(s), counts x1.59, ticket x0.83 |
| real event | industry shock x0.71 | TVZ, TXN | all | 2015-12-08 | 2015-12-12 | airlines |

## audit-bench-009

| List | Type | Ticker | Source | Start | End | Note |
|---|---|---|---|---|---|---|
| required | unit_scale | TUY | 2 | 2015-01-25 | 2015-04-13 | planted, note amount reported in cents |
| required | outage | TGR | 4 | 2013-12-28 | 2014-01-05 | planted |
| required | double_count | TMY | 2 | 2015-03-10 | 2015-06-18 | planted, share 0.71 |
| required | level_shift | TUY | 2 | 2014-07-23 | end | planted, mult 1.53 |
| required | outage | TFT | 3 | 2014-10-08 | 2014-10-29 | planted, note source-wide |
| required | outage | TGR | 3 | 2014-10-08 | 2014-10-29 | planted, note source-wide |
| required | outage | TMY | 3 | 2014-10-08 | 2014-10-29 | planted, note source-wide |
| required | outage | TUY | 3 | 2014-10-08 | 2014-10-29 | planted, note source-wide |
| required | outage | TVJ | 3 | 2014-10-08 | 2014-10-29 | planted, note source-wide |
| required | outage | TFT | all | 2016-03-06 | 2016-03-22 | natural, note every sensor at 5-10% of normal |
| optional | — | TGR | 4 | 2014-05-04 | 2015-02-03 | start window |
| optional | — | TUY | 4 | 2014-05-04 | 2015-02-03 | start window |
| optional | — | TFT | 2 | 2013-09-17 | 2014-02-17 | start window |
| optional | — | TMY | 2 | 2013-09-17 | 2014-02-17 | start window |
| optional | — | TVJ | 2 | 2013-09-17 | 2014-02-17 | start window |
| optional | — | TFT | all | 2016-02-18 | 2016-04-17 | start window |
| optional | — | TGR | 4 | 2016-07-12 | 2016-07-31 | start window |
| optional | — | TMY | 4 | 2016-07-12 | 2016-07-31 | start window |
| optional | — | TUY | 4 | 2016-07-12 | 2016-07-31 | start window |
| ignore | — | TMY | 4 | | | low volume |
| real event | recurring promotion | TUY | all | 2012-12-06 | 2016-12-15 | 5 period(s), counts x1.32, ticket x0.83 |
| real event | promotion | TUY | all | 2016-04-05 | 2016-04-13 | 1 period(s), counts x1.44, ticket x0.85 |

## audit-bench-010

| List | Type | Ticker | Source | Start | End | Note |
|---|---|---|---|---|---|---|
| required | double_count | TDS | 2 | 2017-12-09 | 2018-02-23 | planted, share 0.73 |
| required | swapped_columns | TOI | 1 | 2018-06-24 | 2018-07-15 | planted |
| required | dst_shift | TLT | 1 | 2018-03-10 | 2018-11-03 | planted, note summer dates off by -1 day |
| required | dst_shift | TLT | 1 | 2019-03-09 | 2019-11-02 | planted, note summer dates off by -1 day |
| required | level_shift | TQU | 3 | 2017-05-18 | 2017-10-27 | planted, mult 0.68 |
| required | level_shift | TLT | 1 | 2018-04-21 | 2018-08-11 | planted, mult 0.69 |
| required | outage | TDS | 2 | 2017-09-23 | 2017-10-19 | planted, note source-wide |
| required | outage | THV | 2 | 2017-09-23 | 2017-10-19 | planted, note source-wide |
| required | outage | TLT | 2 | 2017-09-23 | 2017-10-19 | planted, note source-wide |
| required | outage | TOI | 2 | 2017-09-23 | 2017-10-19 | planted, note source-wide |
| required | outage | TQU | 2 | 2017-09-23 | 2017-10-19 | planted, note source-wide |
| required | outage | TQU | 1 | 2019-09-24 | end | planted |
| required | outage | TOI | 3 | 2015-12-19 | 2016-01-05 | planted |
| required | outage | TOI | 3 | 2017-06-04 | 2017-06-29 | planted |
| required | outage | TOI | 3 | 2018-09-19 | 2018-10-12 | planted |
| required | outage | THV | all | 2019-03-03 | 2019-03-19 | natural, note every sensor at 5-10% of normal |
| optional | — | TDS | 4 | 2017-04-30 | 2018-01-30 | start window |
| optional | — | TQU | 4 | 2017-04-30 | 2018-01-30 | start window |
| optional | — | THV | 2 | 2016-09-13 | 2017-02-13 | start window |
| optional | — | TLT | 2 | 2016-09-13 | 2017-02-13 | start window |
| optional | — | TOI | 2 | 2016-09-13 | 2017-02-13 | start window |
| optional | — | THV | all | 2019-02-14 | 2019-04-14 | start window |
| optional | — | TDS | 4 | 2019-07-09 | 2019-07-28 | start window |
| optional | — | TLT | 4 | 2019-07-09 | 2019-07-28 | start window |
| optional | — | TQU | 4 | 2019-07-09 | 2019-07-28 | start window |
| ignore | — | TLT | 4 | | | low volume |
| not usable | — | TOI | 3 | | | |
| not usable | — | TQU | 1 | | | |
| real event | industry shock x0.52 | THV, TLT, TOI | all | 2018-07-03 | 2018-07-05 | department stores |
| real event | promotion | TLT | all | 2018-06-11 | 2018-06-18 | 1 period(s), counts x1.48, ticket x0.85 |

## audit-bench-control-01

| List | Type | Ticker | Source | Start | End | Note |
|---|---|---|---|---|---|---|
| required | outage | TNU | all | 2019-03-03 | 2019-03-19 | natural, note every sensor at 5-10% of normal |
| optional | — | TLB | 4 | 2017-04-30 | 2018-01-30 | start window |
| optional | — | TCG | 4 | 2017-04-30 | 2018-01-30 | start window |
| optional | — | TNU | 3 | 2016-09-13 | 2017-02-13 | start window |
| optional | — | TUF | 3 | 2016-09-13 | 2017-02-13 | start window |
| optional | — | TPX | 3 | 2016-09-13 | 2017-02-13 | start window |
| optional | — | TNU | all | 2019-02-14 | 2019-04-14 | start window |
| optional | — | TLB | 4 | 2019-07-09 | 2019-07-28 | start window |
| optional | — | TUF | 4 | 2019-07-09 | 2019-07-28 | start window |
| optional | — | TCG | 4 | 2019-07-09 | 2019-07-28 | start window |
| real event | industry shock x0.69 | TCG, TLB | all | 2016-05-26 | 2016-05-27 | airlines |

## audit-bench-control-02

| List | Type | Ticker | Source | Start | End | Note |
|---|---|---|---|---|---|---|
| required | outage | TDA | all | 2017-03-05 | 2017-03-21 | natural, note every sensor at 5-10% of normal |
| optional | — | TQA | 3 | 2015-05-03 | 2016-02-02 | start window |
| optional | — | TGN | 3 | 2015-05-03 | 2016-02-02 | start window |
| optional | — | TDA | 2 | 2014-09-16 | 2015-02-16 | start window |
| optional | — | TMQ | 2 | 2014-09-16 | 2015-02-16 | start window |
| optional | — | TKG | 2 | 2014-09-16 | 2015-02-16 | start window |
| optional | — | TDA | all | 2017-02-16 | 2017-04-16 | start window |
| optional | — | TQA | 3 | 2017-07-11 | 2017-07-30 | start window |
| optional | — | TMQ | 3 | 2017-07-11 | 2017-07-30 | start window |
| optional | — | TGN | 3 | 2017-07-11 | 2017-07-30 | start window |
| real event | industry shock x0.66 | TGN, TQA | all | 2015-06-03 | 2015-06-07 | airlines |
