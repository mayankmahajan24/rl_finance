Terminal feed row (fixed-coupon bullet bond):

  ID_ISIN        US037833CR12
  SECURITY_DES   AAPL 3.85 05/04/2043
  ISSUER         Apple Inc
  CPN            3.85
  CPN_FREQ       2
  MATURITY       2043-05-04
  DAY_CNT_DES    30/360
  SETTLE_DT      2026-03-10
  YLD_YTM_MID    5.05
  CRNCY          USD
  PAR_AMT        100

Task: Using the quoted yield to maturity (YLD_YTM_MID, in percent) and the stated day-count
convention, compute for settlement on SETTLE_DT:
  - clean_price: clean (flat) price per 100 face
  - accrued_interest: accrued interest per 100 face
  - dirty_price: full (invoice) price per 100 face

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: clean_price, accrued_interest, dirty_price.
