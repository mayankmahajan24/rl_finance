Terminal feed row (fixed-coupon bullet bond):

  ID_ISIN        US78013XZG61
  SECURITY_DES   RY FRN-FIX 3.9 01/17/2031
  ISSUER         Royal Bank of Canada
  CPN            3.9
  CPN_FREQ       4
  MATURITY       2031-01-17
  DAY_CNT_DES    ACT/360
  SETTLE_DT      2026-03-10
  YLD_YTM_MID    4.6
  CRNCY          USD
  PAR_AMT        100

Task: Using the quoted yield to maturity (YLD_YTM_MID, in percent) and the stated day-count
convention, compute for settlement on SETTLE_DT:
  - clean_price: clean (flat) price per 100 face
  - accrued_interest: accrued interest per 100 face
  - dirty_price: full (invoice) price per 100 face

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: clean_price, accrued_interest, dirty_price.
