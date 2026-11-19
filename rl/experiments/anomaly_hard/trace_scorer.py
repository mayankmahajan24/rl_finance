"""Replace each review card's chart with the scorer's own workings: python trace_scorer.py ITEMS.json SCORE_PY

Built for the scorer Opus wrote for the current task (a per-source state-space model on log count and log ticket
size: expected = source level + weekday profile + the company's common move from the other sources; residual z =
(actual - expected) / noise; a one-day flag above Z_POINT; a two-sided CUSUM on z that opens a shift run at
CUSUM_H; a run held steady for ACCEPT_DAYS accepted as a new normal; confidence = the lower of the two channels).
It runs a copy of that scorer, instrumented to record each day's state, on the task's hidden panel, and gives each
card the full history the scorer had seen when it set the alert: from the source's first row to the alert's last day.

Each card's chart: dates, the alert, known problems and real events in that history, and panels: count (actual,
expected, cleaned), count z, ticket size (actual, expected, cleaned), ticket z, drift evidence (CUSUM, both channels)
and confidence (with the days in a shift run and the days a new normal was accepted). Each card's reason is rewritten
from the same state on the day the alert began.
"""
from __future__ import annotations

import json
import pathlib
import sys
import types

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
TASKS = HERE.parents[1] / "tasks" / "proto" / "anomaly_hard"
HOOK = '    out["conf"][t] = conf\n'
REC = ('    _REC.append(dict(t=t, r=r.copy(), sd=sd.copy(), exp=expected.copy(), cp=ch.cp.copy(), cn=ch.cn.copy(),\n'
       '                     inrun=ch.inrun.copy(), adj=(ch.adj - ch.adj0).copy(), conf=conf.copy(), flag=flag.copy()))\n')


def instrumented(score_py: pathlib.Path):
    src = score_py.read_text()
    if HOOK not in src or 'def channel_step' not in src:
        raise SystemExit(f'{score_py} is not the scorer this tracer understands')
    mod = types.ModuleType('traced_scorer')
    mod._REC = []
    exec(compile(src.replace(HOOK, REC + HOOK), str(score_py), 'exec'), mod.__dict__)
    return mod


def trace_task(mod, task: str):
    """Run the scorer on the task's hidden panel; per (ticker, source): a frame of the recorded state by date."""
    d = TASKS / task
    data = pd.read_csv(d / 'tests' / 'eval_panel.csv.gz', parse_dates=['date'])
    mod._REC.clear()
    dbg = {}
    out = mod.score(data, debug=dbg)
    rec = mod._REC
    ct, tk = rec[0::2], rec[1::2]                      # channel_step runs count, then ticket, for every date
    dates = pd.DatetimeIndex(dbg['dates'])
    out['date'] = pd.to_datetime(out['date'])
    res = {}
    for (tkr, s), j in dbg['slot'].items():
        n = dbg['tix'][tkr]
        f = pd.DataFrame(index=dates)
        for name, rr in (('c', ct), ('k', tk)):
            f[f'{name}_r'] = [x['r'][n, j] for x in rr]
            f[f'{name}_sd'] = [x['sd'][n, j] for x in rr]
            f[f'{name}_exp'] = [x['exp'][n, j] for x in rr]
            f[f'{name}_cus'] = [max(x['cp'][n, j], x['cn'][n, j]) for x in rr]
            f[f'{name}_run'] = [bool(x['inrun'][n, j]) for x in rr]
            f[f'{name}_acc'] = [x['adj'][n, j] for x in rr]
            f[f'{name}_conf'] = [x['conf'][n, j] for x in rr]
        o = out[(out.ticker == tkr) & (out.source_id == s)].set_index('date')
        f = f.join(o[['confidence', 'clean_ct', 'clean_amt']])
        raw = data[(data.ticker == tkr) & (data.source_id == s)].set_index('date')
        f = f.join(raw[['ct', 'amt']])
        res[(tkr, int(s))] = f[f.ct.notna()]
    return res, mod.Z_POINT, mod.CUSUM_H


def r3(v):
    return [None if v_ is None or not np.isfinite(v_) else float(f'{v_:.4g}') for v_ in v]


def card_chart(f: pd.DataFrame, shift: pd.Timedelta, a_end: pd.Timestamp, known, zp: float, ch: float):
    h = f[f.index <= a_end]
    tk = np.log(h.amt / h.ct)
    ctk = np.log(h.clean_amt / h.clean_ct)
    panels = [
        dict(title='Daily count: actual, the model\'s expected count, and the cleaned count', key='count', positive=True, lines=[
            dict(v=r3(h.ct), color='count', w=1.4), dict(v=r3(np.exp(h.c_exp)), color='muted', w=1, dash=True),
            dict(v=r3(h.clean_ct.where((h.clean_ct - h.ct).abs() > 1e-6)), color='clean', w=1.6)]),
        dict(title=f'Count residual in noise units (one-day flag beyond ±{zp:g})', key='z', lines=[
            dict(v=r3(h.c_r / h.c_sd), color='count', w=1)], hlines=[zp, -zp], zero=True, clip=10),
        dict(title='Ticket size ($ per transaction): actual, expected, and cleaned', key='ticket', positive=True, lines=[
            dict(v=r3(np.exp(tk)), color='ticket', w=1.4), dict(v=r3(np.exp(h.k_exp)), color='muted', w=1, dash=True),
            dict(v=r3(np.exp(ctk).where((ctk - tk).abs() > 1e-6)), color='clean', w=1.6)]),
        dict(title=f'Ticket-size residual in noise units (one-day flag beyond ±{zp:g})', key='z', lines=[
            dict(v=r3(h.k_r / h.k_sd), color='ticket', w=1)], hlines=[zp, -zp], zero=True, clip=10),
        dict(title=f'Drift evidence (CUSUM): count and ticket size; a shift run opens at {ch:g}', key='cusum', lines=[
            dict(v=r3(h.c_cus), color='count', w=1.2), dict(v=r3(h.k_cus), color='ticket', w=1.2)], hlines=[ch],
             floor=0),
        dict(title='Confidence (below 0.5: distrusted); shaded: in a shift run; marked: new normal accepted',
             key='conf', lines=[dict(v=r3(h.confidence), color='ink', w=1.3)], hlines=[0.5], lo=0, hi=1,
             runs=[bool(a or b) for a, b in zip(h.c_run, h.k_run)],
             accepted=[bool(abs(a) > 1e-9 or abs(b) > 1e-9) for a, b in zip(h.c_acc, h.k_acc)]),
    ]
    return dict(algo=True, dates=[str((x - shift).date()) for x in h.index],
                flags=[bool(c < 0.5) for c in h.confidence], known=known, panels=panels)


