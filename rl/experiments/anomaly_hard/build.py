"""Build anomaly_hard prototype tasks: python rl/experiments/anomaly_hard/build.py [--n 4] [--controls 1]

A prototype, not a family: it is not in any manifest, CI or approval, and its tasks go to
rl/tasks/proto/anomaly_hard/ (gitignored). It uses the bench split's companies, so results on it are eval
results, and its own seeds (300001.., 390001.. for controls; train split 320001.., 392001..), outside every family's
ranges. --split train builds from the train companies into rl/tasks/proto/anomaly_hard_train/.

Each task has a visible panel (environment/data/transactions.csv) built from one industry-balanced half of the
split's companies, and a hidden panel (tests/eval_panel.csv.gz) from the other half, with its own random stream; plus
the gold (tests/gold.json: every planted problem, exact) and the hidden panel before the problems were planted
(tests/truth_panel.csv.gz: real events included), which the cleaned series is scored against.

Every source is rebuilt on its company's real daily move (background.semi_real), so the only source-level oddities are
the planted ones: normal behaviour (yearly closures, a thin beginning, company-wide real events) and problems
(one-day problems, steps, ramps, slow ramps).
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
from families._shared.panel_perturb import Frame, _fmt  # noqa: E402


class UnscaledFrame(Frame):
    """The shared disguise (codes, shuffled sources, dates shifted by whole years) without the per-series rescale of
    counts and dollars: the twenty-a-day low-signal bar and a series' counting noise refer to its real transactions
    (feedback #95). The rescale's random draws are still made, so everything else matches the shared Frame."""

    def __init__(self, raw, rng, tickers=None, artifacts=((), ())):
        super().__init__(raw, rng, tickers=tickers, artifacts=artifacts)
        orig = raw if tickers is None else raw[raw.ticker.isin(tickers)]
        df = orig.copy()
        df['ticker'] = df.ticker.map(self.tmap)
        df['source_id'] = df.source_id.map(self.smap)
        df['date'] = df.date + self.shift
        self.df = df[df.ct > 0].sort_values(['ticker', 'source_id', 'date']).reset_index(drop=True)
import background  # noqa: E402
import grade  # noqa: E402
import perturb as P  # noqa: E402

OUT = RL / "tasks" / "proto" / "anomaly_hard"
EVAL_START_DAYS = 365   # one year of warm-up: enough history for levels, noise and a yearly pattern
THIN_CT = 20   # a source's thin beginning (28-day median count under this, before it is established) must be dropped
N_POINTS, SHIFTS = 2, [('step', 2), ('ramp', 2)]   # per panel: 2 of each point kind, 2 step and 2 ramp level shifts
N_PANELS = 3           # hidden panels a task is graded on (the reward is their mean): fresh draws of problems
N_INSIDE, N_STACKED = 2, 1   # per panel: one-offs placed inside a level change, and a step stacked on one
N_RECURRING, N_SLOW = 2, 2   # per panel: planted yearly closures (normal) and slow panel ramps (problems)
N_MULTI = 1            # per panel: one of each several-day problem (perturb.MULTI)
N_PHANTOM, N_SMALL, N_CHAIN = 1, 1, 1   # per panel: a phantom-count stretch, a small step on a clean source, and a
#                                         one-off planted a week or two before a level change on the same source


def plant(rng, control, ctx, n_tickers=8, sensors=None):
    raw = ctx.raw
    pool = sorted(sensors) if sensors else sorted(raw.ticker.unique())
    tks = list(rng.choice(pool, min(n_tickers, len(pool)), replace=False))
    F = UnscaledFrame(raw, rng, tickers=tks, artifacts=ctx.artifacts)
    F.df = background.semi_real(F.df)        # every source rebuilt on its company's real moves
    d0, d1 = F.df.date.min(), F.df.date.max()
    span = (d1 - d0).days
    req, opt = F.natural()                   # known natural breaks and source artifacts of the real panel
    art_series = {(i['ticker'], i['source_id']) for i in opt if i['source_id'] is not None}   # nothing planted on them
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
    recurring_planted, thin_planted = [], []
    # source behaviour that is normal, planted with exact labels
    cands0 = F.candidates(exclude_series=art_series)
    for _ in range(N_RECURRING):
        for _ in range(100):
            t, s_ = cands0[int(rng.integers(len(cands0)))]
            r = background.plant_recurring(F, rng, t, s_, d0, d1)
            if r:
                recurring_planted.append(r)
                for x in r['dates']:
                    busy.append(((t, s_), pd.Timestamp(x) - pd.Timedelta(days=3), pd.Timestamp(x) + pd.Timedelta(days=3)))
                break
    for _ in range(500):                 # every panel has a thin start (so doing nothing cannot pass)
        t, s_ = cands0[int(rng.integers(len(cands0)))]
        if any((r['ticker'], r['source_id']) == (t, s_) for r in recurring_planted):
            continue                     # a closure hidden in thin data would first show years later
        r = background.plant_thin_start(F, rng, t, s_, d0)
        if r:
            thin_planted.append(r)
            busy.append(((t, s_), d0, pd.Timestamp(r['thin_until']) + pd.Timedelta(days=150)))
            break
    truth_df = F.df.copy()
    if not control:
        cands = F.candidates(exclude_series=art_series)
        jobs = [(f, None) for f in P.POINTS for _ in range(N_POINTS)] + [(mode, None) for mode, n in SHIFTS
                                                                        for _ in range(n)]
        jobs += [('slow', None) for _ in range(N_SLOW)]
        for f, _ in jobs:
            for _ in range(500):
                t, s = cands[int(rng.integers(len(cands)))]
                if callable(f):
                    lo = hi = day(0.32, 0.95)
                    hi = lo + pd.Timedelta(days=3)
                elif f == 'slow':
                    lo, hi = day(0.3, 0.6), d1
                    # one level change at a time per company, so every change can be told from its peers
                    if free((t, s), lo, hi) and free(('chg', t), lo, d1):   # its whole span: it lasts to the end
                        ev = background.slow_ramp(F, rng, t, s, lo, d1)
                        if ev:
                            events += ev
                            busy.append(((t, s), lo, hi))
                            busy.append((('chg', t), lo, d1))     # a lasting change: the company's only one from here on
                            break
                    continue
                else:
                    permanent = bool(rng.random() < 0.5)
                    lo = day(0.3, 0.8 if permanent else 0.7)
                    length = None if permanent else int(rng.integers(60, 241))
                    hi = d1 if permanent else lo + pd.Timedelta(days=length + 45)
                own = ('pt', t, s) if callable(f) else (t, s)    # one-offs may land inside a level change
                if not free(own, lo, hi) or not free(t, lo, lo + pd.Timedelta(days=3)):
                    continue
                if not callable(f) and not free(('chg', t), lo, hi):
                    continue                     # one level change at a time per company, over its whole span
                ev = f(F, t, s, lo) if callable(f) else P.level_shift(F, t, s, lo, f, length, d1)
                if ev:
                    events += ev
                    busy.append((own, lo, hi))
                    if not callable(f):
                        # a lasting change holds the company to the end; a temporary one until it is over
                        busy.append((('chg', t), lo, d1 if length is None else lo + pd.Timedelta(days=length + 45)))
                    break
        # several-day problems that are not a steady level (feedback #98): on a source with no level change, thin
        # start or closure in their span, away from company events, one at a time per company
        for f, longest in [x for x in P.MULTI for _ in range(N_MULTI)]:
            for _ in range(500):
                t, s = cands[int(rng.integers(len(cands)))]
                lo = day(0.32, 0.93)
                hi = lo + pd.Timedelta(days=longest)
                if hi > d1 or not (free((t, s), lo, hi) and free(('pt', t, s), lo, hi) and free(t, lo, hi)
                                   and free(('multi', t), lo, hi)):
                    continue
                ev = f(F, t, s, lo)
                if ev:
                    events += ev
                    busy += [(k_, lo, hi) for k_ in ((t, s), ('pt', t, s), ('multi', t))]
                    break
        # level changes of two more shapes: a fixed number of phantom transactions a day, and a step sized against
        # the source's noise to its sisters, on one of the panel's cleaner sources
        sig = grade.own_noise(truth_df).set_index(['ticker', 'source_id'])
        clean_half = [c for c in cands if c in sig.index and sig.loc[c, 'sig_c'] <= sig.reindex(cands).sig_c.median()]
        for what in ['phantom'] * N_PHANTOM + ['small'] * N_SMALL:
            for _ in range(500):
                pool_ = clean_half if what == 'small' and clean_half else cands
                t, s = pool_[int(rng.integers(len(pool_)))]
                lo = day(0.3, 0.7)
                length = int(rng.integers(30, 121)) if what == 'phantom' else int(rng.integers(90, 241))
                hi = lo + pd.Timedelta(days=length + 45)
                if not (free((t, s), lo, hi) and free(('pt', t, s), lo, hi) and free(t, lo, lo + pd.Timedelta(days=3))
                        and free(('chg', t), lo, hi)):
                    continue
                ev = P.phantom(F, t, s, lo, length) if what == 'phantom' else P.level_shift(
                    F, t, s, lo, 'step', length, d1, small=dict(ct=float(sig.loc[(t, s), 'sig_c']),
                                                                tkt=float(sig.loc[(t, s), 'sig_t'])))
                if ev:
                    events += ev
                    busy += [((t, s), lo, hi), (('chg', t), lo, hi)]
                    break
        # problems in quick succession: a one-off 5-14 days before a level change on the same source
        firsts = [e for e in events if e.get('regime') and not e.get('small') and e.get('measure') != 'phantom']
        for _ in range(N_CHAIN):
            for _ in range(200):
                if not firsts:
                    break
                e = firsts[int(rng.integers(len(firsts)))]
                t, s = e['ticker'], e['source_id']
                lo = pd.Timestamp(e.get('shift_start', e['start'])) - pd.Timedelta(days=int(rng.integers(5, 15)))
                if lo < d0 + pd.Timedelta(days=EVAL_START_DAYS) or not free(('pt', t, s), lo, lo + pd.Timedelta(days=3)) \
                        or not free(t, lo, lo + pd.Timedelta(days=3)) or not free((t, s), lo, lo, pad=0):
                    continue
                ev = P.POINTS[int(rng.integers(len(P.POINTS)))](F, t, s, lo)
                if ev:
                    events += [dict(x, before_change=True) for x in ev]
                    busy.append((('pt', t, s), lo, lo + pd.Timedelta(days=3)))
                    break
        # overlapping problems in one source (feedback #97): one-offs inside a level change, and a step on top of an
        # earlier level change, each in the same source while its sisters stay clean
        levels = [e for e in events if e.get('regime') or e['type'] == 'level_shift_slow']
        for k in range(N_INSIDE + N_STACKED):
            for _ in range(200):
                if not levels:
                    break
                e = levels[int(rng.integers(len(levels)))]
                t, s = e['ticker'], e['source_id']
                a = pd.Timestamp(e.get('shift_start', e['start'])) + pd.Timedelta(days=30)
                b = min(pd.Timestamp(e['end']), d1) - pd.Timedelta(days=60)
                if b <= a:
                    continue
                lo = a + pd.Timedelta(days=int(rng.integers(0, (b - a).days + 1)))
                if k < N_INSIDE:                            # a one-off inside the level change
                    f = P.POINTS[int(rng.integers(len(P.POINTS)))]
                    if not free(('pt', t, s), lo, lo + pd.Timedelta(days=3)) or not free(t, lo, lo + pd.Timedelta(days=3)):
                        continue
                    ev = f(F, t, s, lo)
                    if ev:
                        events += ev
                        busy.append((('pt', t, s), lo, lo + pd.Timedelta(days=3)))
                        break
                else:                                       # a temporary step on top of the level change, same source
                    length = int(rng.integers(30, 121))
                    if lo + pd.Timedelta(days=length + 45) > min(pd.Timestamp(e['end']), d1):
                        continue
                    ev = P.level_shift(F, t, s, lo, 'step', length, d1)
                    if ev:
                        events += ev
                        break
    # company-wide natural breaks (every source at once: nothing to recover them from) are not scored
    excl = [dict(ticker=i['ticker'], source_id=i['source_id'], lo=i['start'],
                 hi=i['end'] or F.d(ctx.panel_end)) for i in req]
    closures = []
    for r in recurring_planted:                               # planted yearly patterns: first year not scored
        first = pd.Timestamp(r['dates'][0])
        excl.append(dict(ticker=r['ticker'], source_id=r['source_id'], lo=_fmt(first), hi=_fmt(first),
                         kind='recurring_first'))
        closures += [dict(ticker=r['ticker'], source_id=r['source_id'], start=x, end=x) for x in r['dates']]
    truth = dict(family='anomaly_hard', control=control, events=events, decoys=decoys, exclusions=excl,
                 closures=closures, thin_start=thin_planted, ignore_series=F.low_volume_series(),
                 eval_start=_fmt(d0 + pd.Timedelta(days=EVAL_START_DAYS)), threshold=0.5, thin_ct=THIN_CT,
                 truncation_cutoffs=[_fmt(d0 + (d1 - d0) * f) for f in (0.45, 0.7)])
    df = F.df.sort_values(['date', 'ticker', 'source_id']).reset_index(drop=True)
    truth_df = truth_df.sort_values(['date', 'ticker', 'source_id']).reset_index(drop=True)
    assert len(truth_df) == len(df) and (truth_df[['date', 'ticker', 'source_id']] == df[['date', 'ticker', 'source_id']]).all().all()
    mapping = dict(tickers={o: d for o, d in F.tmap.items() if d in set(df.ticker)}, sources=F.smap,
                   shift_days=int(F.shift.days))
    annotate_events(truth, df, truth_df)
    return df, truth, mapping, truth_df


MEDIAN7_SD = 1.2533 / np.sqrt(7)   # a 7-day median's noise, as a share of one day's (normal noise)


def annotate_events(truth, df, truth_df):
    """What a point-in-time scorer could see, written into each level change: it becomes `visible` on the first day its
    deviation (raw against the truth panel, trailing 7-day median) reaches P.SHIFT_K times the noise of a 7-day median
    of the source's relation to its sisters (MEDIAN7_SD of its daily noise), in count or ticket; its onset is scored from then (earlier days unscored). A change that never gets there is
    `unscored`. A planted slow ramp, or a change that took longer than grade.SETTLE_DAYS to become visible, is `slow`:
    scored on the cleaned series only. The noise is the grader's (grade.own_noise), so what is scored is what the
    grader can tell apart from the source's normal variation against its sister sources."""
    # the source's own noise as the grader measures it (grade.own_noise: its daily relation to its sister sources),
    # so a change is scored only once it stands out the way the grader and any peer-based scorer can see it
    sig = grade.own_noise(truth_df).set_index(['ticker', 'source_id'])
    raw = df.set_index(grade.KEYS)[['ct', 'amt']]
    tru = truth_df.set_index(grade.KEYS)[['ct', 'amt']]
    lg = lambda x: np.log(np.maximum(x.astype(float), 0.01))  # noqa: E731
    for e in truth['events']:
        key = (e['ticker'], e['source_id'])
        if key not in sig.index:
            continue
        sc, st = sig.loc[key, 'sig_c'], sig.loc[key, 'sig_t']
        if not e.get('regime'):
            continue
        a = pd.Timestamp(e.get('shift_start', e['start']))
        b = pd.Timestamp(e['end'])
        r = raw.xs((e['ticker'], e['source_id']), level=('ticker', 'source_id'))
        r = r[(r.index >= a) & (r.index <= b)]
        x = tru.xs((e['ticker'], e['source_id']), level=('ticker', 'source_id'))
        j = r.join(x, rsuffix='_x', how='inner')
        if j.empty:
            continue
        dc = lg(j.ct) - lg(j.ct_x)
        dt = (lg(j.amt) - lg(j.ct)) - (lg(j.amt_x) - lg(j.ct_x))
        z = np.maximum(dc.rolling(7, min_periods=1).median().abs() / sc, dt.rolling(7, min_periods=1).median().abs() / st)
        seen = z[z >= P.SHIFT_K * MEDIAN7_SD]              # against the noise of a 7-day median, not of one day
        if seen.empty:
            e['unscored'] = True
        else:
            e['visible'] = _fmt(seen.index.min())
            # slower to show than a change's settling window (weeks), or planted as a build-up over months: no
            # point-in-time code can date its onset, so it is scored on the cleaned series only
            if (seen.index.min() - pd.Timestamp(e.get('shift_start', e['start']))).days > grade.SETTLE_DAYS \
                    or e['type'] == 'level_shift_slow':     # a build-up over months is slow, however large
                e['slow'] = True


# the disguise, as this task describes it: the companies are named; codes, sources, dates and levels
# stay disguised, and the panel the code is graded on has its own codes
COPY_NOTE = """This copy of the panel is built from the companies' real daily transactions: each source follows its company's real
day-to-day moves, with its own level, weekday pattern and day-to-day noise. It is disguised. Each ticker is a code
for a company named in the table below. The panel your
code is graded on covers other companies, with their own codes and source ids, so the code must not depend on them. Source ids
are shuffled. Dates are shifted by a whole multiple of 364 days, so weekdays line up but holidays can sit a few days
off their usual dates. Counts, dollars, growth and average ticket size (`amt` / `ct`) are real."""
BRANDS = {'M_M': "Macy's stores", 'M_BL': "Bloomingdale's", 'JWN_JWN': 'Nordstrom full-line stores',
          'JWN_RACK': 'Nordstrom Rack', 'ROST_ROST': 'Ross Dress for Less', 'ROST_DD': "dd's DISCOUNTS",
          'TJX_TJMAXX': 'T.J. Maxx and Marshalls'}


def company_groups(ctx, seed) -> tuple[list[str], list[str]]:
    """The split's companies in two groups, balanced by industry (each industry's companies shuffled and dealt in
    turn): the visible panel is built from one group and the hidden panel the code is graded on from the other, so the
    code is always graded on companies it was not built on. Returns the two groups' sensor tickers."""
    ent = yaml.safe_load((RL / 'sources' / 'txn_panel' / 'annotations' / 'entities.yaml').read_text())['companies']
    have = set(ctx.raw.ticker.unique())
    rng = np.random.default_rng([seed, 2])
    a, b, turn = [], [], 0
    for ind in sorted({e['industry'] for e in ent.values()}):
        comps = sorted(c for c, e in ent.items() if e['industry'] == ind and set(e['sensors']) & have)
        for c in rng.permutation(comps):
            (a if turn % 2 == 0 else b).extend(x for x in ent[c]['sensors'] if x in have)
            turn += 1
    return a, b


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


def build_task(ctx, d: pathlib.Path, seed: int, control: bool) -> dict:
    """One task into folder d (created): visible panel from one company group; N_PANELS hidden panels from the other,
    each with its own planted problems, disguise, truth panel and gold (panel 1 in tests/, panel k in tests/panel-k/).
    Returns panel 1's gold."""
    tmpl = (HERE / 'instruction.md').read_text()
    text = tmpl.format(firm=build_panel.FIRM, schema=build_panel.SCHEMA, copy_note=COPY_NOTE, companies='{companies}')
    vis, hid = company_groups(ctx, seed)
    shown, _, shown_map, _ = plant(np.random.default_rng(seed), control, ctx, sensors=vis)
    hidden, truth, mapping, clean = plant(np.random.default_rng([seed, 1]), control, ctx, sensors=hid)
    (d / 'environment' / 'data').mkdir(parents=True)
    for f in ('Dockerfile', 'requirements.lock'):     # the pinned task image (environment/ in this folder)
        shutil.copy(HERE / 'environment' / f, d / 'environment' / f)
    (d / 'tests').mkdir()
    shown.to_csv(d / 'environment' / 'data' / 'transactions.csv', index=False, date_format='%Y-%m-%d')
    (d / 'tests' / 'eval_panel.csv.gz').write_bytes(gzip.compress(
        hidden.to_csv(index=False, date_format='%Y-%m-%d').encode(), mtime=0))
    (d / 'tests' / 'truth_panel.csv.gz').write_bytes(gzip.compress(
        clean.to_csv(index=False, date_format='%Y-%m-%d').encode(), mtime=0))
    (d / 'tests' / 'gold.json').write_text(json.dumps(dict(truth, seed=seed), indent=1))
    for k in range(2, N_PANELS + 1):      # more hidden panels: the same companies, fresh problems and disguise
        h, t, _, c = plant(np.random.default_rng([seed, k]), control, ctx, sensors=hid)
        pk = d / 'tests' / f'panel-{k}'
        pk.mkdir()
        pk.joinpath('eval_panel.csv.gz').write_bytes(gzip.compress(h.to_csv(index=False, date_format='%Y-%m-%d').encode(), mtime=0))
        pk.joinpath('truth_panel.csv.gz').write_bytes(gzip.compress(c.to_csv(index=False, date_format='%Y-%m-%d').encode(), mtime=0))
        pk.joinpath('gold.json').write_text(json.dumps(dict(t, seed=seed, panel=k), indent=1))
    (d / 'tests').chmod(0o700)          # grader-only: the scorer runs as nobody and cannot read it
    (d / 'instruction.md').write_text(text.replace('{companies}', companies_table(shown, shown_map)))
    # the hidden panel's disguise (original -> task coordinates), outside tests/ and environment/
    (d / 'mapping.json').write_text(json.dumps(mapping, indent=1))
    kinds = pd.Series([e['type'] for e in truth['events']]).value_counts().to_dict()
    print(d.name, 'visible', sorted(vis), 'hidden', sorted(hid), len(hidden), 'rows;', kinds,
          '; decoys', [x['kind'] for x in truth['decoys']])
    return truth


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=4)
    ap.add_argument('--controls', type=int, default=1)
    ap.add_argument('--split', default='bench', choices=['bench', 'train'])   # held-out companies are never used here
    a = ap.parse_args()
    ctx = build_panel.context('txn_panel', a.split)
    out = OUT if a.split == 'bench' else OUT.with_name(f'anomaly_hard_{a.split}')
    base, cbase, pre = (300000, 390000, 'anomhard') if a.split == 'bench' else (320000, 392000, f'anomhard-{a.split}')
    shutil.rmtree(out, ignore_errors=True)
    jobs = [(base + i, False, f'{pre}-{i:03d}') for i in range(1, a.n + 1)] + \
           [(cbase + i, True, f'{pre}-control-{i:02d}') for i in range(1, a.controls + 1)]
    for seed, control, tid in jobs:
        build_task(ctx, out / tid, seed, control)


if __name__ == '__main__':
    main()
