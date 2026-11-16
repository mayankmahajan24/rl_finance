"""Verifier for the data-validation audit task.

Reads /app/output/issues.json, a list of objects:
  {"type": <one of ISSUE_TYPES>, "ticker": str, "source_id": int|null, "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"|null, ...}
(source_id null = affects every source of the ticker; end null = continues to the end of the panel),
/app/output/usability.json, a verdict per series:
  {"ticker": str, "source_id": int, "usable": bool, "reason": str}
and /app/output/cleaned.csv, the repaired panel (date, ticker, source_id, ct, amt; empty ct and amt = nulled).

Core score = 0.4 x issues F1 + 0.4 x repair score + 0.2 x usability F1 (0 if issues.json can't be read).
Reward = core x (0.5 + 0.5 x write-up score) once the judge has graded writeup.md and its chart; the core
score alone when the judge can't run.

Issues F1 is a soft F1 against the hidden ground truth. A report on the same series as a required item
(same ticker, or the other ticker of a swap; same source, where a report with source_id null only covers
a problem on every source) and of a compatible type is matched to the one whose dates it fits best, and
earns that fit as credit: the generalized intersection over union of the two date ranges, from 1 (exact)
through 0 (barely touching) to near -1 (far apart). A range with no end runs to the end of the panel.
  * recall = total credit / number of required items,
  * precision = (total credit + 1) / (matched + false reports + 1): smoothed by one, so a task with
    nothing required falls with each false report (1, 0.67, 0.5, ...) instead of dropping to 0.
A report on no required item's series is false, unless it falls in an *optional* item (real but debatable
source-level behaviour) or on a low-volume series (median ct < 10), which are ignored. A report on an
already matched item is false too, except one per source of a problem on every source.

Repair score: every required problem the right repair can be checked for is scored over its dates on its
series against the clean panel (tests/clean.csv.gz: the panel before any problem was planted).
  * a gap of more than UNRECOVERABLE_DAYS days (a planted one, or a real one on every source) must be nulled:
    credit is the share of its days with a row whose ct is left empty (a missing row is not a null: copying
    the input must not earn it);
  * any other planted problem must be repaired, scored on the days it changed (tests/given.csv.gz, the panel
    as given, against clean.csv.gz) and the days that had to be filled in: each day earns 1 within TOL of the
    true ct and amt, falling to 0 at 3 x TOL (TOL is 5%, or 20% on a day that had to be filled in), and 0 if
    left empty.
The mean over problems is scaled by (1 - 10 x the share of the other days that were changed by more than 1%,
nulled, or invented), floored at 0: every day outside a problem, including real events, should be left as it
came. Days in an optional item's series from its window on are not checked. Other real breaks have no true
values, so they are graded on the flag only. Duplicate rows left in cleaned.csv are summed, as a user would.

Usability F1 is the F1 on the "not usable" class over every scored series (the gold's `usability`, from
the rule in generate.py; low-volume series are not scored). A series with no verdict counts as wrong
whichever way its gold falls, and precision is smoothed by one as above.

The write-up score is the share of judge.md items passed, judged with the chart in output/figures/,
scaled down by 3 / sentences past 3 sentences and by 120 / words past 120 words.
"""
import json
import re

import numpy as np
import pandas as pd

import writeup
from common import APP, TESTS, f1, load_gold

ISSUE_TYPES = ['duplicate_rows', 'swapped_columns', 'unit_scale', 'date_shift', 'series_swap',
               'double_count', 'outage', 'level_shift', 'ticker_remap', 'dst_shift', 'amount_shift']
# truth type -> reported types that count as a correct identification
COMPATIBLE = {
    'double_count': {'double_count', 'level_shift'},
    'ticker_remap': {'ticker_remap', 'level_shift'},
    'outage': {'outage'},
    'level_shift': {'level_shift', 'double_count'},
    'dst_shift': {'dst_shift', 'date_shift'},
}
WEIGHTS = dict(issues=0.4, repair=0.4, usability=0.2)
MAX_SENTENCES, MAX_WORDS = 3, 120
UNRECOVERABLE_DAYS = 7   # as in generate.py
TOL, IMPUTE_TOL, KEEP_TOL, DAMAGE = 0.05, 0.20, 0.01, 10


