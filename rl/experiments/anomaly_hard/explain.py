"""Add a short reason to every alert in a review items file: python explain.py ITEMS.json LABEL=SOLUTION_DIR ...

The reason comes from the scorer's own internals on the day its run of flags began (which can be before the
alert, when the flags carry on from a planted problem), re-run on that task's hidden
panel: which piece of evidence crossed the scorer's line and by how much, plus the plain size of the move (the
source against the median of the other sources, compared with its previous 28 days) and how long the flag lasted.
Only the two Opus scorers graded so far are understood: LABEL `hinted-run` (debug components) and `neutral-run`
(per-channel trace); any other scorer, given as LABEL=-, gets the plain size of the move. Writes the reasons into
each item's parts, in place.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import warnings

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
TASKS = HERE.parents[1] / "tasks" / "proto" / "anomaly_hard"
CH = {'ct': 'count', 'amt': 'dollars', 'tkt': 'ticket size'}
GENERIC: set[str] = set()   # labels given as LABEL=- : described by the plain size of the move only


def load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path / 'score.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def held(n: int) -> str:
    return '' if n <= 1 else f" Stayed flagged {n} days."


def why_hinted(mod, g, src, t, n, cache):
    key = id(g)
    if key not in cache:
        cache[key] = mod.score_ticker(g, dict(mod.P, debug=True))
    r = cache[key]
    row = r[(r.source_id == src) & (r.date == t)].iloc[0]
    pl = plain(g, src, t)
    comp = {k: float(row[k]) for k in ('e_vol', 'e_tk', 'e_ca', 'lowrun', 'catch', 'drift')}
    k = max(comp, key=comp.get)
    v = comp[k]
    if k == 'drift':
        lk = np.log(g.pivot(index='date', columns='source_id', values='amt')) - \
            np.log(g.pivot(index='date', columns='source_id', values='ct'))
        gap = lk[src] - lk[[c for c in lk.columns if c != src]].median(axis=1)
        moved = gap[t - pd.Timedelta(days=13):t].median() - gap[t - pd.Timedelta(days=134):t - pd.Timedelta(days=14)].median()
        txt = (f"Slow ticket-size drift: days with this source's ticket size away from the others' added up until "
               f"they crossed the alarm level. Its ticket size over the last 2 weeks was {pct(moved)} where it sat "
               f"against the others in the previous 4 months.")
    elif k == 'e_vol':
        txt = (f"One-day volume jump: count and dollars together {v * 5:.1f} noise units out (line at 5). "
               f"Count {pct(pl['ct'])}, dollars {pct(pl['amt'])} the usual relation to the other sources.")
    elif k == 'e_tk':
        txt = (f"One-day ticket-size jump: {v * 5:.1f} noise units out (line at 5). Ticket size {pct(pl['tkt'])} "
               f"the usual relation to the other sources.")
    elif k == 'e_ca':
        c = 'ct' if abs(pl['ct']) >= abs(pl['amt']) else 'amt'
        txt = (f"One-day {CH[c]} jump on its own: {v * 6:.1f} noise units out (line at 6). {CH[c].capitalize()} "
               f"{pct(pl[c])} the usual relation to the other sources.")
    elif k == 'lowrun':
        txt = (f"Second low day in a row (each at least 2 noise units low), read as part of the feed missing its "
               f"cutoff. Count {pct(pl['ct'])} the usual relation to the other sources.")
    else:
        txt = (f"High day straight after a low one, read as late settlement catching up. Count {pct(pl['ct'])} "
               f"the usual relation to the other sources.")
    if float(row['disc']) < 1:
        txt += ' Evidence was halved because other sources were also off that day.'
    margin = v * float(row['disc'])
    if k != 'drift' and margin < 1.15:
        txt += ' Only just over the line.'
    return txt + held(n)


def why_neutral(mod, g, src, t, n, cache):
    key = id(g)
    if key not in cache:
        mod.TRACE = []
        gg = g.copy()
        gg['_row'] = np.arange(len(gg))
        mod._score_group(gg)
        tr = pd.DataFrame(mod.TRACE, columns=['date', 's', 'ch', 'e', 'z', 'sig', 'mkt', 'R', 'alarm', 'sticky'])
        mod.TRACE = None
        cache[key] = (tr, sorted(g.source_id.unique(), key=str))
    tr, srcs = cache[key]
    j = srcs.index(src)
    day = tr[(tr.s == j) & (tr.date == t)].set_index('ch')
    if day.empty:
        return 'No trace for this day.'
    c = day.R.idxmax()
    R = float(day.R.max())
    mkt = float(day.mkt.max())
    if c == 'shift':
        txt = ("Date check: over the last 2 weeks this source's count lines up better with the other sources when "
               "moved by a day, as if its dates were off by one.")
    else:
        h = tr[(tr.s == j) & (tr.ch == c) & (tr.date <= t)]
        best = None
        for w, (thr, dmin) in mod.RULES.items():
            if len(h) < w:
                break
            st, me = h.z.iloc[-w:].sum() / np.sqrt(w), h.e.iloc[-w:].mean()
            r = abs(st) / thr if dmin == 0 else min(abs(st) / thr, abs(me) / dmin)
            if best is None or r > best[0]:
                best = (r, w, st, me, thr, dmin)
        r, w, st, me, thr, dmin = best
        if w == 1:
            txt = (f"One-day {CH[c]} jump: {abs(st):.1f} noise units (line at {thr:.1f}); {CH[c]} {pct(me)} "
                   f"its usual relation to the other sources.")
        else:
            txt = (f"{CH[c].capitalize()} ran {pct(me)} its usual relation to the other sources on average over the "
                   f"{w} days to this one: {abs(st):.1f} combined noise units (line at {thr:.1f}), average gap "
                   f"{abs(me):.2f} log (minimum {dmin:.2f}).")
        if mkt > 0.1:
            txt += f' The noise allowance was widened for a company-wide move of {mkt:.2f} log that day.'
        if bool(day.loc[c, 'sticky']):
            txt += ' A large abrupt shift, so its baseline was frozen until it ended.'
    if R < 1.05:   # its alarms start on the first day the evidence crosses, so most start close to the line
        txt += ' Only just over the line.'
    return txt + held(n)


def why_generic(g, src, t):
    """For a scorer whose internals aren't traced: the plain size of the move on its first flagged day."""
    pl = plain(g, src, t)
    return (f"(This scorer's workings aren't traced.) On the first flagged day, against its usual relation to the other "
            f"sources over the previous 4 weeks: count {pct(pl['ct'])}, dollars {pct(pl['amt'])}, ticket size "
            f"{pct(pl['tkt'])}.")


