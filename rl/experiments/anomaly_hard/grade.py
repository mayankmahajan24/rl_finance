"""Grade a solution on an anomaly_hard prototype task:
    python grade.py TASK_DIR SOLUTION_DIR [--writeup PATH] [--json OUT] [--cache DIR]

Runs SOLUTION_DIR/score.py on the task's hidden panel, truncated at the gold's cutoffs (earliest first) and then
whole, each run in its own empty folder with the network off (its own network namespace where the machine allows it,
and no proxy settings, minimal environment). A prototype: unlike
the Harbor verifier it does not sandbox the scorer as another user, so only grade code copied out of its run folder.

Gates (reward 0 if any fails): output format (one row per input row; confidence in [0, 1]; clean_ct and clean_amt
blank or non-negative), the point-in-time check on all three columns, no model or network calls in the code, a
write-up (default SOLUTION_DIR/../output/writeup.md), and low signal dropped: at least LOW_SIGNAL_SHARE of the rows of
thin beginnings (below) distrusted and left blank.

Reward = W_CONF x confidence + W_CLEAN x cleaned series x stability.
  Scored rows: from eval_start, not on low-volume series, not on company-wide natural breaks. Thin beginnings (before a
  source is established: its truth count's centred 28-day median has held thin_ct for THIN_ESTABLISHED days) where
  that median is under THIN_LO x thin_ct, after their first THIN_EDGE days, must be dropped (the gate above) and are
  otherwise not scored; borderline rows (median between THIN_LO and THIN_HI x thin_ct) and THIN_EDGE days either side
  of a thin stretch's edges are not scored; a source that thins after it was established is kept (scored for the
  cleaned series). What a point-in-time scorer could see (build.annotate_events, in the gold): a level change is
  scored from the day it became visible (its deviation reached 3x the source's own noise; earlier days not scored), and
  a change that never did, or a reviewed one-day problem under 6x that noise, is not scored at all. Untrustworthy rows
  (label_rows): every day of a one-day problem (planted, or reviewed real); a level change (planted, reviewed, or a
  known source quirk measured in the data) is untrustworthy for its first CHANGE_DAYS days from when it became visible, then not scored up to SETTLE_DAYS from its start (or its settle date) while the code decides whether the new
  level is the new normal; after that the new level is trusted (and the cleaned series should rescale it). When a
  temporary change ends, the next SETTLE_DAYS are not scored, and after that the source must be trusted.
  Confidence: row F1 of the rows scored below 0.5 (distrusted): row precision vs day recall (share of each problem's
    untrustworthy days distrusted, averaged within each kind, then over kinds; the planted one-day problems are one
    kind). A panel with no untrustworthy rows: the share of scored rows trusted.
  Cleaned series: gain x intact x kept, against the truth panel (the hidden panel before the problems were planted;
    real events kept). Error = mean over count and dollars of |log value - log truth|; a blank cleaned value counts as
    the raw value.
    gain:   for each problem, 1 - (cleaned error / raw error) summed over the scored rows it changed, each error
            counted only beyond the source's own noise (own_noise; dollars: the count and ticket noises combined),
            floored at 0;
            averaged within each kind, then over kinds. Reviewed real problems and known quirks have no truth panel
            value (the truth panel is the real data), so they are scored against a hindsight reference built from the
            full hidden series (hindsight_ref): the source's relation to the median of its company's other sources (log
            count, log ticket), from REF_DAYS either side of a one-off problem (other problems left out), or the
            REF_DAYS before a lasting change (the old basis); errors within the source's own noise in that relation
            are not counted
    intact: share of the scored rows no problem changed whose cleaned value is within the source's own noise of the
            truth (own_noise: its daily relation to its peers' median, robust spread), in count and in ticket
    kept:   share of the scored rows that should be kept (all but thin beginnings) not left blank
  Stability (multiplies the cleaned series): score.py run again on its own cleaned series (rows it left blank dropped)
    and on the truth panel (genuinely clean data, its own baseline): 1 - (rows distrusted on its cleaned series beyond
    those distrusted on the truth panel) / (the task's untrustworthy rows), floored at 0: new alarms measured against
    the size of what is actually wrong. If the run fails, 0.
  Reported, not scored: distrusted rows on real data nobody has judged (unknown_flagged_rows).
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
CHANGE_DAYS, SETTLE_DAYS = 14, 45
ALERT_GAP = 2            # days of trust that still join two distrusted runs into one (for known_rows)
ONE_DAY = {'volume_spike', 'dropout', 'count_flood', 'dollar_spike'}   # planted one-day problems: one kind
REAL_TYPES = {'real', 'real_change'}   # problems in the source data (reviewed or known quirks): cleaned against hindsight_ref
REF_DAYS = 56
THIN_ESTABLISHED = 90    # a source is established once its median has held at thin_ct or more this many days running
THIN_LO, THIN_HI, THIN_EDGE = 0.8, 1.25, 14   # thin: truth count's 28-day median under THIN_LO x thin_ct must be
# dropped (distrusted, left blank); between THIN_LO and THIN_HI x thin_ct, and the first THIN_EDGE days of a thin
# stretch and the THIN_EDGE days after it, are not scored (the code cannot tell yet, point in time)
LOW_SIGNAL_SHARE = 0.9   # gate: share of a task's thin-beginning rows that must be distrusted and left blank
W_CONF, W_CLEAN = 0.5, 0.5   # confidence (row F1) and cleaned series (x stability)
# imports or shell calls that reach a model or the network
NO_AI = re.compile(r'\b(anthropic|openai|google\.generativeai|google\.genai|mistralai|cohere|ollama|litellm|langchain|'
                   r'transformers|requests|httpx|aiohttp|urllib\.request|urllib3|http\.client|socket|websocket|'
                   r'curl|wget)\b')


def f1(p, r):
    return 2 * p * r / (p + r) if p + r else 0.0


class GateError(Exception):
    pass


def _offline_prefix() -> list[str]:
    """The scorer runs in a network namespace of its own (no interfaces: nothing reachable, proxy or not) where the
    machine allows it; elsewhere it still gets an environment with no proxy settings."""
    try:
        ok = subprocess.run(['unshare', '-n', '--', 'true'], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        ok = False
    return ['unshare', '-n', '--'] if ok else []


OFFLINE = _offline_prefix()


def run(script: pathlib.Path, panel: pd.DataFrame, cache: pathlib.Path | None = None) -> pd.DataFrame:
    if cache and cache.exists():
        return pd.read_csv(cache, parse_dates=['date'])
    work = pathlib.Path(tempfile.mkdtemp())
    try:
        panel.to_csv(work / 'in.csv', index=False, date_format='%Y-%m-%d')
        env = {'PATH': os.environ['PATH'], 'HOME': str(work)}            # no proxy settings: no network
        env.update({k: v for k, v in os.environ.items() if k == 'ORACLE_TASK'})   # the grader-check oracle only
        cmd = [sys.executable, str(script), '--input', str(work / 'in.csv'), '--output', str(work / 'out.csv')]
        r = subprocess.run(OFFLINE + cmd, cwd=work, capture_output=True, text=True, timeout=1200, env=env)
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
    ev['midthin'] = False       # thin after the source was established: keep it (scored for the cleaned series only)
    thin_parts = []
    if clean_truth is not None:                     # thin stretches, from the truth count's centred 28-day median
        bar = truth.get('thin_ct', 20)
        ct = clean_truth.sort_values('date').copy()
        ct['med'] = ct.groupby(['ticker', 'source_id']).ct.transform(
            lambda x: x.rolling(28, min_periods=1, center=True).median())
        ct['core'] = False
        ct['grey'] = (ct.med >= THIN_LO * bar) & (ct.med < THIN_HI * bar)
        runs = []
        ct['mid'] = False
        for (tk, s), g in ct.groupby(['ticker', 'source_id']):
            low = (g.med < THIN_LO * bar).to_numpy()
            if not low.any():
                continue
            held = (g.med >= bar).astype(int).rolling(THIN_ESTABLISHED).sum().to_numpy() >= THIN_ESTABLISHED
            est = g.date.iloc[int(np.argmax(held))] - D(THIN_ESTABLISHED - 1) if held.any() else None
            rid = np.cumsum(np.r_[True, low[1:] != low[:-1]])
            for r in np.unique(rid[low]):
                d = g.date[rid == r]
                a, b = d.min(), d.max()
                if est is not None and a > est:
                    # thin in the middle of an established source: its history should be kept, not dropped
                    ct.loc[d.index, 'mid'] = True
                    continue
                near = (g.date >= a - D(THIN_EDGE)) & (g.date < a + D(THIN_EDGE)) | \
                       (g.date > b - D(THIN_EDGE)) & (g.date <= b + D(THIN_EDGE))
                ct.loc[near[near].index, 'grey'] = True
                core = g.index[(rid == r) & ~near.to_numpy()]
                ct.loc[core, 'core'] = True
                runs.append((tk, s, core))
        k = ev[KEYS].merge(ct[KEYS + ['core', 'grey', 'mid']], on=KEYS, how='left')
        core = k.core.fillna(False).astype(bool).to_numpy()
        mid = k.mid.fillna(False).astype(bool).to_numpy()
        ev['midthin'] = mid & ev.use.to_numpy()
        ev['use'] &= ~(core | mid | k.grey.fillna(False).astype(bool).to_numpy())
        for tk, s, idx in runs:
            m = (ev.ticker == tk) & (ev.source_id == s) & ev.date.isin(set(ct.loc[idx, 'date']))
            thin_parts.append((tk, s, m))
    parts, quiet = [], pd.Series(False, index=ev.index)
    for e in truth['events']:
        a, b = pd.Timestamp(e['start']), pd.Timestamp(e['end'])
        ser = (ev.ticker == e['ticker']) & (ev.source_id == e['source_id'])
        first = pd.Timestamp(e.get('shift_start', e['start']))
        if e.get('unscored'):              # too small for any point-in-time scorer to see: not scored at all
            quiet |= ser & ev.date.between(min(first, a), b + D(SETTLE_DAYS if e['regime'] else 0))
            continue
        if e.get('visible'):               # scored from the day the change became visible; before that, not scored
            v = pd.Timestamp(e['visible'])
            quiet |= ser & (ev.date >= min(first, a)) & (ev.date < v)
            a = v
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
    for tk, s, m in thin_parts:           # thin beginnings not excluded for another reason: must be dropped (a gate)
        m = m & ~excluded_thin(truth, ev, tk, s) & (ev.date >= pd.Timestamp(truth['eval_start']))
        ev.loc[m, 'thin'] = True
    scored = []
    for e, m in parts:
        m = m & (ev.date >= pd.Timestamp(truth['eval_start'])) & ~ev.thin
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


def kind(t: str) -> str:
    return 'one_day' if t in ONE_DAY else t


def confidence_score(ev, scored):
    e_ = ev[ev.use]
    flag, pos = e_.flag, e_.label
    if not pos.any():
        return float(1 - flag.mean()), dict(no_bad_rows=True, distrusted_share=round(float(flag.mean()), 4))
    tp, fp, fn = int((flag & pos).sum()), int((flag & ~pos).sum()), int((~flag & pos).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    table = []
    for e, m in scored:
        days = ev.date[m & ev.flag]
        table.append(dict(type=e['type'], kind=kind(e['type']), part=e.get('part', ''), ticker=e['ticker'],
                          source_id=e['source_id'], start=e['start'], end=e['end'], days=int(m.sum()),
                          distrusted_days=int((m & ev.flag).sum()),
                          delay_days=int((days.min() - pd.Timestamp(e['start'])).days) if len(days) else None))
    t = pd.DataFrame(table)
    t['day_recall'] = t.distrusted_days / t.days.clip(lower=1)
    by_kind = t.groupby('kind').agg(events=('day_recall', 'size'), days=('days', 'sum'),
                                    distrusted_days=('distrusted_days', 'sum'), day_recall=('day_recall', 'mean'))
    day_rec = float(by_kind.day_recall.mean())
    row_f1 = f1(prec, day_rec)
    return row_f1, dict(precision=round(prec, 3), day_recall=round(day_rec, 3), row_f1=round(row_f1, 3), tp=tp,
                        fp=fp, fn=fn, by_kind=by_kind.round(3).reset_index().to_dict('records'), events=table)


def own_noise(truth_panel: pd.DataFrame) -> pd.DataFrame:
    """Per series: the robust spread of its daily relation to its peers' median (log count: sig_c, log ticket: sig_t),
    around its own 28-day median: how far a value can sit from the truth and still be within the source's noise."""
    out = []
    for tk, g in truth_panel.groupby('ticker'):
        lc = np.log(g.pivot(index='date', columns='source_id', values='ct').clip(lower=0.01))
        lt = np.log(g.pivot(index='date', columns='source_id', values='amt').clip(lower=0.01)) - lc
        for s in lc.columns:
            peers = [c for c in lc.columns if c != s]
            row = dict(ticker=tk, source_id=s)
            for name, x in (('sig_c', lc), ('sig_t', lt)):
                rel = x[s] - (x[peers].median(axis=1) if peers else 0)
                r = (rel - rel.rolling(28, min_periods=7, center=True).median()).dropna()
                row[name] = max(float(1.4826 * (r - r.median()).abs().median()), 0.02) if len(r) > 20 else 0.15
            out.append(row)
    return pd.DataFrame(out)


