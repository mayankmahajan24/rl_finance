Press release (Meridian Freight Systems, MFRT, Q2 FY2026):

<<<
MERIDIAN FREIGHT SYSTEMS REPORTS Q2 FISCAL 2026 RESULTS

Meridian Freight Systems (NASDAQ: MFRT) today announced financial results for the second quarter of fiscal 2026. Revenue was $963.8 million, down 5.6% year over year. GAAP net income was $89.0 million, or $1.01 per diluted share. Non-GAAP net income was $50.6 million, or $0.57 per diluted share. Results include a $62.5 million gain on sale of terminal assets (gain), which is excluded from non-GAAP measures along with stock-based compensation of $12.0 million. For fiscal 2026, the company now expects revenue of $3,850.0 million to $3,950.0 million on a GAAP basis.

Condensed income statement (in millions, unaudited)
  Revenue                       $963.8 million
  Cost of revenue               $711.0 million
  Gross profit                  $252.8 million
  Operating expenses            $135.7 million (incl. $-62.5 million of items noted above)
  Operating income (loss)       $117.1 million
  Income tax expense            $28.1 million
  Net income (loss)             $89.0 million
  Diluted shares (millions)     88.2

Prior-year quarter: revenue $1,021.4 million; operating income $118.0 million.
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
