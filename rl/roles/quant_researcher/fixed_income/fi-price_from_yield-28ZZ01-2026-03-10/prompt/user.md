Terminal feed row (fixed-coupon bullet bond):

  ID_ISIN        US912828ZZ01
  SECURITY_DES   T 4 1/4 08/15/2034
  ISSUER         United States Treasury
  CPN            4.25
  CPN_FREQ       2
  MATURITY       2034-08-15
  DAY_CNT_DES    ACT/ACT
  SETTLE_DT      2026-03-10
  YLD_YTM_MID    4.12
  CRNCY          USD
  PAR_AMT        100

Task: Using the quoted yield to maturity (YLD_YTM_MID, in percent) and the stated day-count
convention, compute for settlement on SETTLE_DT:
  - clean_price: clean (flat) price per 100 face
  - accrued_interest: accrued interest per 100 face
  - dirty_price: full (invoice) price per 100 face

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: clean_price, accrued_interest, dirty_price.
