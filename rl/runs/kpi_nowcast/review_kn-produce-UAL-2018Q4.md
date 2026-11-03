# kn-produce-UAL-2018Q4: agent output and grades

Model `claude-opus-5-5` (high effort), 13 code calls, 173.0s. Judge `claude-sonnet-5-5`.

## Grades

- **Reported:** 9,556. **Forecast:** 9,232 (range 8,800–9,670, 90%). **Naive:** 9,588
- **Accuracy:** miss -3.4%, in range: yes, skill vs naive -0.82, interval score 0.091
- **Write-up score:** 0.91

| Item | Judge | Reason |
|---|---|---|
| C1 | pass | The first lines give 2018Q4, about $9.23B, a 90% range of $8.80B–$9.67B, and the growth rate; the units are in dollars (B) and the JSON uses USD millions. |
| C2 | pass | Plain-language explanation of year-over-year growth and the back-test; 'percentile miss' is explained as the typical and worst miss; no unexplained jargon. |
| C3 | pass | Table covers all four sources with evidence: source 1 spend roughly tripled in 2016-17 and is sparse, source 2 adds about +10 points of growth per quarter, source 4 takes about -5 points off; source 3 shows no bias. |
| C4 | pass | Names the source 1 level shift (spend roughly tripled in 2016–17 from a source change) and excludes it; also covers the panel drift in sources 2 and 4 and the anomaly check on days. |
| C5 | pass | Notes the ASC 606 restatement of 2017 (+6.1–6.7%), applies a 1.064 factor to the 2017Q4 base, and labels the in-sample table basis. |
| C6 | fail | Reports in-sample misses (mean 2.1%, median 1.1%) but never compares them with a naive benchmark such as same-as-last-year. |
| C7 | pass | Uses only data through 2018Q3 and the sensor data; no post-as-of information is cited. |
| C8 | na | No consensus was provided, and the write-up says so. |
| C9 | pass | Gives case-specific risks: the restated Q4 base is an estimate, source 3 was chosen with hindsight, the Q3-to-Q4 slowdown, and a recent bias to under-forecast. |
| C10 | pass | Point 9,232, range 8,800–9,670 (8.80B–9.67B) and the 90% level match the JSON; in-sample numbers match too. |
| C11 | pass | States 15 quarters, says the choice of source 3 was made after seeing the full history so the record is flattering, and notes that 2014 is not modelled. |
| C12 | pass | Flags the source 1 panel change and the ASC 606 restatement as structural issues, along with the drift in the source panels. |

## Grader facts the judge saw (not visible to the agent)

```json
{
  "reporting_basis_and_structural": [
    "Reporting basis changed: 3 earlier quarter(s) were re-reported in filings from 2018-04-18 on, by +6.1% to +6.7% (e.g. a new accounting standard or a segment redefinition). The target quarter will be reported on the new basis; its same-quarter-last-year comparable is NOT yet available on the new basis (only its original figure is in the feed)."
  ],
  "sensor_data_quality_auto": [
    "UAL source 1: spend changed +77% 2015->2016 vs -4% on the other sources (level shift / panel change)",
    "UAL source 1: spend changed +111% 2016->2017 vs +2% on the other sources (level shift / panel change)"
  ]
}
```

## Agent's final message (verbatim)

~~~~markdown
I estimate UAL's 2018Q4 passenger revenue at about **$9.23B**, with a 90% range of **$8.80B to $9.67B**. That is about 7.4% growth over the same quarter last year.

## Write-up for the investment staff

### How the estimate is built
1. **Use year-over-year growth, not raw dollar levels.** The number of cardholders behind each data source changes over time, so the raw dollar totals drift. Comparing each quarter with the same quarter a year earlier removes most of that drift and also handles seasonality.
2. **Source 3 is the only source used.** I checked each of the four sources against UAL's reported growth over 15 quarters (2015Q1–2018Q3):

| Source | What's going on | Usable? |
|---|---|---|
| 1 | Very few transactions per day, so it's noisy. Its UAL spend also roughly tripled during 2016–17 because the source changed, not because UAL grew. | No |
| 2 | Its panel grows steadily, adding about +10 points of growth every quarter. | No |
| 3 | Its growth matches UAL's reported growth closely, with no bias. | **Yes** |
| 4 | Its panel shrinks, taking about −5 points off every quarter. | Cross-check only |

   Source 3 is used exactly as reported, with no fitted weights or adjustments. Adding sources 2 and 4 after correcting for their drift made the back-test worse, or improved it only trivially.
