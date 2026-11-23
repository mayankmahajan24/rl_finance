"""Build anomaly_hard prototype tasks: python rl/experiments/anomaly_hard/build.py [--n 4] [--controls 1]

A prototype, not a family: it is not in any manifest, CI or approval, and its tasks go to
rl/tasks/proto/anomaly_hard/ (gitignored). It uses the bench split's companies, so results on it are eval
results, and its own seeds (300001.., 390001.. for controls; train split 320001.., 392001..), outside every family's
ranges. --split train builds from the train companies into rl/tasks/proto/anomaly_hard_train/.

Like anomaly_scoring, each task has a visible panel (environment/data/transactions.csv) and a hidden panel
(tests/eval_panel.csv.gz) built with a different random stream, plus the gold (tests/gold.json) and the hidden
panel as it was before the problems were planted (tests/truth_panel.csv.gz: real events included), which is what
the cleaned series is scored against.
"""
from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import shutil
import sys

import numpy as np
import pandas as pd
import yaml

HERE = pathlib.Path(__file__).resolve().parent
RL = HERE.parents[1]
sys.path[:0] = [str(RL), str(HERE)]
from families._shared import build_panel  # noqa: E402
from families._shared.panel_perturb import D, Frame, _fmt  # noqa: E402
import perturb as P  # noqa: E402

OUT = RL / "tasks" / "proto" / "anomaly_hard"
REVIEWED = HERE / "reviewed.yaml"   # verdicts on real (unplanted) problems, in original coordinates; grader-only
EVAL_START_DAYS = 365   # one year of warm-up: enough history for levels, noise and a yearly pattern (feedback #27)
THIN_CT = 20   # a stretch whose 28-day median count is under this is too thin to trust: not scored (feedback #18)
N_POINTS, SHIFTS = 2, [('step', 2), ('ramp', 2)]   # per panel: 2 of each point kind, 2 step and 2 ramp level shifts