def main():
    warnings.filterwarnings('ignore')
    items_path = pathlib.Path(sys.argv[1])
    sols = dict(a.split('=', 1) for a in sys.argv[2:])
    GENERIC.update(lab for lab, p in sols.items() if p == '-')
    mods = {lab: load(pathlib.Path(p), 'score_' + lab.replace('-', '_')) for lab, p in sols.items() if p != '-'}
    items = json.loads(items_path.read_text())
    panels, groups, caches = {}, {}, {lab: {} for lab in sols}
    for it in items:
        for p in it['parts']:
            if p['by'] not in mods and p['by'] not in GENERIC:
                p['why'] = ''
                continue
            mp = json.loads((TASKS / p['task'] / 'mapping.json').read_text())
            shift = pd.Timedelta(days=mp['shift_days'])
            if p['task'] not in panels:
                panels[p['task']] = pd.read_csv(TASKS / p['task'] / 'tests' / 'eval_panel.csv.gz', parse_dates=['date'])
            gk = (p['task'], p['task_ticker'])
            if gk not in groups:
                d = panels[p['task']]
                groups[gk] = d[d.ticker == p['task_ticker']].reset_index(drop=True)
            onset = p.get('run_start') or p['start']
            g, t = groups[gk], pd.Timestamp(onset) + shift
            if p['by'] in GENERIC:
                txt = why_generic(g, p['task_source'], t)
            else:
                fn = why_hinted if p['by'] == 'hinted-run' else why_neutral
                txt = fn(mods[p['by']], g, p['task_source'], t, 1, caches[p['by']])
            lead = ''
            if p.get('run_start'):
                pl = p.get('run_planted')
                where = '' if not pl else (
                    f", during a planted {pl['kind']} problem ({pl['start']} to {pl['end']})" if pl['when'] == 'during'
                    else f", just after a planted {pl['kind']} problem ({pl['start']} to {pl['end']}) ended")
                lead = (f"These flags continue a run that began on {p['run_start']}{where}."
                        + (" The scorer kept flagging after that problem was over." if pl else '')
                        + ' On the day the run began: ')
            p['why'] = lead + txt + held(p['flagged_days'])
    items_path.write_text(json.dumps(items))
    print(sum(len(i['parts']) for i in items), 'alerts explained')


if __name__ == '__main__':
    main()
