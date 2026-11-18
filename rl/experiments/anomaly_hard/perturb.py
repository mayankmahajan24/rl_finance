"""Planted problems for the anomaly_hard prototype: data errors in ONE source of a company (labelled bad data),
and real events in EVERY source of a company (decoys, labelled good data).

Each injector edits F.df (a panel_perturb.Frame) in place and returns event dicts:
    type, ticker, source_id, start, end   the labelled days (inclusive); end == start for a one-day event
    regime                                True for long-running problems, scored with a delay allowance
    plus the parameters drawn.
Sizes are set against the real panel's noise, measured on the bench control panels, log units, source vs the
median of its company's other sources: daily count 0.13 (worst series 0.26), daily ticket size 0.135 (0.27),
ticket-size drift over 90 days 0.09 at the 90th percentile (0.25), day-of-week profile per 8 weeks 0.12 (0.23).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from families._shared.panel_perturb import _fmt

DAY = pd.Timedelta(days=1)


def _row(F, t, s, day):
    m = F.mask(t, s, day, day)
    return m if m.sum() == 1 else None


def _add(F, m, dct, damt):
    F.df.loc[m, 'ct'] = np.maximum(np.round(F.df.loc[m, 'ct'] + dct), 1).astype(int)
    F.df.loc[m, 'amt'] = np.maximum(F.df.loc[m, 'amt'] + damt, 0.01).round(2)


def _ev(type_, t, s, start, end=None, regime=False, **kw):
    return dict(type=type_, ticker=t, source_id=int(s), start=_fmt(start), end=_fmt(end if end is not None else start),
                regime=regime, **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in kw.items()})


# ---------------------------------------------------------------- one source: count and value come apart
def card_testing(F, t, s, day):
    """A flood of tiny authorisations: count x3-7, dollars up by $0.50-2.00 a transaction (ticket size collapses)."""
    m = _row(F, t, s, day)
    if m is None:
        return []
    ct = float(F.df.loc[m, 'ct'].iloc[0])
    dn = float(F.rng.poisson(ct * F.rng.uniform(2, 6)))
    _add(F, m, dn, dn * F.rng.uniform(0.5, 2.0))
    return [_ev('card_testing', t, s, day, ct_mult=(ct + dn) / ct)]


def whale(F, t, s, day):
    """A few very large tickets (B2B, settlement): dollars +80-200%, count unchanged."""
    m = _row(F, t, s, day)
    if m is None:
        return []
    mult = float(np.clip(F.rng.lognormal(np.log(1.3), 0.3), 0.8, 2.0))
    _add(F, m, 0, float(F.df.loc[m, 'amt'].iloc[0]) * mult)
    return [_ev('whale', t, s, day, amt_mult=1 + mult)]


def fragmentation(F, t, s, start, length):
    """Purchases start being split into instalments: count drifts up to x1.3-1.5 over 30-60 days while dollars
    don't, holds, then snaps back. Starts from the day the count is 15% high (log 0.14, about 1.5x the 90-day
    ticket-size drift at the 90th percentile). Scored as a change of level (grade.label_rows); `settle` keeps the
    new level unscored until two weeks after the ramp ends."""
    kmax, ramp = float(F.rng.uniform(1.3, 1.5)), int(F.rng.integers(30, 61))
    end = start + pd.Timedelta(days=length)
    m = F.mask(t, s, start, end)
    days = (F.df.loc[m, 'date'] - start).dt.days.to_numpy()
    k = 1 + (kmax - 1) * np.minimum(days / ramp, 1.0)
    F.df.loc[m, 'ct'] = np.maximum(np.round(F.df.loc[m, 'ct'] * k), 1).astype(int)
    lab = start + pd.Timedelta(days=int(np.ceil(ramp * 0.15 / (kmax - 1))))
    return [_ev('fragmentation', t, s, lab, end, regime=True, kmax=kmax, ramp_days=ramp, drift_start=_fmt(start),
                settle=_fmt(start + pd.Timedelta(days=ramp + 14)))]


# ---------------------------------------------------------------- one source: volume up or down
def feed_dropout(F, t, s, day):
    """One upstream feed misses the cutoff: count and dollars x(0.4-0.65) for 2-4 days, ticket size normal;
    half the time the missing volume is backfilled on the next day."""
    k, p = int(F.rng.integers(2, 5)), float(F.rng.uniform(0.35, 0.6))
    ms = [_row(F, t, s, day + i * DAY) for i in range(k + 1)]
    if any(x is None for x in ms):
        return []
    miss_ct = miss_amt = 0.0
    for mi in ms[:k]:
        c, a = float(F.df.loc[mi, 'ct'].iloc[0]) * p, float(F.df.loc[mi, 'amt'].iloc[0]) * p
        _add(F, mi, -c, -a); miss_ct += c; miss_amt += a
    back = bool(F.rng.random() < 0.5)
    if back:
        _add(F, ms[k], miss_ct, miss_amt)
    return [_ev('feed_dropout', t, s, day, day + (k if back else k - 1) * DAY, dropped=p, days=k, backfill=back)]


def duplicate_batch(F, t, s, day):
    """A batch loaded twice: adds 60-100% of the same day's, the day before's or the week before's rows
    (count and dollars together, ticket size unchanged)."""
    tau = int(F.rng.choice([0, 1, 7]))
    m, src = _row(F, t, s, day), _row(F, t, s, day - tau * DAY)
    if m is None or src is None:
        return []
    g = float(F.rng.uniform(0.6, 1.0))
    _add(F, m, float(F.df.loc[src, 'ct'].iloc[0]) * g, float(F.df.loc[src, 'amt'].iloc[0]) * g)
    return [_ev('duplicate_batch', t, s, day, gamma=g, lag_days=tau)]


# ---------------------------------------------------------------- every source of one company: real events (decoys)
PANTRY = [0.6, 0.4, -0.25, -0.20, -0.15, -0.15, -0.10, -0.10, -0.05]   # sums to 0: demand pulled forward


def pantry_loading(F, t, day):
    """Stock-up before a storm: +60%/+40% for two days, then a hangover that gives it back over a week."""
    for i, w in enumerate(PANTRY):
        m = F.mask(t, None, day + i * DAY, day + i * DAY)
        F.df.loc[m, 'ct'] = np.maximum(np.round(F.df.loc[m, 'ct'] * (1 + w)), 1).astype(int)
        F.df.loc[m, 'amt'] = (F.df.loc[m, 'amt'] * (1 + w)).round(2)
    return dict(kind='pantry_loading', ticker=t, start=_fmt(day), end=_fmt(day + (len(PANTRY) - 1) * DAY))
