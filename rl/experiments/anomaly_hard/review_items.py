"""Turn a scorer's unexplained alerts into review items: python review_items.py OUT.json TASK=CACHE_DIR ...

An unexplained alert is a run of flags (gaps of up to 2 days joined) on a scored row that touches no labelled bad
data. Each is mapped back to original coordinates with the task's mapping.json, alerts on the same series that
overlap across tasks are merged (all tasks share the bench companies), and each item carries a chart window from
the task's hidden panel, in original dates: the source's log count and log ticket size against the median of the
company's other sources, its flags, and any planted problem or decoy in the window.

Arguments are TASK=CACHE_DIR or TASK=CACHE_DIR@LABEL (LABEL names the scorer on the page). CACHE_DIR is grade.py's --cache folder for that task and scorer (it holds full.csv). Verdicts on the items go to
reviewed.yaml, which build.py maps into every task.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
TASKS = HERE.parents[1] / "tasks" / "proto" / "anomaly_hard"
GAP, PAD = 2, 60


def alerts_for(task: str, cache: pathlib.Path, label: str = '') -> list[dict]:
    d = TASKS / task
    truth = json.loads((d / 'tests' / 'gold.json').read_text())
    mp = json.loads((d / 'mapping.json').read_text())
    inv_t = {v: k for k, v in mp['tickers'].items()}
    inv_s = {int(v): int(k) for k, v in mp['sources'].items()}
    shift = pd.Timedelta(days=mp['shift_days'])
    data = pd.read_csv(d / 'tests' / 'eval_panel.csv.gz', parse_dates=['date'])
    out = pd.read_csv(cache / 'full.csv', parse_dates=['date'])
    ev = data.merge(out, on=['date', 'ticker', 'source_id'], how='left')
    ev['flag'] = ev.anomaly_score.fillna(0) > truth['threshold']
    use = ev.date >= pd.Timestamp(truth['eval_start'])
    for i in truth['ignore_series']:
        use &= ~((ev.ticker == i['ticker']) & (ev.source_id == i['source_id']))
    for x in truth['exclusions']:
        m = (ev.ticker == x['ticker']) & ev.date.between(pd.Timestamp(x['lo']) - pd.Timedelta(days=14),
                                                        pd.Timestamp(x['hi']) + pd.Timedelta(days=30))
        if x['source_id'] is not None:
            m &= ev.source_id == x['source_id']
        use &= ~m
    lab = pd.Series(False, index=ev.index)
    for e in truth['events']:
        lab |= (ev.ticker == e['ticker']) & (ev.source_id == e['source_id']) & \
            ev.date.between(pd.Timestamp(e['start']), pd.Timestamp(e['end']) + pd.Timedelta(days=7))
    items = []
    f = ev[ev.flag & use]
    for (t, s), g in f.sort_values('date').groupby(['ticker', 'source_id']):
        rid = (g.date.diff().dt.days.fillna(999) > GAP + 1).cumsum()
        for _, r in g.groupby(rid):
            if lab[r.index].any():
                continue
            items.append(dict(task=task, ticker=inv_t[t], source_id=inv_s[int(s)], task_ticker=t,
                              task_source=int(s), start=r.date.min() - shift, end=r.date.max() - shift,
                              flagged_days=len(r), max_score=round(float(r.anomaly_score.max()), 3), by=label))
    for it in items:
        cols = sorted(ev[ev.ticker == it['task_ticker']].source_id.unique())
        it['source_map'] = {int(c): inv_s[int(c)] for c in cols}
        it['chart'] = chart(ev, truth, it, shift)
        it.pop('source_map')
    return items


def chart(ev, truth, it, shift):
    t, s = it['task_ticker'], it['task_source']
    a, b = it['start'] + shift - pd.Timedelta(days=PAD), it['end'] + shift + pd.Timedelta(days=PAD)
    x = ev[(ev.ticker == t) & ev.date.between(a, b)]
    ct = np.log(x.pivot(index='date', columns='source_id', values='ct'))
    aov = np.log(x.pivot(index='date', columns='source_id', values='amt')) - ct
    peers = [c for c in ct.columns if c != s]
    rc = (ct[s] - ct[peers].median(axis=1)) if peers else ct[s] - ct[s].median()
    ra = (aov[s] - aov[peers].median(axis=1)) if peers else aov[s] - aov[s].median()
    rc, ra = rc - rc.median(), ra - ra.median()
    fl = x[x.source_id == s].set_index('date').flag.reindex(rc.index, fill_value=False)
    known = [dict(kind=e['type'], start=str((pd.Timestamp(e['start']) - shift).date()),
                  end=str((pd.Timestamp(e['end']) - shift).date()))
             for e in truth['events'] if e['ticker'] == t and e['source_id'] == s]
    known += [dict(kind='decoy:' + k['kind'], start=str((pd.Timestamp(k['start']) - shift).date()),
                   end=str((pd.Timestamp(k['end']) - shift).date())) for k in truth['decoys'] if k['ticker'] == t]
    lo_d, hi_d = str((a - shift).date()), str((b - shift).date())
    known = [k for k in known if k['end'] >= lo_d and k['start'] <= hi_d]
    r2 = lambda v: [None if pd.isna(z) else round(float(z), 3) for z in v]  # noqa: E731
    raw = {k: {str(inv): r2(np.exp(frame[c].reindex(rc.index)).values) if k == 'ct' else
               r2(x[x.source_id == c].set_index('date').amt.reindex(rc.index).values)
               for c, inv in it['source_map'].items()}
           for k, frame in (('ct', ct), ('amt', None))}
    return dict(dates=[str((dd - shift).date()) for dd in rc.index], count=r2(rc.values), ticket=r2(ra.values),
                flags=[bool(z) for z in fl.values], sources=int(len(ct.columns)), known=known,
                raw=raw, source=str(it['source_id']))


def merge(items: list[dict]) -> list[dict]:
    """One item per original series and overlapping date range, across tasks."""
    out = []
    for it in sorted(items, key=lambda i: (i['ticker'], i['source_id'], i['start'])):
        last = out[-1] if out else None
        if last and (last['ticker'], last['source_id']) == (it['ticker'], it['source_id']) and \
                it['start'] <= last['end'] + pd.Timedelta(days=GAP + 1):
            last['end'] = max(last['end'], it['end'])
            last['tasks'] = sorted(set(last['tasks']) | {it['task']})
            last['by'] = sorted(set(last['by']) | {it['by']})
            last['flagged_days'] += it['flagged_days']
            if len(it['chart']['dates']) > len(last['chart']['dates']):
                last['chart'] = it['chart']
            continue
        out.append(dict(it, tasks=[it['task']], by=[it['by']]))
    for i, it in enumerate(out, 1):
        it['id'] = f"{it['ticker']}-{it['source_id']}-{it['start'].date()}"
        it['start'], it['end'] = str(it['start'].date()), str(it['end'].date())
        for k in ('task', 'task_ticker', 'task_source'):
            it.pop(k)
    return out


def main():
    dest, pairs = pathlib.Path(sys.argv[1]), [a.split('=', 1) for a in sys.argv[2:]]
    items = [x for task, rest in pairs for cache, _, label in [rest.partition('@')]
             for x in alerts_for(task, pathlib.Path(cache), label)]
    merged = merge(items)
    dest.write_text(json.dumps(merged))
    print(len(items), 'unexplained alerts ->', len(merged), 'review items')


if __name__ == '__main__':
    main()