def reason(f: pd.DataFrame, t0: pd.Timestamp, zp: float, ch: float, shift: pd.Timedelta) -> str:
    """What the scorer's state says on the alert's first day."""
    row = f.loc[t0]
    prev = f[f.index < t0]
    zc, zk = row.c_r / row.c_sd, row.k_r / row.k_sd
    parts = []
    run_c = bool(row.c_run) and (prev.empty or not bool(prev.c_run.iloc[-1]))
    run_k = bool(row.k_run) and (prev.empty or not bool(prev.k_run.iloc[-1]))
    held_c = bool(row.c_run) and not run_c
    held_k = bool(row.k_run) and not run_k
    for nm, z, run, held, rr, exp in (('count', zc, run_c, held_c, row.c_r, row.c_exp),
                                      ('ticket size', zk, run_k, held_k, row.k_r, row.k_exp)):
        pct = f'{abs(np.expm1(rr)) * 100:.0f}% {"above" if rr > 0 else "below"} expected'
        if run:
            parts.append(f'{nm.capitalize()} drift evidence reached the alarm ({ch:g}): a shift run opened. '
                         f'That day {nm} was {pct} ({z:+.1f} noise units).')
        elif held:
            col = 'c_run' if nm == 'count' else 'k_run'
            began = prev[~prev[col]].index.max()
            since = '' if pd.isna(began) else f' since {(began + pd.Timedelta(days=1) - shift).date()}'
            parts.append(f'{nm.capitalize()} still in a shift run{since}: {pct} ({z:+.1f} noise units), not yet '
                         f'back on its old level.')
        elif abs(z) > zp:
            parts.append(f'One-day {nm} flag: {pct}, {z:+.1f} noise units (line at ±{zp:g}).')
    if not parts:
        parts.append(f'No single trigger above its line; confidence {row.confidence:.2f} '
                     f'(count {zc:+.1f}, ticket size {zk:+.1f} noise units).')
    if abs(row.c_acc) > 1e-9 or abs(row.k_acc) > 1e-9:
        parts.append('An earlier shift on this source had been accepted as its new normal.')
    return ' '.join(parts)


def main():
    items_path, score_py = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    items = json.loads(items_path.read_text())
    mod = instrumented(score_py)
    cache = {}
    for it in items:
        p = it['parts'][0]                             # the chart follows the card's first alert
        if p['task'] not in cache:
            cache[p['task']] = trace_task(mod, p['task'])
        tr, zp, ch = cache[p['task']]
        mp = json.loads((TASKS / p['task'] / 'mapping.json').read_text())
        shift = pd.Timedelta(days=mp['shift_days'])
        f = tr[(p['task_ticker'], p['task_source'])]
        a_end = pd.Timestamp(p['end']) + shift
        gold = json.loads((TASKS / p['task'] / 'tests' / 'gold.json').read_text())
        lo = f.index.min()
        known = []
        for e in gold['events']:
            if e['ticker'] == p['task_ticker'] and e['source_id'] == p['task_source'] and \
                    pd.Timestamp(e.get('shift_start', e['start'])) <= a_end:
                known.append(dict(kind=e['type'], start=str((pd.Timestamp(e.get('shift_start', e['start'])) - shift).date()),
                                  end=str((min(pd.Timestamp(e['end']), a_end) - shift).date())))
        for x in gold['decoys']:
            if x['ticker'] == p['task_ticker'] and lo <= pd.Timestamp(x['start']) <= a_end:
                known.append(dict(kind='real event: ' + x['kind'].replace('_', ' '),
                                  start=str((pd.Timestamp(x['start']) - shift).date()),
                                  end=str((pd.Timestamp(x['start']) - shift).date()) if x['kind'] == 'company_step'
                                  else str((min(pd.Timestamp(x['end']), a_end) - shift).date()), marker=x['kind'] == 'company_step'))
        it['chart'] = card_chart(f, shift, a_end, known, zp, ch)
        for q in it['parts']:
            fq = cache[q['task']][0][(q['task_ticker'], q['task_source'])] if q['task'] in cache else None
            if fq is None:
                cache[q['task']] = trace_task(mod, q['task'])
                fq = cache[q['task']][0][(q['task_ticker'], q['task_source'])]
            mq = json.loads((TASKS / q['task'] / 'mapping.json').read_text())
            sq = pd.Timedelta(days=mq['shift_days'])
            q['why'] = reason(fq, pd.Timestamp(q['start']) + sq, zp, ch, sq) + \
                ('' if q['flagged_days'] <= 1 else f' Distrusted {q["flagged_days"]} days.')
    items_path.write_text(json.dumps(items, separators=(',', ':')))
    print(len(items), 'cards traced; page data', round(items_path.stat().st_size / 1e6, 1), 'MB')


if __name__ == '__main__':
    main()
