Terminal feed row (fixed-coupon bullet bond):

  ID_ISIN        GB00BM8Z2V59
  SECURITY_DES   UKT 4 1/8 01/29/2027
  ISSUER         United Kingdom Gilt
  CPN            4.125
  CPN_FREQ       2
  MATURITY       2027-01-29
  DAY_CNT_DES    ACT/365
  SETTLE_DT      2026-03-10
  YLD_YTM_MID    3.95
  CRNCY          GBP
  PAR_AMT        100

Task: For settlement on SETTLE_DT, determine:
  - days_accrued: number of accrued days from the previous coupon date under DAY_CNT_DES
  - accrued_interest: accrued interest per 100 face
  - day_count_convention: the convention you applied, exactly as written in the feed

Respond with your reasoning in at most a few sentences, then a ```json block with exactly
these keys: days_accrued, accrued_interest, day_count_convention.
