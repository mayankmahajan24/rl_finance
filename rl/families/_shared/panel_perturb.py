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
    start = F.pick_date(); end = start + pd.Timedelta(days=int(F.rng.integers(10, 45)))
    rows = F.df[F.mask(t, s, start, end)]
    dup = rows.sample(frac=float(F.rng.uniform(0.1, 0.4)), random_state=int(F.rng.integers(1e9)))
    F.df = pd.concat([F.df, dup], ignore_index=True)
    return dict(type='duplicate_rows', ticker=t, source_id=s, start=_fmt(dup.date.min()), end=_fmt(dup.date.max()))


def inj_swapped_columns(F, t, s):
    start = F.pick_date(); end = start + pd.Timedelta(days=int(F.rng.integers(5, 30)))
    m = F.mask(t, s, start, end)
    ct, amt = F.df.loc[m, 'ct'].values.copy(), F.df.loc[m, 'amt'].values.copy()
    F.df.loc[m, 'ct'] = np.round(amt).astype(int); F.df.loc[m, 'amt'] = ct.astype(float)
    return dict(type='swapped_columns', ticker=t, source_id=s, start=_fmt(start), end=_fmt(end))


def inj_unit_scale(F, t, s):
    start = F.pick_date(); end = start + pd.Timedelta(days=int(F.rng.integers(14, 180)))
    m = F.mask(t, s, start, end)
    F.df.loc[m, 'amt'] = (F.df.loc[m, 'amt'] * 100).round(2)
    return dict(type='unit_scale', ticker=t, source_id=s, start=_fmt(start), end=_fmt(end), note='amount reported in cents')


def inj_date_shift(F, t, s):
    start = F.pick_date()
    k = int(F.rng.choice([-1, 1]))
    redate(F, t, s, start, None, k)
    gmax = F.df.date.max()
    # the days a repair has to fill in: the one left empty, and the one that took two days' rows
    impute = [start, gmax] if k > 0 else [start - DAY]
    return dict(type='date_shift', ticker=t, source_id=s, start=_fmt(start + min(k, 0) * DAY), end=None,
                note=f'dates off by {k:+d} day', impute_days=[_fmt(d) for d in impute])


def redate(F, t, s, start, end, k):
    """Move one series' rows from start to end (inclusive; None = to the end of the panel) by k days, merging
    a row that lands on an existing day into it; rows pushed past the end of the panel are lost."""
    gmax = F.df.date.max()
    m = F.mask(t, s, start, end)
    F.df.loc[m, 'date'] = F.df.loc[m, 'date'] + k * DAY
    F.df = F.df[F.df.date <= gmax]
    ser = F.mask(t, s)
    one = F.df[ser].groupby('date', as_index=False).agg(
        {c: ('sum' if c in ('ct', 'amt') else 'first') for c in F.df.columns if c != 'date'})
    F.df = pd.concat([F.df[~ser], one[F.df.columns]], ignore_index=True)


def dst_windows(d0, d1):
    """US daylight-saving periods [second Sunday of March, first Sunday of November) inside [d0, d1]."""
    out = []
    for y in range(d0.year, d1.year + 1):
        mar, nov = pd.Timestamp(y, 3, 8), pd.Timestamp(y, 11, 1)
        a = mar + pd.Timedelta(days=(6 - mar.weekday()) % 7)
        b = nov + pd.Timedelta(days=(6 - nov.weekday()) % 7)
        if a - DAY >= d0 and b <= d1:
            out.append((a, b))
    return out


def inj_dst_shift(F, t, s):
    """From some year on, the source cuts each day's batch at a fixed UTC time but stamps it with the local date
    at the cut. While clocks are on summer time the cut falls on the other side of local midnight, so every
    summer day carries the next day's date (k=+1) or, for a cut just before midnight, the previous day's (k=-1).
    One item per summer."""
    wins = dst_windows(F.df.date.min(), F.df.date.max())
    first = max(0, len(wins) - int(F.rng.integers(2, 4)))   # the last two or three summers
    k = int(F.rng.choice([-1, 1]))
    items = []
    for a, b in wins[first:]:
        redate(F, t, s, a, b - DAY, k)
        lo, hi = (a, b) if k > 0 else (a - DAY, b - DAY)
        items.append(dict(type='dst_shift', ticker=t, source_id=s, start=_fmt(lo), end=_fmt(hi),
                          note=f'summer dates off by {k:+d} day', impute_days=[_fmt(lo), _fmt(hi)]))
    return items


def inj_amount_shift(F, t, s):
    """From some date the source's amounts include fees and tax, or come in another currency: amt steps 20-40%
    overnight, ct doesn't."""
    start = F.pick_date()
    end = None if F.rng.random() < 0.5 else start + pd.Timedelta(days=int(F.rng.integers(60, 365)))
    mult = float(F.rng.uniform(1.2, 1.4))   # smaller steps are lost in the sources' normal ticket-size noise
    m = F.mask(t, s, start, end)
    F.df.loc[m, 'amt'] = (F.df.loc[m, 'amt'] * mult).round(2)
    return dict(type='amount_shift', ticker=t, source_id=s, start=_fmt(start), end=_fmt(end), mult=round(mult, 3),
                note='amounts include tax or fees')


