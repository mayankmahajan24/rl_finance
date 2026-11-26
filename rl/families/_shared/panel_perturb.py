"""Disguise a transaction panel and inject artifacts, recording ground truth in the new coordinates.

Shared by the txn_panel families (data_audit, anomaly_scoring, growth_thesis). Ported verbatim from
~/altdata_evals/generator.py (2026-10-21); the only changes are that the natural artifacts come from
the source's annotations instead of constants here, and the panel is passed in (already restricted
to one split's companies) instead of read from a fixed path.

Every variant starts from the real panel and is made unrecognisable before anything is injected:

  * tickers are renamed to random codes and source ids are shuffled,
  * dates are shifted by a multiple of 364 days (keeps weekdays aligned, breaks calendar recall),
  * every (ticker, source) series is rescaled by its own random factor.
"""
from __future__ import annotations

import string

import numpy as np
import pandas as pd

D = pd.Timestamp
DAY = pd.Timedelta(days=1)

# --------------------------------------------------------------------------------------------------
# Disguise: anonymise, shift dates, rescale
# --------------------------------------------------------------------------------------------------
class Frame:
    """Holds the mapping from original to disguised coordinates so ground truth can be translated."""

    def __init__(self, raw: pd.DataFrame, rng: np.random.Generator, tickers=None, artifacts=((), ())):
        self.rng = rng
        self.required, self.optional = artifacts   # natural artifacts, original coordinates
        raw = raw if tickers is None else raw[raw.ticker.isin(tickers)]
        tks = sorted(raw.ticker.unique())
        codes = rng.choice([a + b for a in string.ascii_uppercase for b in string.ascii_uppercase],
                           len(tks), replace=False)
        self.tmap = {t: f'T{c}' for t, c in zip(tks, codes)}
        perm = rng.permutation([1, 2, 3, 4])
        self.smap = {s: int(p) for s, p in zip([1, 2, 3, 4], perm)}
        self.k = int(rng.choice([-3, -2, -1, 1, 2, 3, 4]))
        self.shift = pd.Timedelta(days=364 * self.k)
        df = raw.copy()
        df['ticker'] = df.ticker.map(self.tmap)
        df['source_id'] = df.source_id.map(self.smap)
        df['date'] = df.date + self.shift
        # per-series volume rescale (keeps ct integer; a 0-count day is "no row", matching the source data)
        fac = {key: float(np.clip(np.exp(rng.normal(0, 0.5)), 0.3, 3.0))
               for key in df.groupby(['ticker', 'source_id']).groups}
        f = df.set_index(['ticker', 'source_id']).index.map(fac).values.astype(float)
        df['ct'] = np.round(df.ct * f).astype(int)
        df['amt'] = (df.amt * f).round(2)
        self.df = df[df.ct > 0].sort_values(['ticker', 'source_id', 'date']).reset_index(drop=True)

    # translators -----------------------------------------------------------------------------
    def t(self, ticker):
        return self.tmap.get(ticker)

    def s(self, source):
        return None if source is None else self.smap[source]

    def d(self, date):
        return None if date is None else (D(date) + self.shift).strftime('%Y-%m-%d')

    def year(self, y):
        """Calendar year in disguised coordinates that best overlaps original year y."""
        return (D(f'{y}-07-01') + self.shift).year

    def natural(self):
        req = [dict(it, ticker=self.t(it['ticker']), source_id=self.s(it['source_id']),
                    start=self.d(it['start']), end=self.d(it['end']), origin='natural')
               for it in self.required if self.t(it['ticker'])]
        opt = [dict(it, ticker=self.t(it['ticker']), source_id=self.s(it['source_id']),
                    lo=self.d(it['lo']), hi=self.d(it['hi']))
               for it in self.optional if self.t(it['ticker'])]
        return req, opt

    def low_volume_series(self, min_ct=10):
        med = self.df.groupby(['ticker', 'source_id']).ct.median()
        return [dict(ticker=t, source_id=int(s)) for (t, s), m in med.items() if m < min_ct]

    # helpers for injection -------------------------------------------------------------------
    def candidates(self, min_ct=30, exclude_tickers=(), exclude_series=()):
        med = self.df.groupby(['ticker', 'source_id']).ct.median()
        nat = {self.t(it['ticker']) for it in self.required}
        out = [(t, int(s)) for (t, s), m in med.items()
               if m >= min_ct and t not in nat and t not in exclude_tickers and (t, s) not in exclude_series]
        return out

    def pick_date(self, lo_frac=0.3, hi_frac=0.75):
        d0, d1 = self.df.date.min(), self.df.date.max()
        span = (d1 - d0).days
        return d0 + pd.Timedelta(days=int(self.rng.integers(int(span * lo_frac), int(span * hi_frac))))

    def mask(self, ticker, source=None, start=None, end=None):
        m = self.df.ticker == ticker
        if source is not None:
            m &= self.df.source_id == source
        if start is not None:
            m &= self.df.date >= start
        if end is not None:
            m &= self.df.date <= end
        return m