3. **Bad-data check.** I compared each day with the same weekday over the prior 8 weeks. In sources 2–4 the only dips are holidays like Christmas and Thanksgiving, which fall in the same place each year and cancel out in year-over-year comparisons. Only source 1 needed fixing (16 days).
4. **Same accounting basis.** In 2018 UAL adopted a new revenue-recognition rule (ASC 606), which moved some revenue into passenger revenue. Its 2017 figures were restated up by 6.1–6.7%. Because 2018 is compared with restated 2017, the comparisons are like-for-like. The restated 2017Q4 figure hasn't been published yet, so I applied the average restatement factor (1.064) to the original $8,080M, which gives a base of about **$8,596M**.

### The 2018Q4 estimate
- Source 3 UAL spend in 2018Q4 was up **7.4%** on the year: October +7%, November +6%, December +9.5%.
- $8,596M × 1.074 ≈ **$9,232M**.
- **Range of $8.80B–$9.67B (±4.7%).** This is the 90th-percentile miss from the 15-quarter back-test. The typical miss is 2.1% on average, and 1.1% at the median.

### How much to trust it
- **The back-test is effectively out-of-sample.** The method has no fitted parameters. However, I chose source 3 after seeing the full history, so the record is a little flattering.
- **Recent misses have mostly been too low.** In 2017Q4–2018Q2 the estimate came in 1–2.5% under. 2018Q3 was very close (+0.4%).
- **Biggest past misses:** 2016Q4 (+5.8%) and 2015Q3 (+6.9%).
- **Slowdown from Q3 to Q4.** All three usable sources slow down. Source 3 drops 4.6 points; sources 2 and 4 drop about 2.4 points each.
  - If I apply the average slowdown of the three sources to UAL's reported Q3 growth of 11.6%, I get about 8.5% growth, or roughly **$9.33B**.
  - Source 4 corrected for its drift gives about 7.9%.
  - I keep $9.23B as the main estimate. The risks lean slightly upward, mainly because the misses before Q3 were mostly too low.
- **No consensus figure was provided,** so I can't compare the estimate with the Street.
- **Quarters not modelled:** 2014 can't be estimated this way, because the sensor data starts in January 2014 and there's no prior year to compare against.

### In-sample estimates vs. reported ($M)
| Qtr | Est. | Reported | Miss |
|---|---|---|---|
| 15Q1 | 7,631 | 7,420 | +2.8% |
| 15Q2 | 8,945 | 8,676 | +3.1% |
| 15Q3 | 9,580 | 8,960 | +6.9% |
| 15Q4 | 7,811 | 7,729 | +1.1% |
| 16Q1 | 6,954 | 6,990 | −0.5% |
| 16Q2 | 8,065 | 8,103 | −0.5% |
| 16Q3 | 8,426 | 8,603 | −2.1% |
| 16Q4 | 8,207 | 7,761 | +5.8% |
| 17Q1 | 7,215 | 7,174 | +0.6% |
| 17Q2 | 8,535 | 8,622 | −1.0% |
| 17Q3 | 8,504 | 8,528 | −0.3% |
| 17Q4 | 7,894 | 8,080 | −2.3% |
| 18Q1 | 7,941 | 8,149 | −2.6% |
| 18Q2 | 9,768 | 9,880 | −1.1% |
| 18Q3 | 10,162 | 10,120 | +0.4% |

The 2017 quarters are on the old accounting basis. The 2018 quarters are on the new basis.

Files are in the output folder:
- `model.py` – the code that rebuilds the estimates
- `estimates.csv` – the quarterly table above
- `ual_passenger_revenue.png` – a chart of the estimates against reported revenue

```json
{"target_period": "2018Q4", "unit": "USD millions",
 "point": 9232, "low": 8800, "high": 9670, "interval_level": 0.9,
 "in_sample": [{"period_end": "2015-03-31", "estimate": 7631}, {"period_end": "2015-06-30", "estimate": 8945}, {"period_end": "2015-09-30", "estimate": 9580}, {"period_end": "2015-12-31", "estimate": 7811}, {"period_end": "2016-03-31", "estimate": 6954}, {"period_end": "2016-06-30", "estimate": 8065}, {"period_end": "2016-09-30", "estimate": 8426}, {"period_end": "2016-12-31", "estimate": 8207}, {"period_end": "2017-03-31", "estimate": 7215}, {"period_end": "2017-06-30", "estimate": 8535}, {"period_end": "2017-09-30", "estimate": 8504}, {"period_end": "2017-12-31", "estimate": 7894}, {"period_end": "2018-03-31", "estimate": 7941}, {"period_end": "2018-06-30", "estimate": 9768}, {"period_end": "2018-09-30", "estimate": 10162}],
 "vs_consensus": "no_consensus"}
```
~~~~
