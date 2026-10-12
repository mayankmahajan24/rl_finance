Terminal feed row (fixed-coupon bullet bond):

  ID_ISIN        US91282CFX71
  SECURITY_DES   T 0 1/2 04/30/2027
  ISSUER         United States Treasury
  CPN            0.5
  CPN_FREQ       2
  MATURITY       2027-04-30
  DAY_CNT_DES    ACT/ACT
  SETTLE_DT      2026-01-31
  YLD_YTM_MID    4.45
  CRNCY          USD
  PAR_AMT        100

Task: Using the quoted yield to maturity (YLD_YTM_MID, in percent) and the stated day-count
convention, compute for settlement on SETTLE_DT:
  - clean_price: clean (flat) price per 100 face
  - accrued_interest: accrued interest per 100 face
  - dirty_price: full (invoice) price per 100 face

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: clean_price, accrued_interest, dirty_price.
