"""Grade a scorer on an anomaly_hard prototype task: python grade.py TASK_DIR SOLUTION_DIR [--json OUT]

Runs SOLUTION_DIR/score.py on the task's hidden panel, truncated at the gold's cutoffs (earliest first) and then
whole, each run in its own empty folder, and scores it as the instruction says. A prototype: unlike the Harbor
verifier it does not sandbox the scorer (no `nobody` user, gold not removed from disk), so only grade code you trust
not to look for the gold, such as a submission copied out of its run folder.

Reward = (0.5 x row F1 + 0.5 x event F1) x coverage x no-foresight gate.
  labelled rows: every day of each planted event; 7 days after a regime ends are not scored
  event recall: mean over event kinds of the kind's mean credit; a short event counts if any day is flagged,
                a regime in full if first flagged within 14 days of its labelled start, nothing at 45
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

KEYS = ['date', 'ticker', 'source_id']
FULL_DAYS, ZERO_DAYS = 14, 45


def f1(p, r):
    return 2 * p * r / (p + r) if p + r else 0.0


def run(script: pathlib.Path, panel: pd.DataFrame) -> pd.DataFrame:
    work = pathlib.Path(tempfile.mkdtemp())
    try:
        panel.to_csv(work / 'in.csv', index=False, date_format='%Y-%m-%d')
        r = subprocess.run([sys.executable, str(script), '--input', str(work / 'in.csv'), '--output',
                            str(work / 'out.csv')], cwd=work, capture_output=True, text=True, timeout=1200)
        if r.returncode:
            raise RuntimeError(r.stderr[-1500:])
        s = pd.read_csv(work / 'out.csv', parse_dates=['date'])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    s['source_id'] = s.source_id.astype(int)
    return s[KEYS + ['anomaly_score']].drop_duplicates(KEYS)


def score(truth: dict, data: pd.DataFrame, script: pathlib.Path):
    cuts = sorted(truth['truncation_cutoffs'])
    trunc = {c: run(script, data[data.date <= pd.Timestamp(c)]) for c in cuts}
    full = run(script, data)
    leaks = []
    for c in cuts:
        cmp = (data[data.date <= pd.Timestamp(c)][KEYS].merge(trunc[c], on=KEYS, how='left')
               .merge(full, on=KEYS, how='left', suffixes=('_t', '_f')))
        leaks.append(int((~((cmp.anomaly_score_t - cmp.anomaly_score_f).abs() <= 1e-6)).sum()))
    gate = all(x == 0 for x in leaks)

    ev = data[KEYS].merge(full, on=KEYS, how='left')
    coverage = float(ev.anomaly_score.notna().mean())
    ev['flag'] = ev.anomaly_score.fillna(0) > truth['threshold']
    ev['label'] = False
    ev['use'] = ev.date >= pd.Timestamp(truth['eval_start'])
    for i in truth['ignore_series']:
        ev.loc[(ev.ticker == i['ticker']) & (ev.source_id == i['source_id']), 'use'] = False
    for x in truth['exclusions']:
        m = (ev.ticker == x['ticker']) & ev.date.between(pd.Timestamp(x['lo']) - pd.Timedelta(days=14),
                                                        pd.Timestamp(x['hi']) + pd.Timedelta(days=30))
        if x['source_id'] is not None:
            m &= ev.source_id == x['source_id']
        ev.loc[m, 'use'] = False
    masks = []
    for e in truth['events']:
        a, b = pd.Timestamp(e['start']), pd.Timestamp(e['end'])
        ser = (ev.ticker == e['ticker']) & (ev.source_id == e['source_id'])
        m = ser & ev.date.between(a, b)
        if e['regime']:
            ev.loc[ser & (ev.date > b) & (ev.date <= b + pd.Timedelta(days=truth['ignore_after_days'])), 'use'] = False
        ev.loc[m, 'label'] = True; ev.loc[m, 'use'] = True
        masks.append(m)
    e_ = ev[ev.use]
    flag, pos = e_.flag, e_.label
    out = dict(coverage=round(coverage, 4), no_foresight=gate, changed_on_truncation=leaks, rows_scored=int(len(e_)))
    if not pos.any():
        rate = float(flag.mean())
        return max(0.0, 1 - rate / 0.05) * coverage * gate, dict(out, control=True, flagged_share=round(rate, 4))
    tp, fp, fn = int((flag & pos).sum()), int((flag & ~pos).sum()), int((~flag & pos).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn)
    table = []
    for e, m in zip(truth['events'], masks):
        days = ev.date[m & ev.flag]
        delay = int((days.min() - pd.Timestamp(e['start'])).days) if len(days) else None
        if e['regime']:
            credit = 0.0 if delay is None else float(np.clip((ZERO_DAYS - delay) / (ZERO_DAYS - FULL_DAYS), 0, 1))
        else:
            credit = float(delay is not None)
        table.append(dict(type=e['type'], ticker=e['ticker'], source_id=e['source_id'], start=e['start'],
                          end=e['end'], days=int(m.sum()), flagged_days=int((m & ev.flag).sum()),
                          delay_days=delay, credit=round(credit, 3)))
    t = pd.DataFrame(table)
    by_kind = t.groupby('type').agg(events=('credit', 'size'), credit=('credit', 'mean'),
                                    days=('days', 'sum'), flagged_days=('flagged_days', 'sum'))
    ev_rec = float(by_kind.credit.mean())
    decoy_fp = 0
    for x in truth['decoys']:
        decoy_fp += int((e_.flag & (e_.ticker == x['ticker']) & e_.date.between(x['start'], x['end'])).sum())
    row_f1, event_f1 = f1(prec, rec), f1(prec, ev_rec)
    reward = (0.5 * row_f1 + 0.5 * event_f1) * coverage * gate
    return reward, dict(out, precision=round(prec, 3), recall=round(rec, 3), row_f1=round(row_f1, 3),
                        event_recall=round(ev_rec, 3), event_f1=round(event_f1, 3), tp=tp, fp=fp, fn=fn,
                        decoy_fp=decoy_fp, by_kind=by_kind.round(3).reset_index().to_dict('records'), events=table)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('task'); ap.add_argument('solution'); ap.add_argument('--json')
    a = ap.parse_args()
    task, sol = pathlib.Path(a.task), pathlib.Path(a.solution).resolve()
    truth = json.loads((task / 'tests' / 'gold.json').read_text())
    data = pd.read_csv(task / 'tests' / 'eval_panel.csv.gz', parse_dates=['date'])
    try:
        reward, d = score(truth, data, sol / 'score.py')
    except Exception as e:  # noqa: BLE001
        reward, d = 0.0, dict(error=str(e)[-800:])
    res = dict(task=task.name, solution=str(sol), reward=round(reward, 3), **d)
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, indent=1, default=str))
    short = {k: v for k, v in res.items() if k not in ('events', 'by_kind', 'solution')}
    print(json.dumps(short, default=str))
    for k in res.get('by_kind', []):
        print('   ', k)


if __name__ == '__main__':
    main()
