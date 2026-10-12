"""Reference implementation of fixed-coupon bond analytics used as ground truth.

Conventions
-----------
- Coupon dates are generated backwards from maturity every 12/freq months.
- Street convention: cash flows are discounted at (1 + y/freq) per period, with the first
  period fractional (`w`) according to the day-count basis.
- Day counts supported: ``30/360`` (US/NASD), ``ACT/360``, ``ACT/365``, ``ACT/ACT``
  (ICMA: actual days over actual days in the coupon period, times the frequency).
- Prices are per 100 face. Yields are in percent.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

DayCount = str  # "30/360" | "ACT/360" | "ACT/365" | "ACT/ACT"
SUPPORTED_DAY_COUNTS = ("30/360", "ACT/360", "ACT/365", "ACT/ACT")


def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def days_30_360(start: date, end: date) -> int:
    d1, d2 = start.day, end.day
    if d1 == 31:
        d1 = 30
    if d2 == 31 and d1 == 30:
        d2 = 30
    return 360 * (end.year - start.year) + 30 * (end.month - start.month) + (d2 - d1)


def coupon_schedule(settle: date, maturity: date, freq: int) -> tuple[date, date, list[date]]:
    """Return (previous_coupon, next_coupon, remaining_coupon_dates) relative to settle."""
    step = 12 // freq
    dates = [maturity]
    while True:
        prev = add_months(maturity, -step * len(dates))
        if prev <= settle:
            break
        dates.append(prev)
    dates.reverse()
    next_cpn = dates[0]
    prev_cpn = add_months(maturity, -step * len(dates))
    return prev_cpn, next_cpn, dates


def accrual_fraction(
    prev_cpn: date, settle: date, next_cpn: date, freq: int, basis: DayCount
) -> float:
    """Fraction of the current coupon that has accrued by settlement."""
    if basis == "30/360":
        return days_30_360(prev_cpn, settle) / (360 / freq)
    if basis == "ACT/360":
        return (settle - prev_cpn).days / (360 / freq)
    if basis == "ACT/365":
        return (settle - prev_cpn).days / (365 / freq)
    if basis == "ACT/ACT":
        return (settle - prev_cpn).days / (next_cpn - prev_cpn).days
    raise ValueError(f"unsupported day count {basis!r}")


@dataclass(frozen=True)
class Bond:
    coupon_pct: float
    maturity: date
    freq: int = 2
    basis: DayCount = "30/360"
    face: float = 100.0

    def accrued_days(self, settle: date) -> int:
        prev_cpn, _, _ = coupon_schedule(settle, self.maturity, self.freq)
        if self.basis == "30/360":
            return days_30_360(prev_cpn, settle)
        return (settle - prev_cpn).days

    def accrued_interest(self, settle: date) -> float:
        prev_cpn, next_cpn, _ = coupon_schedule(settle, self.maturity, self.freq)
        frac = accrual_fraction(prev_cpn, settle, next_cpn, self.freq, self.basis)
        return self.face * self.coupon_pct / 100 / self.freq * frac

    def _cashflows(self, settle: date) -> tuple[list[float], list[float]]:
        """Return (period_times, amounts) where times are in coupon periods from settle."""
        prev_cpn, next_cpn, dates = coupon_schedule(settle, self.maturity, self.freq)
        w = 1.0 - accrual_fraction(prev_cpn, settle, next_cpn, self.freq, self.basis)
        c = self.face * self.coupon_pct / 100 / self.freq
        times = [w + i for i in range(len(dates))]
        amounts = [c] * len(dates)
        amounts[-1] += self.face
        return times, amounts

    def dirty_price(self, settle: date, yield_pct: float) -> float:
        times, amounts = self._cashflows(settle)
        r = 1 + yield_pct / 100 / self.freq
        return float(sum(a / r**t for t, a in zip(times, amounts, strict=True)))

    def clean_price(self, settle: date, yield_pct: float) -> float:
        return self.dirty_price(settle, yield_pct) - self.accrued_interest(settle)

    def ytm(self, settle: date, clean_price: float, tol: float = 1e-10) -> float:
        lo, hi = -50.0, 200.0
        for _ in range(300):
            mid = (lo + hi) / 2
            if self.clean_price(settle, mid) > clean_price:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol:
                break
        return (lo + hi) / 2

    def durations(self, settle: date, yield_pct: float) -> tuple[float, float, float]:
        """Return (macaulay_years, modified_years, convexity)."""
        times, amounts = self._cashflows(settle)
        r = 1 + yield_pct / 100 / self.freq
        pvs = [a / r**t for t, a in zip(times, amounts, strict=True)]
        dirty = sum(pvs)
        mac_periods = sum(t * pv for t, pv in zip(times, pvs, strict=True)) / dirty
        macaulay = mac_periods / self.freq
        modified = macaulay / r
        convexity = sum(t * (t + 1) * pv for t, pv in zip(times, pvs, strict=True)) / (
            dirty * r**2 * self.freq**2
        )
        return macaulay, modified, convexity

    def dv01(self, settle: date, yield_pct: float) -> float:
        """Price change per 1bp yield move, per 100 face (positive number)."""
        _, modified, _ = self.durations(settle, yield_pct)
        return modified * self.dirty_price(settle, yield_pct) / 10_000
