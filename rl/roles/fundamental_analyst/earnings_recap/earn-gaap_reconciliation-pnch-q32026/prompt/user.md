Press release (Pinecrest Hospitality, PNCH, Q3 FY2026):

<<<
PINECREST HOSPITALITY REPORTS Q3 FISCAL 2026 RESULTS

Pinecrest Hospitality (NASDAQ: PNCH) today announced financial results for the third quarter of fiscal 2026. Revenue was $1,576.0 million, up 5.2% year over year. GAAP net income was $119.9 million, or $0.58 per diluted share. Non-GAAP net income was $143.6 million, or $0.69 per diluted share. Results include a $54.0 million hurricane-related losses (charge), a $31.0 million insurance recoveries (gain), which are excluded from non-GAAP measures along with stock-based compensation of $9.0 million. For fiscal 2026, the company now expects revenue of $6,050.0 million to $6,150.0 million and a non-GAAP operating margin of approximately 12.0%.

Condensed income statement (in millions, unaudited)
  Revenue                       $1,576.0 million
  Cost of revenue               $1,012.0 million
  Gross profit                  $564.0 million
  Operating expenses            $402.0 million (incl. $23.0 million of items noted above)
  Operating income (loss)       $162.0 million
  Income tax expense            $42.1 million
  Net income (loss)             $119.9 million
  Diluted shares (millions)     208.0

Prior-year quarter: revenue $1,498.0 million; operating income $160.0 million.
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
