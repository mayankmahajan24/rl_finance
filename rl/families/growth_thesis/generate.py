"""growth_thesis generator: a semi-synthetic airline panel with known true growth and traps.

Ported from make_thesis_variant in ~/altdata_evals/generator.py. The airlines and their activity
are synthetic. The only real data used is the seasonality template, taken from the split's own clean
airlines, so no other split's company shapes its tasks.
"""
from __future__ import annotations

import string

import numpy as np
import pandas as pd

from families._shared.panel_perturb import _fmt
from sources.txn_panel import panel

TEMPLATE_TICKERS = ['DAL', 'UAL', 'LUV', 'JBLU', 'SAVE', 'ALK']   # clean real airline series
N_AIRLINES = 9
CODES = [a + b for a in string.ascii_uppercase for b in string.ascii_uppercase]


def _seasonal_template(raw, tickers=TEMPLATE_TICKERS):
    """Realistic daily airline seasonality (weekly + annual + holidays) from clean real series."""
    a = raw[(raw.industry == 'airlines') & raw.ticker.isin(list(tickers))
            & raw.source_id.isin([2, 3, 4])]
    p = a.pivot_table(index='date', columns=['ticker', 'source_id'], values='ct')
    p = p.reindex(pd.date_range(p.index.min(), p.index.max()))
    x = np.log(p.clip(lower=1))
    x = x - x.rolling(365, center=True, min_periods=120).mean()
    return x.median(axis=1).interpolate().fillna(0.0)


def make_variant(seed: int, control: bool, ctx):
    template = [t for t in TEMPLATE_TICKERS if t in ctx.sensors]
    if not template:
        raise SystemExit('no clean airline in this split for the seasonality template')
    rng = np.random.default_rng(seed)
    tickers = sorted(f'T{c}' for c in rng.choice(CODES, N_AIRLINES, replace=False))
    shift = pd.Timedelta(days=364 * int(rng.choice([-3, -2, -1, 1, 2, 3, 4])))   # disguises dates, as Frame does
    seas = _seasonal_template(ctx.raw, template)
    dates = seas.index + shift
    T = len(dates); tt = np.arange(T) / 365.0
    y1, y2 = ((pd.Timestamp(f'{y}-07-01') + shift).year for y in (2015, 2017))

    def yearly_mean(series, y):
        return series[dates.year == y].mean()

    # true company activity with known growth; resample until the winner is unambiguous
    for _ in range(200):
        g = {t: float(rng.uniform(-0.06, 0.16)) for t in tickers}         # annual log-growth
        level = {t: float(np.exp(rng.uniform(np.log(80), np.log(2500)))) for t in tickers}
        truth_series = {}
        for t in tickers:
            ar = np.zeros(T); e = rng.normal(0, 0.03, T)
            for i in range(1, T):
                ar[i] = 0.7 * ar[i - 1] + e[i]
            truth_series[t] = level[t] * np.exp(seas.values + g[t] * tt + ar)
        growth = {t: yearly_mean(truth_series[t], y2) / yearly_mean(truth_series[t], y1) - 1 for t in tickers}
        order = sorted(growth, key=growth.get, reverse=True)
        if growth[order[0]] - growth[order[1]] >= 0.06:
            break
    fastest = order[0]

    # sensors: share x slowly drifting source coverage x Poisson noise
    sources = [1, 2, 3, 4]
    cov = {s: np.exp(np.cumsum(rng.normal(0, 0.003, T)) * 0.5) for s in sources}
    traps = {}
    y1_start = pd.Timestamp(f'{y1}-01-01')
    if not control:
        # (1) source-wide panel ramp in one source: x2.5 over ~90 days, mid-window (affects every airline)
        s_ramp = int(rng.choice(sources))
        r0 = int(np.searchsorted(dates, y1_start + pd.Timedelta(days=int(rng.integers(300, 500)))))
        ramp = np.clip((np.arange(T) - r0) / 90.0, 0, 1)
        cov[s_ramp] = cov[s_ramp] * np.exp(np.log(2.5) * ramp)
        traps['panel_ramp'] = dict(source_id=s_ramp, start=_fmt(dates[r0]), mult=2.5)
    rows = []
    share = {(t, s): float(rng.uniform(0.05, 0.6)) for t in tickers for s in sources}
    ticket = {t: float(rng.uniform(90, 320)) for t in tickers}
    for t in tickers:
        for s in sources:
            lam = truth_series[t] * share[(t, s)] * cov[s] * np.exp(np.cumsum(rng.normal(0, 0.002, T)) * 0.3)
            ct = rng.poisson(np.maximum(lam, 0))
            amt = ct * ticket[t] * np.exp(rng.normal(0, 0.08, T))
            rows.append(pd.DataFrame(dict(date=dates, ct=ct, amt=amt.round(2), ticker=t, industry='airlines', source_id=s)))
    df = pd.concat(rows, ignore_index=True)
    unreliable, optional_unreliable = [], []
    if not control:
        others = [t for t in tickers if t != fastest]
        r_t, o_t, d_t = rng.choice(others, 3, replace=False)
        # (2) ticker-wide re-mapping jump inside the comparison window (all sources x5-10)
        r_day = y1_start + pd.Timedelta(days=int(rng.integers(380, 640)))
        mult = round(float(rng.uniform(5, 10)), 4)   # rounded so arm64 and x86_64 builds match
        m = (df.ticker == r_t) & (df.date >= r_day)
        df.loc[m, 'ct'] = np.round(df.loc[m, 'ct'] * mult).astype(int); df.loc[m, 'amt'] *= mult
        traps['ticker_remap'] = dict(ticker=r_t, start=_fmt(r_day), mult=mult)
        unreliable.append(str(r_t))
        # (3) ticker-wide outage in the base year (every source near-dark for 60-90 days)
        o_day = y1_start + pd.Timedelta(days=int(rng.integers(60, 220)))
        o_end = o_day + pd.Timedelta(days=int(rng.integers(60, 90)))
        m = (df.ticker == o_t) & (df.date >= o_day) & (df.date <= o_end)
        df.loc[m, 'ct'] = rng.binomial(df.loc[m, 'ct'].values, 0.03)
        df.loc[m, 'amt'] *= 0.03
        traps['outage'] = dict(ticker=o_t, start=_fmt(o_day), end=_fmt(o_end))
        optional_unreliable.append(str(o_t))
        # (4) one source of one ticker double-counted through the end year
        d_s = int(rng.choice(sources))
        d_day = pd.Timestamp(f'{y2}-01-01') + pd.Timedelta(days=int(rng.integers(0, 120)))
        m = (df.ticker == d_t) & (df.source_id == d_s) & (df.date >= d_day)
        df.loc[m, 'ct'] *= 2; df.loc[m, 'amt'] *= 2
        traps['double_count'] = dict(ticker=d_t, source_id=d_s, start=_fmt(d_day))
    df = df[df.ct > 0]
    truth = dict(family='thesis', seed=seed, control=control, year_start=y1, year_end=y2,
                 true_growth={t: round(float(v), 4) for t, v in growth.items()}, fastest=fastest,
                 unreliable=unreliable, optional_unreliable=optional_unreliable, traps=traps,
                 growth_tolerance=0.15)
    df = df.sort_values(['date', 'ticker', 'source_id']).reset_index(drop=True)
    years = {'year_start': y1, 'year_end': y2}
    return df, truth, {'y1': y1, 'y2': y2}, years, sorted({panel.company_of_sensor(t) for t in template})
