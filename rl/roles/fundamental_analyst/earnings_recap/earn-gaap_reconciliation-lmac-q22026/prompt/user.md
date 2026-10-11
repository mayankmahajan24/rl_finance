Press release (Lumen Analytics Cloud, LMAC, Q2 FY2026):

<<<
LUMEN ANALYTICS CLOUD REPORTS Q2 FISCAL 2026 RESULTS

Lumen Analytics Cloud (NASDAQ: LMAC) today announced financial results for the second quarter of fiscal 2026. Revenue was $486.9 million, compared with $352.2 million in the prior-year quarter. Non-GAAP net income was $82.2 million, or $0.58 per diluted share. GAAP net loss was $5.8 million, or $0.04 per diluted share (loss). Non-GAAP measures exclude stock-based compensation of $88.0 million; there were no other adjusting items in the quarter. For fiscal 2026, the company now expects revenue of $2,010.0 million to $2,030.0 million and a non-GAAP operating margin of approximately 4.0%.

Condensed income statement (in millions, unaudited)
  Revenue                       $486.9 million
  Cost of revenue               $121.7 million
  Gross profit                  $365.2 million
  Operating expenses            $371.0 million
  Operating income (loss)       $-5.8 million
  Income tax expense            $0.0 million
  Net income (loss)             $-5.8 million
  Diluted shares (millions)     142.8

Prior-year quarter: revenue $352.2 million; operating income $-41.0 million.
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
