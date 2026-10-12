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

Task: For settlement on SETTLE_DT, determine:
  - days_accrued: number of accrued days from the previous coupon date under DAY_CNT_DES
  - accrued_interest: accrued interest per 100 face
  - day_count_convention: the convention you applied, exactly as written in the feed

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: days_accrued, accrued_interest, day_count_convention.