def hindsight_ref(truth: dict, panel: pd.DataFrame) -> pd.DataFrame:
    """What each reviewed real problem's rows should have read, from the full series (panel = the hidden truth panel,
    which still has the real problems in it): KEYS + ref_ct, ref_amt, tol_ct, tol_amt (log-units noise allowance),
    one row per day of each real problem (for a lasting change, from its start to its end)."""
    real = [e for e in truth['events'] if e['type'] in REAL_TYPES]
    out = []
    empty = pd.DataFrame({'date': pd.Series(dtype='datetime64[ns]'), 'ticker': pd.Series(dtype=object),
                          'source_id': pd.Series(dtype='int64'), **{c: pd.Series(dtype=float)
                                                                    for c in ('ref_ct', 'ref_amt', 'tol_ct', 'tol_amt')}})
    if not real:            # typed, so merging it keeps the value columns numeric
        return empty
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
    return pd.concat(out, ignore_index=True) if out else empty


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
    sig_a = np.hypot(ev.sig_c, ev.sig_t)              # dollars = count x ticket: their noises add
    beyond = lambda d, s: (d.abs() - s).clip(lower=0)  # noqa: E731   error beyond the source's own noise
    for e in truth['events']:
        ser = (ev.ticker == e['ticker']) & (ev.source_id == e['source_id'])
        first = pd.Timestamp(e.get('shift_start', e['start']))
        span = ser & ev.date.between(first, pd.Timestamp(e['end']))
        if e.get('unscored'):
            real |= span                                  # not scored, and not counted as untouched rows either
            continue
        if e.get('visible'):                              # before it was visible, it is not scored
            real |= span & (ev.date < pd.Timestamp(e['visible']))
            span &= ev.date >= pd.Timestamp(e['visible'])
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
            gains.append(dict(type=e['type'], kind=kind(e['type']), ticker=e['ticker'], source_id=e['source_id'],
                              start=e['start'], rows=int(m.sum()), raw_error=round(float(er[m].mean()), 3),
                              clean_error=round(float(ec[m].mean()), 3), gain=round(g, 3)))
            continue
        er = 0.5 * (beyond(lg(ev.ct) - lg(ev.tct), ev.sig_c) + beyond(lg(ev.amt) - lg(ev.tamt), sig_a))
        ec = 0.5 * (beyond(lg(cc) - lg(ev.tct), ev.sig_c) + beyond(lg(ca) - lg(ev.tamt), sig_a))
        m = span & changed & scored_rows & ~ev.thin & (er > 1e-6)
        if not m.any():
            continue
        g = max(0.0, 1 - ec[m].sum() / er[m].sum())
        gains.append(dict(type=e['type'], kind=kind(e['type']), ticker=e['ticker'], source_id=e['source_id'],
                          start=e['start'], rows=int(m.sum()), raw_error=round(float(er[m].mean()), 3),
                          clean_error=round(float(ec[m].mean()), 3), gain=round(g, 3)))
    # rows no problem touched should be left as they are: intact = within the source's own noise of the truth
    ok = scored_rows & ~changed & ~real & ~ev.thin
    dc, dt = (lg(cc) - lg(ev.tct)).abs(), ((lg(ca) - lg(cc)) - (lg(ev.tamt) - lg(ev.tct))).abs()
    intact_rows = (dc <= ev.sig_c) & (dt <= ev.sig_t)
    intact = float(intact_rows[ok].mean()) if ok.any() else 1.0
    keep = scored_rows & ~ev.thin
    blank = int((keep & (ev.clean_ct.isna() | ev.clean_amt.isna())).sum())
    kept = 1 - blank / int(keep.sum()) if keep.any() else 1.0
    if gains:
        g = pd.DataFrame(gains)
        gain = float(g.groupby('kind').gain.mean().mean())
        by_kind = g.groupby('kind').agg(events=('gain', 'size'), gain=('gain', 'mean'),
                                        raw_error=('raw_error', 'mean'), clean_error=('clean_error', 'mean'))
        by_kind = by_kind.round(3).reset_index().to_dict('records')
    else:
        gain, by_kind = 1.0, []
    return gain * intact * kept, dict(gain=round(gain, 3), intact=round(intact, 4), kept=round(kept, 4),
                                      damaged_rows=int((ok & ~intact_rows).sum()), blank_rows=blank,
                                      mean_damage=round(float(err_cln[ok].mean()) if ok.any() else 0.0, 4),
                                      by_kind=by_kind, events=gains)


