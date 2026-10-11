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

Task: For settlement on SETTLE_DT, determine:
  - days_accrued: number of accrued days from the previous coupon date under DAY_CNT_DES
  - accrued_interest: accrued interest per 100 face
  - day_count_convention: the convention you applied, exactly as written in the feed

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: days_accrued, accrued_interest, day_count_convention.
