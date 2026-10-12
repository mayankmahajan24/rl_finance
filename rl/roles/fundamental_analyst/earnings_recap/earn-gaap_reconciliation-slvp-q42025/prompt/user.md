Press release (Silverline Payments, SLVP, Q4 FY2025):

<<<
SILVERLINE PAYMENTS REPORTS Q4 FISCAL 2025 RESULTS

Silverline Payments (NASDAQ: SLVP) today announced financial results for the fourth quarter of fiscal 2025. Revenue was $1.398 billion, up 21.3% year over year. GAAP net income was $0.208 billion, or $0.75 per diluted share. Non-GAAP net income was $0.346 billion, or $1.25 per diluted share. Results include a $0.027 billion acquisition-related costs (charge), which is excluded from non-GAAP measures along with stock-based compensation of $0.142 billion. For fiscal 2025, the company now expects revenue of $6.200 billion to $6.400 billion and a non-GAAP operating margin of approximately 24.0%.

Condensed income statement (in billions, unaudited)
  Revenue                       $1.398 billion
  Cost of revenue               $0.412 billion
  Gross profit                  $0.986 billion
  Operating expenses            $0.729 billion (incl. $0.027 billion of items noted above)
  Operating income (loss)       $0.257 billion
  Income tax expense            $0.049 billion
  Net income (loss)             $0.208 billion
  Diluted shares (millions)     276.4

Prior-year quarter: revenue $1.153 billion; operating income $0.190 billion.
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
