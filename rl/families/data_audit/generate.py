"""data_audit generator: one disguised panel with planted data-quality problems, and its ground truth.

Ported from make_audit_variant in ~/altdata_evals/generator.py, then made harder (2026-11-10):
  * smaller, shorter and partial problems than the pilot, and a swap picks the partner closest in volume;
  * new kinds: a daylight-saving date offset, amounts that start including tax, one source failing for every
    company at once, and a level shift stacked on another problem;
  * real events planted in every source (an industry shock, a promotion, a yearly promotion) as decoys.
The panel after the real events and before any problem (clean.csv.gz, hidden in tests/ with the panel as given,
given.csv.gz) is what a repair is graded against. On a split's smaller panel it plants fewer problems when it runs out of untouched companies.
"""
from __future__ import annotations

import gzip

import numpy as np
import pandas as pd

from families._shared import panel_perturb as P
from families._shared.panel_perturb import Frame, inj_series_swap

# A series is usable if what is wrong with it can be fixed. Every problem type has an exact or peer-based fix
# except missing data: an outage longer than UNRECOVERABLE_DAYS can't be filled from the seasonal pattern.
# A series is not usable if such a period reaches into the last RECENT_DAYS of the panel, or if it has
# MAX_PERIODS or more of them, or if they cover more than MAX_SHARE of its history.
UNRECOVERABLE_DAYS = 7
RECENT_DAYS = 90
MAX_PERIODS = 3
MAX_SHARE = 0.10


def make_variant(seed: int, control: bool, ctx):
    rng = np.random.default_rng(seed)
    F = Frame(ctx.raw, rng, artifacts=ctx.artifacts)
    decoys = plant_real_events(F, rng)            # real activity: part of the clean panel
    clean = F.df[['date', 'ticker', 'source_id', 'ct', 'amt']].copy()
    ignore = F.low_volume_series()
    low = {(i['ticker'], i['source_id']) for i in ignore}
    planted, used_series, used_tickers = [], set(), set()
    if not control:
        n = int(rng.integers(3, 6))
        for typ in rng.choice(P.AUDIT_TYPES, n, replace=False):
            cands = F.candidates(exclude_tickers=used_tickers, exclude_series=used_series)
            if not cands:          # a small split ran out of untouched companies: plant fewer problems
                break
            t, s = cands[int(rng.integers(len(cands)))]
            if typ == 'series_swap':
                partners = [c for c in cands if c[1] == s and c[0] != t]
                if not partners:   # no second company on this source: skip the swap
                    continue
                # the partner closest in volume, so the swap is not an obvious jump in level
                med = F.df[F.df.source_id == s].groupby('ticker').ct.median()
                t2 = min((c[0] for c in partners), key=lambda x: abs(np.log(med[x] / med[t])))
                items = [inj_series_swap(F, t, s, t2)]; used_tickers |= {t, t2}
            else:
                items = getattr(P, f'inj_{typ}')(F, t, s); used_tickers.add(t)
                items = items if isinstance(items, list) else [items]
            used_series.add((t, s))
            planted += items
        stackable = [i for i in planted if i['type'] in STACKABLE]
        if stackable and rng.random() < 0.5:     # a second problem on a series that already has one
            i = stackable[int(rng.integers(len(stackable)))]
            planted.append(P.inj_level_shift(F, i['ticker'], i['source_id']))
        if rng.random() < 0.4:                   # one source fails for every company at once
            items = P.inj_source_outage(F, int(rng.choice(sorted(F.df.source_id.unique()))), exclude=low)
            planted += items; used_series |= {(i['ticker'], i['source_id']) for i in items}
        planted += plant_unusable(F, rng, used_series)
    planted = [dict(i, origin='planted') for i in planted]
    req, opt = F.natural()
    truth = dict(family='audit', seed=seed, control=control, required=planted + req, optional=opt,
                 ignore_series=ignore, decoys=decoys, panel_end=P._fmt(F.df.date.max()),
                 usability=usability(F.df, planted + req, ignore),
                 hidden_files={})
    df = F.df.sort_values(['date', 'ticker', 'source_id']).reset_index(drop=True)
    # the grader's copies: the true panel, and the panel as given (which days each problem changed)
    for name, panel in (('clean.csv.gz', clean), ('given.csv.gz', df)):
        truth['hidden_files'][name] = gzip.compress(panel[['date', 'ticker', 'source_id', 'ct', 'amt']].sort_values(
            ['date', 'ticker', 'source_id']).to_csv(index=False, date_format='%Y-%m-%d').encode(), mtime=0)
    return df, truth, {}, None, ctx.companies


