Press release (Verdant Agri Holdings, VRDA, Q1 FY2026):

<<<
VERDANT AGRI HOLDINGS REPORTS Q1 FISCAL 2026 RESULTS

Verdant Agri Holdings (NASDAQ: VRDA) today announced financial results for the first quarter of fiscal 2026. Revenue was $845.5 million, up 7.0% year over year. GAAP net income was $55.0 million, or $0.46 per diluted share. Non-GAAP net income was $46.6 million, or $0.39 per diluted share. Results include a $18.0 million legal reserve release (gain), which is excluded from non-GAAP measures along with stock-based compensation of $7.5 million. For fiscal 2026, the company expects revenue of $3,500.0 million to $3,650.0 million and a non-GAAP operating margin of approximately 8.5%.

Condensed income statement (in millions, unaudited)
  Revenue                       $845.5 million
  Cost of revenue               $611.4 million
  Gross profit                  $234.1 million
  Operating expenses            $153.3 million (incl. $-18.0 million of items noted above)
  Operating income (loss)       $80.8 million
  Other income (expense), net   $-12.0 million
  Income tax expense            $13.8 million
  Net income (loss)             $55.0 million
  Diluted shares (millions)     118.5

Prior-year quarter: revenue $790.2 million; operating income $56.0 million.
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
