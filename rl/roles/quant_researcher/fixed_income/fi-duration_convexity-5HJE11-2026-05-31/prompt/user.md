Terminal feed row (fixed-coupon bullet bond):

  ID_ISIN        US46625HJE11
  SECURITY_DES   JPM 4.95 06/01/2045
  ISSUER         JPMorgan Chase & Co
  CPN            4.95
  CPN_FREQ       2
  MATURITY       2045-06-01
  DAY_CNT_DES    30/360
  SETTLE_DT      2026-05-31
  YLD_YTM_MID    5.5
  CRNCY          USD
  PAR_AMT        100

Task: At the quoted yield (YLD_YTM_MID, in percent) compute for settlement on SETTLE_DT:
  - macaulay_duration: in years
  - modified_duration: in years
  - convexity: in years^2, using the standard (1+y/f)^-2 scaling
  - dv01: price change per 100 face for a 1 basis-point move in yield (positive number)

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: macaulay_duration, modified_duration, convexity, dv01.