def _d(x):
    try:
        return None if x in (None, '', 'null') else pd.Timestamp(x)
    except (TypeError, ValueError):
        return None


def span(item, panel_end):
    """(start, end) of a report or gold item; no end means the end of the panel."""
    s = _d(item.get('start'))
    if s is None:
        return None
    e = _d(item.get('end')) or panel_end
    return (s, max(s, e))


def giou(a, b):
    """Generalized intersection over union of two inclusive date ranges, in [-1, 1]."""
    days = lambda x, y: (y - x).days + 1  # noqa: E731
    inter = max(0, days(max(a[0], b[0]), min(a[1], b[1])))
    union = days(*a) + days(*b) - inter
    hull = days(min(a[0], b[0]), max(a[1], b[1]))
    return inter / union - (hull - union) / hull


def same_series(rep, tr):
    if rep.get('type') not in COMPATIBLE.get(tr['type'], {tr['type']}):
        return False
    if rep.get('ticker') not in {tr['ticker'], tr.get('other_ticker')} - {None}:
        return False
    return tr['source_id'] is None or rep.get('source_id') == tr['source_id']


def optional_match(rep, opt):
    if rep.get('ticker') != opt['ticker']:
        return False
    if opt['source_id'] is not None and rep.get('source_id') not in (None, opt['source_id']):
        return False
    # a break between two regimes: the report may start at it (the later regime is wrong) or end at it
    lo, hi = _d(opt['lo']), _d(opt['hi'])
    return any(d is not None and lo <= d <= hi for d in (_d(rep.get('start')), _d(rep.get('end'))))


def score(truth):
    reward, details = score_issues(truth)
    if 'error' in details:
        return reward, details
    usable, verdicts = score_usability(truth)
    repaired, repair = score_repair(truth)
    core = WEIGHTS['issues'] * reward + WEIGHTS['repair'] * repaired + WEIGHTS['usability'] * usable
    return core, dict(details, issues_f1=round(reward, 4), repair_score=round(repaired, 4),
                      usability_f1=round(usable, 4), repair=repair, usability=verdicts)


def read_panel(path):
    """(date, ticker, source_id) -> ct, amt; duplicate keys summed, empty values kept as NaN."""
    df = pd.read_csv(path)
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['source_id'] = pd.to_numeric(df['source_id'], errors='coerce')
    df = df.dropna(subset=['date', 'ticker', 'source_id'])
    df['source_id'] = df['source_id'].astype(int)
    for c in ('ct', 'amt'):
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df.groupby(['date', 'ticker', 'source_id'])[['ct', 'amt']].sum(min_count=1)


def day_credit(truth, said, tol):
    """Per-day credit for a repaired value: 1 within tol of the truth, 0 at 3 x tol; a day with no true row
    should have no value either."""
    absent = truth.ct.isna()
    empty = said.ct.isna() | (said.ct <= 0)
    err = np.maximum(abs(said.ct - truth.ct) / truth.ct.clip(lower=1), abs(said.amt - truth.amt) / truth.amt.clip(lower=1))
    credit = ((3 * tol - err) / (2 * tol)).clip(0, 1).fillna(0)
    return credit.where(~absent, empty.astype(float))


def repair_targets(truth, series):
    """(item, mode, [(ticker, source)], start, end) for each required item whose repair can be checked."""
    end = _d(truth['panel_end'])
    out = []
    for i in truth['required']:
        a, b = span(i, end)
        on = [(t, s) for t, s in series if t in {i['ticker'], i.get('other_ticker')} and i['source_id'] in (None, s)]
        long_gap = i['type'] == 'outage' and (b - a).days + 1 > UNRECOVERABLE_DAYS
        if long_gap:
            out.append((i, 'null', on, a, b))
        elif i.get('origin') == 'planted':
            out.append((i, 'fix', on, a, b))
    return out


