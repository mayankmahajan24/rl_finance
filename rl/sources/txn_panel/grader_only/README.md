# Gold KPI table

Built 2026-10-18 from SEC XBRL instance documents for every 10-Q/10-K filed 2014-01 to 2019-06 by the 16 companies (17 series). Regenerate it with:

```
python3 -I fetch_xbrl.py <cik ...>   # sec/facts/CIK*.csv, one row per revenue-like fact incl. dimensions
python3 -I assemble_gold.py          # gold/kpi_facts.csv, gold/kpi_quarterly.csv
python3 -I check_gold.py             # consistency checks
```

| File | One row per | Use |
|---|---|---|
| `kpi_facts.csv` | (series, quarter, filing that reported it) | Point-in-time actuals feed: keep rows with `filed` ≤ as-of date. Includes restated comparatives |
| `kpi_quarterly.csv` | (series, quarter) | Gold target = `first_value` (as first reported). `latest_value` / `restated_pct` show later restatements |

Every value carries its filing (`accession`, `filed`, `source` = instance-document URL). Q4 values for companies that don't tag a 3-month Q4 are derived as full year − nine months, flagged `derived`. They're taken either from the same filing, or from a restated full year paired with nine months restated on the same line item.

Line-item mapping per series is in `../series.py` (with comments on each basis change).

## Coverage
17 series, complete: 20 calendar quarters (2014Q1–2018Q4) for the 9 airlines, and 19 fiscal quarters (FY14 Q1–FY18 Q3) for the 8 retail series.

## Sensor–KPI fit
`kpi_fit.py` compares sensor YoY growth (median of the 4 sources) with each candidate KPI's YoY growth, 2015–2017. Results and the choices they drove are in `../../design/cases.md` (amendment 1).

## Checks run
- **Quarters sum to full year** (first reported, direct-Q4 years): 0 mismatches.
- **YoY outside ±15% (consistent basis):** 16 flags, all with known causes. ALK 2017 (Virgin America acquisition), JWN off-price 2015 (Rack expansion), ROST FY17 Q4 (53-week year), SAVE 2017–18 (~25% capacity growth), ALGT 2017Q2.
- **Independent spot-checks against filings and press:**
  - UAL: every quarter matches the frozen run's sources, including restated 2017 and 2018.
  - SAVE 2018Q3 passenger revenue $888.0M sits within total operating revenue of $904.3M (10-Q).
  - JWN 2018Q3 off-price +8.7% and full-price +8.9% match the 10-Q growth rates against the restated base.

## Known quirks (become grader-side facts for the cases)
- **ASC 606 (2018):** airlines' 2017 restated +3% to +8% (Spirit −2.5% because fees moved out of passenger). Retail restatements are small.
- **JWN full-price:** redefined in FY18 (adds Trunk Club and other units). The restated FY17 Q3 was first published 2018-12-10, *after* the FY18 Q3 as-of date, so the feed for that case holds only the old-basis comparable.
- **ALGT:** "passenger revenue" changed meaning in 2018. The KPI is scheduled service throughout.
- **SAVE:** before 2018 the KPI is fares + non-ticket revenue (two line items), matching the 606 "passenger" definition.
- **DDS:** KPI is the retail operations segment. Consolidated net sales also include the CDI construction business, which no card panel sees (changed 2026-10-18).
- **TJX:** the sensor covers TJ Maxx only, while the Marmaxx KPI is TJ Maxx + Marshalls (2015–17 YoY fit 0.02). Its tasks are tagged `low_signal` and reported separately.
- **Retail FY17 Q4:** 53-week year (14-week quarter).
