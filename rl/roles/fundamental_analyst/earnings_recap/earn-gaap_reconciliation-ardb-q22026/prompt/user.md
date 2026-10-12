Press release (Ardent Biologics, ARDB, Q2 FY2026):

<<<
ARDENT BIOLOGICS REPORTS Q2 FISCAL 2026 RESULTS

Ardent Biologics (NASDAQ: ARDB) today announced financial results for the second quarter of fiscal 2026. Revenue was $318.6 million, compared with $204.1 million in the prior-year quarter. GAAP net loss was $210.5 million, or $3.27 per diluted share (loss). Non-GAAP net loss was $87.5 million, or $1.36 per diluted share (loss). Results include a $85.0 million acquired in-process R&D (charge), which is excluded from non-GAAP measures along with stock-based compensation of $38.0 million. For fiscal 2026, the company now expects revenue of $1,250.0 million to $1,350.0 million and a non-GAAP operating margin of approximately -30.0%.

Condensed income statement (in millions, unaudited)
  Revenue                       $318.6 million
  Cost of revenue               $41.2 million
  Gross profit                  $277.4 million
  Operating expenses            $487.9 million (incl. $85.0 million of items noted above)
  Operating income (loss)       $-210.5 million
  Income tax expense            $0.0 million
  Net income (loss)             $-210.5 million
  Diluted shares (millions)     64.3

Prior-year quarter: revenue $204.1 million; operating income $-148.0 million.
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
