"""Planted problems for the anomaly_hard prototype. Data moving up or down; one kind (rollup) also moves a weekend-length
stretch of volume onto the next day.

Problems in ONE source (labelled: the rows cannot be trusted, and the grader knows what the source should have
reported, from the panel as it was before these were planted):
  point anomalies, 1-3 days then straight back:  volume spike, volume dropout to near zero, count flood, dollar spike
  level shifts, immediate (step) or over 2-8 weeks (ramp), in volume, count only or dollars only; temporary
  (60-240 days, then back) or permanent (a new baseline to the end of the panel)
  problems the instruction already covers but no single-day or steady-level model fits (feedback #98):
    volume block   4-10 days too high or too low, then straight back ("a day or a few", stretched)
    outage         4-21 days at 1-5% of normal: the reported value carries no signal to rescale
    intermittent   3-8 weeks in which a third or so of the days are doubled or mostly lost, the rest fine
    stuck          one day's count and dollars repeated for the next 3-7 days (scored from the third identical day)
    rollup         2-3 days nearly empty, their volume reported on the following day
    phantom        a fixed number of tiny extra transactions every day for 1-4 months (a level shift whose size in
                   log terms depends on the day's volume)
    small step     a step a few times the source's noise against its sisters, however small that is in percent
Real events in EVERY source of one company (decoys: trusted, and the cleaned series should keep them):
  a pull-forward wave (spike, then a trough that gives it back) and a company-wide step (stores opening or closing)

Each injector edits F.df (a panel_perturb.Frame) in place and returns event dicts:
    type, ticker, source_id, start, end   the problem's days (inclusive); for a level shift, start is the first day
                                          the change is visible and end the last shifted day (the panel's last day
                                          if permanent)
    regime, permanent, settle             level shifts: scored as a change (grade.label_rows)
    plus the parameters drawn.
Sizes are set against the real panel's noise, measured on the bench control panels, log units, source vs the
median of its company's other sources: daily count 0.13 (worst series 0.26), daily ticket size 0.135 (0.27),
ticket-size drift over 90 days 0.09 at the 90th percentile (0.25), count drift over 120 days 0.15 (0.5). And against
each source's own noise (own_noise: day-to-day, after its weekday pattern and a 28-day running median): a one-day
problem is at least POINT_K times it, a single-measure level shift at least SHIFT_K times, so nothing planted is
within what that source normally does.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from families._shared.panel_perturb import _fmt

DAY = pd.Timedelta(days=1)
VISIBLE = 0.14   # log size from which a ramping shift is labelled: about the 90th-percentile slow drift
STUCK_DAYS = 3   # identical reports in a row from which a feed counts as stuck (the days before are not scored)
POINT_K, SHIFT_K = 6.0, 3.0   # a one-day problem is at least 6x the source's own day-to-day noise; a level shift 3x


def own_noise(F, t, s):
    """The source's own day-to-day noise (log units) in count and in ticket size, after its weekday pattern and a
    28-day running median are removed: what "obviously off for this source" is measured against."""
    x = F.df[(F.df.ticker == t) & (F.df.source_id == s)].set_index('date').sort_index()
    out = {}
    for k, v in (('ct', np.log(x.ct)), ('tkt', np.log(x.amt / x.ct))):
        v = v - v.groupby(v.index.dayofweek).transform('median')
        r = (v - v.rolling(28, center=True, min_periods=7).median()).dropna()
        out[k] = float(1.4826 * (r - r.median()).abs().median()) if len(r) else 0.1
    return out


def _rows(F, t, s, a, b):
    m = F.mask(t, s, a, b)
    return m if m.sum() == (b - a).days + 1 else None


def _scale(F, m, ct_mult, amt_mult):
    """Multiply count and dollars (arrays or scalars); counts stay whole and at least 1, so no row disappears."""
    F.df.loc[m, 'ct'] = np.maximum(np.round(F.df.loc[m, 'ct'] * ct_mult), 1).astype(int)
    F.df.loc[m, 'amt'] = np.maximum(F.df.loc[m, 'amt'] * amt_mult, 0.01).round(2)


def _ev(type_, t, s, start, end, regime=False, **kw):
    return dict(type=type_, ticker=t, source_id=int(s), start=_fmt(start), end=_fmt(end), regime=regime,
                **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in kw.items()})


# ---------------------------------------------------------------- one source: point anomalies
def volume_spike(F, t, s, day):
    """A batch loaded twice, or a settlement dump: count and dollars x2-5 for 1-3 days."""
    k, mult = int(F.rng.integers(1, 4)), float(F.rng.uniform(2, 5))
    mult = max(mult, float(np.exp(POINT_K * own_noise(F, t, s)['ct'])))
    m = _rows(F, t, s, day, day + (k - 1) * DAY)
    if m is None:
        return []
    _scale(F, m, mult, mult)
    return [_ev('volume_spike', t, s, day, day + (k - 1) * DAY, mult=mult)]


def dropout(F, t, s, day):
    """An ingestion failure: count and dollars fall to 1-5% of normal for 1-3 days (the panel has no zero rows)."""
    k, frac = int(F.rng.integers(1, 4)), float(F.rng.uniform(0.01, 0.05))
    m = _rows(F, t, s, day, day + (k - 1) * DAY)
    if m is None:
        return []
    _scale(F, m, frac, frac)
    return [_ev('dropout', t, s, day, day + (k - 1) * DAY, frac=frac)]


def count_flood(F, t, s, day):
    """A flood of tiny transactions (card testing, fee-only charges): count x3-7, dollars up $0.50-2.00 each."""
    m = _rows(F, t, s, day, day)
    if m is None:
        return []
    ct, amt = float(F.df.loc[m, 'ct'].iloc[0]), float(F.df.loc[m, 'amt'].iloc[0])
    u, need = F.rng.uniform(0.5, 2.0), POINT_K * own_noise(F, t, s)['tkt']
    dn = float(F.rng.poisson(ct * F.rng.uniform(2, 6)))
    while abs(np.log((amt + dn * u) / (ct + dn)) - np.log(amt / ct)) < need and dn < 50 * ct:
        dn = dn * 1.5 + 1                        # the ticket must fall clearly beyond this source's own noise
    F.df.loc[m, 'ct'] = int(round(ct + dn))
    F.df.loc[m, 'amt'] = round(amt + dn * u, 2)
    return [_ev('count_flood', t, s, day, day, ct_mult=(ct + dn) / ct)]


def dollar_spike(F, t, s, day):
    """A few very large tickets (corporate or settlement batches): dollars x1.8-3, count unchanged."""
    m = _rows(F, t, s, day, day)
    if m is None:
        return []
    mult = max(float(F.rng.uniform(1.8, 3.0)), float(np.exp(POINT_K * own_noise(F, t, s)['tkt'])))
    _scale(F, m, 1.0, mult)
    return [_ev('dollar_spike', t, s, day, day, amt_mult=mult)]


POINTS = [volume_spike, dropout, count_flood, dollar_spike]


# ---------------------------------------------------------------- one source: several days, not a steady level
def _clear(F, t, s, lo, hi):
    """A multiplier that stands POINT_K times clear of the source's own noise: drawn in [lo, hi] (up) or its inverse."""
    up = bool(F.rng.random() < 0.5)
    mult = max(float(F.rng.uniform(lo, hi)), float(np.exp(POINT_K * own_noise(F, t, s)['ct'])))
    return mult if up else 1.0 / mult


