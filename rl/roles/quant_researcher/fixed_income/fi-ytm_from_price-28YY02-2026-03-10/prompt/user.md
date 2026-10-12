Terminal feed row (fixed-coupon bullet bond):

  ID_ISIN        US912828YY02
  SECURITY_DES   T 1 7/8 02/28/2029
  ISSUER         United States Treasury
  CPN            1.875
  CPN_FREQ       2
  MATURITY       2029-02-28
  DAY_CNT_DES    ACT/ACT
  SETTLE_DT      2026-03-10
  PX_CLEAN       94.375
  CRNCY          USD
  PAR_AMT        100

Task: Using the quoted clean price (PX_CLEAN, per 100 face) and the stated day-count
convention, compute for settlement on SETTLE_DT:
  - ytm_pct: street-convention yield to maturity, in percent (e.g. 4.37 for 4.37%)
  - accrued_interest: accrued interest per 100 face

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: ytm_pct, accrued_interest.