# problems a later level shift can sit on top of (the repair has to undo both)
STACKABLE = {'duplicate_rows', 'swapped_columns', 'unit_scale', 'date_shift', 'dst_shift', 'amount_shift'}


def plant_real_events(F, rng):
    """One or two real events, in every source: an industry-wide shock, a one-off promotion, or one that recurs
    every year. Reports on them are false and changing them is damage."""
    events = []
    inds = F.df.groupby('industry').ticker.nunique()
    kinds = [k for k in ('industry_shock', 'promotion', 'recurring_promotion')
             if k != 'industry_shock' or (inds >= 2).any()]
    for kind in rng.choice(kinds, int(rng.integers(1, 3)), replace=False):
        if kind == 'industry_shock':
            events.append(P.real_industry_shock(F, str(rng.choice(sorted(inds[inds >= 2].index)))))
        else:
            cands = sorted({t for t, _ in F.candidates()})
            if cands:
                events.append(P.real_promotion(F, cands[int(rng.integers(len(cands)))], kind == 'recurring_promotion'))
    return events


def plant_unusable(F, rng, used_series):
    """Outages that leave a series unusable, each on about half of the tasks: one that runs to the end of
    the panel, and three separate ones on a single series."""
    items, d0, d1 = [], F.df.date.min(), F.df.date.max()
    span = (d1 - d0).days
    for kind in ('to_end', 'repeated'):
        if rng.random() >= 0.5:
            continue
        cands = F.candidates(exclude_series=used_series)
        if not cands:
            continue
        t, s = cands[int(rng.integers(len(cands)))]
        used_series.add((t, s))
        if kind == 'to_end':
            windows = [(d1 - pd.Timedelta(days=int(rng.integers(30, 120))), None)]
        else:
            windows = []
            for k in range(3):     # one in each of three bands of the history, none near the end
                start = d0 + pd.Timedelta(days=int(span * (0.1 + 0.25 * k + rng.uniform(0, 0.15))))
                windows.append((start, start + pd.Timedelta(days=int(rng.integers(10, 30)))))
        for start, end in windows:
            F.df = F.df[~F.mask(t, s, start, end)]
            items.append(dict(type='outage', ticker=t, source_id=s, start=P._fmt(start), end=P._fmt(end)))
    return items


def unrecoverable(required, ticker, source, panel_end):
    """(start, end) of the outages on this series too long to fill in."""
    out = []
    for i in required:
        if i['type'] == 'outage' and i['ticker'] == ticker and i['source_id'] in (None, source):
            a, b = pd.Timestamp(i['start']), pd.Timestamp(i['end']) if i['end'] else panel_end
            if (b - a).days + 1 > UNRECOVERABLE_DAYS:
                out.append((a, b))
    return out


def usability(df, required, ignore):
    """Whether each scored series is usable once its problems are fixed (the rule at the top of this file)."""
    end = df.date.max()
    skip = {(i['ticker'], i['source_id']) for i in ignore}
    out = []
    for (t, s), first in df.groupby(['ticker', 'source_id']).date.min().items():
        if (t, int(s)) in skip:
            continue
        periods = unrecoverable(required, t, int(s), end)
        recent = any(b > end - pd.Timedelta(days=RECENT_DAYS) for _, b in periods)
        share = sum((b - a).days + 1 for a, b in periods) / ((end - first).days + 1)
        out.append(dict(ticker=t, source_id=int(s),
                        usable=not (recent or len(periods) >= MAX_PERIODS or share > MAX_SHARE)))
    return out