def _fmt(d):
    return None if d is None else pd.Timestamp(d).strftime('%Y-%m-%d')


# --------------------------------------------------------------------------------------------------
# Artifact injectors (operate on Frame.df in place, return a ground-truth item)
# --------------------------------------------------------------------------------------------------
def inj_duplicate_rows(F, t, s):
    start = F.pick_date(); end = start + pd.Timedelta(days=int(F.rng.integers(20, 60)))
    rows = F.df[F.mask(t, s, start, end)]
    dup = rows.sample(frac=float(F.rng.uniform(0.5, 1.0)), random_state=int(F.rng.integers(1e9)))
    F.df = pd.concat([F.df, dup], ignore_index=True)
    return dict(type='duplicate_rows', ticker=t, source_id=s, start=_fmt(dup.date.min()), end=_fmt(dup.date.max()))


def inj_swapped_columns(F, t, s):
    start = F.pick_date(); end = start + pd.Timedelta(days=int(F.rng.integers(20, 90)))
    m = F.mask(t, s, start, end)
    ct, amt = F.df.loc[m, 'ct'].values.copy(), F.df.loc[m, 'amt'].values.copy()
    F.df.loc[m, 'ct'] = np.round(amt).astype(int); F.df.loc[m, 'amt'] = ct.astype(float)
    return dict(type='swapped_columns', ticker=t, source_id=s, start=_fmt(start), end=_fmt(end))


def inj_unit_scale(F, t, s):
    start = F.pick_date()
    m = F.mask(t, s, start)
    F.df.loc[m, 'amt'] = (F.df.loc[m, 'amt'] * 100).round(2)
    return dict(type='unit_scale', ticker=t, source_id=s, start=_fmt(start), end=None, note='amount reported in cents')


def inj_date_shift(F, t, s):
    start = F.pick_date()
    gmax = F.df.date.max()
    m = F.mask(t, s, start)
    F.df.loc[m, 'date'] = F.df.loc[m, 'date'] + DAY
    F.df = F.df[F.df.date <= gmax]
    return dict(type='date_shift', ticker=t, source_id=s, start=_fmt(start), end=None, note='dates off by +1 day')


def inj_series_swap(F, t, s, t2):
    start = F.pick_date()
    ma, mb = F.mask(t, s, start), F.mask(t2, s, start)
    F.df.loc[ma, 'ticker'] = '__TMP__'
    F.df.loc[mb, 'ticker'] = t
    F.df.loc[F.df.ticker == '__TMP__', 'ticker'] = t2
    # industries follow the series' new label
    ind = F.df.groupby('ticker').industry.agg(lambda x: x.mode().iloc[0])
    F.df['industry'] = F.df.ticker.map(ind)
    return dict(type='series_swap', ticker=t, other_ticker=t2, source_id=s, start=_fmt(start), end=None)


def inj_double_count(F, t, s):
    start = F.pick_date(); end = start + pd.Timedelta(days=int(F.rng.integers(60, 150)))
    m = F.mask(t, s, start, end)
    F.df.loc[m, 'ct'] *= 2; F.df.loc[m, 'amt'] = (F.df.loc[m, 'amt'] * 2).round(2)
    return dict(type='double_count', ticker=t, source_id=s, start=_fmt(start), end=_fmt(end))


def inj_outage(F, t, s):
    start = F.pick_date(); end = start + pd.Timedelta(days=int(F.rng.integers(14, 60)))
    F.df = F.df[~F.mask(t, s, start, end)]
    return dict(type='outage', ticker=t, source_id=s, start=_fmt(start), end=_fmt(end))


def inj_level_shift(F, t, s, mult=None, length=None):
    start = F.pick_date()
    mult = mult or float(F.rng.choice([0.45, 0.55, 1.7, 1.9]))
    end = None if length is None else start + pd.Timedelta(days=length)
    m = F.mask(t, s, start, end)
    F.df.loc[m, 'ct'] = np.maximum(np.round(F.df.loc[m, 'ct'] * mult), 0).astype(int)
    F.df.loc[m, 'amt'] = (F.df.loc[m, 'amt'] * mult).round(2)
    F.df = F.df[F.df.ct > 0]
    return dict(type='level_shift', ticker=t, source_id=s, start=_fmt(start), end=_fmt(end), mult=mult)


def inj_ticker_remap(F, t):
    start = F.pick_date(); mult = float(F.rng.uniform(5, 10))
    m = F.mask(t, None, start)
    F.df.loc[m, 'ct'] = np.round(F.df.loc[m, 'ct'] * mult).astype(int)
    F.df.loc[m, 'amt'] = (F.df.loc[m, 'amt'] * mult).round(2)
    return dict(type='ticker_remap', ticker=t, source_id=None, start=_fmt(start), end=None, mult=mult)


AUDIT_TYPES = ['duplicate_rows', 'swapped_columns', 'unit_scale', 'date_shift', 'series_swap',
               'double_count', 'outage', 'level_shift']

