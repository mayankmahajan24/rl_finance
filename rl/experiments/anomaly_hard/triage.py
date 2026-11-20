"""Sort review cards into the patterns the reviewer has already ruled on: python triage.py ITEMS.json

Each card gets `triage`: the move on the alert's strongest day against the source's own history (log change of count
and ticket size from their weekday-matched 28-day running median, in units of the source's own day-to-day noise),
whether the same source moved the same way within a week of the same date one or two years earlier, and a group:

  recurring   the same move happened a year (or two) earlier                      suggested: normal, recurs each year
  ticket      a one-day ticket-size move under SMALL_K x the source's ticket noise   suggested: false alarm
  small       nothing beyond SMALL_K x the source's own noise in count or ticket    suggested: false alarm
  review      alerts longer than LONG_DAYS (sustained moves), and everything else, judged one card at a time

The rules come from the reviewer's feedback (feedback log #11-12): a one-day ticket move is not off for a source whose
ticket size is that volatile, and a move the source makes every year at the same time is normal.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
TASKS = HERE.parents[1] / "tasks" / "proto" / "anomaly_hard"
SMALL_K = 6.0      # the bar planted one-day problems clear (perturb.POINT_K)
RECUR_DAYS = 7     # how far either side of the same date a year earlier counts
RECUR_SHARE = 0.5  # a move counts as the same if it is at least half as big, the same way
LONG_DAYS = 7      # alerts longer than this are sustained moves: always reviewed one by one


def own_moves(g: pd.DataFrame) -> pd.DataFrame:
    """Per day: log count and log ticket against their weekday-matched trailing 28-day median, and the series'
    own noise (robust sd of that, over the whole series)."""
    g = g.set_index('date').sort_index()
    out = pd.DataFrame(index=g.index)
    for k, v in (('ct', np.log(g.ct)), ('tkt', np.log(g.amt / g.ct))):
        base = v.groupby(v.index.dayofweek).transform(lambda x: x.shift(1).rolling(4, min_periods=2).median())
        dev = v - base
        dev = dev - dev.rolling(28, min_periods=7).median().shift(1).fillna(0)
        out[k] = dev
        out[k + '_sd'] = 1.4826 * (dev - dev.median()).abs().median()
    return out


def classify(m: pd.DataFrame, a: pd.Timestamp, b: pd.Timestamp, why: str) -> dict:
    w = m[(m.index >= a) & (m.index <= b)]
    if w.empty:
        return dict(group='review')
    zc, zt = (w.ct / w.ct_sd).abs(), (w.tkt / w.tkt_sd).abs()
    day = (zc.fillna(0) + zt.fillna(0)).idxmax()
    ch = 'ct' if zc.get(day, 0) >= zt.get(day, 0) else 'tkt'
    dev, sd = float(m.at[day, ch]), float(m.at[day, ch + '_sd'])
    recur = []
    for yrs in (1, 2):
        lo, hi = day - pd.DateOffset(years=yrs) - pd.Timedelta(days=RECUR_DAYS), \
            day - pd.DateOffset(years=yrs) + pd.Timedelta(days=RECUR_DAYS)
        past = m[(m.index >= lo) & (m.index <= hi)][ch].dropna()
        if len(past) and (np.sign(dev) * past).max() >= RECUR_SHARE * abs(dev) and abs(dev) > 3 * sd:
            hit = (np.sign(dev) * past).idxmax()
            recur.append(dict(years=yrs, date=str(hit.date()), move=round(float(past[hit]), 3)))
    size = dict(ct=round(float(zc.max()), 1), tkt=round(float(zt.max()), 1))
    one_day_ticket = 'One-day ticket size flag' in why
    if (b - a).days + 1 > LONG_DAYS:
        group = 'review'          # a sustained move is a level question, not a daily-noise one: judge it on its card
    elif recur:
        group = 'recurring'
    elif one_day_ticket and size['tkt'] < SMALL_K:
        group = 'ticket'
    elif max(size.values()) < SMALL_K:
        group = 'small'
    else:
        group = 'review'
    return dict(group=group, day=str(day.date()), channel='count' if ch == 'ct' else 'ticket size',
                move_pct=round(float(np.expm1(dev)) * 100), noise_units=size, recurs=recur)


def main():
    path = pathlib.Path(sys.argv[1])
    items = json.loads(path.read_text())
    panels, moves = {}, {}
    for it in items:
        p = it['parts'][0]
        mp = json.loads((TASKS / p['task'] / 'mapping.json').read_text())
        shift = pd.Timedelta(days=mp['shift_days'])
        if p['task'] not in panels:
            panels[p['task']] = pd.read_csv(TASKS / p['task'] / 'tests' / 'eval_panel.csv.gz', parse_dates=['date'])
        key = (p['task'], p['task_ticker'], p['task_source'])
        if key not in moves:
            d = panels[p['task']]
            m = own_moves(d[(d.ticker == p['task_ticker']) & (d.source_id == p['task_source'])])
            m.index = m.index - shift                      # original dates, as on the cards
            moves[key] = m
        it['triage'] = classify(moves[key], pd.Timestamp(it['start']), pd.Timestamp(it['end']), p.get('why', ''))
    path.write_text(json.dumps(items, separators=(',', ':')))
    print(pd.Series([it['triage']['group'] for it in items]).value_counts().to_dict())


if __name__ == '__main__':
    main()