def plant(rng, control, ctx, n_tickers=8):
    raw = ctx.raw
    tks = list(rng.choice(sorted(raw.ticker.unique()), min(n_tickers, raw.ticker.nunique()), replace=False))
    F = Frame(raw, rng, tickers=tks, artifacts=ctx.artifacts)
    d0, d1 = F.df.date.min(), F.df.date.max()
    span = (d1 - d0).days
    req, opt = F.natural()
    art_series = {(i['ticker'], i['source_id']) for i in opt if i['source_id'] is not None}
    events, decoys, busy = [], [], []      # busy: (key, lo, hi) windows already used, so problems don't overlap

    def free(key, lo, hi, pad=20):
        return all(not (b[0] == key and lo - pd.Timedelta(days=pad) <= b[2] and b[1] <= hi + pd.Timedelta(days=pad))
                   for b in busy)

    def day(lo, hi):
        return d0 + pd.Timedelta(days=int(rng.integers(int(span * lo), int(span * hi))))

    for f in P.DECOYS:                       # real events first: they are part of what the sources should report
        for _ in range(200):
            t, x = F.t(tks[int(rng.integers(len(tks)))]), day(0.32, 0.9)
            if free(t, x, x + pd.Timedelta(days=30)):
                decoys.append(f(F, t, x)); busy.append((t, x, x + pd.Timedelta(days=30)))
                break
    truth_df = F.df.copy()
    if not control:
        cands = F.candidates(exclude_series=art_series)
        jobs = [(f, None) for f in P.POINTS for _ in range(N_POINTS)] + [(mode, None) for mode, n in SHIFTS
                                                                        for _ in range(n)]
        for f, _ in jobs:
            for _ in range(500):
                t, s = cands[int(rng.integers(len(cands)))]
                if callable(f):
                    lo = hi = day(0.32, 0.95)
                    hi = lo + pd.Timedelta(days=3)
                else:
                    permanent = bool(rng.random() < 0.5)
                    lo = day(0.3, 0.8 if permanent else 0.7)
                    length = None if permanent else int(rng.integers(60, 241))
                    hi = d1 if permanent else lo + pd.Timedelta(days=length + 45)
                if not free((t, s), lo, hi) or not free(t, lo, lo + pd.Timedelta(days=3)):
                    continue
                ev = f(F, t, s, lo) if callable(f) else P.level_shift(F, t, s, lo, f, length, d1)
                if ev:
                    events += ev
                    busy.append(((t, s), lo, hi))
                    break
    # a series reviewed end to end, or with a reviewed level change, is judged by the review, not by the shared
    # panel's list of known source artifacts (which would leave it unscored from the artifact to the panel end)
    judged = {(F.t(x['ticker']), F.s(int(x['source_id']))) for x in reviewed_series()} | \
             {(F.t(r['ticker']), F.s(int(r['source_id']))) for r in reviewed() if r['verdict'] == 'change'}
    # company-wide natural breaks (every source at once: nothing to recover them from) stay out of scoring. A known
    # quirk of one source is graded by what it did in this data (quirk_event): a lasting change to flag and rescale,
    # or nothing (normal data); it stays out only when it cannot be cross-checked (fewer than two usable peers)
    excl = [dict(ticker=i['ticker'], source_id=i['source_id'], lo=i['start'],
                 hi=i['end'] or F.d(ctx.panel_end)) for i in req]
    quirks = []
    for i in opt:
        if (i['ticker'], i['source_id']) in judged:
            continue
        if i['source_id'] is None:
            excl.append(dict(ticker=i['ticker'], source_id=None, lo=i['lo'], hi=i['hi']))
            continue
        q = quirk_event(F.df, i, d1)
        if q == 'unrecoverable':
            excl.append(dict(ticker=i['ticker'], source_id=i['source_id'], lo=i['lo'], hi=F.d(ctx.panel_end)))
        elif q:
            events.append(q)
            quirks.append(q)
    not_real, recurring = [], []
    for r in reviewed():                                      # real problems in the source data, as reviewed
        t, s_ = F.t(r['ticker']), F.s(r['source_id'])
        if t is None:
            continue
        x = dict(ticker=t, source_id=s_, start=F.d(r['start']), end=F.d(r['end']), note=r.get('note', ''))
        if r['verdict'] == 'real':
            events.append(dict(x, type='real', regime=False))   # the days the reviewer marked bad, as marked
        elif r['verdict'] == 'change':
            # a real lasting change in the source, scored like a planted level shift (grade.label_rows): its first
            # days are untrustworthy, then the new level is normal; it returns after `end` unless end == start
            lasts = r['end'] == r['start']
            events.append(dict(x, type='real_change', regime=True, permanent=lasts,
                               end=F.d(ctx.panel_end) if lasts else x['end'], settle=F.d(r.get('settle', r['start']))))
        elif r['verdict'] == 'recurring':
            # a pattern the source shows every year is normal: the first time it appears in the data it is not scored
            # (distrusting it then is understandable); every later year it must be trusted and left as it is
            first = recurring_first(F, t, s_, r)
            if first:
                excl.append(dict(ticker=t, source_id=s_, lo=first[0], hi=first[1], kind='recurring_first'))
            recurring.append(dict(x, first=first))
        elif r['verdict'] == 'unsure':
            excl.append(dict(ticker=t, source_id=s_, lo=x['start'], hi=x['end']))
        else:
            not_real.append(x)
    full = [dict(ticker=F.t(x['ticker']), source_id=F.s(int(x['source_id']))) for x in reviewed_series()
            if F.t(x['ticker']) is not None]
    truth = dict(family='anomaly_hard', control=control, events=events, decoys=decoys, exclusions=excl,
                 reviewed_not_real=not_real, reviewed_recurring=recurring, reviewed_series=full,
                 ignore_series=F.low_volume_series(), eval_start=_fmt(d0 + pd.Timedelta(days=EVAL_START_DAYS)),
                 threshold=0.5, thin_ct=THIN_CT,
                 truncation_cutoffs=[_fmt(d0 + (d1 - d0) * f) for f in (0.45, 0.7)])
    df = F.df.sort_values(['date', 'ticker', 'source_id']).reset_index(drop=True)
    truth_df = truth_df.sort_values(['date', 'ticker', 'source_id']).reset_index(drop=True)
    assert len(truth_df) == len(df) and (truth_df[['date', 'ticker', 'source_id']] == df[['date', 'ticker', 'source_id']]).all().all()
    mapping = dict(tickers={o: d for o, d in F.tmap.items() if d in set(df.ticker)}, sources=F.smap,
                   shift_days=int(F.shift.days))
    return df, truth, mapping, truth_df


QUIRK_MIN = 0.15        # a known source quirk that moved the source less than this (log) did nothing to grade
# windows on the shared artifact list that are narrower than the effect in the data, widened here (not in the shared
# list, which is also data_audit's gold): days added before lo and after hi
QUIRK_WIDEN = {'source-1 airline panel ramp': (517, 150)}   # 2016-05-01..2017-01-31 -> 2014-12-01..2017-06-30 (data_audit review G4)


