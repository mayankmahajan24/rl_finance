Press release (Cobalt Harbor Semiconductor, CBHS, Q4 FY2025):

<<<
COBALT HARBOR SEMICONDUCTOR REPORTS Q4 FISCAL 2025 RESULTS

Cobalt Harbor Semiconductor (NASDAQ: CBHS) today announced financial results for the fourth quarter of fiscal 2025. Revenue was $4,218,000 thousand, up 34.3% year over year. GAAP net income was $600,100 thousand, or $0.50 per diluted share. Non-GAAP net income was $1,207,850 thousand, or $1.00 per diluted share. Results include a $215,000 thousand inventory write-down (charge), a $90,000 thousand litigation settlement (charge), which are excluded from non-GAAP measures along with stock-based compensation of $410,000 thousand. For fiscal 2025, the company now expects revenue of $18,900,000 thousand to $19,500,000 thousand and a non-GAAP operating margin of approximately 33.0%.

Condensed income statement (in thousands, unaudited)
  Revenue                       $4,218,000 thousand
  Cost of revenue               $1,897,000 thousand
  Gross profit                  $2,321,000 thousand
  Operating expenses            $1,615,000 thousand (incl. $305,000 thousand of items noted above)
  Operating income (loss)       $706,000 thousand
  Income tax expense            $105,900 thousand
  Net income (loss)             $600,100 thousand
  Diluted shares (millions)     1,205.0

Prior-year quarter: revenue $3,140,000 thousand; operating income $540,000 thousand.
>>>

Task: Reconcile GAAP and non-GAAP results.
  - one_time_items: list of the one-time / non-recurring items named in the release
    (short labels as written; do NOT include stock-based compensation)
  - one_time_items_net_musd: net impact of those items on operating income in USD millions
    (charges positive, gains negative)
  - sbc_is_one_time_item: true/false - is stock-based compensation a one-time item?
  - net_income_gaap_musd / net_income_non_gaap_musd: in USD millions
  - eps_gaap / eps_non_gaap: diluted EPS
  - guidance_basis: "GAAP" or "non-GAAP" - the basis on which guidance is given

Write a two-sentence recap, then a ```json block with exactly these keys:
one_time_items, one_time_items_net_musd, sbc_is_one_time_item, net_income_gaap_musd, net_income_non_gaap_musd, eps_gaap, eps_non_gaap, guidance_basis.
