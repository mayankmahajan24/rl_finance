Terminal feed row (fixed-coupon bullet bond):

  ID_ISIN        US71654QDE98
  SECURITY_DES   PEMEX 6 7/8 10/16/2032
  ISSUER         Petroleos Mexicanos
  CPN            6.875
  CPN_FREQ       2
  MATURITY       2032-10-16
  DAY_CNT_DES    30/360
  SETTLE_DT      2026-03-10
  PX_CLEAN       88.5
  CRNCY          USD
  PAR_AMT        100

Task: Using the quoted clean price (PX_CLEAN, per 100 face) and the stated day-count
convention, compute for settlement on SETTLE_DT:
  - ytm_pct: street-convention yield to maturity, in percent (e.g. 4.37 for 4.37%)
  - accrued_interest: accrued interest per 100 face

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: ytm_pct, accrued_interest.