def score_repair(truth):
    path = APP / 'output' / 'cleaned.csv'
    try:
        said = read_panel(path)
    except Exception as e:  # noqa: BLE001
        return 0.0, dict(error=f'could not read output/cleaned.csv: {e}')
    clean, given = read_panel(TESTS / "clean.csv.gz"), read_panel(TESTS / "given.csv.gz")
    end = _d(truth['panel_end'])
    ignore = {(i['ticker'], i['source_id']) for i in truth['ignore_series']}
    series = sorted({k[1:] for k in clean.index} - ignore)
    first = clean.reset_index().groupby(['ticker', 'source_id']).date.min()
    grid = pd.MultiIndex.from_tuples([(d, t, s) for t, s in series for d in pd.date_range(first[(t, s)], end)],
                                     names=['date', 'ticker', 'source_id'])
    T, S, G = clean.reindex(grid), said.reindex(grid), given.reindex(grid)
    nulled = pd.Series(grid.isin(said.index), index=grid) & S.ct.isna()
    changed_by_problem = (T.ct.isna() != G.ct.isna()) | (abs(T.ct - G.ct) > 0.5) | (abs(T.amt - G.amt) > 0.01)
    covered = pd.Series(False, index=grid)
    dates, keys = grid.get_level_values('date'), list(zip(grid.get_level_values('ticker'), grid.get_level_values('source_id')))
    def on(pairs, a, b):
        return pd.Series([k in pairs for k in keys], index=grid) & (dates >= a) & (dates <= b)
    items = []
    for i, mode, pairs, a, b in repair_targets(truth, series):
        m = on(set(pairs), a, b)
        covered |= m
        if not m.any():
            continue
        if mode == 'null':
            c = nulled[m].astype(float)
        else:
            fill = pd.Series(dates.isin(pd.to_datetime(i.get('impute_days', []))), index=grid)
            m = m & (changed_by_problem | fill)
            if not m.any():
                continue
            tol = pd.Series(np.where(fill[m], IMPUTE_TOL, TOL), index=grid[m])
            c = day_credit(T[m], S[m], tol)
        items.append(dict(type=i['type'], ticker=i['ticker'], source_id=i['source_id'], start=i['start'], mode=mode,
                          credit=round(float(c.mean()), 3)))
    for i in truth['required']:              # the rest of the required items: dates not checked either way
        a, b = span(i, end)
        covered |= on({(t, s) for t, s in series if t in {i['ticker'], i.get('other_ticker')}
                       and i['source_id'] in (None, s)}, a, b)
    for o in truth['optional']:
        covered |= on({(t, s) for t, s in series if t == o['ticker'] and o['source_id'] in (None, s)}, _d(o['lo']), end)
    rest = ~covered
    t, s = T[rest], S[rest]
    changed = (t.ct.notna() & (s.ct.isna() | (abs(s.ct - t.ct) > KEEP_TOL * t.ct + 1) | (abs(s.amt - t.amt) > KEEP_TOL * t.amt + 1))) \
        | (t.ct.isna() & (s.ct > 0))
    share = float(changed.mean()) if len(changed) else 0.0
    keep = max(0.0, 1 - DAMAGE * share)
    mean = float(np.mean([x['credit'] for x in items])) if items else 1.0
    return mean * keep, dict(items=items, damaged_days=int(changed.sum()), checked_days=int(len(changed)),
                             keep=round(keep, 3))


def score_usability(truth):
    try:
        said = json.loads((APP / 'output' / 'usability.json').read_text())
        said = said.get('series', []) if isinstance(said, dict) else said
        assert isinstance(said, list)
    except Exception:  # noqa: BLE001
        said = []
    calls = {}
    for v in said:
        try:
            if isinstance(v, dict) and isinstance(v.get('usable'), bool):
                calls[(v.get('ticker'), int(v.get('source_id')))] = v['usable']
        except (TypeError, ValueError):
            pass
    tp = fp = fn = 0
    wrong = []
    for u in truth['usability']:
        call = calls.get((u['ticker'], u['source_id']))
        if call is not u['usable']:
            wrong.append(dict(ticker=u['ticker'], source_id=u['source_id'], usable=u['usable'], said=call))
        if not u['usable']:
            tp += call is False; fn += call is not False
        else:
            fp += call is not True
    precision = (tp + 1) / (tp + fp + 1)
    recall = tp / (tp + fn) if tp + fn else 1.0
    return f1(precision, recall), dict(n_series=len(truth['usability']), not_usable=tp + fn, tp=tp, fp=fp, fn=fn,
                                       wrong=wrong)