def scored_stretches(truth, ev, clean_truth):
    """Rows scored for the cleaned series: the same exclusions as the confidence score, but every day of a problem
    and every settling day counts (the cleaned series should be right throughout)."""
    tmp = ev[KEYS].copy()
    tmp['date'] = ev.date
    probe = dict(truth, events=[])
    label_rows(probe, tmp, clean_truth)
    return tmp.use | tmp.midthin          # thin stretches of an established source are kept: the cleaned series counts


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
    ev = ev.merge(ref, on=KEYS, how='left').merge(own_noise(clean_truth), on=['ticker', 'source_id'], how='left')
    stretches = scored_stretches(truth, ev, clean_truth)
    scored = label_rows(truth, ev, clean_truth)
    conf, conf_d = confidence_score(ev, scored)
    cln, cln_d = clean_score(truth, ev, stretches, ref)
    cons, cons_d = consistency_score(sol, data, clean_truth, full, ev, stretches, c_)
    # low signal dropped: a source's thin beginning distrusted and left blank
    th = ev.thin
    dropped = (th & ev.flag & ev.clean_ct.isna() & ev.clean_amt.isna())
    low_share = float(dropped.sum() / th.sum()) if th.any() else 1.0
    gates['low_signal_dropped'] = low_share >= LOW_SIGNAL_SHARE
    reward = (W_CONF * conf + W_CLEAN * cln * cons) * all(gates.values())
    unknown = ev.use & ev.flag & ~ev.label & ~known_rows(truth, ev)   # distrusted real data nobody has judged
    return reward, dict(gates=gates, ai_hits=hits, changed_on_truncation=leaks, rows_scored=int(ev.use.sum()),
                        low_signal=dict(rows=int(th.sum()), dropped_share=round(low_share, 3)),
                        unknown_flagged_rows=int(unknown.sum()), confidence_score=round(conf, 3),
                        clean_score=round(cln, 3), stability=round(cons, 3), confidence=conf_d, clean=cln_d,
                        consistency=cons_d)


