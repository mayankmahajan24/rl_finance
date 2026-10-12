Terminal feed row (fixed-coupon bullet bond):

  ID_ISIN        XS2345678901
  SECURITY_DES   DBR 2 1/2 08/15/2046
  ISSUER         Bundesrepublik Deutschland
  CPN            2.5
  CPN_FREQ       1
  MATURITY       2046-08-15
  DAY_CNT_DES    ACT/ACT
  SETTLE_DT      2026-03-10
  YLD_YTM_MID    2.85
  CRNCY          EUR
  PAR_AMT        100

Task: Using the quoted yield to maturity (YLD_YTM_MID, in percent) and the stated day-count
convention, compute for settlement on SETTLE_DT:
  - clean_price: clean (flat) price per 100 face
  - accrued_interest: accrued interest per 100 face
  - dirty_price: full (invoice) price per 100 face

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: clean_price, accrued_interest, dirty_price.