def volume_block(F, t, s, day):
    """A backlog loaded over a week, or a partial feed: count and dollars x2-4 or x0.25-0.5 for 4-10 days."""
    k = int(F.rng.integers(4, 11))
    m = _rows(F, t, s, day, day + (k - 1) * DAY)
    if m is None:
        return []
    mult = _clear(F, t, s, 2.0, 4.0)
    _scale(F, m, mult, mult)
    return [_ev('volume_block', t, s, day, day + (k - 1) * DAY, mult=mult)]


def outage(F, t, s, day):
    """The feed all but down for 4-21 days: count and dollars at 1-5% of normal, so nothing is left to rescale."""
    k, frac = int(F.rng.integers(4, 22)), float(F.rng.uniform(0.01, 0.05))
    m = _rows(F, t, s, day, day + (k - 1) * DAY)
    if m is None:
        return []
    _scale(F, m, frac, frac)
    return [_ev('outage', t, s, day, day + (k - 1) * DAY, frac=frac)]


def intermittent(F, t, s, day):
    """A flaky feed: for 3-8 weeks, 30-45% of the days (at random, at least five) are doubled or mostly lost; the
    days in between are reported correctly."""
    k = int(F.rng.integers(21, 57))
    m = _rows(F, t, s, day, day + (k - 1) * DAY)
    if m is None:
        return []
    mult = _clear(F, t, s, 2.0, 3.0)
    idx = F.df.index[m]
    n = max(5, int(round(k * F.rng.uniform(0.30, 0.45))))
    bad = np.sort(F.rng.choice(len(idx), n, replace=False))
    hit = pd.Series(False, index=F.df.index)
    hit[idx[bad]] = True
    _scale(F, hit, mult, mult)
    days = sorted(F.df.loc[hit, 'date'])
    return [_ev('intermittent', t, s, days[0], days[-1], mult=mult, days=[_fmt(x) for x in days])]


