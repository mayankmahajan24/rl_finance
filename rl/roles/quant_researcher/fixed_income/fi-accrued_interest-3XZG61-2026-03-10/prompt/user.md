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

Task: For settlement on SETTLE_DT, determine:
  - days_accrued: number of accrued days from the previous coupon date under DAY_CNT_DES
  - accrued_interest: accrued interest per 100 face
  - day_count_convention: the convention you applied, exactly as written in the feed

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: days_accrued, accrued_interest, day_count_convention.
