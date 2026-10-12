Terminal feed row (fixed-coupon bullet bond):

  ID_ISIN        GB00BM8Z2V59
  SECURITY_DES   UKT 4 1/8 01/29/2027
  ISSUER         United Kingdom Gilt
  CPN            4.125
  CPN_FREQ       2
  MATURITY       2027-01-29
  DAY_CNT_DES    ACT/365
  SETTLE_DT      2026-03-10
  PX_CLEAN       100.42
  CRNCY          GBP
  PAR_AMT        100

Task: Using the quoted clean price (PX_CLEAN, per 100 face) and the stated day-count
convention, compute for settlement on SETTLE_DT:
  - ytm_pct: street-convention yield to maturity, in percent (e.g. 4.37 for 4.37%)
  - accrued_interest: accrued interest per 100 face

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: ytm_pct, accrued_interest.