def stuck(F, t, s, day):
    """A stuck feed: the day's count and dollars are reported again, to the cent, on each of the next 3-7 days."""
    k = int(F.rng.integers(3, 8))
    m = _rows(F, t, s, day, day + k * DAY)
    if m is None:
        return []
    first = F.mask(t, s, day, day)
    rest = F.mask(t, s, day + DAY, day + k * DAY)
    F.df.loc[rest, 'ct'] = int(F.df.loc[first, 'ct'].iloc[0])
    F.df.loc[rest, 'amt'] = float(F.df.loc[first, 'amt'].iloc[0])
    # two identical days can be chance; the feed counts as stuck from the third (STUCK_DAYS), scored from then
    return [_ev('stuck', t, s, day + DAY, day + k * DAY, repeated=k, visible=_fmt(day + (STUCK_DAYS - 1) * DAY))]


def rollup(F, t, s, day):
    """A batch held back: 2-3 days at 1-5% of normal, and the volume they lost reported on the following day."""
    k, frac = int(F.rng.integers(2, 4)), float(F.rng.uniform(0.01, 0.05))
    m = _rows(F, t, s, day, day + k * DAY)
    if m is None:
        return []
    held = F.mask(t, s, day, day + (k - 1) * DAY)
    last = F.mask(t, s, day + k * DAY, day + k * DAY)
    ct0, amt0 = F.df.loc[held, 'ct'].sum(), F.df.loc[held, 'amt'].sum()
    _scale(F, held, frac, frac)
    F.df.loc[last, 'ct'] = int(F.df.loc[last, 'ct'].iloc[0] + round(ct0 - F.df.loc[held, 'ct'].sum()))
    F.df.loc[last, 'amt'] = round(float(F.df.loc[last, 'amt'].iloc[0] + amt0 - F.df.loc[held, 'amt'].sum()), 2)
    return [_ev('rollup', t, s, day, day + k * DAY, frac=frac, held_days=k)]


MULTI = [(volume_block, 10), (outage, 21), (intermittent, 56), (stuck, 8), (rollup, 4)]   # injector, longest span


# ---------------------------------------------------------------- one source: level shifts
MEASURES = {   # measure -> (multiplier range for count, for dollars); one draw u in [0, 1] places it in the range
    'volume': None,                        # count and dollars together: x0.55-0.75 or x1.4-1.8
    'count': ((1.3, 1.6), None),           # count up, dollars flat: smaller tickets (instalments, unbundled fees)
    'dollars': (None, (0.6, 0.75)),        # dollars down, count flat: the high-dollar tail lost
}


def phantom(F, t, s, start, length):
    """A test or fee stream left running: a fixed number of tiny extra transactions every day (0.4-1.2 times the
    source's median daily count, $0.50-2.00 each) for `length` days. A level shift in count and ticket whose size in
    log terms is larger on quiet days and smaller on busy ones."""
    end = start + pd.Timedelta(days=length)
    m = _rows(F, t, s, start, end)
    if m is None:
        return []
    base = float(F.df.loc[F.mask(t, s), 'ct'].median())
    n, u = base * float(F.rng.uniform(0.4, 1.2)), float(F.rng.uniform(0.5, 2.0))
    dn = F.rng.poisson(n, int(m.sum()))
    ct0 = F.df.loc[m, 'ct'].to_numpy(float)
    F.df.loc[m, 'ct'] = (ct0 + dn).astype(int)
    F.df.loc[m, 'amt'] = (F.df.loc[m, 'amt'].to_numpy(float) + dn * u).round(2)
    return [_ev('level_shift_step', t, s, start, end, regime=True, permanent=False, measure='phantom',
                ct_mult=float(np.median((ct0 + dn) / ct0)), amt_mult=1.0, ramp_days=0, shift_start=_fmt(start),
                settle=_fmt(start + pd.Timedelta(days=14)), extra_per_day=n)]


