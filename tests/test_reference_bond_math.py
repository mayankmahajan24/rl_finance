from datetime import date

import pytest

from finrl_eval.suites.fixed_income.reference import (
    Bond,
    accrual_fraction,
    coupon_schedule,
    days_30_360,
)


def test_textbook_price_on_coupon_date() -> None:
    # 5% semiannual, 10 years, yield 6%: classic 92.5613 per 100.
    bond = Bond(coupon_pct=5.0, maturity=date(2036, 1, 15), freq=2, basis="30/360")
    settle = date(2026, 1, 15)
    assert bond.accrued_interest(settle) == pytest.approx(0.0)
    assert bond.clean_price(settle, 6.0) == pytest.approx(92.5613, abs=1e-4)


def test_par_bond_prices_at_par() -> None:
    bond = Bond(coupon_pct=4.0, maturity=date(2031, 6, 30), freq=2, basis="ACT/ACT")
    assert bond.clean_price(date(2026, 6, 30), 4.0) == pytest.approx(100.0, abs=1e-9)


def test_ytm_round_trips_price() -> None:
    bond = Bond(coupon_pct=3.85, maturity=date(2043, 5, 4), freq=2, basis="30/360")
    settle = date(2026, 3, 10)
    px = bond.clean_price(settle, 5.05)
    assert bond.ytm(settle, px) == pytest.approx(5.05, abs=1e-7)


def test_30_360_day_count_rules() -> None:
    assert days_30_360(date(2026, 1, 31), date(2026, 2, 28)) == 28
    assert days_30_360(date(2026, 1, 30), date(2026, 3, 31)) == 60
    assert days_30_360(date(2026, 1, 15), date(2026, 7, 15)) == 180


def test_coupon_schedule_and_accrual_fractions() -> None:
    prev_cpn, next_cpn, dates = coupon_schedule(date(2026, 3, 10), date(2029, 2, 28), 2)
    assert prev_cpn == date(2026, 2, 28)
    assert next_cpn == date(2026, 8, 28)
    assert dates[-1] == date(2029, 2, 28)
    assert len(dates) == 6
    act_act = accrual_fraction(prev_cpn, date(2026, 3, 10), next_cpn, 2, "ACT/ACT")
    assert act_act == pytest.approx(10 / 181)
    assert accrual_fraction(prev_cpn, date(2026, 3, 10), next_cpn, 2, "ACT/360") == pytest.approx(
        10 / 180
    )
    assert accrual_fraction(prev_cpn, date(2026, 3, 10), next_cpn, 2, "ACT/365") == pytest.approx(
        10 / 182.5
    )
    with pytest.raises(ValueError):
        accrual_fraction(prev_cpn, date(2026, 3, 10), next_cpn, 2, "BUS/252")


def test_duration_relationships() -> None:
    bond = Bond(coupon_pct=4.95, maturity=date(2045, 6, 1), freq=2, basis="30/360")
    settle = date(2026, 5, 31)
    mac, mod, conv = bond.durations(settle, 5.5)
    assert 0 < mod < mac < 19.0
    assert mod == pytest.approx(mac / (1 + 0.055 / 2))
    assert conv > 0
    # DV01 should agree with a central finite difference on the dirty price.
    up = bond.dirty_price(settle, 5.5 + 0.01)
    down = bond.dirty_price(settle, 5.5 - 0.01)
    assert bond.dv01(settle, 5.5) == pytest.approx((down - up) / 2, rel=1e-3)


def test_zero_coupon_duration_equals_maturity() -> None:
    bond = Bond(coupon_pct=0.0, maturity=date(2031, 3, 10), freq=1, basis="ACT/365")
    mac, _, _ = bond.durations(date(2026, 3, 10), 4.0)
    assert mac == pytest.approx(5.0, abs=0.01)
