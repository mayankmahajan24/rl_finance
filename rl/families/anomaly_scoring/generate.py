"""anomaly_scoring generator: a disguised panel of up to 8 sensor tickers with planted one-day
anomalies and level shifts, and the labels the verifier scores against.

Ported from make_anomaly_variant in ~/altdata_evals/generator.py; identical on the full panel. On a
split's smaller panel it uses every ticker the split has when that is fewer than 8.

The agent gets one such panel and is graded on a second, built with a different random stream and
shipped only in tests/ (hidden_files), so scores worked out on the data it can see are worth nothing.
"""
from __future__ import annotations

import gzip

import numpy as np
import pandas as pd

from families._shared.panel_perturb import D, Frame, _fmt, inj_level_shift

EVAL_START_DAYS = 545     # warm-up: rows before this are not scored
SHIFT_IGNORE_AFTER = 7    # a level shift is bad data on every day it lasts; the 7 days after it ends are not scored
MIN_RECOVERY = 60         # scored days that must follow that, so flagging the recovery is visible


def make_variant(seed: int, control: bool, ctx, n_tickers=8):
    shown, labels = plant(np.random.default_rng(seed), control, ctx, n_tickers)
    hidden, truth = plant(np.random.default_rng([seed, 1]), control, ctx, n_tickers)
    truth = dict(truth, seed=seed, shown_planted={k: labels[k] for k in ("points", "shifts")}, hidden_files={"eval_panel.csv.gz": gzip.compress(
        hidden.to_csv(index=False, date_format="%Y-%m-%d").encode(), mtime=0)})
    return shown, truth, {}, None, ctx.companies


def plant(rng, control: bool, ctx, n_tickers: int):
    """One disguised panel with its planted anomalies, and the labels for it."""
    raw = ctx.raw
    tks = list(rng.choice(sorted(raw.ticker.unique()), min(n_tickers, raw.ticker.nunique()), replace=False))
    F = Frame(raw, rng, tickers=tks, artifacts=ctx.artifacts)
    points, shifts = [], []
    d0, d1 = F.df.date.min(), F.df.date.max()
    if not control:
        cands = F.candidates()
        picks = [cands[i] for i in rng.choice(len(cands), min(6, len(cands)), replace=False)]
        for t, s in picks[:3]:                                     # 4 one-day anomalies on each of 3 series
            days = F.df[F.mask(t, s, d0 + (d1 - d0) * 0.3, d0 + (d1 - d0) * 0.95)].date
            for i, day in enumerate(rng.choice(days.values, 4, replace=False)):
                mult = 3.0 if i % 2 == 0 else 0.25
                m = F.mask(t, s, D(day), D(day))
                F.df.loc[m, 'ct'] = np.maximum(np.round(F.df.loc[m, 'ct'] * mult), 1).astype(int)
                F.df.loc[m, 'amt'] = (F.df.loc[m, 'amt'] * mult).round(2)
                points.append(dict(ticker=t, source_id=s, date=_fmt(day), mult=mult))
        for t, s in picks[3:]:                                     # 3 level shifts of 60-240 days
            # the shift starts in [0.3, 0.75] of the panel (inj_level_shift's default date), so it ends inside
            # the scored window with months of recovered data after it: a scorer that lets its baseline absorb
            # the shift and then flags the return to normal pays for it in precision
            it = inj_level_shift(F, t, s, mult=float(rng.choice([0.55, 1.7])), length=int(rng.integers(60, 241)))
            assert D(it['start']) >= d0 + pd.Timedelta(days=EVAL_START_DAYS) and \
                D(it['end']) + pd.Timedelta(days=SHIFT_IGNORE_AFTER + MIN_RECOVERY) <= d1, it
            shifts.append(dict(ticker=t, source_id=s, start=it['start'], end=it['end'], mult=it['mult']))
    req, opt = F.natural()
    excl = [dict(ticker=i['ticker'], source_id=i['source_id'], lo=i['start'],
                 hi=i['end'] or F.d(ctx.panel_end)) for i in req] + \
           [dict(ticker=i['ticker'], source_id=i['source_id'], lo=i['lo'],
                 hi=F.d(ctx.panel_end) if i['source_id'] is not None else i['hi']) for i in opt]
    # a real source-level artifact (a coverage ramp, an under-capture) can leave the source at a new level for good;
    # a scorer told that a shift is bad until it returns to normal would flag it forever, and on day t no causal
    # scorer can tell that from a long planted shift, so that series is not scored from the artifact to the end
    cutoffs = [_fmt(d0 + (d1 - d0) * f) for f in (0.45, 0.7)]
    truth = dict(family='anomaly', control=control, points=points, shifts=shifts,
                 exclusions=excl, ignore_series=F.low_volume_series(),
                 eval_start=_fmt(d0 + pd.Timedelta(days=EVAL_START_DAYS)), shift_ignore_after_days=SHIFT_IGNORE_AFTER,
                 threshold=0.5, truncation_cutoffs=cutoffs)
    df = F.df.sort_values(['date', 'ticker', 'source_id']).reset_index(drop=True)
    return df, truth