def quirk_event(df, it, d1):
    """What a known source-level quirk (artifact list: lo..hi, one source) did to that source in this data: its
    relation to the median of its company's other sources, in log count and log ticket, over the 90 days before lo
    against the 90 days after hi. Under QUIRK_MIN: None (normal data). Otherwise a real_change event (scored like a
    reviewed level change): onset = first day the 14-day median relation is a third of the way to the new level,
    settled = first day it is within a quarter of it, lasting to the panel end unless the source returns to its old
    relation later (then until it does). 'unrecoverable' when the source has fewer than two other usable sources."""
    t, s = it['ticker'], it['source_id']
    lo, hi = pd.Timestamp(it['lo']), pd.Timestamp(it['hi'])
    before, after_ = QUIRK_WIDEN.get(it.get('note', ''), (0, 0))
    lo, hi = lo - pd.Timedelta(days=before), hi + pd.Timedelta(days=after_)
    g = df[df.ticker == t]
    ct = g.pivot(index='date', columns='source_id', values='ct').astype(float)
    if s not in ct.columns or ct.shape[1] < 3:
        return 'unrecoverable'
    amt = g.pivot(index='date', columns='source_id', values='amt').astype(float)
    peers = [c for c in ct.columns if c != s and ct[c].median() >= 20]
    if len(peers) < 2:
        return 'unrecoverable'
    lc, lt = np.log(ct), np.log(amt) - np.log(ct)
    best = None
    for name, x in (('count', lc), ('ticket', lt)):
        rel = (x[s] - x[peers].median(axis=1)).dropna()
        pre = rel[(rel.index >= lo - pd.Timedelta(days=90)) & (rel.index < lo)]
        post = rel[(rel.index > hi) & (rel.index <= hi + pd.Timedelta(days=90))]
        if len(pre) < 30 or len(post) < 30:
            continue
        sh = float(post.median() - pre.median())
        if best is None or abs(sh) > abs(best[1]):
            best = (name, sh, rel, float(pre.median()))
    if best is None or abs(best[1]) < QUIRK_MIN:
        return None
    name, sh, rel, base = best
    sm = rel.rolling(14, min_periods=7, center=True).median()
    dev = (sm - base) * np.sign(sh)
    win = dev[(dev.index >= lo - pd.Timedelta(days=30)) & (dev.index <= hi + pd.Timedelta(days=30))]
    onset = win[win > abs(sh) / 3].index.min()
    settle = win[win > 0.75 * abs(sh)].index.min()
    if pd.isna(onset):
        return None
    after = dev[dev.index > hi + pd.Timedelta(days=30)]
    back = after[after < abs(sh) / 3].index
    end = back.min() if len(back) and (after.loc[back.min():] < abs(sh) / 3).mean() > 0.8 else d1
    return dict(type='real_change', regime=True, ticker=t, source_id=s, start=_fmt(onset), end=_fmt(end),
                permanent=bool(end == d1), settle=_fmt(settle if not pd.isna(settle) else hi), origin='quirk',
                note=f"{it.get('note', 'known source quirk')}: {name} {sh:+.2f} against peers")


# the disguise, as this task describes it: the companies are named (feedback #28); codes, sources, dates and levels
# stay disguised, and the panel the code is graded on has its own codes
COPY_NOTE = """This copy of the panel is disguised. Each ticker is a code for a company named in the table below; the codes
and source ids are different in the panel your code is graded on, so the code must not depend on them. Source ids
are shuffled. Dates are shifted by a whole multiple of 364 days, so weekdays line up but holidays can sit a few days
off their usual dates. Each ticker-source series has its `ct` and `amt` multiplied by its own hidden factor between
0.3 and 3, so levels are not comparable across series. Growth within a series and average ticket size (`amt` / `ct`)
are real."""
BRANDS = {'M_M': "Macy's stores", 'M_BL': "Bloomingdale's", 'JWN_JWN': 'Nordstrom full-line stores',
          'JWN_RACK': 'Nordstrom Rack', 'ROST_ROST': 'Ross Dress for Less', 'ROST_DD': "dd's DISCOUNTS",
          'TJX_TJMAXX': 'T.J. Maxx and Marshalls'}


