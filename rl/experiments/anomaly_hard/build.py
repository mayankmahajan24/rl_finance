"""Build anomaly_hard prototype tasks: python rl/experiments/anomaly_hard/build.py [--n 4] [--controls 1]

A prototype, not a family: it is not in any manifest, CI or approval, and its tasks go to
rl/tasks/proto/anomaly_hard/ (gitignored). It uses the bench split's companies, so results on it are eval
results, and its own seeds (300001.., 390001.. for controls), outside every family's ranges.

Like anomaly_scoring, each task has a visible panel (environment/data/transactions.csv) and a hidden panel
(tests/eval_panel.csv.gz) built with a different random stream, plus the gold (tests/gold.json).
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
EVAL_START_DAYS, IGNORE_AFTER, MIN_RECOVERY = 545, 7, 60
ONE_DAY = [P.card_testing, P.whale, P.settlement_lag, P.feed_dropout, P.duplicate_batch]   # 2 of each per panel
REGIMES = [(P.fragmentation, (90, 200))]                                                      # 1 per panel
# P.day_cut_shift is left out: at any realistic bleed it moves a source's weekly profile and day-to-day noise by
# less than they vary naturally over the 45 days the scoring allows, so labelling it would grade guessing


def plant(rng, control, ctx, n_tickers=8):
    raw = ctx.raw
    tks = list(rng.choice(sorted(raw.ticker.unique()), min(n_tickers, raw.ticker.nunique()), replace=False))
    F = Frame(raw, rng, tickers=tks, artifacts=ctx.artifacts)
    d0, d1 = F.df.date.min(), F.df.date.max()
    span = (d1 - d0).days
    req, opt = F.natural()
    art_series = {(i['ticker'], i['source_id']) for i in opt if i['source_id'] is not None}
    events, decoys, busy = [], [], []      # busy: (ticker, lo, hi) windows already used, so problems don't overlap

    def free(t, lo, hi, pad=20):
        return all(not (b[0] == t and lo - pd.Timedelta(days=pad) <= b[2] and b[1] <= hi + pd.Timedelta(days=pad))
                   for b in busy)

    def day(lo, hi):
        return d0 + pd.Timedelta(days=int(rng.integers(int(span * lo), int(span * hi))))

    if not control:
        cands = F.candidates(exclude_series=art_series)
        order = [cands[i] for i in rng.permutation(len(cands))]
        jobs = [(f, None) for f in ONE_DAY for _ in range(2)] + list(REGIMES)
        for f, lengths in jobs:
            for _ in range(200):
                t, s = order[int(rng.integers(len(order)))]
                if lengths:
                    start, length = day(0.3, 0.7), int(rng.integers(*lengths))
                    lo, hi = start, start + pd.Timedelta(days=length)
                else:
                    lo = hi = day(0.32, 0.95)
                if not free(t, lo, hi):
                    continue
                ev = f(F, t, s, lo, length) if lengths else f(F, t, s, lo)
                if ev:
                    events += ev
                    busy.append((t, lo, D(ev[-1]['end'])))
                    break
        for e in events:
            if e['regime']:
                assert D(e['end']) + pd.Timedelta(days=IGNORE_AFTER + MIN_RECOVERY) <= d1, e
    for f in (P.pantry_loading, P.holiday_settlement):                          # real events: every source
        for _ in range(200):
            t, x = F.t(tks[int(rng.integers(len(tks)))]), day(0.32, 0.95)
            if free(t, x, x + pd.Timedelta(days=10)):
                decoys.append(f(F, t, x)); busy.append((t, x, x + pd.Timedelta(days=10)))
                break
    excl = [dict(ticker=i['ticker'], source_id=i['source_id'], lo=i['start'],
                 hi=i['end'] or F.d(ctx.panel_end)) for i in req] + \
           [dict(ticker=i['ticker'], source_id=i['source_id'], lo=i['lo'],
                 hi=F.d(ctx.panel_end) if i['source_id'] is not None else i['hi']) for i in opt]
    not_real = []
    for r in reviewed():                                      # real problems in the source data, as reviewed
        t, s_ = F.t(r['ticker']), F.s(r['source_id'])
        if t is None:
            continue
        x = dict(ticker=t, source_id=s_, start=F.d(r['start']), end=F.d(r['end']), note=r.get('note', ''))
        if r['verdict'] == 'real':
            events.append(dict(x, type='real', regime=(D(r['end']) - D(r['start'])).days >= 7))
        elif r['verdict'] == 'unsure':
            excl.append(dict(ticker=t, source_id=s_, lo=x['start'], hi=x['end']))
        else:
            not_real.append(x)
    truth = dict(family='anomaly_hard', control=control, events=events, decoys=decoys, exclusions=excl,
                 reviewed_not_real=not_real,
                 ignore_series=F.low_volume_series(), eval_start=_fmt(d0 + pd.Timedelta(days=EVAL_START_DAYS)),
                 ignore_after_days=IGNORE_AFTER, threshold=0.5,
                 truncation_cutoffs=[_fmt(d0 + (d1 - d0) * f) for f in (0.45, 0.7)])
    df = F.df.sort_values(['date', 'ticker', 'source_id']).reset_index(drop=True)
    mapping = dict(tickers={o: d for o, d in F.tmap.items() if d in set(df.ticker)}, sources=F.smap,
                   shift_days=int(F.shift.days))
    return df, truth, mapping


def reviewed() -> list[dict]:
    return (yaml.safe_load(REVIEWED.read_text()) or {}).get('reviewed', []) if REVIEWED.exists() else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=4)
    ap.add_argument('--controls', type=int, default=1)
    a = ap.parse_args()
    ctx = build_panel.context('txn_panel', 'bench')
    tmpl = (HERE / 'instruction.md').read_text()
    text = tmpl.format(firm=build_panel.FIRM, schema=build_panel.SCHEMA, copy_note=build_panel.COPY_NOTE)
    shutil.rmtree(OUT, ignore_errors=True)
    jobs = [(300000 + i, False, f'anomhard-{i:03d}') for i in range(1, a.n + 1)] + \
           [(390000 + i, True, f'anomhard-control-{i:02d}') for i in range(1, a.controls + 1)]
    for seed, control, tid in jobs:
        shown, _, _ = plant(np.random.default_rng(seed), control, ctx)
        hidden, truth, mapping = plant(np.random.default_rng([seed, 1]), control, ctx)
        d = OUT / tid
        (d / 'environment' / 'data').mkdir(parents=True)
        (d / 'tests').mkdir()
        shown.to_csv(d / 'environment' / 'data' / 'transactions.csv', index=False, date_format='%Y-%m-%d')
        (d / 'tests' / 'eval_panel.csv.gz').write_bytes(gzip.compress(
            hidden.to_csv(index=False, date_format='%Y-%m-%d').encode(), mtime=0))
        (d / 'tests' / 'gold.json').write_text(json.dumps(dict(truth, seed=seed), indent=1))
        (d / 'instruction.md').write_text(text)
        # the hidden panel's disguise (original -> task coordinates), outside tests/ and environment/: for turning
        # review verdicts on this task's flags back into original coordinates
        (d / 'mapping.json').write_text(json.dumps(mapping, indent=1))
        kinds = pd.Series([e['type'] for e in truth['events']]).value_counts().to_dict()
        print(tid, len(hidden), 'rows;', kinds, '; decoys', [x['kind'] for x in truth['decoys']])


if __name__ == '__main__':
    main()
