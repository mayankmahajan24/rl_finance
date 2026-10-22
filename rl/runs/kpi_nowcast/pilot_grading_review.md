# Pilot grading review

Four pilot runs (`claude-opus-5-5`, high effort), graded by `claude-sonnet-5-5` on rubric C1–C12, plus the programmatic accuracy metrics.
For each case, read the write-up (end of the linked transcript) and mark any verdict you would have scored differently.

Note: these grades used the **old** grader facts. ALK's C5 failure is a known grader bug, fixed in the as-of-aware facts.

## Rubric

- **C1**: States the target period, the point estimate, the range and the units within the first screen of text (roughly the first 15 lines).
- **C2**: Explains the method in plain language; any statistical term used (R², MAPE, regression, standard deviation, confidence interval) is explained in words or avoided.
- **C3**: Says which data sources/sensors were used and why any were excluded, citing evidence (a number, a comparison, a chart description), not just an adjective like "noisy".
- **C4**: Names the main data-quality problems present in this case's sensors and says how each was handled. Compare against grader_facts.sensor_data_quality_auto: the write-up must cover the large level shifts / panel changes listed there (it need not list every minor gap). If grader facts list none, pass if the write-up describes a data check it ran.
- **C5**: Compares periods on a consistent reporting basis. If grader_facts.reporting_basis_and_structural lists an accounting change, restatement, fiscal calendar effect (53-week year) or segment redefinition that affects the comparisons used, the write-up must notice it and handle or caveat it. If none apply, pass if the write-up doesn't introduce an inconsistency.
- **C6**: Reports in-sample accuracy next to a simple benchmark (e.g. "same as last year" or a seasonal naive).
- **C7**: Makes no claim that depends on information dated after the as-of date (e.g. citing the target quarter's reported figure, later restatements, or later consensus).
- **C8**: If the task provided consensus: compares with it and states the implied beat/miss with a confidence level. Mark na when the task provided no consensus.
- **C9**: Caveats are specific to this case: names the weakest assumption and what would make the estimate wrong.
- **C10**: Every number in the write-up that also appears in forecast_json (point, low, high, interval level) matches it.
- **C11**: Does not overclaim: in-sample fit is not presented as validation of out-of-sample accuracy, the sample size (number of quarters) is stated, and limits of the approach are acknowledged.
- **C12**: If grader_facts list a structural break specific to this case (merger, store closures, sensor/KPI coverage mismatch, combining multiple sensor tickers, segment redefinition), the write-up flags it. Mark na when none is listed.

## kn-produce-AIR03-2018Q4-anon

- **Target:** 2018Q4 passenger revenue. **Reported:** 21,625.6. **Naive:** 21,698.9
- **Forecast:** 20,839 (range 19,796–21,883 at 90%)
- **Accuracy:** miss -3.6%, in range: yes, skill vs naive -0.83, interval score 0.097
- **Write-up score:** 0.90
- **Transcript:** [`traces/kn-produce-AIR03-2018Q4-anon_rep0.json`](baseline/traces/kn-produce-AIR03-2018Q4-anon_rep0.json)

| Item | Judge | Judge's reason | You'd score it… |
|---|---|---|---|
| C1 | pass | Opening lines give 2018Q4, ~$20.8bn point, 90% range $19.8–21.9bn, and USD units. | |
| C2 | pass | Method explained plainly (growth ratio, straight-line fit, applied to last year's base); 'correlation 0.87' is the only technical term and it is not jargon-heavy. | |
| C3 | pass | Explains each sensor's exclusion with evidence: Sensor 2 grew 10–16% while revenue fell, Sensor 1 spend grew several-fold, Sensor 4 drifts down 3–5% with Saturday dropouts. | |
| C4 | pass | Flags Sensor 1's several-fold 2016–2017 jump (the panel level shift) and excludes it; also covers dropouts and the Sensor 3 checks. | |
| C5 | pass | Identifies the ASC 606 restatement of 2017Q1–Q3 (~6.1–6.7%) and puts 2017Q4 on the new basis by applying the average uplift. | |
| C6 | fail | Reports in-sample average miss (2.0%) but gives no simple benchmark such as same-as-last-year or seasonal naive. | |
| C7 | pass | Uses only data through the as-of date; the 2017Q4 restatement is treated as pending and estimated, not looked up. | |
| C8 | na | No consensus was provided, and the write-up says so. | |
| C9 | pass | Names specific risks: the 2017Q4 restatement uplift (each 0.5pp ≈ $100m), reliance on a single sensor panel, and only 15 data points. | |
| C10 | pass | Point $20,839m, range $19,796m–$21,883m and 90% level match the JSON. | |
| C11 | pass | States the sample is 15 quarters, reports misses on quarters the model hadn't seen, and acknowledges single-sensor limits. | |
| C12 | na | The grader facts list no structural break beyond the ASC 606 reporting-basis change (covered in C5) and sensor panel shifts (covered in C4). | |

## kn-produce-UAL-2018Q4

- **Target:** 2018Q4 passenger revenue. **Reported:** 9,556.0. **Naive:** 9,588.4
- **Forecast:** 9,232 (range 8,800–9,670 at 90%)
- **Accuracy:** miss -3.4%, in range: yes, skill vs naive -0.82, interval score 0.091
- **Write-up score:** 0.91
- **Transcript:** [`traces/kn-produce-UAL-2018Q4_rep0.json`](baseline/traces/kn-produce-UAL-2018Q4_rep0.json)

| Item | Judge | Judge's reason | You'd score it… |
|---|---|---|---|
| C1 | pass | The first lines give 2018Q4, about $9.23B, a 90% range of $8.80B–$9.67B, and the growth rate; the units are in dollars (B) and the JSON uses USD millions. | |
| C2 | pass | Plain-language explanation of year-over-year growth and the back-test; 'percentile miss' is explained as the typical and worst miss; no unexplained jargon. | |
| C3 | pass | Table covers all four sources with evidence: source 1 spend roughly tripled in 2016-17 and is sparse, source 2 adds about +10 points of growth per quarter, source 4 takes about -5 points off; source 3 shows no bias. | |
| C4 | pass | Names the source 1 level shift (spend roughly tripled in 2016–17 from a source change) and excludes it; also covers the panel drift in sources 2 and 4 and the anomaly check on days. | |
| C5 | pass | Notes the ASC 606 restatement of 2017 (+6.1–6.7%), applies a 1.064 factor to the 2017Q4 base, and labels the in-sample table basis. | |
| C6 | fail | Reports in-sample misses (mean 2.1%, median 1.1%) but never compares them with a naive benchmark such as same-as-last-year. | |
| C7 | pass | Uses only data through 2018Q3 and the sensor data; no post-as-of information is cited. | |
| C8 | na | No consensus was provided, and the write-up says so. | |
| C9 | pass | Gives case-specific risks: the restated Q4 base is an estimate, source 3 was chosen with hindsight, the Q3-to-Q4 slowdown, and a recent bias to under-forecast. | |
| C10 | pass | Point 9,232, range 8,800–9,670 (8.80B–9.67B) and the 90% level match the JSON; in-sample numbers match too. | |
| C11 | pass | States 15 quarters, says the choice of source 3 was made after seeing the full history so the record is flattering, and notes that 2014 is not modelled. | |
| C12 | pass | Flags the source 1 panel change and the ASC 606 restatement as structural issues, along with the drift in the source panels. | |

## kn-produce-JWN_FP-FY2018Q3

- **Target:** FY2018 Q3 full-price net sales. **Reported:** 2,367.0. **Naive:** 2,022.7
- **Forecast:** 2,082 (range 1,959–2,213 at 90%)
- **Accuracy:** miss -12.0%, in range: no, skill vs naive +0.09, interval score 1.409
- **Write-up score:** 1.00
- **Transcript:** [`traces/kn-produce-JWN_FP-FY2018Q3_rep0.json`](baseline/traces/kn-produce-JWN_FP-FY2018Q3_rep0.json)

| Item | Judge | Judge's reason | You'd score it… |
|---|---|---|---|
| C1 | pass | The opening paragraph gives FY2018 Q3, $2,082M, the $1,959M–$2,213M 90% range and USD millions. | |
| C2 | pass | The method is explained in plain steps. Terms like 'median growth' and 'fitted a simple line' are described in words, and there is no unexplained jargon. | |
| C3 | pass | Source 1 is excluded as tiny (~80 transactions/day) and noisy, and the flags are concentrated there. Sources 2–4 are used and described as essentially clean. | |
| C4 | pass | It covers the Source 1 outlier days, and the level shifts (Source 1 +80% in 2017, Source 3 −10% in 2016). These are handled by detrending against panel median growth and dropping Source 1. | |
| C5 | pass | It notices the segment restatement and the 53-week FY17. It restates the Q3 FY17 base using the Q1 and Q2 uplifts, and it uses exact fiscal dates. | |
| C6 | pass | In-sample error is 2.4% and out-of-sample 2.8%, against a roll-forward-last-year benchmark at 3.6%. | |
| C7 | pass | Nothing relies on information after 2018-11-03; it uses only the restatements already published. | |
| C8 | na | No consensus was provided. | |
| C9 | pass | The risks section names the restatement basis as the weakest assumption. It also covers the sensor/sales divergence seen in Q2 FY18 and the Anniversary Sale timing. | |
| C10 | pass | The point of 2,082, the range of 1,959–2,213 and the 90% level all match the JSON. | |
| C11 | pass | It states 14 quarters, separates out-of-sample from in-sample error, and says the sensors help only modestly. It also flags the model misses in FY18. | |
| C12 | pass | It flags the segment redefinition, the 53-week year and the sensor level shifts specific to this case. | |

## kn-produce-ALK-2017Q4

- **Target:** 2017Q4 passenger revenue. **Reported:** 1,703.0. **Naive:** 1,777.1
- **Forecast:** 1,675 (range 1,555–1,805 at 90%)
- **Accuracy:** miss -1.6%, in range: yes, skill vs naive +0.45, interval score 0.147
- **Write-up score:** 0.82
- **Transcript:** [`traces/kn-produce-ALK-2017Q4_rep0.json`](baseline/traces/kn-produce-ALK-2017Q4_rep0.json)

| Item | Judge | Judge's reason | You'd score it… |
|---|---|---|---|
| C1 | pass | Opening lines give 2017Q4, $1,675M point, 90% range $1,555M–$1,805M, and USD millions units. | |
| C2 | pass | Method is explained plainly (share of airline card spend, lead-time, growth applied to year-ago quarter); 'one standard deviation' is used without explanation, but it is minor and the rest is in words. | |
| C3 | pass | Says Source 3 chosen; excludes Source 4 because ALK spend flat in 2017 while revenue rose 30–40%, Source 2 panel grows 15–20%/yr, Source 1 too few transactions; American excluded for breaks. | |
| C4 | fail | Notes Source 4 and panel drift, but dismisses Source 1 as 'too few transactions' and claims none of ALK's unusual days needed removing; does not address Source 1's missing days or its large level shifts (+93%, +156%). | |
| C5 | fail | Flags Virgin America in the 2016Q4 base quarter, but does not mention the ASC 606 restatement of 2017 revenue (~5%), and actuals include re-reported figures not discussed. | |
| C6 | pass | Reports in-sample error (2.8% fitted, 3.4% leave-one-out) and a seasonal rule cross-check, but no benchmark error for the naive rule is given; the seasonal rule is only a forecast comparison. | |
| C7 | pass | No use of post-2017-12-31 information; the target quarter's reported figure is not cited. | |
| C8 | na | No consensus was provided in the task. | |
| C9 | pass | Names the weakest assumption: calibration on only three post-merger quarters and the possibility that Source 3's 2017 jump was a sensor change; also notes recent misses running low. | |
| C10 | pass | Point 1675, range 1555–1805 and 90% level in the write-up match the JSON. | |
| C11 | pass | States about 10–11 usable quarters, distinguishes fitted from leave-one-out error, widens the range, and acknowledges the effective sample of three post-merger quarters. | |
| C12 | pass | Flags the Virgin America merger as a structural break, including its timing within the 2016Q4 base and Source 4 missing the deal. | |
