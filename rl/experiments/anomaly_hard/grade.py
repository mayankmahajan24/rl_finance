"""Grade a solution on an anomaly_hard prototype task:
    python grade.py TASK_DIR SOLUTION_DIR [--writeup PATH] [--json OUT] [--cache DIR]

Runs SOLUTION_DIR/score.py on the task's hidden panel, truncated at the gold's cutoffs (earliest first) and then
whole, each run in its own empty folder with the network off (no proxy, minimal environment). A prototype: unlike
the Harbor verifier it does not sandbox the scorer as another user, so only grade code copied out of its run folder.

Gates (reward 0 if any fails): output format (one row per input row; confidence in [0, 1]; clean_ct and clean_amt
blank or non-negative), the point-in-time check on all three columns, no model or network calls in the code, and a
write-up (default SOLUTION_DIR/../output/writeup.md).

Reward = W_CONF x confidence score + W_CLEAN x cleaned-series score + W_CONS x self-consistency score.
  Scored rows: from eval_start, not on low-volume series, not near known natural artifacts. Thin stretches (the truth
  count's centred 28-day median under THIN_LO x thin_ct, after their first THIN_EDGE days) are untrustworthy and should
  be dropped: distrusted (kind `thin` in the confidence score) and left blank (kind `thin` in the cleaned-series gain:
  the share of its rows blank). Borderline rows (median between THIN_LO and THIN_HI x thin_ct) and the THIN_EDGE days
  either side of a thin stretch's start and end are not scored. Untrustworthy rows (label_rows): every day of a point anomaly or
  reviewed real problem. A level shift is a change, as a time series monitor sees it: its first CHANGE_DAYS days are
  untrustworthy (event: onset); then not scored up to SETTLE_DAYS from its start (or two weeks after a ramp ends) while
  the code decides whether the new level is the new normal; after that the new level is trusted (and the cleaned series
  should rescale it). When a temporary shift ends the data is right again: the next SETTLE_DAYS are not scored, and
  after that the source must be trusted.
  Confidence score: 0.5 x row F1 + 0.5 x event F1 of the rows scored below 0.5 (distrusted).
    row F1:   row precision vs day recall (share of each event's labelled days distrusted, averaged within each kind,
              then over kinds)
    event F1: alert precision (runs of distrusted days on a series, gaps of up to ALERT_GAP days joined, that touch an
              untrustworthy row) vs event recall (mean over kinds of the kind's mean credit; a point event counts if
              any of its days is distrusted, a level shift's onset in full if first distrusted within 14 days, nothing
              at 45)
    A panel with no untrustworthy rows: 1 - share of scored rows distrusted / 5%, floored at 0.
  Cleaned-series score: gain x damage penalty, against the truth panel (the hidden panel before the problems were
  planted; real events kept). Error = mean over count and dollars of |log value - log truth|; a blank cleaned value
  counts as the raw value.
    gain: for each planted problem, 1 - (cleaned error / raw error) summed over the scored rows it changed, floored at
          0; averaged within each kind, then over kinds. Reviewed real problems have no truth panel value (the truth
          panel is the real data, problems included), so they are scored the same way against a hindsight reference
          built from the full hidden series (hindsight_ref): the source's relation to the median of its company's
          other sources (log count, log ticket), taken from REF_DAYS either side of the problem (other reviewed
          problems left out) for a one-off problem, or from the REF_DAYS before it for a lasting change (the old
          basis, as for a planted shift); errors within the source's own noise in that relation are not counted
    damage penalty: max(0, 1 - mean cleaned error on scored rows no problem changed / DAMAGE_TOL)
  Self-consistency score: score.py run again, once on its own cleaned series (rows it left blank dropped) and once on
  the truth panel (genuinely clean data, its own baseline). fixed x (0.5 x no new alarms + 0.5 x idempotent):
    fixed:         share of the planted untrustworthy scored rows that the first run distrusted and the run on the
                   cleaned series trusts (caught, and repaired so well the code no longer objects)
    no new alarms: max(0, 1 - excess / NEW_ALARM_TOL), excess = share of scored rows distrusted on the cleaned series
                   minus the share distrusted on the truth panel, floored at 0
    idempotent:    max(0, 1 - mean |log change| of the cleaned series when cleaned again / DAMAGE_TOL)
    If the run on its own cleaned series fails, the score is 0.
  Unknowns: distrusted rows on real data nobody has judged (not planted, not a real event, not in a reviewed stretch,
  not on a series reviewed end to end). The reward counts them as false alarms; reward_lenient leaves them unscored.
  The write-up's quality is judged separately (not in this reward).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

KEYS = ['date', 'ticker', 'source_id']
OUT_COLS = ['confidence', 'clean_ct', 'clean_amt']
FULL_DAYS, ZERO_DAYS = 14, 45
CHANGE_DAYS, SETTLE_DAYS = 14, 45
ALERT_GAP = 2
REAL_TYPES = {'real', 'real_change'}   # reviewed problems in the source data (cleaned against hindsight_ref)
REF_DAYS = 56
THIN_LO, THIN_HI, THIN_EDGE = 0.8, 1.25, 14   # thin: truth count's 28-day median under THIN_LO x thin_ct must be
# dropped (distrusted, left blank); between THIN_LO and THIN_HI x thin_ct, and the first THIN_EDGE days of a thin
# stretch and the THIN_EDGE days after it, are not scored (the code cannot tell yet, point in time)
DAMAGE_TOL = 0.05
NEW_ALARM_TOL = 0.01
W_CONF, W_CLEAN, W_CONS = 0.4, 0.4, 0.2
# imports or shell calls that reach a model or the network
NO_AI = re.compile(r'\b(anthropic|openai|google\.generativeai|google\.genai|mistralai|cohere|ollama|litellm|langchain|'
                   r'transformers|requests|httpx|aiohttp|urllib\.request|urllib3|http\.client|socket|websocket|'
                   r'curl|wget)\b')


def f1(p, r):
    return 2 * p * r / (p + r) if p + r else 0.0


class GateError(Exception):
    pass


def run(script: pathlib.Path, panel: pd.DataFrame, cache: pathlib.Path | None = None) -> pd.DataFrame:
    if cache and cache.exists():
        return pd.read_csv(cache, parse_dates=['date'])
    work = pathlib.Path(tempfile.mkdtemp())
    try:
        panel.to_csv(work / 'in.csv', index=False, date_format='%Y-%m-%d')
        env = {'PATH': os.environ['PATH'], 'HOME': str(work)}            # no proxy settings: no network
        env.update({k: v for k, v in os.environ.items() if k == 'ORACLE_TASK'})   # the grader-check oracle only
        r = subprocess.run([sys.executable, str(script), '--input', str(work / 'in.csv'), '--output',
                            str(work / 'out.csv')], cwd=work, capture_output=True, text=True, timeout=1200, env=env)
        if r.returncode:
            raise GateError(f'score.py failed: {r.stderr[-1500:]}')
        s = pd.read_csv(work / 'out.csv', parse_dates=['date'])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    check_format(panel, s)
    s['source_id'] = s.source_id.astype(int)
    s = s[KEYS + OUT_COLS]
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        s.to_csv(cache, index=False, date_format='%Y-%m-%d')
    return s


def check_format(panel, s):
    missing = set(KEYS + OUT_COLS) - set(s.columns)
    if missing:
        raise GateError(f'output is missing columns {sorted(missing)}')
    dup = int(s[KEYS].duplicated().sum())
    if len(s) != len(panel) or dup:
        raise GateError(f'output has {len(s)} rows ({dup} duplicated); input has {len(panel)}')
    c = pd.to_numeric(s.confidence, errors='coerce')
    if c.isna().any() or ((c < 0) | (c > 1)).any():
        raise GateError('confidence must be a number in [0, 1] on every row')
    for col in ('clean_ct', 'clean_amt'):
        v = pd.to_numeric(s[col], errors='coerce')
        if (s[col].notna() & v.isna()).any() or (v < 0).any() or np.isinf(v).any():
            raise GateError(f'{col} must be blank or a finite non-negative number')


def scan_no_ai(sol: pathlib.Path) -> list[str]:
    """Lines that import a model or network client, or shell out to one."""
    hits = []
    for f in sorted(sol.rglob('*.py')):
        for i, line in enumerate(f.read_text(errors='replace').splitlines(), 1):
            code = line.split('#', 1)[0]
            if re.search(r'\b(import|from|subprocess|os\.system|os\.popen)\b', code) and NO_AI.search(code):
                hits.append(f'{f.name}:{i}: {line.strip()[:120]}')
    return hits


def label_rows(truth: dict, ev: pd.DataFrame, clean_truth: pd.DataFrame | None = None) -> list[tuple[dict, pd.Series]]:
    """Set ev['label'] (untrustworthy) and ev['use'] (scored), and return the scored events with their labelled rows:
    point problems as they are, each level shift as its onset."""
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
    ev['thin'] = False
    thin_parts = []
    if clean_truth is not None:                     # thin stretches, from the truth count's centred 28-day median
        bar = truth.get('thin_ct', 20)
        ct = clean_truth.sort_values('date').copy()
        ct['med'] = ct.groupby(['ticker', 'source_id']).ct.transform(
            lambda x: x.rolling(28, min_periods=1, center=True).median())
        ct['core'] = False
        ct['grey'] = (ct.med >= THIN_LO * bar) & (ct.med < THIN_HI * bar)
        runs = []
        for (tk, s), g in ct.groupby(['ticker', 'source_id']):
            low = (g.med < THIN_LO * bar).to_numpy()
            if not low.any():
                continue
            rid = np.cumsum(np.r_[True, low[1:] != low[:-1]])
            for r in np.unique(rid[low]):
                d = g.date[rid == r]
                a, b = d.min(), d.max()
                near = (g.date >= a - D(THIN_EDGE)) & (g.date < a + D(THIN_EDGE)) | \
                       (g.date > b - D(THIN_EDGE)) & (g.date <= b + D(THIN_EDGE))
                ct.loc[near[near].index, 'grey'] = True
                core = g.index[(rid == r) & ~near.to_numpy()]
                ct.loc[core, 'core'] = True
                runs.append((tk, s, core))
        k = ev[KEYS].merge(ct[KEYS + ['core', 'grey']], on=KEYS, how='left')
        core = k.core.fillna(False).astype(bool).to_numpy()
        ev['use'] &= ~(core | k.grey.fillna(False).astype(bool).to_numpy())
        for tk, s, idx in runs:
            m = (ev.ticker == tk) & (ev.source_id == s) & ev.date.isin(set(ct.loc[idx, 'date']))
            thin_parts.append((tk, s, m))
    parts, quiet = [], pd.Series(False, index=ev.index)
    for e in truth['events']:
        a, b = pd.Timestamp(e['start']), pd.Timestamp(e['end'])
        ser = (ev.ticker == e['ticker']) & (ev.source_id == e['source_id'])
        if not e['regime']:
            parts.append((e, ser & ev.date.between(a, b)))
            continue
        settle = max(a + D(SETTLE_DAYS - 1), pd.Timestamp(e.get('settle', a)))
        on_end = min(a + D(CHANGE_DAYS - 1), b)
        quiet |= ser & (ev.date > on_end) & (ev.date <= min(settle, b))
        parts.append((dict(e, part='onset', end=str(on_end.date())), ser & ev.date.between(a, on_end)))
        if not e.get('permanent'):
            # back on its old level: the data is right again, so distrusting the return is neither required nor
            # penalised for SETTLE_DAYS; after that the source must be trusted
            quiet |= ser & (ev.date > b) & (ev.date <= b + D(SETTLE_DAYS))
    ev['use'] &= ~quiet
    for tk, s, m in thin_parts:           # thin stretches not excluded for another reason: untrustworthy, drop them
        m = m & ~excluded_thin(truth, ev, tk, s)
        if m.any():
            ev.loc[m, 'thin'] = True
            d = ev.date[m]
            parts.append((dict(type='thin', ticker=tk, source_id=s, start=str(d.min().date()), end=str(d.max().date()),
                               regime=False), m))
    scored = []
    for e, m in parts:
        m = m & (ev.date >= pd.Timestamp(truth['eval_start']))
        ev.loc[m, 'label'] = True; ev.loc[m, 'use'] = True
        if m.any():
            scored.append((e, m))
    return scored


def excluded_thin(truth, ev, tk, s):
    """Rows of series (tk, s) that are not scored for a reason other than being thin."""
    D = lambda n: pd.Timedelta(days=n)  # noqa: E731
    out = ev.date < pd.Timestamp(truth['eval_start'])
    for i in truth['ignore_series']:
        if i['ticker'] == tk and i['source_id'] == s:
            out |= True
    for x in truth['exclusions']:
        if x['ticker'] == tk and x['source_id'] in (None, s):
            out |= ev.date.between(pd.Timestamp(x['lo']) - D(14), pd.Timestamp(x['hi']) + D(30))
    return out


def confidence_score(ev, scored):
    e_ = ev[ev.use]
    flag, pos = e_.flag, e_.label
    if not pos.any():
        rate = float(flag.mean())
        return max(0.0, 1 - rate / 0.05), dict(no_bad_rows=True, distrusted_share=round(rate, 4))
    tp, fp, fn = int((flag & pos).sum()), int((flag & ~pos).sum()), int((~flag & pos).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    table = []
    for e, m in scored:
        days = ev.date[m & ev.flag]
        delay = int((days.min() - pd.Timestamp(e['start'])).days) if len(days) else None
        if e['regime']:
            credit = 0.0 if delay is None else float(np.clip((ZERO_DAYS - delay) / (ZERO_DAYS - FULL_DAYS), 0, 1))
        else:
            credit = float(delay is not None)
        table.append(dict(type=e['type'], part=e.get('part', ''), ticker=e['ticker'], source_id=e['source_id'],
                          start=e['start'], end=e['end'], days=int(m.sum()), distrusted_days=int((m & ev.flag).sum()),
                          delay_days=delay, credit=round(credit, 3)))
    t = pd.DataFrame(table)
    t['day_recall'] = t.distrusted_days / t.days.clip(lower=1)
    by_kind = t.groupby('type').agg(events=('credit', 'size'), credit=('credit', 'mean'), days=('days', 'sum'),
                                    distrusted_days=('distrusted_days', 'sum'), day_recall=('day_recall', 'mean'))
    ev_rec, day_rec = float(by_kind.credit.mean()), float(by_kind.day_recall.mean())
    n_alerts, true_alerts = alerts(e_)
    alert_prec = true_alerts / n_alerts if n_alerts else 0.0
    row_f1, event_f1 = f1(prec, day_rec), f1(alert_prec, ev_rec)
    return 0.5 * row_f1 + 0.5 * event_f1, dict(
        precision=round(prec, 3), day_recall=round(day_rec, 3), row_f1=round(row_f1, 3), alerts=n_alerts,
        true_alerts=true_alerts, alert_precision=round(alert_prec, 3), event_recall=round(ev_rec, 3),
        event_f1=round(event_f1, 3), tp=tp, fp=fp, fn=fn, by_kind=by_kind.round(3).reset_index().to_dict('records'),
        events=table)


def hindsight_ref(truth: dict, panel: pd.DataFrame) -> pd.DataFrame:
    """What each reviewed real problem's rows should have read, from the full series (panel = the hidden truth panel,
    which still has the real problems in it): KEYS + ref_ct, ref_amt, tol_ct, tol_amt (log-units noise allowance),
    one row per day of each real problem (for a lasting change, from its start to its end)."""
    real = [e for e in truth['events'] if e['type'] in REAL_TYPES]
    out = []
    if not real:
        return pd.DataFrame(columns=KEYS + ['ref_ct', 'ref_amt', 'tol_ct', 'tol_amt'])
    mad = lambda x: float(1.4826 * (x - x.median()).abs().median()) if len(x) > 5 else np.nan  # noqa: E731
    for tk in sorted({e['ticker'] for e in real}):
        g = panel[panel.ticker == tk]
        lc = np.log(g.pivot(index='date', columns='source_id', values='ct').clip(lower=0.01))
        lt = np.log(g.pivot(index='date', columns='source_id', values='amt').clip(lower=0.01)) - lc
        for s in sorted({e['source_id'] for e in real if e['ticker'] == tk}):
            peers = [c for c in lc.columns if c != s]
            if not peers:
                continue
            rc, rt = lc[s] - lc[peers].median(axis=1), lt[s] - lt[peers].median(axis=1)
            mine = [e for e in real if e['ticker'] == tk and e['source_id'] == s]
            bad = pd.Series(False, index=lc.index)
            for e in mine:
                bad |= (lc.index >= pd.Timestamp(e['start'])) & (lc.index <= pd.Timestamp(e['end']))
            for e in mine:
                a, b = pd.Timestamp(e['start']), pd.Timestamp(e['end'])
                pre = (lc.index >= a - pd.Timedelta(days=REF_DAYS)) & (lc.index < a)
                post = (lc.index > b) & (lc.index <= b + pd.Timedelta(days=REF_DAYS))
                win = (pre | (post if e['type'] == 'real' else False)) & ~bad & rc.notna() & rt.notna()
                if win.sum() < 10:
                    continue
                span = (lc.index >= a) & (lc.index <= b)
                d = lc.index[span]
                ref_lc = lc.loc[d, peers].median(axis=1) + rc[win].median()
                ref_lt = lt.loc[d, peers].median(axis=1) + rt[win].median()
                tc, tt = mad(rc[win]), mad(rt[win])
                out.append(pd.DataFrame(dict(date=d, ticker=tk, source_id=s, ref_ct=np.exp(ref_lc).to_numpy(),
                                             ref_amt=np.exp(ref_lc + ref_lt).to_numpy(), tol_ct=tc,
                                             tol_amt=float(np.hypot(tc, tt)))))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=KEYS + ['ref_ct', 'ref_amt', 'tol_ct', 'tol_amt'])


def clean_score(truth, ev, scored_rows, ref=None):
    """ev carries raw ct/amt, truth tct/tamt and the cleaned values (blank = raw); scored_rows is the scored mask
    before label_rows forced labelled rows in (the cleaned series is scored on the same stretches)."""
    lg = lambda x: np.log(np.maximum(x.astype(float), 0.01))  # noqa: E731
    cc = ev.clean_ct.where(ev.clean_ct.notna(), ev.ct)
    ca = ev.clean_amt.where(ev.clean_amt.notna(), ev.amt)
    err_raw = 0.5 * ((lg(ev.ct) - lg(ev.tct)).abs() + (lg(ev.amt) - lg(ev.tamt)).abs())
    err_cln = 0.5 * ((lg(cc) - lg(ev.tct)).abs() + (lg(ca) - lg(ev.tamt)).abs())
    changed = err_raw > 1e-6
    real = pd.Series(False, index=ev.index)
    gains = []
    for e in truth['events']:
        ser = (ev.ticker == e['ticker']) & (ev.source_id == e['source_id'])
        span = ser & ev.date.between(pd.Timestamp(e.get('shift_start', e['start'])), pd.Timestamp(e['end']))
        if e['type'] == 'thin':
            continue
        if e['type'] in REAL_TYPES:          # real problems: against the hindsight reference, net of its noise
            real |= span
            if ref is None or not ev.ref_ct.notna().any():
                continue
            rc, ra = ev.ref_ct, ev.ref_amt
            er = 0.5 * (((lg(ev.ct) - lg(rc)).abs() - ev.tol_ct).clip(lower=0)
                        + ((lg(ev.amt) - lg(ra)).abs() - ev.tol_amt).clip(lower=0))
            ec = 0.5 * (((lg(cc) - lg(rc)).abs() - ev.tol_ct).clip(lower=0)
                        + ((lg(ca) - lg(ra)).abs() - ev.tol_amt).clip(lower=0))
            m = span & scored_rows & rc.notna() & (er > 1e-6) & ~ev.thin          # a thin stretch is dropped, not repaired
            if not m.any():
                continue
            g = max(0.0, 1 - ec[m].sum() / er[m].sum())
            gains.append(dict(type=e['type'], ticker=e['ticker'], source_id=e['source_id'], start=e['start'],
                              rows=int(m.sum()), raw_error=round(float(er[m].mean()), 3),
                              clean_error=round(float(ec[m].mean()), 3), gain=round(g, 3)))
            continue
        m = span & changed & scored_rows & ~ev.thin
        if not m.any():
            continue
        g = max(0.0, 1 - err_cln[m].sum() / err_raw[m].sum())
        gains.append(dict(type=e['type'], ticker=e['ticker'], source_id=e['source_id'], start=e['start'],
                          rows=int(m.sum()), raw_error=round(float(err_raw[m].mean()), 3),
                          clean_error=round(float(err_cln[m].mean()), 3), gain=round(g, 3)))
    thin = ev.thin & scored_rows
    for (tk, s), g in ev[thin].groupby(['ticker', 'source_id']):
        blank = (g.clean_ct.isna() & g.clean_amt.isna())
        gains.append(dict(type='thin', ticker=tk, source_id=int(s), start=str(g.date.min().date()), rows=len(g),
                          raw_error=None, clean_error=None, gain=round(float(blank.mean()), 3)))
    ok = scored_rows & ~changed & ~real & ~ev.thin
    damage = float(err_cln[ok].mean()) if ok.any() else 0.0
    penalty = max(0.0, 1 - damage / DAMAGE_TOL)
    blank = int((scored_rows & ~ev.thin & (ev.clean_ct.isna() | ev.clean_amt.isna())).sum())
    if gains:
        g = pd.DataFrame(gains)
        gain = float(g.groupby('type').gain.mean().mean())
        by_kind = g.groupby('type').agg(events=('gain', 'size'), gain=('gain', 'mean'),
                                        raw_error=('raw_error', 'mean'), clean_error=('clean_error', 'mean'))
        by_kind = by_kind.round(3).reset_index().to_dict('records')
    else:
        gain, by_kind = 1.0, []
    return gain * penalty, dict(gain=round(gain, 3), damage=round(damage, 4), damage_penalty=round(penalty, 3),
                                blank_scored_rows=blank, by_kind=by_kind, events=gains)


def scored_stretches(truth, ev, clean_truth):
    """Rows scored for the cleaned series: the same exclusions as the confidence score, but every day of a problem
    and every settling day counts (the cleaned series should be right throughout)."""
    tmp = ev[KEYS].copy()
    tmp['date'] = ev.date
    probe = dict(truth, events=[])
    label_rows(probe, tmp, clean_truth)
    return tmp.use


def score(truth: dict, data: pd.DataFrame, clean_truth: pd.DataFrame, sol: pathlib.Path,
          writeup: pathlib.Path, cache: pathlib.Path | None = None):
    hits = scan_no_ai(sol)
    gates = dict(no_ai=not hits, writeup=writeup.exists() and writeup.stat().st_size > 0)
    cuts = sorted(truth['truncation_cutoffs'])
    c_ = (lambda name: cache / f'{name}.csv') if cache else (lambda name: None)
    try:
        trunc = {c: run(sol / 'score.py', data[data.date <= pd.Timestamp(c)], c_(f'cut-{c}')) for c in cuts}
        full = run(sol / 'score.py', data, c_('full'))
        gates['format'] = True
    except GateError as e:
        return 0.0, dict(gates=dict(gates, format=False), ai_hits=hits, error=str(e)[-800:])
    leaks = {}
    for c in cuts:
        cmp = (data[data.date <= pd.Timestamp(c)][KEYS].merge(trunc[c], on=KEYS, how='left')
               .merge(full, on=KEYS, how='left', suffixes=('_t', '_f')))
        for col in OUT_COLS:
            a, b = cmp[f'{col}_t'].astype(float), cmp[f'{col}_f'].astype(float)
            same = ((a - b).abs() <= 1e-6 * np.maximum(1, b.abs())) | (a.isna() & b.isna())
            leaks[f'{c}:{col}'] = int((~same).sum())
    gates['point_in_time'] = all(v == 0 for v in leaks.values())

    ev = data[KEYS + ['ct', 'amt']].merge(full, on=KEYS, how='left')
    ev = ev.merge(clean_truth[KEYS + ['ct', 'amt']].rename(columns={'ct': 'tct', 'amt': 'tamt'}), on=KEYS, how='left')
    ev['flag'] = ev.confidence < 0.5
    ref = hindsight_ref(truth, clean_truth)
    ev = ev.merge(ref, on=KEYS, how='left')
    stretches = scored_stretches(truth, ev, clean_truth)
    scored = label_rows(truth, ev, clean_truth)
    conf, conf_d = confidence_score(ev, scored)
    cln, cln_d = clean_score(truth, ev, stretches, ref)
    cons, cons_d = consistency_score(truth, sol, data, clean_truth, full, ev, stretches, c_)
    reward = (W_CONF * conf + W_CLEAN * cln + W_CONS * cons) * all(gates.values())
    # unknowns: distrusted rows on real data nobody has judged. The reward counts them as false alarms (strict);
    # the lenient reward leaves them unscored. The gap is how much the score still rests on missing labels.
    unknown = ev.use & ev.flag & ~ev.label & ~known_rows(truth, ev)
    lev = ev.copy()
    lev.loc[unknown, 'use'] = False
    lconf, _ = confidence_score(lev, [(e, m) for e, m in scored])
    lreward = (W_CONF * lconf + W_CLEAN * cln + W_CONS * cons) * all(gates.values())
    return reward, dict(gates=gates, ai_hits=hits, changed_on_truncation=leaks, rows_scored=int(ev.use.sum()),
                        reward_lenient=round(lreward, 3), unknown_flagged_rows=int(unknown.sum()),
                        unknown_alerts=alerts(ev[unknown].assign(label=True))[0] if unknown.any() else 0,
                        confidence_score=round(conf, 3), clean_score=round(cln, 3), consistency_score=round(cons, 3),
                        confidence=conf_d, clean=cln_d, consistency=cons_d)


def consistency_score(truth, sol, data, clean_truth, full, ev, stretches, c_):
    """Run the code on its own cleaned series and on the truth panel; see the module docstring."""
    lg = lambda x: np.log(np.maximum(x.astype(float), 0.01))  # noqa: E731
    cleaned = data.drop(columns=['ct', 'amt']).merge(
        full[KEYS + ['clean_ct', 'clean_amt']].rename(columns={'clean_ct': 'ct', 'clean_amt': 'amt'}), on=KEYS)
    cleaned = cleaned.dropna(subset=['ct', 'amt'])[data.columns]
    try:
        again = run(sol / 'score.py', cleaned, c_('self'))
        base = run(sol / 'score.py', clean_truth[data.columns], c_('truthrun'))
    except GateError as e:
        return 0.0, dict(error=str(e)[-500:])
    k = ev[KEYS].copy()
    k = k.merge(again.rename(columns={c: c + '2' for c in OUT_COLS}), on=KEYS, how='left')
    k = k.merge(base[KEYS + ['confidence']].rename(columns={'confidence': 'confidence_t'}), on=KEYS, how='left')
    real = pd.Series(False, index=ev.index)
    for e in truth['events']:
        if e['type'] in REAL_TYPES:
            real |= (ev.ticker == e['ticker']) & (ev.source_id == e['source_id']) & \
                ev.date.between(pd.Timestamp(e['start']), pd.Timestamp(e['end']))
    bad = (ev.use & ev.label & ~real & ~ev.thin).to_numpy()   # thin rows are dropped, not repaired
    trusted2 = (k.confidence2 >= 0.5).to_numpy()       # a row missing from the second run is not trusted
    if bad.any():
        fixed = float((bad & ev.flag.to_numpy() & trusted2).sum() / bad.sum())
    else:                     # nothing planted (a control): the share of the labelled problems the first run distrusted
        lab = (ev.use & ev.label).to_numpy()
        fixed = float((lab & ev.flag.to_numpy()).sum() / lab.sum()) if lab.any() else 1.0
    sc = stretches.to_numpy() & k.confidence2.notna().to_numpy()
    rate_c = float((k.confidence2[sc] < 0.5).mean()) if sc.any() else 0.0
    rate_t = float((k.confidence_t[sc] < 0.5).mean()) if sc.any() else 0.0
    no_new = max(0.0, 1 - max(0.0, rate_c - rate_t) / NEW_ALARM_TOL)
    c1ct, c1amt = ev.clean_ct.where(ev.clean_ct.notna(), ev.ct), ev.clean_amt.where(ev.clean_amt.notna(), ev.amt)
    c2ct, c2amt = k.clean_ct2.where(k.clean_ct2.notna(), c1ct), k.clean_amt2.where(k.clean_amt2.notna(), c1amt)
    change = 0.5 * ((lg(c2ct) - lg(c1ct)).abs() + (lg(c2amt) - lg(c1amt)).abs())
    moved = float(change[sc].mean()) if sc.any() else 0.0
    idem = max(0.0, 1 - moved / DAMAGE_TOL)
    return fixed * (0.5 * no_new + 0.5 * idem), dict(
        fixed=round(fixed, 3), planted_bad_rows=int(bad.sum()), distrusted_share_cleaned=round(rate_c, 4),
        distrusted_share_truth=round(rate_t, 4), no_new_alarms=round(no_new, 3), recleaning_change=round(moved, 4),
        idempotent=round(idem, 3))


def known_rows(truth: dict, ev: pd.DataFrame) -> pd.Series:
    """Rows whose status is known without a label: changed by a planted problem (raw differs from the truth panel),
    inside a real-event decoy, inside a reviewed fine or recurring stretch, on a series reviewed end to end, or in a run
    of distrusted days that touches any of those or a labelled problem."""
    k = (np.abs(np.log(ev.ct.astype(float)) - np.log(ev.tct.astype(float))) > 1e-9) | \
        (np.abs(np.log(ev.amt.astype(float)) - np.log(ev.tamt.astype(float))) > 1e-9)
    for x in truth.get('decoys', []):
        k |= (ev.ticker == x['ticker']) & ev.date.between(pd.Timestamp(x['start']), pd.Timestamp(x['end']) + pd.Timedelta(days=14))
    for x in truth.get('reviewed_not_real', []) + truth.get('reviewed_recurring', []):
        k |= (ev.ticker == x['ticker']) & (ev.source_id == x['source_id']) & \
            ev.date.between(pd.Timestamp(x['start']), pd.Timestamp(x['end']))
    for x in truth.get('reviewed_series', []):
        k |= (ev.ticker == x['ticker']) & (ev.source_id == x['source_id'])
    # a run of distrusted days that touches a planted or labelled problem is that problem's (over-)flagging: known
    f = ev[ev.flag].sort_values('date')
    for _, g in f.groupby(['ticker', 'source_id']):
        rid = (g.date.diff().dt.days.fillna(999) > ALERT_GAP + 1).cumsum()
        for _, r in g.groupby(rid):
            if (k[r.index] | ev.label[r.index]).any():
                k[r.index] = True
    return k


def alerts(e_: pd.DataFrame) -> tuple[int, int]:
    """Runs of distrusted scored days on a series (gaps of up to ALERT_GAP days joined), and how many touch an
    untrustworthy row."""
    n = hit = 0
    for _, g in e_[e_.flag].sort_values('date').groupby(['ticker', 'source_id']):
        run_id = (g.date.diff().dt.days.fillna(999) > ALERT_GAP + 1).cumsum()
        runs = g.groupby(run_id).label.any()
        n += len(runs); hit += int(runs.sum())
    return n, hit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('task'); ap.add_argument('solution'); ap.add_argument('--json')
    ap.add_argument('--writeup'); ap.add_argument('--cache')
    a = ap.parse_args()
    task, sol = pathlib.Path(a.task), pathlib.Path(a.solution).resolve()
    truth = json.loads((task / 'tests' / 'gold.json').read_text())
    data = pd.read_csv(task / 'tests' / 'eval_panel.csv.gz', parse_dates=['date'])
    clean_truth = pd.read_csv(task / 'tests' / 'truth_panel.csv.gz', parse_dates=['date'])
    writeup = pathlib.Path(a.writeup) if a.writeup else sol.parent / 'output' / 'writeup.md'
    reward, d = score(truth, data, clean_truth, sol, writeup, pathlib.Path(a.cache) if a.cache else None)
    res = dict(task=task.name, solution=str(sol), reward=round(reward, 3), **d)
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, indent=1, default=str))
    short = {k: v for k, v in res.items() if k not in ('confidence', 'clean', 'solution', 'changed_on_truncation')}
    print(json.dumps(short, default=str))
    for part in ('confidence', 'clean'):
        for k in res.get(part, {}).get('by_kind', []):
            print('   ', part, k)


if __name__ == '__main__':
    main()