def level_shift(F, t, s, start, mode, length, d1, small=None):
    """A source's level changes, at once (mode 'step') or over 2-8 weeks ('ramp'), in volume, count only or dollars
    only; temporary (length days, then back) or permanent (length None: to the end of the panel). `small` (the
    source's noise against its sisters, count and ticket): a step of 3-5 times that noise, whatever it is in percent."""
    measure = str(F.rng.choice(list(MEASURES)))
    if small is not None:
        k = float(F.rng.uniform(3.0, 5.0))
        sc, st = k * small['ct'], k * small['tkt']
        sign = float(F.rng.choice([-1.0, 1.0]))
        cm, am = {'volume': (np.exp(sign * sc),) * 2, 'count': (float(np.exp(sc)), 1.0),
                  'dollars': (1.0, float(np.exp(-st)))}[measure]
        cm, am = float(cm), float(am)
    elif measure == 'volume':
        m_ = float(F.rng.choice([F.rng.uniform(0.55, 0.75), F.rng.uniform(1.4, 1.8)]))
        cm, am = m_, m_
    elif measure == 'count':
        cm, am = float(F.rng.uniform(*MEASURES['count'][0])), 1.0
    else:
        cm, am = 1.0, float(F.rng.uniform(*MEASURES['dollars'][1]))
    sig = own_noise(F, t, s)
    floor = 0.0 if small is not None else SHIFT_K * (sig['ct'] if measure != 'dollars' else sig['tkt'])
    if measure == 'volume' and abs(np.log(cm)) < floor:     # every shift stands clear of the source's own noise
        cm = am = float(np.exp(np.sign(np.log(cm)) * floor))
    if measure == 'count' and np.log(cm) < floor:
        cm = float(np.exp(floor))
    if measure == 'dollars' and -np.log(am) < floor:
        am = float(np.exp(-floor))
    ramp = int(F.rng.integers(14, 57)) if mode == 'ramp' else 0
    end = d1 if length is None else start + pd.Timedelta(days=length)
    m = F.mask(t, s, start, end)
    days = (F.df.loc[m, 'date'] - start).dt.days.to_numpy()
    w = np.minimum(days / ramp, 1.0) if ramp else np.ones(len(days))
    _scale(F, m, np.exp(w * np.log(cm)), np.exp(w * np.log(am)))
    size = max(abs(np.log(cm)), abs(np.log(am)))
    lab = start + pd.Timedelta(days=int(np.ceil(ramp * min(VISIBLE / size, 1.0)))) if ramp else start
    return [_ev(f'level_shift_{mode}', t, s, lab, end, regime=True, permanent=length is None, measure=measure,
                ct_mult=cm, amt_mult=am, ramp_days=ramp, shift_start=_fmt(start),
                settle=_fmt(start + pd.Timedelta(days=ramp + 14)), **(dict(small=True) if small is not None else {}))]


# ---------------------------------------------------------------- every source of one company: real events (decoys)
WAVE = [0.6, 0.4, -0.25, -0.20, -0.15, -0.15, -0.10, -0.10, -0.05]   # sums to 0: demand pulled forward


def pull_forward(F, t, day):
    """A promotion or flash sale: +60%/+40% for two days, then a trough that gives it back over a week."""
    for i, w in enumerate(WAVE):
        _scale(F, F.mask(t, None, day + i * DAY, day + i * DAY), 1 + w, 1 + w)
    return dict(kind='pull_forward', ticker=t, start=_fmt(day), end=_fmt(day + (len(WAVE) - 1) * DAY))


def company_step(F, t, day):
    """Stores opening or closing: every source of the company steps x0.8-0.9 or x1.15-1.3 for good."""
    mult = float(F.rng.choice([F.rng.uniform(0.8, 0.9), F.rng.uniform(1.15, 1.3)]))
    _scale(F, F.mask(t, None, day, None), mult, mult)
    return dict(kind='company_step', ticker=t, start=_fmt(day), end=_fmt(F.df.date.max()), mult=round(mult, 3))


DECOYS = [pull_forward, company_step]
