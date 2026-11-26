"""Verifier for the online anomaly-scoring task.

Runs the agent's /app/solution/score.py on a hidden panel (tests/eval_panel.csv.gz) the agent never saw,
truncated at hidden cutoff dates and then whole:
    python score.py --input IN.csv --output OUT.csv
OUT.csv must have columns date, ticker, source_id, anomaly_score (0..1, higher = more anomalous),
one row per input row (duplicate keys are not expected in this task).

A flag is a score above 0.5.
Positives: planted one-day anomalies, and every day of each planted level shift (start to end).
Ignored:   the 7 days after a shift ends, low-volume series, windows around known natural artifacts, and
           the warm-up period.

Reward = (ROW_WEIGHT x row F1 + EVENT_WEIGHT x event F1)
       x coverage (share of input rows scored)
       x no-foresight gate: 0 if any score dated <= a cutoff changes, or goes missing, when later data is removed.
  row F1:   F1 over the labelled rows. Shift days are most of the positives, so this is mainly "kept flagging
            the shifted source until it recovered, and did not flag it once it had".
  event F1: F1 of row precision and event recall. Event recall gives spikes and drops half the weight and
            shifts the other half: a spike or drop counts if its day is flagged; a shift counts in full if
            flagged within SHIFT_FULL_DAYS of its start, and the credit falls linearly to 0 at SHIFT_ZERO_DAYS.
            It sits next to row precision so that flagging everything doesn't buy detection.
Control variants (nothing planted): reward = 1 - (share of evaluated rows flagged) / 5%, floored at 0.

score.py is agent code. Before it runs, the gold and the hidden panel leave the disk and it runs as
`nobody` when the verifier is root. Truncated runs come first, earliest cutoff first, and every run
gets its own folder, so no run can find or remember rows dated after its cutoff.

/app/output/writeup.md is judged against judge.md (writeup.py) as a separate metric, never blended in,
and before score.py runs, so agent code never gets to touch it.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import writeup
from common import APP, TESTS, f1, load_gold

TIMEOUT = int(os.environ.get('SCORE_TIMEOUT_SEC', '1200'))
KEYS = ['date', 'ticker', 'source_id']
ROW_WEIGHT, EVENT_WEIGHT = 0.5, 0.5
SHIFT_FULL_DAYS, SHIFT_ZERO_DAYS = 7, 30   # days from a shift's start to its first flag: full credit / none
RECOVERY_DAYS = 90                          # window after the ignore days where flags count as recovery_fp


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
    code = '\n\n'.join(f'# {f.name}\n{f.read_text(errors="replace")}' for f in sorted((APP / 'solution').glob('*.py')))
    facts = dict(control=truth['control'], **truth['shown_planted'])
    judged = writeup.grade(writeup.read(), facts, {'code': code or '(missing)'})
    reward, details = score(truth, data)
    writeup.report(reward, details, *judged)


def score(truth, data):
    # ---- no-foresight gate: the truncated runs come first, so nothing later is on disk to reuse
    cutoffs = sorted(truth['truncation_cutoffs'])
    truncated = {}
    for c in cutoffs:
        try:
            truncated[c] = run_scorer(data[data.date <= pd.Timestamp(c)])
        except Exception as e:  # noqa: BLE001
            return 0.0, dict(error=f'truncated run failed: {e}')
    try:
        full = run_scorer(data)
    except Exception as e:  # noqa: BLE001
        return 0.0, dict(error=str(e))

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
    ignore_after = pd.Timedelta(days=truth['shift_ignore_after_days'])
    shift_rows, recovery = [], pd.Series(False, index=ev.index)
    for sh in truth['shifts']:
        s0, s1 = pd.Timestamp(sh['start']), pd.Timestamp(sh['end'])
        ser = (ev.ticker == sh['ticker']) & (ev.source_id == sh['source_id'])
        pos = ser & ev.date.between(s0, s1)
        ign = ser & (ev.date > s1) & (ev.date <= s1 + ignore_after)
        ev.loc[pos, 'label'] = 1; ev.loc[pos, 'use'] = True; ev.loc[ign, 'use'] = False
        recovery |= ser & (ev.date > s1 + ignore_after) & (ev.date <= s1 + ignore_after + pd.Timedelta(days=RECOVERY_DAYS))
        shift_rows.append(pos)
    for pt in truth['points']:
        m = (ev.ticker == pt['ticker']) & (ev.source_id == pt['source_id']) & (ev.date == pd.Timestamp(pt['date']))
        ev.loc[m, 'label'] = 1; ev.loc[m, 'use'] = True
    ev['flag'] = ev.anomaly_score > truth['threshold']
    e = ev[ev.use]
    flag = e.flag
    pos = e.label == 1
    if pos.sum():
        tp = int((flag & pos).sum()); fp = int((flag & ~pos).sum()); fn = int((~flag & pos).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0; rec = tp / (tp + fn)
        point_rec = float(flag[pos & e.date.isin(pd.to_datetime([p['date'] for p in truth['points']]))].mean()) if truth['points'] else None
        events = event_table(truth, ev, shift_rows)
        ev_rec = event_recall(events)
        row_f1, event_f1 = f1(prec, rec), f1(prec, ev_rec)
        base = ROW_WEIGHT * row_f1 + EVENT_WEIGHT * event_f1
        rec_fp = int((flag & ~pos & recovery[e.index]).sum())
        shift_pos = pos & pd.concat(shift_rows, axis=1).any(axis=1)[e.index] if shift_rows else pos & False
        delays = [x['delay_days'] for x in events if x['type'] == 'level_shift' and x['caught']]
        det = dict(precision=round(prec, 3), recall=round(rec, 3), f1=round(row_f1, 3), tp=tp, fp=fp, fn=fn,
                   point_recall=point_rec, event_recall=round(ev_rec, 3), event_f1=round(event_f1, 3),
                   shift_day_recall=round(float(flag[shift_pos].mean()), 3) if shift_pos.any() else None,
                   shift_delay_days=delays, recovery_fp=rec_fp, other_fp=fp - rec_fp, events=events)
    else:
        rate = float(flag.mean())
        base = max(0.0, 1 - rate / 0.05)
        det = dict(control=True, flagged_share=round(rate, 4))
    reward = base * coverage * (1.0 if no_foresight else 0.0)
    return reward, dict(det, coverage=round(coverage, 4), no_foresight=no_foresight,
                        truncation_checks=leaks, rows_evaluated=int(len(e)), positives=int(pos.sum()))


def event_table(truth, ev, shift_rows):
    """Each planted spike, drop and shift: was it flagged, and after how many days."""
    out = []
    for pt in truth['points']:
        m = (ev.ticker == pt['ticker']) & (ev.source_id == pt['source_id']) & (ev.date == pd.Timestamp(pt['date']))
        hit = bool(ev.flag[m].any())
        out.append(dict(type='spike' if pt['mult'] > 1 else 'drop', ticker=pt['ticker'], source_id=pt['source_id'],
                        start=pt['date'], caught=hit, delay_days=0 if hit else None, credit=float(hit)))
    for sh, m in zip(truth['shifts'], shift_rows):
        s0 = pd.Timestamp(sh['start'])
        days = ev.date[m & ev.flag]
        delay = int((days.min() - s0).days) if len(days) else None
        credit = 0.0 if delay is None else float(np.clip((SHIFT_ZERO_DAYS - delay) / (SHIFT_ZERO_DAYS - SHIFT_FULL_DAYS), 0, 1))
        out.append(dict(type='level_shift', ticker=sh['ticker'], source_id=sh['source_id'], start=sh['start'],
                        end=sh['end'], mult=sh['mult'], caught=delay is not None, delay_days=delay,
                        flagged_share=round(float(ev.flag[m].mean()), 3) if m.any() else None, credit=round(credit, 3)))
    return out


def event_recall(events):
    """Half the weight on one-day anomalies, half on shifts (whichever kinds are planted)."""
    kinds = [[x['credit'] for x in events if (x['type'] == 'level_shift') == sh] for sh in (False, True)]
    kinds = [k for k in kinds if k]
    return float(np.mean([np.mean(k) for k in kinds])) if kinds else 0.0


if __name__ == '__main__':
    main()