def inj_source_outage(F, s, exclude=()):
    """One source drops out or goes near-dark for every company at once: a vendor-side failure. One item per
    ticker (`exclude`: series whose items the gold leaves out, e.g. low-volume ones)."""
    start = F.pick_date(); end = start + pd.Timedelta(days=int(F.rng.integers(8, 30)))
    keep = 0.0 if F.rng.random() < 0.5 else float(F.rng.uniform(0.05, 0.2))
    m = (F.df.source_id == s) & (F.df.date >= start) & (F.df.date <= end)
    tickers = sorted(F.df.loc[m, 'ticker'].unique())
    F.df.loc[m, 'ct'] = np.round(F.df.loc[m, 'ct'] * keep).astype(int)
    F.df.loc[m, 'amt'] = (F.df.loc[m, 'amt'] * keep).round(2)
    F.df = F.df[F.df.ct > 0]
    return [dict(type='outage', ticker=t, source_id=s, start=_fmt(start), end=_fmt(end), note='source-wide')
            for t in tickers if (t, s) not in exclude]


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
    start = F.pick_date(); end = start + pd.Timedelta(days=int(F.rng.integers(30, 120)))
    share = float(F.rng.uniform(0.4, 1.0))   # the share of transactions counted twice (under 40% is lost in noise)
    m = F.mask(t, s, start, end)
    F.df.loc[m, 'ct'] = np.round(F.df.loc[m, 'ct'] * (1 + share)).astype(int)
    F.df.loc[m, 'amt'] = (F.df.loc[m, 'amt'] * (1 + share)).round(2)
    return dict(type='double_count', ticker=t, source_id=s, start=_fmt(start), end=_fmt(end), share=round(share, 2))


def inj_outage(F, t, s):
    start = F.pick_date(); end = start + pd.Timedelta(days=int(F.rng.integers(8, 40)))
    m = F.mask(t, s, start, end)
    if F.rng.random() < 0.5:                  # missing
        F.df = F.df[~m]
    else:                                     # near-dark: a thin trickle of rows still arrives
        keep = float(F.rng.uniform(0.05, 0.2))
        F.df.loc[m, 'ct'] = np.round(F.df.loc[m, 'ct'] * keep).astype(int)
        F.df.loc[m, 'amt'] = (F.df.loc[m, 'amt'] * keep).round(2)
        F.df = F.df[F.df.ct > 0]
    return dict(type='outage', ticker=t, source_id=s, start=_fmt(start), end=_fmt(end))


def inj_level_shift(F, t, s, mult=None, length=None):
    start = F.pick_date()
    if mult is None:   # data_audit: a smaller step, temporary half the time; smaller than 1.4x either way is
        # lost in the steps real sources show against each other in this panel
        mult = float(F.rng.choice([F.rng.uniform(0.6, 0.72), F.rng.uniform(1.4, 1.65)]))
        length = None if F.rng.random() < 0.5 else int(F.rng.integers(60, 240))
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
               'double_count', 'outage', 'level_shift', 'dst_shift', 'amount_shift']


# --------------------------------------------------------------------------------------------------
# Real events (decoys): planted in every source of a ticker, so they are business activity, not problems.
# They change the clean panel too, before any problem is planted.
# --------------------------------------------------------------------------------------------------
def _scale(F, m, ct_mult, amt_mult):
    F.df.loc[m, 'ct'] = np.maximum(np.round(F.df.loc[m, 'ct'] * ct_mult), 0).astype(int)
    F.df.loc[m, 'amt'] = (F.df.loc[m, 'amt'] * amt_mult).round(2)
    F.df = F.df[F.df.ct > 0]


def real_industry_shock(F, industry):
    """A few days of lower sales across every source of every company in one industry (e.g. a storm)."""
    start = F.pick_date(0.1, 0.9); end = start + pd.Timedelta(days=int(F.rng.integers(1, 5)))
    mult = float(F.rng.uniform(0.5, 0.8))
    m = (F.df.industry == industry) & (F.df.date >= start) & (F.df.date <= end)
    tickers = sorted(F.df.loc[m, 'ticker'].unique())
    _scale(F, m, mult, mult)
    return dict(kind='industry_shock', industry=industry, tickers=tickers, start=_fmt(start), end=_fmt(end),
                mult=round(mult, 2))


def real_promotion(F, t, recurring):
    """A promotion in every source of one company: more transactions at a lower ticket. A recurring one runs in
    the same week every year."""
    d0, d1 = F.df.date.min(), F.df.date.max()
    start = F.pick_date(0.05, 0.95); days = int(F.rng.integers(3, 10))
    ct_mult, ticket = float(F.rng.uniform(1.3, 1.8)), float(F.rng.uniform(0.8, 0.9))
    starts = [start]
    if recurring:
        starts = [start + pd.DateOffset(years=y) for y in range(d0.year - start.year, d1.year - start.year + 1)]
        starts = [pd.Timestamp(a) for a in starts if d0 <= a and a + pd.Timedelta(days=days) <= d1]
    for a in starts:
        _scale(F, F.mask(t, None, a, a + pd.Timedelta(days=days)), ct_mult, ct_mult * ticket)
    return dict(kind='recurring_promotion' if recurring else 'promotion', ticker=t,
                periods=[[_fmt(a), _fmt(a + pd.Timedelta(days=days))] for a in starts],
                ct_mult=round(ct_mult, 2), ticket_mult=round(ticket, 2))

