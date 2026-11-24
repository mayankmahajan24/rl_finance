"""Grade a solution on an anomaly_hard task:
    python grade.py TASK_DIR SOLUTION_DIR [--writeup PATH] [--json OUT] [--cache DIR]

Runs SOLUTION_DIR/score.py on the task's hidden panel (tests/eval_panel.csv.gz), truncated at the gold's cutoffs and
then whole, each run in an empty folder with the network off (its own network namespace where the machine allows it;
no proxy settings, minimal environment). Scores against the gold (tests/gold.json: every planted problem, exact) and
the truth panel (tests/truth_panel.csv.gz: the hidden panel before the problems were planted, real events kept).

Gates (reward 0 if any fails):
  format         one output row per input row; confidence in [0, 1]; clean_ct, clean_amt blank or non-negative
  point_in_time  outputs on the truncated panels equal the full run's, all three columns
  no_ai          no model or network client imported or shelled out to
  writeup        SOLUTION_DIR/../output/writeup.md (or --writeup) exists and is not empty
  low_signal_dropped  at least LOW_SIGNAL_SHARE of the thin beginning's rows distrusted (confidence < 0.5) and blank
  detects        confidence score at least MIN_CONFIDENCE (repairing the series without detecting problems cannot pass)

Reward = W_CONF x confidence + W_CLEAN x cleaned series + W_STAB x stability (0.4 / 0.4 / 0.2). Also reported: the
three components and the geometric mean sqrt(confidence x cleaned series x stability) (reward_geometric).

Scored rows (label_rows): from eval_start (one year in), not on low-volume series (ignore_series), not near
company-wide natural breaks (exclusions with no source), not on a closure's first year (exclusions of kind
recurring_first). Timing, from what a point-in-time scorer could see (build.annotate_events, written into the gold):
  * a problem is scored from the day it becomes `visible` (its trailing 7-day median deviation reaches 3x the source's
    own noise); a level change that never does is `unscored`; one that takes over SETTLE_DAYS to show is `slow`
    (cleaned series only; for confidence unscored until settled, then trusted)
  * one-day problems: every day untrustworthy
  * level changes: the first CHANGE_DAYS from when visible untrustworthy, unscored up to SETTLE_DAYS while the code
    decides, then the new level trusted; after a temporary change ends, SETTLE_DAYS unscored, then trusted
  * thin beginning: before a source is established (its truth count's centred 28-day median has held thin_ct for
    THIN_ESTABLISHED days), rows with that median under THIN_LO x thin_ct must be dropped (the gate); rows between
    THIN_LO and THIN_HI x thin_ct and THIN_EDGE days either side of the stretch's edges are unscored. A source that
    thins after it was established is kept (scored for the cleaned series).

Confidence = F1(alert precision, recall).
  recall           share of problems with any untrustworthy day distrusted, per kind (the four one-day kinds are one
                   kind), mean over kinds
  alert precision  alerts are runs of distrusted scored days on a source, gaps up to ALERT_GAP days joined, split every
                   ALERT_DAYS days; the share that touch an untrustworthy row
  A panel with no untrustworthy rows (a control): the share of scored rows trusted.

Cleaned series = gain x intact x kept, against the truth panel; a blank cleaned value counts as the raw value.
  gain    per kind, 1 - (cleaned error / raw error) pooled over the kind's problems' scored rows, each error = mean over
          count and dollars of |log value - log truth| beyond the source's own noise (own_noise; dollars: count and
          ticket noise combined), floored at 0; mean over kinds
  intact  share of scored rows no problem changed whose cleaned value is within the source's own noise of the truth,
          in count and in ticket
  kept    share of scored rows that should be kept (all but the thin beginning) not left blank

Stability: score.py run again on its own cleaned series (blank rows dropped) and on the truth panel: 1 - (rows
distrusted on its cleaned series beyond those distrusted on the truth panel) / (rows of the task's scored problems,
in either score; a panel with none: its scored rows), floored at 0. If a run fails, 0.

The write-up's quality is judged separately (not in this reward).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

KEYS = ['date', 'ticker', 'source_id']
OUT_COLS = ['confidence', 'clean_ct', 'clean_amt']
CHANGE_DAYS, SETTLE_DAYS = 14, 45
W_CONF, W_CLEAN, W_STAB = 0.4, 0.4, 0.2   # headline reward weights (confidence, cleaned series, stability)
ALERT_GAP = 2            # days of trust that still join two distrusted runs into one alert
ALERT_DAYS = CHANGE_DAYS  # an alert longer than a change's onset window counts as several
ONE_DAY = {'volume_spike', 'dropout', 'count_flood', 'dollar_spike'}   # planted one-day problems: one kind
THIN_ESTABLISHED = 90    # a source is established once its median has held at thin_ct or more this many days running
THIN_LO, THIN_HI, THIN_EDGE = 0.8, 1.25, 14   # thin: truth count's 28-day median under THIN_LO x thin_ct must be
# dropped (distrusted, left blank); between THIN_LO and THIN_HI x thin_ct, and the first THIN_EDGE days of a thin
# stretch and the THIN_EDGE days after it, are not scored (the code cannot tell yet, point in time)
LOW_SIGNAL_SHARE = 0.9   # gate: share of a task's thin-beginning rows that must be distrusted and left blank
MIN_CONFIDENCE = 0.25    # gate: the confidence score a solution must reach (it must actually detect problems)
# imports or shell calls that reach a model or the network
NO_AI = re.compile(r'\b(anthropic|openai|google\.generativeai|google\.genai|mistralai|cohere|ollama|litellm|langchain|'
                   r'transformers|requests|httpx|aiohttp|urllib\.request|urllib3|http\.client|socket|websocket|'
                   r'curl|wget)\b')


def f1(p, r):
    return 2 * p * r / (p + r) if p + r else 0.0


class GateError(Exception):
    pass


HERE = pathlib.Path(__file__).resolve().parent
# grader checks that read the gold on purpose (ORACLE_TASK): only these run as root with the task folder visible
TRUSTED = {HERE / 'solutions' / n / 'score.py' for n in ('oracle', 'ceiling', 'ceiling_ideal', 'distrust_all')}
WRITABLE = ('/tmp', '/var/tmp', '/dev/shm', '/run/lock', '/var/lib/php/sessions')   # shared folders anyone can write
WORK_ROOT = pathlib.Path('/var/lib/anomaly_hard_grade')     # run folders (not under /tmp, which each run gets empty)


def _can_isolate() -> bool:
    """Root with network and mount namespaces: the scorer can run as nobody, offline, with nothing shared to write."""
    if os.geteuid() != 0:
        return False
    try:
        return subprocess.run(['unshare', '-n', '-m', '--', 'true'], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


ISOLATE = _can_isolate()


def _sandboxed(cmd: list[str], work: pathlib.Path) -> list[str]:
    """Agent code: its own network namespace (nothing reachable), its own mount namespace with every shared writable
    folder replaced by an empty one (no memory between runs), and run as nobody (the task's tests/, root-only, is out
    of reach). Elsewhere (not root): the bare command, and the result says isolation is off."""
    if not ISOLATE:
        return cmd
    mounts = ' '.join(f'[ -d {d} ] && mount -t tmpfs -o size=256m,mode=1777 tmpfs {d};' for d in WRITABLE)
    inner = ' '.join(shlex.quote(c) for c in ['setpriv', '--reuid=nobody', '--regid=nogroup', '--clear-groups', '--'] + cmd)
    return ['unshare', '-n', '-m', '--propagation', 'private', '--', 'sh', '-c', f'{mounts} cd {shlex.quote(str(work))} && exec {inner}']


def run(script: pathlib.Path, panel: pd.DataFrame, cache: pathlib.Path | None = None) -> pd.DataFrame:
    if cache and cache.exists():
        return pd.read_csv(cache, parse_dates=['date'])
    trusted = script.resolve() in TRUSTED
    WORK_ROOT.mkdir(mode=0o711, parents=True, exist_ok=True) if ISOLATE else None
    work = pathlib.Path(tempfile.mkdtemp(dir=WORK_ROOT if ISOLATE else None))
    try:
        work.chmod(0o777)
        panel.to_csv(work / 'in.csv', index=False, date_format='%Y-%m-%d')
        (work / 'in.csv').chmod(0o644)
        env = {'PATH': os.environ['PATH'], 'HOME': str(work)}            # no proxy settings: no network
        cmd = [sys.executable, str(script), '--input', str(work / 'in.csv'), '--output', str(work / 'out.csv')]
        if trusted:                      # grader checks only: they read the gold through ORACLE_TASK
            env.update({k: v for k, v in os.environ.items() if k == 'ORACLE_TASK'})
            cmd = (['unshare', '-n', '--'] if ISOLATE else []) + cmd
        else:
            if ISOLATE:
                subprocess.run(['chmod', '-R', 'a+rX', str(script.parent)], check=True)
            cmd = _sandboxed(cmd, work)
        r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=1200, env=env)
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
        if e.get('slow'):                  # no onset to date: confidence not scored until it has settled, then trusted
            quiet |= ser & (ev.date >= first) & (ev.date <= max(a + D(SETTLE_DAYS - 1), pd.Timestamp(e.get('settle', a))))
            continue
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
    table = []
    for e, m in scored:
        days = ev.date[m & ev.flag]
        table.append(dict(type=e['type'], kind=kind(e['type']), part=e.get('part', ''), ticker=e['ticker'],
                          source_id=e['source_id'], start=e['start'], end=e['end'], days=int(m.sum()),
                          distrusted_days=int((m & ev.flag).sum()),
                          delay_days=int((days.min() - pd.Timestamp(e['start'])).days) if len(days) else None))
    t = pd.DataFrame(table)
    t['caught'] = (t.distrusted_days > 0).astype(float)
    by_kind = t.groupby('kind').agg(events=('caught', 'size'), caught=('caught', 'mean'), days=('days', 'sum'),
                                    distrusted_days=('distrusted_days', 'sum'))
    # recall = share of problems caught (averaged within each kind, then over kinds); precision = share of alerts
    # (runs of distrusted days on a source) that touch a problem
    recall = float(by_kind.caught.mean())
    n_alerts, true_alerts = alerts(e_)
    alert_prec = true_alerts / n_alerts if n_alerts else 0.0
    score = f1(alert_prec, recall)
    return score, dict(alert_precision=round(alert_prec, 3), recall=round(recall, 3), alerts=n_alerts,
                       true_alerts=true_alerts, by_kind=by_kind.round(3).reset_index().to_dict('records'), events=table)


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


def clean_score(truth, ev, scored_rows):
    """ev carries raw ct/amt, truth tct/tamt and the cleaned values (blank = raw); scored_rows is the scored mask
    before label_rows forced labelled rows in (the cleaned series is scored on the same stretches)."""
    lg = lambda x: np.log(np.maximum(x.astype(float), 0.01))  # noqa: E731
    cc = ev.clean_ct.where(ev.clean_ct.notna(), ev.ct)
    ca = ev.clean_amt.where(ev.clean_amt.notna(), ev.amt)
    err_raw = 0.5 * ((lg(ev.ct) - lg(ev.tct)).abs() + (lg(ev.amt) - lg(ev.tamt)).abs())
    err_cln = 0.5 * ((lg(cc) - lg(ev.tct)).abs() + (lg(ca) - lg(ev.tamt)).abs())
    changed = err_raw > 1e-6
    unscored = pd.Series(False, index=ev.index)        # rows of problems before they show (not scored)
    gains = []
    sig_a = np.hypot(ev.sig_c, ev.sig_t)              # dollars = count x ticket: their noises add
    beyond = lambda d, s: (d.abs() - s).clip(lower=0)  # noqa: E731   error beyond the source's own noise
    for e in truth['events']:
        ser = (ev.ticker == e['ticker']) & (ev.source_id == e['source_id'])
        first = pd.Timestamp(e.get('shift_start', e['start']))
        span = ser & ev.date.between(first, pd.Timestamp(e['end']))
        if e.get('unscored'):
            unscored |= span                              # not scored, and not counted as untouched rows either
            continue
        if e.get('visible'):                              # before it was visible, it is not scored
            unscored |= span & (ev.date < pd.Timestamp(e['visible']))
            span &= ev.date >= pd.Timestamp(e['visible'])
        er = 0.5 * (beyond(lg(ev.ct) - lg(ev.tct), ev.sig_c) + beyond(lg(ev.amt) - lg(ev.tamt), sig_a))
        ec = 0.5 * (beyond(lg(cc) - lg(ev.tct), ev.sig_c) + beyond(lg(ca) - lg(ev.tamt), sig_a))
        m = span & changed & scored_rows & ~ev.thin & (er > 1e-6)
        if not m.any():
            continue
        g = max(0.0, 1 - ec[m].sum() / er[m].sum())
        gains.append(dict(type=e['type'], kind=kind(e['type']), ticker=e['ticker'], source_id=e['source_id'],
                          start=e['start'], rows=int(m.sum()), raw_total=float(er[m].sum()), clean_total=float(ec[m].sum()),
                          raw_error=round(float(er[m].mean()), 3), clean_error=round(float(ec[m].mean()), 3), gain=round(g, 3)))
    # rows no problem touched should be left as they are: intact = within the source's own noise of the truth
    ok = scored_rows & ~changed & ~unscored & ~ev.thin
    dc, dt = (lg(cc) - lg(ev.tct)).abs(), ((lg(ca) - lg(cc)) - (lg(ev.tamt) - lg(ev.tct))).abs()
    intact_rows = (dc <= ev.sig_c) & (dt <= ev.sig_t)
    intact = float(intact_rows[ok].mean()) if ok.any() else 1.0
    keep = scored_rows & ~ev.thin
    blank = int((keep & (ev.clean_ct.isna() | ev.clean_amt.isna())).sum())
    kept = 1 - blank / int(keep.sum()) if keep.any() else 1.0
    if gains:
        g = pd.DataFrame(gains)
        # per kind, the share of its error (beyond noise) repaired, pooled over its problems (a problem that barely
        # moved the series weighs little); then the mean over kinds
        tot = g.groupby('kind')[['raw_total', 'clean_total']].sum()
        gain = float((1 - tot.clean_total / tot.raw_total).clip(lower=0).mean())
        g = g.drop(columns=['raw_total', 'clean_total'])
        gains = g.to_dict('records')
        by_kind = g.groupby('kind').agg(events=('gain', 'size'), raw_error=('raw_error', 'mean'),
                                        clean_error=('clean_error', 'mean'))
        by_kind['gain'] = (1 - tot.clean_total / tot.raw_total).clip(lower=0)
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
    ev = ev.merge(own_noise(clean_truth), on=['ticker', 'source_id'], how='left')
    stretches = scored_stretches(truth, ev, clean_truth)
    scored = label_rows(truth, ev, clean_truth)
    conf, conf_d = confidence_score(ev, scored)
    cln, cln_d = clean_score(truth, ev, stretches)
    problem_rows = max(int((ev.use & ev.label).sum()), sum(x['rows'] for x in cln_d.get('events', [])))
    cons, cons_d = consistency_score(sol, data, clean_truth, full, ev, stretches, c_, problem_rows)
    # low signal dropped: a source's thin beginning distrusted and left blank
    th = ev.thin
    dropped = (th & ev.flag & ev.clean_ct.isna() & ev.clean_amt.isna())
    low_share = float(dropped.sum() / th.sum()) if th.any() else 1.0
    gates['low_signal_dropped'] = low_share >= LOW_SIGNAL_SHARE
    gates['detects'] = conf >= MIN_CONFIDENCE                          # cleaning alone cannot pass
    ok = all(gates.values())
    reward = (W_CONF * conf + W_CLEAN * cln + W_STAB * cons) * ok           # headline: a weighted average
    geo = float(np.sqrt(max(conf, 0.0) * max(cln * cons, 0.0))) * ok      # reported: the geometric mean
    return reward, dict(gates=gates, ai_hits=hits, changed_on_truncation=leaks, rows_scored=int(ev.use.sum()),
                        reward_geometric=round(geo, 3),
                        low_signal=dict(rows=int(th.sum()), dropped_share=round(low_share, 3)),
                        confidence_score=round(conf, 3),
                        clean_score=round(cln, 3), stability=round(cons, 3), confidence=conf_d, clean=cln_d,
                        consistency=cons_d)


def consistency_score(sol, data, clean_truth, full, ev, stretches, c_, problem_rows):
    """Stability: run the code on its own cleaned series and on the truth panel; see the module docstring."""
    cleaned = data.drop(columns=['ct', 'amt']).merge(
        full[KEYS + ['clean_ct', 'clean_amt']].rename(columns={'clean_ct': 'ct', 'clean_amt': 'amt'}), on=KEYS)
    cleaned = cleaned.dropna(subset=['ct', 'amt'])[data.columns]
    cleaned['ct'] = cleaned.ct.round().clip(lower=1).astype(int)          # reported like raw data: whole counts,
    cleaned['amt'] = cleaned.amt.round(2).clip(lower=0.01)                # dollars to the cent
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
    # the scale of what is wrong: rows of scored problems, in either score; a panel with none: its scored rows (as for
    # confidence on a clean panel, the share of rows the code keeps trusting)
    n_bad = problem_rows if problem_rows else max(1, int(sc.sum()))
    return max(0.0, 1 - max(0, n_c - n_t) / n_bad), dict(distrusted_rows_cleaned=n_c, distrusted_rows_truth=n_t,
                                                         untrustworthy_rows=n_bad, rows=int(sc.sum()))


def alerts(e_: pd.DataFrame) -> tuple[int, int]:
    """Alerts: runs of distrusted scored days on a source (gaps of up to ALERT_GAP days joined), each split into pieces
    of at most ALERT_DAYS days (so distrusting a long stretch counts as many alerts, not one); and how many touch an
    untrustworthy row."""
    n = hit = 0
    for _, g in e_[e_.flag].sort_values('date').groupby(['ticker', 'source_id']):
        run_id = (g.date.diff().dt.days.fillna(999) > ALERT_GAP + 1).cumsum()
        piece = (g.date - g.groupby(run_id).date.transform('min')).dt.days // ALERT_DAYS
        runs = g.groupby([run_id, piece]).label.any()
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
    if ISOLATE:
        (task / 'tests').chmod(0o700)    # grader-only: out of reach of the scorer, which runs as nobody
    reward, d = score(truth, data, clean_truth, sol, writeup, pathlib.Path(a.cache) if a.cache else None)
    d['isolation'] = 'nobody, offline, no shared writable folders' if ISOLATE else 'off (not root): grading only'
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
