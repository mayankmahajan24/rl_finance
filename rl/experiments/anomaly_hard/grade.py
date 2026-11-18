"""Grade a scorer on an anomaly_hard prototype task: python grade.py TASK_DIR SOLUTION_DIR [--json OUT]

Runs SOLUTION_DIR/score.py on the task's hidden panel, truncated at the gold's cutoffs (earliest first) and then
whole, each run in its own empty folder, and scores it as the instruction says. A prototype: unlike the Harbor
verifier it does not sandbox the scorer (no `nobody` user, gold not removed from disk), so only grade code you trust
not to look for the gold, such as a submission copied out of its run folder.

Reward = (0.5 x row F1 + 0.5 x event F1) x coverage x no-foresight gate.
  labelled rows (label_rows): every day of a short planted or reviewed problem, except days it lists as unscored
     (too small to see). A problem that persists is a change of level, labelled the way a time series monitor
     sees it: its first CHANGE_DAYS days are bad data (event: onset); the days after that, up to SETTLE_DAYS from its
     start, are not scored while the scorer decides whether the new level is the new normal; after that the shifted
     level is the normal level, so flags there are false; when the source returns, the first CHANGE_DAYS days are
     bad data again (event: return) and the next days up to SETTLE_DAYS after it are not scored.
  row F1:   row precision (flagged rows that are labelled) vs day recall: the share of each event's days flagged,
            averaged within each kind and then over kinds, so a long problem weighs the same as a one-day one
  event F1: alert precision (runs of flagged days on a series, gaps of up to ALERT_GAP days joined, that touch a
            labelled day) vs event recall (mean over kinds of the kind's mean credit; a short event counts if any
            day is flagged, an onset or return in full if first flagged within 14 days, nothing at 45)
Scorer outputs are cached in --cache, so a task can be re-graded without rerunning the scorer.
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
CHANGE_DAYS, SETTLE_DAYS = 14, 45
ALERT_GAP = 2


def f1(p, r):
    return 2 * p * r / (p + r) if p + r else 0.0


def run(script: pathlib.Path, panel: pd.DataFrame, cache: pathlib.Path | None = None) -> pd.DataFrame:
    if cache and cache.exists():
        return pd.read_csv(cache, parse_dates=['date'])
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
    s = s[KEYS + ['anomaly_score']].drop_duplicates(KEYS)
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        s.to_csv(cache, index=False, date_format='%Y-%m-%d')
    return s


def score(truth: dict, data: pd.DataFrame, script: pathlib.Path, cache: pathlib.Path | None = None):
    cuts = sorted(truth['truncation_cutoffs'])
    c_ = (lambda name: cache / f'{name}.csv') if cache else (lambda name: None)
    trunc = {c: run(script, data[data.date <= pd.Timestamp(c)], c_(f'cut-{c}')) for c in cuts}
    full = run(script, data, c_('full'))
    leaks = []
    for c in cuts:
        cmp = (data[data.date <= pd.Timestamp(c)][KEYS].merge(trunc[c], on=KEYS, how='left')
               .merge(full, on=KEYS, how='left', suffixes=('_t', '_f')))
        leaks.append(int((~((cmp.anomaly_score_t - cmp.anomaly_score_f).abs() <= 1e-6)).sum()))
    gate = all(x == 0 for x in leaks)

    ev = data[KEYS].merge(full, on=KEYS, how='left')
    coverage = float(ev.anomaly_score.notna().mean())
    ev['flag'] = ev.anomaly_score.fillna(0) > truth['threshold']
    scored = label_rows(truth, ev)
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
    for e, m in scored:
        days = ev.date[m & ev.flag]
        delay = int((days.min() - pd.Timestamp(e['start'])).days) if len(days) else None
        if e['regime']:
            credit = 0.0 if delay is None else float(np.clip((ZERO_DAYS - delay) / (ZERO_DAYS - FULL_DAYS), 0, 1))
        else:
            credit = float(delay is not None)
        table.append(dict(type=e['type'], part=e.get('part', ''), ticker=e['ticker'], source_id=e['source_id'],
                          start=e['start'], end=e['end'], days=int(m.sum()), flagged_days=int((m & ev.flag).sum()),
                          delay_days=delay, credit=round(credit, 3)))
    t = pd.DataFrame(table)
    by_kind = t.groupby('type').agg(events=('credit', 'size'), credit=('credit', 'mean'),
                                    days=('days', 'sum'), flagged_days=('flagged_days', 'sum'))
    ev_rec = float(by_kind.credit.mean())
    decoy_fp = 0
    for x in truth['decoys']:
        decoy_fp += int((e_.flag & (e_.ticker == x['ticker']) & e_.date.between(x['start'], x['end'])).sum())
    t['day_recall'] = t.flagged_days / t.days.clip(lower=1)
    day_rec = float(t.groupby('type').day_recall.mean().mean())
    n_alerts, true_alerts = alerts(e_)
    alert_prec = true_alerts / n_alerts if n_alerts else 0.0
    row_f1, event_f1 = f1(prec, day_rec), f1(alert_prec, ev_rec)
    reward = (0.5 * row_f1 + 0.5 * event_f1) * coverage * gate
    return reward, dict(out, precision=round(prec, 3), recall=round(rec, 3), day_recall=round(day_rec, 3),
                        row_f1=round(row_f1, 3), alerts=n_alerts, true_alerts=true_alerts,
                        alert_precision=round(alert_prec, 3), event_recall=round(ev_rec, 3),
                        event_f1=round(event_f1, 3), tp=tp, fp=fp, fn=fn, decoy_fp=decoy_fp,
                        by_kind=by_kind.round(3).reset_index().to_dict('records'), events=table)


def label_rows(truth: dict, ev: pd.DataFrame) -> list[tuple[dict, pd.Series]]:
    """Set ev['label'] (bad data) and ev['use'] (scored), and return the scored events with their labelled rows:
    short problems as they are, each persisting problem as an onset and a return (see the module docstring)."""
    D = lambda n: pd.Timedelta(days=n)  # noqa: E731
    ev['label'] = False
    ev['use'] = ev.date >= pd.Timestamp(truth['eval_start'])
    for i in truth['ignore_series']:
        ev.loc[(ev.ticker == i['ticker']) & (ev.source_id == i['source_id']), 'use'] = False
    for x in truth['exclusions']:
        m = (ev.ticker == x['ticker']) & ev.date.between(pd.Timestamp(x['lo']) - D(14), pd.Timestamp(x['hi']) + D(30))
        if x['source_id'] is not None:
            m &= ev.source_id == x['source_id']
        ev['use'] &= ~m
    parts, quiet = [], pd.Series(False, index=ev.index)
    for e in truth['events']:
        a, b = pd.Timestamp(e['start']), pd.Timestamp(e['end'])
        ser = (ev.ticker == e['ticker']) & (ev.source_id == e['source_id'])
        if not e['regime']:
            m = ser & ev.date.between(a, b) & ~ev.date.isin(pd.to_datetime(e.get('unscored_days', [])))
            quiet |= ser & ev.date.isin(pd.to_datetime(e.get('unscored_days', [])))
            parts.append((e, m))
            continue
        settle = max(a + D(SETTLE_DAYS - 1), pd.Timestamp(e.get('settle', a)))
        on_end, back = min(a + D(CHANGE_DAYS - 1), b), b + D(1)
        quiet |= ser & (ev.date > on_end) & (ev.date <= min(settle, b))
        quiet |= ser & (ev.date > back + D(CHANGE_DAYS - 1)) & (ev.date <= back + D(SETTLE_DAYS - 1))
        parts.append((dict(e, part='onset', end=str(on_end.date())), ser & ev.date.between(a, on_end)))
        parts.append((dict(e, part='return', start=str(back.date()), end=str((back + D(CHANGE_DAYS - 1)).date())),
                      ser & ev.date.between(back, back + D(CHANGE_DAYS - 1))))
    ev['use'] &= ~quiet
    scored = []
    for e, m in parts:
        m = m & (ev.date >= pd.Timestamp(truth['eval_start']))
        ev.loc[m, 'label'] = True; ev.loc[m, 'use'] = True
        scored.append((e, m))
    return scored


def alerts(e_: pd.DataFrame) -> tuple[int, int]:
    """Runs of flagged scored days on a series (gaps of up to ALERT_GAP days joined), and how many touch a
    labelled day."""
    n = hit = 0
    for _, g in e_[e_.flag].sort_values('date').groupby(['ticker', 'source_id']):
        run_id = (g.date.diff().dt.days.fillna(999) > ALERT_GAP + 1).cumsum()
        runs = g.groupby(run_id).label.any()
        n += len(runs); hit += int(runs.sum())
    return n, hit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('task'); ap.add_argument('solution'); ap.add_argument('--json')
    ap.add_argument('--cache')
    a = ap.parse_args()
    task, sol = pathlib.Path(a.task), pathlib.Path(a.solution).resolve()
    truth = json.loads((task / 'tests' / 'gold.json').read_text())
    data = pd.read_csv(task / 'tests' / 'eval_panel.csv.gz', parse_dates=['date'])
    try:
        reward, d = score(truth, data, sol / 'score.py', pathlib.Path(a.cache) if a.cache else None)
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
