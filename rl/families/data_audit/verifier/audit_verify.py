"""Verifier for the data-validation audit task.

Reads /app/output/issues.json, a list of objects:
  {"type": <one of ISSUE_TYPES>, "ticker": str, "source_id": int|null, "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"|null, ...}
(source_id null = affects every source of the ticker).

Reward = F1 of precision and recall against the hidden ground truth:
  * recall over required items (planted issues + clear natural breaks),
  * precision over reported items, ignoring reports that match an *optional* item (real but debatable
    source-level behaviour) or that sit on a low-volume series (median ct < 10).
A reported item can match at most one required item; extra reports of an already-matched issue
(e.g. one per source of a ticker-wide break) are neither credited nor penalised.
"""
import json

import pandas as pd

from common import APP, f1, load_gold, write_reward

ISSUE_TYPES = ['duplicate_rows', 'swapped_columns', 'unit_scale', 'date_shift', 'series_swap',
               'double_count', 'outage', 'level_shift', 'ticker_remap']
# truth type -> reported types that count as a correct identification
COMPATIBLE = {
    'double_count': {'double_count', 'level_shift'},
    'ticker_remap': {'ticker_remap', 'level_shift'},
    'outage': {'outage'},
    'level_shift': {'level_shift', 'double_count'},
}


def _d(x):
    return None if x in (None, '', 'null') else pd.Timestamp(x)


def matches(rep, tr, tol):
    if rep.get('type') not in COMPATIBLE.get(tr['type'], {tr['type']}):
        return False
    tickers = {tr['ticker'], tr.get('other_ticker')} - {None}
    if rep.get('ticker') not in tickers:
        return False
    if tr['source_id'] is not None and rep.get('source_id') not in (None, tr['source_id']):
        return False
    rs, ts = _d(rep.get('start')), _d(tr['start'])
    if rs is None or ts is None:
        return False
    if tr['type'] in ('duplicate_rows', 'swapped_columns', 'outage', 'double_count') and tr.get('end'):
        te = _d(tr['end']); re_ = _d(rep.get('end')) or rs
        return rs <= te + pd.Timedelta(days=tol) and re_ >= ts - pd.Timedelta(days=tol)   # windows overlap
    return abs((rs - ts).days) <= tol


def optional_match(rep, opt):
    if rep.get('ticker') != opt['ticker']:
        return False
    if opt['source_id'] is not None and rep.get('source_id') not in (None, opt['source_id']):
        return False
    rs = _d(rep.get('start'))
    return rs is not None and _d(opt['lo']) <= rs <= _d(opt['hi'])


def main():
    truth = load_gold()
    tol = truth['date_tolerance_days']
    try:
        reported = json.loads((APP / 'output' / 'issues.json').read_text())
        if isinstance(reported, dict):
            reported = reported.get('issues', [])
        assert isinstance(reported, list)
    except Exception as e:  # noqa: BLE001
        return write_reward(0.0, dict(error=f'could not read output/issues.json: {e}'))

    ignore = {(i['ticker'], i['source_id']) for i in truth['ignore_series']}
    req = truth['required']
    matched_req = [False] * len(req)
    n_tp = n_fp = n_ignored = 0
    per_report = []
    for rep in reported:
        if not isinstance(rep, dict):
            n_fp += 1; continue
        try:
            rep['source_id'] = None if rep.get('source_id') in (None, '', 'null') else int(rep['source_id'])
        except (TypeError, ValueError):
            rep['source_id'] = None
        hit = next((j for j, tr in enumerate(req) if not matched_req[j] and matches(rep, tr, tol)), None)
        dup = next((j for j, tr in enumerate(req) if matched_req[j] and matches(rep, tr, tol)), None)
        if hit is not None:
            matched_req[hit] = True; n_tp += 1; status = f'TP:{req[hit]["type"]}'
        elif dup is not None:
            n_ignored += 1; status = 'duplicate-of-matched'
        elif any(optional_match(rep, o) for o in truth['optional']) or (rep.get('ticker'), rep.get('source_id')) in ignore:
            n_ignored += 1; status = 'ignored(optional/low-volume)'
        else:
            n_fp += 1; status = 'FP'
        per_report.append(dict(rep=rep, status=status))

    precision = n_tp / (n_tp + n_fp) if (n_tp + n_fp) else (1.0 if not req else 0.0)
    recall = sum(matched_req) / len(req) if req else 1.0
    missed = [dict(type=r['type'], ticker=r['ticker'], source_id=r['source_id'], start=r['start'], origin=r.get('origin'))
              for r, m in zip(req, matched_req) if not m]
    return write_reward(f1(precision, recall), dict(precision=round(precision, 3), recall=round(recall, 3),
                                                    n_reported=len(reported), tp=n_tp, fp=n_fp, ignored=n_ignored,
                                                    missed=missed, reports=per_report))


if __name__ == '__main__':
    main()
