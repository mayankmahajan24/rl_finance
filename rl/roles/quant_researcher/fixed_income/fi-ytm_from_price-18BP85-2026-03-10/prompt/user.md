Terminal feed row (fixed-coupon bullet bond):

  ID_ISIN        US594918BP85
  SECURITY_DES   MSFT 2.4 08/08/2026
  ISSUER         Microsoft Corp
  CPN            2.4
  CPN_FREQ       2
  MATURITY       2026-08-08
  DAY_CNT_DES    30/360
  SETTLE_DT      2026-03-10
  PX_CLEAN       99.21
  CRNCY          USD
  PAR_AMT        100

Task: Using the quoted clean price (PX_CLEAN, per 100 face) and the stated day-count
convention, compute for settlement on SETTLE_DT:
  - ytm_pct: street-convention yield to maturity, in percent (e.g. 4.37 for 4.37%)
  - accrued_interest: accrued interest per 100 face

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: ytm_pct, accrued_interest.
