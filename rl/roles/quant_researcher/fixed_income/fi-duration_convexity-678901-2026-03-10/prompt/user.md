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

Task: At the quoted yield (YLD_YTM_MID, in percent) compute for settlement on SETTLE_DT:
  - macaulay_duration: in years
  - modified_duration: in years
  - convexity: in years^2, using the standard (1+y/f)^-2 scaling
  - dv01: price change per 100 face for a 1 basis-point move in yield (positive number)

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: macaulay_duration, modified_duration, convexity, dv01.
