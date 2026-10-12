Press release (Halcyon Networks, HLCN, Q3 FY2026):

<<<
HALCYON NETWORKS REPORTS Q3 FISCAL 2026 RESULTS

Halcyon Networks (NASDAQ: HLCN) today announced financial results for the third quarter of fiscal 2026. Revenue was $1,842.3 million, compared with $1,610.5 million in the prior-year quarter. GAAP net income was $246.3 million, or $0.60 per diluted share. Non-GAAP net income was $360.1 million, or $0.87 per diluted share. Results include a $48.0 million restructuring charges (charge), which is excluded from non-GAAP measures along with stock-based compensation of $96.0 million. For fiscal 2026, the company now expects revenue of $7,400.0 million to $7,550.0 million and a non-GAAP operating margin of approximately 19.5%.

Condensed income statement (in millions, unaudited)
  Revenue                       $1,842.3 million
  Cost of revenue               $702.1 million
  Gross profit                  $1,140.2 million
  Operating expenses            $828.4 million (incl. $48.0 million of items noted above)
  Operating income (loss)       $311.8 million
  Income tax expense            $65.5 million
  Net income (loss)             $246.3 million
  Diluted shares (millions)     412.5

Prior-year quarter: revenue $1,610.5 million; operating income $262.0 million.
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
