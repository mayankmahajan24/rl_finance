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
EVAL_START_DAYS = 545
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
    excl = [dict(ticker=i['ticker'], source_id=i['source_id'], lo=i['start'],
                 hi=i['end'] or F.d(ctx.panel_end)) for i in req] + \
           [dict(ticker=i['ticker'], source_id=i['source_id'], lo=i['lo'],
                 hi=F.d(ctx.panel_end) if i['source_id'] is not None else i['hi']) for i in opt
            if (i['ticker'], i['source_id']) not in judged]
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
    text = tmpl.format(firm=build_panel.FIRM, schema=build_panel.SCHEMA, copy_note=build_panel.COPY_NOTE)
    shutil.rmtree(out, ignore_errors=True)
    jobs = [(base + i, False, f'{pre}-{i:03d}') for i in range(1, a.n + 1)] + \
           [(cbase + i, True, f'{pre}-control-{i:02d}') for i in range(1, a.controls + 1)]
    for seed, control, tid in jobs:
        shown, _, _, _ = plant(np.random.default_rng(seed), control, ctx)
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
        (d / 'instruction.md').write_text(text)
        # the hidden panel's disguise (original -> task coordinates), outside tests/ and environment/: for turning
        # review verdicts on this task's flags back into original coordinates
        (d / 'mapping.json').write_text(json.dumps(mapping, indent=1))
        kinds = pd.Series([e['type'] for e in truth['events']]).value_counts().to_dict()
        print(tid, len(hidden), 'rows;', kinds, '; decoys', [x['kind'] for x in truth['decoys']])


if __name__ == '__main__':
    main()