def consistency_score(sol, data, clean_truth, full, ev, stretches, c_):
    """Stability: run the code on its own cleaned series and on the truth panel; see the module docstring."""
    cleaned = data.drop(columns=['ct', 'amt']).merge(
        full[KEYS + ['clean_ct', 'clean_amt']].rename(columns={'clean_ct': 'ct', 'clean_amt': 'amt'}), on=KEYS)
    cleaned = cleaned.dropna(subset=['ct', 'amt'])[data.columns]
    try:
        again = run(sol / 'score.py', cleaned, c_('self'))
        base = run(sol / 'score.py', clean_truth[data.columns], c_('truthrun'))
    except GateError as e:
        return 0.0, dict(error=str(e)[-500:])
    k = ev[KEYS].copy()
    k = k.merge(again[KEYS + ['confidence']].rename(columns={'confidence': 'confidence2'}), on=KEYS, how='left')
    k = k.merge(base[KEYS + ['confidence']].rename(columns={'confidence': 'confidence_t'}), on=KEYS, how='left')
    sc = stretches.to_numpy() & k.confidence2.notna().to_numpy()
    n_c = int((k.confidence2[sc] < 0.5).sum())
    n_t = int((k.confidence_t[sc] < 0.5).sum())
    n_bad = max(1, int((ev.use & ev.label).sum()))      # the task's untrustworthy rows: the scale of what is wrong
    return max(0.0, 1 - max(0, n_c - n_t) / n_bad), dict(distrusted_rows_cleaned=n_c, distrusted_rows_truth=n_t,
                                                         untrustworthy_rows=n_bad, rows=int(sc.sum()))


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
    for part in ('confidence', 'clean'):  # per kind
        for k in res.get(part, {}).get('by_kind', []):
            print('   ', part, k)


if __name__ == '__main__':
    main()