def companies_table(shown: pd.DataFrame, mapping: dict) -> str:
    """The companies behind this task's visible ticker codes (entities.yaml), as a markdown table."""
    ent = yaml.safe_load((RL / 'sources' / 'txn_panel' / 'annotations' / 'entities.yaml').read_text())['companies']
    by_sensor = {x: (tk, e) for tk, e in ent.items() for x in e['sensors']}
    codes = mapping['tickers']
    rows = ['| code | company | ticker | business |', '|---|---|---|---|']
    for sensor, code in sorted(codes.items(), key=lambda kv: kv[1]):
        if code not in set(shown.ticker):
            continue
        tk, e = by_sensor[sensor]
        rows.append(f"| {code} | {e['name']}{' (' + BRANDS[sensor] + ')' if sensor in BRANDS else ''} | {tk} | {e['industry']} |")
    return '\n'.join(rows)


def recurring_first(F, t, s, r, slack=3):
    """The first year a reviewed recurring pattern's calendar window (same month and day, +-slack days) falls inside the
    source's data, in task coordinates, or None."""
    a, b = D(r['start']), D(r['end'])
    have = F.df[(F.df.ticker == t) & (F.df.source_id == s)].date
    if have.empty:
        return None
    first_day = have.min() - F.shift                     # original coordinates
    for k in range(-10, 11):
        lo, hi = a + pd.DateOffset(years=k) - pd.Timedelta(days=slack), b + pd.DateOffset(years=k) + pd.Timedelta(days=slack)
        if lo >= first_day:
            return [F.d(lo), F.d(hi)]
    return None


def reviewed_series() -> list[dict]:
    """Series the reviewer has gone through end to end: every day not marked on them is confirmed fine."""
    return (yaml.safe_load(REVIEWED.read_text()) or {}).get('reviewed_series') or [] if REVIEWED.exists() else []


def reviewed() -> list[dict]:
    return (yaml.safe_load(REVIEWED.read_text()) or {}).get('reviewed') or [] if REVIEWED.exists() else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=4)
    ap.add_argument('--controls', type=int, default=1)
    ap.add_argument('--split', default='bench', choices=['bench', 'train'])   # held-out companies are never used here
    a = ap.parse_args()
    ctx = build_panel.context('txn_panel', a.split)
    out = OUT if a.split == 'bench' else OUT.with_name(f'anomaly_hard_{a.split}')
    base, cbase, pre = (300000, 390000, 'anomhard') if a.split == 'bench' else (320000, 392000, f'anomhard-{a.split}')
    tmpl = (HERE / 'instruction.md').read_text()
    text = tmpl.format(firm=build_panel.FIRM, schema=build_panel.SCHEMA, copy_note=COPY_NOTE, companies='{companies}')
    shutil.rmtree(out, ignore_errors=True)
    jobs = [(base + i, False, f'{pre}-{i:03d}') for i in range(1, a.n + 1)] + \
           [(cbase + i, True, f'{pre}-control-{i:02d}') for i in range(1, a.controls + 1)]
    for seed, control, tid in jobs:
        shown, _, shown_map, _ = plant(np.random.default_rng(seed), control, ctx)
        hidden, truth, mapping, clean = plant(np.random.default_rng([seed, 1]), control, ctx)
        d = out / tid
        (d / 'environment' / 'data').mkdir(parents=True)
        (d / 'tests').mkdir()
        shown.to_csv(d / 'environment' / 'data' / 'transactions.csv', index=False, date_format='%Y-%m-%d')
        (d / 'tests' / 'eval_panel.csv.gz').write_bytes(gzip.compress(
            hidden.to_csv(index=False, date_format='%Y-%m-%d').encode(), mtime=0))
        (d / 'tests' / 'truth_panel.csv.gz').write_bytes(gzip.compress(
            clean.to_csv(index=False, date_format='%Y-%m-%d').encode(), mtime=0))
        (d / 'tests' / 'gold.json').write_text(json.dumps(dict(truth, seed=seed), indent=1))
        (d / 'instruction.md').write_text(text.replace('{companies}', companies_table(shown, shown_map)))
        # the hidden panel's disguise (original -> task coordinates), outside tests/ and environment/: for turning
        # review verdicts on this task's flags back into original coordinates
        (d / 'mapping.json').write_text(json.dumps(mapping, indent=1))
        kinds = pd.Series([e['type'] for e in truth['events']]).value_counts().to_dict()
        print(tid, len(hidden), 'rows;', kinds, '; decoys', [x['kind'] for x in truth['decoys']])


if __name__ == '__main__':
    main()
