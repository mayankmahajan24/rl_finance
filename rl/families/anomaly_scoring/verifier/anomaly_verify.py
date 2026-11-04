"""Verifier for the online anomaly-scoring task.

Runs the agent's /app/solution/score.py on a hidden panel (tests/eval_panel.csv.gz) the agent never saw,
truncated at hidden cutoff dates and then whole:
    python score.py --input IN.csv --output OUT.csv
OUT.csv must have columns date, ticker, source_id, anomaly_score (0..1, higher = more anomalous),
one row per input row (duplicate keys are not expected in this task).

Reward = F1 (threshold 0.5) on the hidden planted anomalies
       x coverage (share of input rows scored)
       x no-foresight gate: 0 if any score dated <= a cutoff changes, or goes missing, when later data is removed.
Positives: planted one-day anomalies, and the first 60 days of each planted level shift.
Ignored:   days 61+ of a planted shift (and 60 days after it ends), low-volume series, windows around
           known natural artifacts, and the warm-up period.
Control variants (nothing planted): reward = 1 - (share of evaluated rows flagged) / 5%, floored at 0.

score.py is agent code. Before it runs, the gold and the hidden panel leave the disk and it runs as
`nobody` when the verifier is root. Truncated runs come first, earliest cutoff first, and every run
gets its own folder, so no run can find or remember rows dated after its cutoff.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from common import APP, TESTS, f1, load_gold, write_reward

TIMEOUT = int(os.environ.get('SCORE_TIMEOUT_SEC', '1200'))
KEYS = ['date', 'ticker', 'source_id']


def run_scorer(panel: pd.DataFrame):
    script = APP / 'solution' / 'score.py'
    root = os.geteuid() == 0
    if root:
        subprocess.run(['chmod', '-R', 'a+rX', str(APP / 'solution')], check=True)
    work = Path(tempfile.mkdtemp())
    work.chmod(0o777)
    inp, out = work / 'in.csv', work / 'out.csv'
    panel.to_csv(inp, index=False)
    inp.chmod(0o644)
    try:
        r = subprocess.run([sys.executable, str(script), '--input', str(inp), '--output', str(out)],
                           capture_output=True, text=True, timeout=TIMEOUT, cwd=str(APP),
                           user='nobody' if root else None, env={'PATH': os.environ['PATH'], 'HOME': str(work)})
        if r.returncode != 0:
            raise RuntimeError(f'score.py failed ({r.returncode}): {r.stderr[-1500:]}')
        s = pd.read_csv(out, parse_dates=['date'])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    missing = {'date', 'ticker', 'source_id', 'anomaly_score'} - set(s.columns)
    if missing:
        raise RuntimeError(f'output missing columns {missing}')
    s['source_id'] = s.source_id.astype(int)
    return s[KEYS + ['anomaly_score']].drop_duplicates(KEYS)


def main():
    truth = load_gold()
    data = pd.read_csv(TESTS / 'eval_panel.csv.gz', parse_dates=['date'])
    for f in ('gold.json', 'eval_panel.csv.gz'):
        (TESTS / f).unlink(missing_ok=True)

    # ---- no-foresight gate: the truncated runs come first, so nothing later is on disk to reuse
    cutoffs = sorted(truth['truncation_cutoffs'])
    truncated = {}
    for c in cutoffs:
        try:
            truncated[c] = run_scorer(data[data.date <= pd.Timestamp(c)])
        except Exception as e:  # noqa: BLE001
            return write_reward(0.0, dict(error=f'truncated run failed: {e}'))
    try:
        full = run_scorer(data)
    except Exception as e:  # noqa: BLE001
        return write_reward(0.0, dict(error=str(e)))

    leaks = []
    for c in cutoffs:
        part, trunc = data[data.date <= pd.Timestamp(c)], truncated[c]
        # every truncated row must be scored, and as on the full data: a missing or NaN truncated
        # score counts as changed, so a scorer can't hide lookahead by dropping or blanking rows
        cmp = (part[KEYS].drop_duplicates().merge(trunc, on=KEYS, how='left')
               .merge(full, on=KEYS, how='left', suffixes=('_trunc', '_full')))
        changed = ~((cmp.anomaly_score_trunc - cmp.anomaly_score_full).abs() <= 1e-6)
        leaks.append(dict(cutoff=c, rows=len(cmp), unscored=int(cmp.anomaly_score_trunc.isna().sum()),
                          changed=int(changed.sum())))
    no_foresight = all(l['rows'] > 0 and l['changed'] == 0 for l in leaks)

    # ---- label rows
    ev = data[KEYS].drop_duplicates().merge(full, on=KEYS, how='left')
    coverage = float(ev.anomaly_score.notna().mean())
    ev['anomaly_score'] = ev.anomaly_score.fillna(0.0)
    ev['label'] = 0; ev['use'] = ev.date >= pd.Timestamp(truth['eval_start'])
    for i in truth['ignore_series']:
        ev.loc[(ev.ticker == i['ticker']) & (ev.source_id == i['source_id']), 'use'] = False
    for x in truth['exclusions']:
        m = (ev.ticker == x['ticker']) & ev.date.between(pd.Timestamp(x['lo']) - pd.Timedelta(days=14),
                                                        pd.Timestamp(x['hi']) + pd.Timedelta(days=30))
        if x['source_id'] is not None:
            m &= ev.source_id == x['source_id']
        ev.loc[m, 'use'] = False
    for sh in truth['shifts']:
        s0, s1 = pd.Timestamp(sh['start']), pd.Timestamp(sh['end'])
        ser = (ev.ticker == sh['ticker']) & (ev.source_id == sh['source_id'])
        pos = ser & ev.date.between(s0, s0 + pd.Timedelta(days=truth['shift_positive_days'] - 1))
        ign = ser & ev.date.between(s0 + pd.Timedelta(days=truth['shift_positive_days']),
                                    s1 + pd.Timedelta(days=truth['shift_ignore_after_days']))
        ev.loc[pos, 'label'] = 1; ev.loc[pos, 'use'] = True; ev.loc[ign, 'use'] = False
    for pt in truth['points']:
        m = (ev.ticker == pt['ticker']) & (ev.source_id == pt['source_id']) & (ev.date == pd.Timestamp(pt['date']))
        ev.loc[m, 'label'] = 1; ev.loc[m, 'use'] = True
    e = ev[ev.use]
    flag = e.anomaly_score > truth['threshold']
    pos = e.label == 1
    if pos.sum():
        tp = int((flag & pos).sum()); fp = int((flag & ~pos).sum()); fn = int((~flag & pos).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0; rec = tp / (tp + fn)
        point_rec = float(flag[pos & e.date.isin(pd.to_datetime([p['date'] for p in truth['points']]))].mean()) if truth['points'] else None
        base = f1(prec, rec)
        det = dict(precision=round(prec, 3), recall=round(rec, 3), f1=round(base, 3), tp=tp, fp=fp, fn=fn,
                   point_recall=point_rec)
    else:
        rate = float(flag.mean())
        base = max(0.0, 1 - rate / 0.05)
        det = dict(control=True, flagged_share=round(rate, 4))
    reward = base * coverage * (1.0 if no_foresight else 0.0)
    return write_reward(reward, dict(det, coverage=round(coverage, 4), no_foresight=no_foresight,
                                     truncation_checks=leaks, rows_evaluated=int(len(e)), positives=int(pos.sum())))


if __name__ == '__main__':
    main()
