Terminal feed row (fixed-coupon bullet bond):

  ID_ISIN        US06051GJX39
  SECURITY_DES   BAC 5.015 07/22/2033
  ISSUER         Bank of America Corp
  CPN            5.015
  CPN_FREQ       2
  MATURITY       2033-07-22
  DAY_CNT_DES    30/360
  SETTLE_DT      2026-03-10
  PX_CLEAN       101.125
  CRNCY          USD
  PAR_AMT        100

Task: Using the quoted clean price (PX_CLEAN, per 100 face) and the stated day-count
convention, compute for settlement on SETTLE_DT:
  - ytm_pct: street-convention yield to maturity, in percent (e.g. 4.37 for 4.37%)
  - accrued_interest: accrued interest per 100 face

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: ytm_pct, accrued_interest.