def score_issues(truth):
    try:
        reported = json.loads((APP / 'output' / 'issues.json').read_text())
        if isinstance(reported, dict):
            reported = reported.get('issues', [])
        assert isinstance(reported, list)
    except Exception as e:  # noqa: BLE001
        return 0.0, dict(error=f'could not read output/issues.json: {e}')

    end = _d(truth['panel_end'])
    ignore = {(i['ticker'], i['source_id']) for i in truth['ignore_series']}
    req = truth['required']
    spans = [span(tr, end) for tr in req]
    credit = [None] * len(req)
    n_fp = n_ignored = 0
    per_report = []
    for rep in reported:
        if not isinstance(rep, dict):
            n_fp += 1; continue
        try:
            rep['source_id'] = None if rep.get('source_id') in (None, '', 'null') else int(rep['source_id'])
        except (TypeError, ValueError):
            rep['source_id'] = None
        sp = span(rep, end)
        fits = [] if sp is None else [(giou(sp, spans[j]), j) for j, tr in enumerate(req) if same_series(rep, tr)]
        free = [(g, j) for g, j in fits if credit[j] is None]
        optional = any(optional_match(rep, o) for o in truth['optional'])
        g, j = max(free) if free else (None, None)
        if j is not None and not (g <= 0 and optional):
            credit[j] = g; status = f'matched {req[j]["type"]} (credit {g:.2f})'
        elif any(g > 0 and req[j]['source_id'] is None and rep['source_id'] is not None for g, j in fits):
            n_ignored += 1; status = 'another source of a matched problem on every source'
        elif optional or (rep.get('ticker'), rep['source_id']) in ignore:
            n_ignored += 1; status = 'ignored (optional or low-volume)'
        else:
            n_fp += 1; status = 'false'
        per_report.append(dict(rep=rep, status=status))

    matched = [c for c in credit if c is not None]
    total = sum(matched)
    precision = max(0.0, total + 1) / (len(matched) + n_fp + 1)
    recall = max(0.0, total) / len(req) if req else 1.0
    missed = [dict(type=r['type'], ticker=r['ticker'], source_id=r['source_id'], start=r['start'], origin=r.get('origin'))
              for r, c in zip(req, credit) if c is None]
    return f1(precision, recall), dict(precision=round(precision, 3), recall=round(recall, 3),
                                       n_reported=len(reported), matched=len(matched), credit=round(total, 3),
                                       fp=n_fp, ignored=n_ignored, missed=missed, reports=per_report)


def prose(text: str) -> str:
    """The note without its image lines."""
    return ' '.join(l for l in text.splitlines() if not l.strip().startswith('![')).strip()


def sentences(text: str) -> int:
    return len(re.findall(r'[.!?](?=\s+[A-Z(]|\s*$)', prose(text)))


def words(text: str) -> int:
    return len(prose(text).split())


def main():
    truth = load_gold()
    core, details = score(truth)
    issues, usability = APP / 'output' / 'issues.json', APP / 'output' / 'usability.json'
    facts = {}   # the rubric grades the note against the author's own findings, not the answer
    material = {'issues_json': issues.read_text(errors='replace') if issues.is_file() else '(missing)',
                'usability_json': usability.read_text(errors='replace') if usability.is_file() else '(missing)'}
    text = writeup.read()
    metrics, judged = writeup.grade(text, facts, material, figures=writeup.figures(APP / 'output' / 'figures'))
    reward = core
    if 'writeup_score' in metrics:
        n, w = sentences(text), words(text)
        metrics['writeup_score'] = round(metrics['writeup_score'] * min(1, MAX_SENTENCES / max(n, 1), MAX_WORDS / max(w, 1)), 4)
        details = dict(details, core=round(core, 4), writeup_sentences=n, writeup_words=w)
        reward = core * (0.5 + 0.5 * metrics['writeup_score'])
    else:
        details = dict(details, core=round(core, 4), reward_basis='core only: the write-up was not judged')
    writeup.report(reward, details, metrics, judged)


if __name__ == '__main__':
    main()
