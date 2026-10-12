Press release (Northgate Consumer Brands, NGCB, Q3 FY2026):

<<<
NORTHGATE CONSUMER BRANDS REPORTS Q3 FISCAL 2026 RESULTS

Northgate Consumer Brands (NASDAQ: NGCB) today announced financial results for the third quarter of fiscal 2026. Revenue was $2,765.0 million, up 2.5% year over year. Non-GAAP net income was $247.5 million, or $0.82 per diluted share. GAAP net income was $168.0 million, or $0.56 per diluted share. Results include a $120.0 million brand impairment (charge), a $45.0 million gain on divestiture (gain), which are excluded from non-GAAP measures along with stock-based compensation of $31.0 million. For fiscal 2026, the company now expects revenue of $11,100.0 million to $11,300.0 million and a non-GAAP operating margin of approximately 9.0%.

Condensed income statement (in millions, unaudited)
  Revenue                       $2,765.0 million
  Cost of revenue               $1,587.0 million
  Gross profit                  $1,178.0 million
  Operating expenses            $954.0 million (incl. $75.0 million of items noted above)
  Operating income (loss)       $224.0 million
  Income tax expense            $56.0 million
  Net income (loss)             $168.0 million
  Diluted shares (millions)     301.0

Prior-year quarter: revenue $2,698.0 million; operating income $236.0 million.
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
