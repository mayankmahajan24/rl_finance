Terminal feed row (fixed-coupon bullet bond):

  ID_ISIN        US06051GJX39
  SECURITY_DES   BAC 5.015 07/22/2033
  ISSUER         Bank of America Corp
  CPN            5.015
  CPN_FREQ       2
  MATURITY       2033-07-22
  DAY_CNT_DES    30/360
  SETTLE_DT      2026-03-10
  YLD_YTM_MID    4.9
  CRNCY          USD
  PAR_AMT        100

Task: For settlement on SETTLE_DT, determine:
  - days_accrued: number of accrued days from the previous coupon date under DAY_CNT_DES
  - accrued_interest: accrued interest per 100 face
  - day_count_convention: the convention you applied, exactly as written in the feed

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: days_accrued, accrued_interest, day_count_convention.
