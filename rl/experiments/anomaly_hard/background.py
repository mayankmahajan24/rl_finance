"""Semi-real background for anomaly_hard tasks: every source follows its company's real daily behaviour, and every
source-level oddity is planted with an exact label.

  semi_real          each source = its company's real daily move (median of its sources, each net of its own
                     level) + the source's own constant level + its weekday pattern + its real day-to-day noise with
                     one-off glitches clipped at CLIP times its robust spread; in log count and log ticket size.
                     Seasonality, holidays, storms, outages and company events (common to all sources) stay real.
  plant_recurring    normal behaviour: a source that drops to 5-30% on the same date every year (a closure); the
                     first year is not scored, later years must be trusted
  plant_thin_start   normal behaviour: a source that starts with a handful of transactions a day and grows into full
                     coverage (counts drawn as a small panel would report them): its thin beginning must be dropped
  slow_ramp          a problem: a source's panel ramps to a new level over months, for good (a slow build-up)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CLIP = 3.0


def _mad(x):
    x = x[np.isfinite(x)]
    return float(1.4826 * np.median(np.abs(x - np.median(x)))) if len(x) else 0.0


def _rebuild(lx: pd.DataFrame) -> pd.DataFrame:
    """One channel (log values, days x sources) rebuilt on the company's common move."""
    m0 = lx.median(axis=1)
    off = lx.sub(m0, axis=0).median()                       # each source's own level against the company
    m = lx.sub(off, axis=1).median(axis=1)                  # the company's move, on a common level
    out = pd.DataFrame(index=lx.index, columns=lx.columns, dtype=float)
    for s in lx.columns:
        res = lx[s] - off[s] - m
        wd = res.groupby(res.index.dayofweek).transform('median')
        r = res - wd
        r = r - r.rolling(28, center=True, min_periods=7).median()   # source-specific drift removed
        sd = _mad(r.to_numpy())
        r = r.clip(-CLIP * sd, CLIP * sd) if sd > 0 else r * 0      # one-off glitches removed
        out[s] = (m + off[s] + wd + r).where(lx[s].notna())
    return out


def semi_real(df: pd.DataFrame) -> pd.DataFrame:
    """The panel with every source rebuilt on its company's real move (see the module docstring)."""
    parts = []
    for tk, g in df.groupby('ticker'):
        ct = g.pivot(index='date', columns='source_id', values='ct').astype(float)
        amt = g.pivot(index='date', columns='source_id', values='amt').astype(float)
        lc = _rebuild(np.log(ct.clip(lower=0.5)))
        lt = _rebuild(np.log(amt.clip(lower=0.01)) - np.log(ct.clip(lower=0.5)))
        new_ct = np.maximum(np.round(np.exp(lc)), 1)
        new_amt = (new_ct * np.exp(lt)).round(2)
        a = new_ct.stack().rename('ct').reset_index()
        b = new_amt.stack().rename('amt').reset_index()
        parts.append(a.merge(b, on=['date', 'source_id']).assign(ticker=tk))
    new = pd.concat(parts, ignore_index=True)
    out = df.drop(columns=['ct', 'amt']).reset_index(drop=True).merge(new, on=['date', 'ticker', 'source_id'], how='left')
    orig = df.reset_index(drop=True)
    out['ct'] = out.ct.fillna(orig.ct).astype(int)
    out['amt'] = out.amt.fillna(orig.amt)
    return out[df.columns]


def plant_recurring(F, rng, t, s, d0, d1) -> dict | None:
    """A yearly closure: the source drops to 5-30% of normal on the same date (month-day) every year."""
    mult = float(rng.uniform(0.05, 0.3))
    first_year = d0 + pd.Timedelta(days=int(rng.integers(30, 330)))
    md = (first_year.month, first_year.day)
    days = []
    for y in range(d0.year, d1.year + 1):
        try:
            x = pd.Timestamp(year=y, month=md[0], day=md[1])
        except ValueError:
            continue
        m = (F.df.ticker == t) & (F.df.source_id == s) & (F.df.date == x)
        if m.any():
            F.df.loc[m, 'ct'] = np.maximum(np.round(F.df.loc[m, 'ct'] * mult), 1).astype(int)
            F.df.loc[m, 'amt'] = (F.df.loc[m, 'amt'] * mult).round(2).clip(lower=0.01)
            days.append(x)
    if len(days) < 2:
        return None
    return dict(ticker=t, source_id=int(s), dates=[str(x.date()) for x in days], mult=round(mult, 3))


def plant_thin_start(F, rng, t, s, d0) -> dict | None:
    """A source that starts thin (about 6-14 transactions a day) for 450-700 days (past the scored panel's first year), then grows into full coverage over
    60-120 days; counts drawn as a small panel would report them (Poisson), dollars at the source's own ticket size."""
    m = (F.df.ticker == t) & (F.df.source_id == s)
    x = F.df[m].sort_values('date')
    if len(x) < 900:
        return None
    level = float(x.ct.median())
    target = float(rng.uniform(6, 14))
    if level <= target * 2:
        return None
    thin_days, grow = int(rng.integers(450, 701)), int(rng.integers(60, 121))   # past the year of warm-up
    age = (x.date - x.date.min()).dt.days.to_numpy()
    frac = np.clip((age - thin_days) / grow, 0, 1)
    scale = np.exp(np.log(target / level) * (1 - frac))
    lam = x.ct.to_numpy() * scale
    new_ct = np.maximum(rng.poisson(lam), 1)
    ticket = x.amt.to_numpy() / x.ct.to_numpy()
    F.df.loc[x.index, 'ct'] = new_ct.astype(int)
    F.df.loc[x.index, 'amt'] = (new_ct * ticket).round(2)
    return dict(ticker=t, source_id=int(s), thin_until=str((x.date.min() + pd.Timedelta(days=thin_days)).date()))


def slow_ramp(F, rng, t, s, lo, d1) -> list[dict]:
    """A panel change that builds up over 4-10 months and lasts: the source's count (and dollars with it, or count only)
    moves to x1.5-3 or x0.35-0.6 of its level, linearly in log terms, then stays there to the end of the panel."""
    m = (F.df.ticker == t) & (F.df.source_id == s) & (F.df.date >= lo)
    if m.sum() < 300:
        return []
    days = int(rng.integers(120, 301))
    up = bool(rng.random() < 0.5)
    mult = float(rng.uniform(1.5, 3.0)) if up else float(rng.uniform(0.35, 0.6))
    measure = 'volume' if rng.random() < 0.6 else 'count'
    age = (F.df.loc[m, 'date'] - lo).dt.days.to_numpy()
    f = np.exp(np.log(mult) * np.clip(age / days, 0, 1))
    F.df.loc[m, 'ct'] = np.maximum(np.round(F.df.loc[m, 'ct'] * f), 1).astype(int)
    if measure == 'volume':
        F.df.loc[m, 'amt'] = (F.df.loc[m, 'amt'] * f).round(2).clip(lower=0.01)
    fmt = lambda x: str(pd.Timestamp(x).date())  # noqa: E731
    return [dict(type='level_shift_slow', ticker=t, source_id=int(s), start=fmt(lo), end=fmt(d1), regime=True,
                 permanent=True, measure=measure, ct_mult=round(mult, 3),
                 amt_mult=round(mult, 3) if measure == 'volume' else 1.0, ramp_days=days, shift_start=fmt(lo),
                 settle=fmt(lo + pd.Timedelta(days=days + 14)))]
