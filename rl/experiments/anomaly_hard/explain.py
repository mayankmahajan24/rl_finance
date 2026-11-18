"""Add a short reason to every alert in a review items file: python explain.py ITEMS.json

For each alert, the plain size of the move on the day its run of flags began: the source's count, dollars and
ticket size against the median of the other sources, compared with its previous 28 days, and how long the flag
lasted. Writes the reasons into each item's parts, in place.
"""
from __future__ import annotations

import json
import pathlib
import sys
import warnings

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
TASKS = HERE.parents[1] / "tasks" / "proto" / "anomaly_hard"
CH = {'ct': 'count', 'amt': 'dollars', 'tkt': 'ticket size'}


def pct(x: float) -> str:
    return f"{abs(np.expm1(x)) * 100:.0f}% {'above' if x > 0 else 'below'}"


def plain(g: pd.DataFrame, src: int, t: pd.Timestamp) -> dict:
    """Log gap of the source vs the median of the others on day t, minus its median over the previous 28 days."""
    out = {}
    for k in ('ct', 'amt', 'tkt'):
        v = np.log(g.pivot(index='date', columns='source_id', values='amt' if k == 'amt' else 'ct'))
        if k == 'tkt':
            v = np.log(g.pivot(index='date', columns='source_id', values='amt')) - v
        oth = [c for c in v.columns if c != src]
        gap = v[src] - v[oth].median(axis=1)
        base = gap[t - pd.Timedelta(days=28):t - pd.Timedelta(days=1)].median()
        out[k] = float(gap.get(t, np.nan) - base)
    return out


def why_generic(g, src, t):
    """For a scorer whose internals aren't traced: the plain size of the move on its first flagged day."""
    pl = plain(g, src, t)
    return (f"On the first flagged day, against its usual relation to the other "
            f"sources over the previous 4 weeks: count {pct(pl['ct'])}, dollars {pct(pl['amt'])}, ticket size "
            f"{pct(pl['tkt'])}.")


def held(n: int) -> str:
    return '' if n <= 1 else f" Stayed flagged {n} days."


def main():
    warnings.filterwarnings('ignore')
    items_path = pathlib.Path(sys.argv[1])
    items = json.loads(items_path.read_text())
    panels, groups = {}, {}
    for it in items:
        for p in it['parts']:
            mp = json.loads((TASKS / p['task'] / 'mapping.json').read_text())
            shift = pd.Timedelta(days=mp['shift_days'])
            if p['task'] not in panels:
                panels[p['task']] = pd.read_csv(TASKS / p['task'] / 'tests' / 'eval_panel.csv.gz', parse_dates=['date'])
            gk = (p['task'], p['task_ticker'])
            if gk not in groups:
                d = panels[p['task']]
                groups[gk] = d[d.ticker == p['task_ticker']].reset_index(drop=True)
            onset = p.get('run_start') or p['start']
            txt = why_generic(groups[gk], p['task_source'], pd.Timestamp(onset) + shift)
            lead = ''
            if p.get('run_start'):
                lead = f"These flags continue a run that began on {p['run_start']}. On the day the run began: "
            p['why'] = lead + txt + held(p['flagged_days'])
    items_path.write_text(json.dumps(items))
    print(sum(len(i['parts']) for i in items), 'alerts explained')


if __name__ == '__main__':
    main()
