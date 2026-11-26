"""Grade a solution on an anomaly_hard task:
    python grade.py TASK_DIR SOLUTION_DIR [--writeup PATH] [--json OUT] [--cache DIR] [--home TASK_DIR]

Grades every hidden panel of the task (tests/, then tests/panel-2, panel-3: the same hidden companies, each with its own
planted problems and disguise, so tuning to one panel does not pay); reward = the mean of the panels' rewards, 0 if
any panel fails an integrity gate (format, point in time, no AI, write-up). On each panel it runs SOLUTION_DIR/score.py
on the hidden panel (eval_panel.csv.gz), truncated at the gold's cutoffs and then whole, each run in an empty folder with the network off (its own network namespace where the machine allows it;
no proxy settings, minimal environment). Scores against the panel's gold (gold.json: every planted problem, exact) and
its truth panel (truth_panel.csv.gz: the hidden panel before the problems were planted, real events kept).

Gates (reward 0 if any fails):
  format         one output row per input row; confidence in [0, 1]; clean_ct, clean_amt blank or non-negative
  point_in_time  outputs on the truncated panels equal the full run's, all three columns
  no_ai          no model or network client imported or shelled out to
  writeup        SOLUTION_DIR/../output/writeup.md (or --writeup) exists and is not empty
  low_signal_dropped  at least LOW_SIGNAL_SHARE of the thin beginning's rows distrusted (confidence < 0.5) and blank
  continuous     confidence is a probability on a continuous scale, not a few levels (see continuous())

Data reward = W_CONF x confidence + W_CLEAN x cleaned series + W_STAB x stability (0.45 / 0.45 / 0.1). Also reported:
the three components and the geometric mean sqrt(confidence x cleaned series x stability) (reward_geometric).

Reward = data reward x (0.5 + 0.5 x writeup_score): the report graded on the task's visible panel and the solution's
own output on it (writeup.py, judge.md: code items and a model judge), so the report can halve the reward but never
earn it alone. The data reward alone when no judge can run (details.writeup says why) or with WRITEUP_JUDGE=skip.
--home TASK grades the report against the task it was written for, when the solution is graded on another task.

Scored rows (label_rows): from eval_start (one year in), not on low-volume series (ignore_series), not near
company-wide natural breaks (exclusions with no source), not on a closure's first year (exclusions of kind
recurring_first; in practice that year falls in the warm-up), not on a source's thin beginning: before a source is
established (its truth count's centred 28-day median has held thin_ct for THIN_ESTABLISHED days), rows with that
median under THIN_LO x thin_ct must be dropped (the gate); rows between THIN_LO and THIN_HI x thin_ct and THIN_EDGE
days either side of the stretch's edges are unscored. A source that thins after it was established is kept (scored
for the cleaned series). A planted problem's days before it shows in the data (`visible`, build.annotate_events: its
trailing 7-day median deviation reaches 3x the noise of a 7-day median of the source's relation to its sisters) are not
scored, nor a problem that never shows (`unscored`): no point-in-time code could know of them.

Confidence: read as the probability that the row's cleaned value is right (cleaned_right): within the source's own
  noise of the truth panel in count and in ticket size (right), or beyond NOISE_WRONG times it in either (wrong);
  rows in between are too close to call and not scored. There are no timing windows: a shift is wrong until the code
  has corrected it, a ramp while the correction lags, a return while the code still rescales, a one-day problem
  where the imputed value is still off; a company's real growth is never wrong (cleaned = raw = truth). Balanced
  Brier skill: 1 - (Brier on wrong rows, the mean within each kind of problem then over kinds; a wrong row with no
  planted problem near it is the code's own damage, kind 'other' + Brier on right rows) / 2 / 0.25, floored at 0
  (a constant 0.5 scores 0), times (0.5 + 0.5 x alert precision): an alert is a run of distrusted scored days on a
  source (gaps up to ALERT_GAP days joined, split every ALERT_DAYS days), precision the share that touch a wrong row.
  A panel with no wrong rows is scored on its right rows alone.

Cleaned series = gain x intact x kept, against the truth panel; a blank cleaned value counts as the raw value.
  gain    per kind, 1 - (cleaned error / raw error) pooled over the kind's problems' scored rows, each error = mean over
          count and dollars of |log value - log truth| beyond the source's own noise (own_noise; dollars: count and
          ticket noise combined), floored at 0; mean over kinds
  intact  share of scored rows no problem changed whose cleaned value is within the source's own noise of the truth,
          in count and in ticket
  kept    share of scored rows that should be kept (all but the thin beginning) not left blank

Stability: score.py run again on its own cleaned series (counts rounded, dollars to the cent, blank rows dropped) and
on the truth panel: 1 - (alerts on its cleaned series beyond the alerts on the truth panel) / (the panel's planted
problems that show), floored at 0. If a run fails, 0.

The write-up must exist (a gate); it is scored by writeup.py (see Reward above).
"""
from __future__ import annotations

import argparse
import ast
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

import writeup as writeup_grade  # the write-up rubric (writeup.py, judge.md)

KEYS = ['date', 'ticker', 'source_id']
OUT_COLS = ['confidence', 'clean_ct', 'clean_amt']
SETTLE_DAYS = 45            # build: marks a change slower than this to show as `slow` (informational; scored like any)
NOISE_WRONG = 2.0           # a cleaned value this many times the source's own noise off the truth is wrong (1x: right)
AFTER_DAYS = 30             # a wrong row within this many days after a problem ends is still that problem's
W_CONF, W_CLEAN, W_STAB = 0.45, 0.45, 0.1   # headline reward weights (confidence, cleaned series, stability)
ALERT_GAP = 2            # days of trust that still join two distrusted runs into one alert
ALERT_DAYS = 14           # an alert longer than two weeks counts as several
ONE_DAY = {'volume_spike', 'dropout', 'count_flood', 'dollar_spike', 'rollup'}   # planted one-day problems: one kind
MULTI_DAY = {'volume_block', 'outage'}   # a week or weeks too high or too low, then straight back: one kind
THIN_ESTABLISHED = 90    # a source is established once its median has held at thin_ct or more this many days running
THIN_LO, THIN_HI, THIN_EDGE = 0.8, 1.25, 14   # thin: truth count's 28-day median under THIN_LO x thin_ct must be
# dropped (distrusted, left blank); between THIN_LO and THIN_HI x thin_ct, and the first THIN_EDGE days of a thin
# stretch and the THIN_EDGE days after it, are not scored (the code cannot tell yet, point in time)
LOW_SIGNAL_SHARE = 0.9   # gate: share of a task's thin-beginning rows that must be distrusted and left blank
CONT_LO, CONT_HI = 0.01, 0.99   # gate continuous: rows scored strictly between these are checked (saturated ends left out)
CONT_DISTINCT, CONT_TOP = 20, 0.5   # at least this many distinct values over all scored rows; between the ends, no
CONT_MIN_BETWEEN = 50               # value on more than this share (tested once this many rows fall between them)
# imports or shell calls that reach a model or the network
NO_AI = re.compile(r'\b(anthropic|openai|google\.generativeai|google\.genai|mistralai|cohere|ollama|litellm|langchain|'
                   r'transformers|requests|httpx|aiohttp|urllib\.request|urllib3|http\.client|socket|websocket|'
                   r'curl|wget)\b')


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


def run(script: pathlib.Path, panel: pd.DataFrame, cache: pathlib.Path | None = None, keep_extra: bool = False) -> pd.DataFrame:
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
            env.update({k: v for k, v in os.environ.items() if k in ('ORACLE_TASK', 'ORACLE_TESTS')})
            cmd = (['unshare', '-n', '--'] if ISOLATE else []) + cmd
        else:
            if ISOLATE:
                if any(script.resolve().is_relative_to(d) for d in WRITABLE):   # hidden by the empty mounts: copy in
                    shutil.copytree(script.resolve().parent, work / 'solution')
                    cmd[1] = str(work / 'solution' / script.name)
                subprocess.run(['chmod', '-R', 'a+rX', str(pathlib.Path(cmd[1]).parent)], check=True)
            cmd = _sandboxed(cmd, work)
        r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=1200, env=env)
        if r.returncode:
            raise GateError(f'score.py failed: {r.stderr[-1500:]}')
        s = pd.read_csv(work / 'out.csv', parse_dates=['date'])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    check_format(panel, s)
    s['source_id'] = s.source_id.astype(int)
    s = s if keep_extra else s[KEYS + OUT_COLS]
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
    """Imports of a model or network client, or calls that load or shell out to one (parsed, so prose and comments
    that mention one are not hits; a file that does not parse is read line by line)."""
    hits = []
    for f in sorted(sol.rglob('*.py')):
        src = f.read_text(errors='replace')
        try:
            tree = ast.parse(src)
        except SyntaxError:
            for k, line in enumerate(src.splitlines(), 1):
                code = line.split('#', 1)[0]
                if re.search(r'\b(import|from|subprocess|os\.system|os\.popen)\b', code) and NO_AI.search(code):
                    hits.append(f'{f.name}:{k}: {line.strip()[:120]}')
            continue
        for n in ast.walk(tree):
            names = []
            if isinstance(n, ast.Import):
                names = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                names = [n.module or '']
            elif isinstance(n, ast.Call):
                fn = ast.unparse(n.func)
                if fn.split('.')[0] in ('subprocess', 'os') or fn in ('__import__', 'importlib.import_module'):
                    names = [ast.unparse(a) for a in n.args]
            if any(NO_AI.search(x) for x in names):
                hits.append(f'{f.name}:{n.lineno}: {(ast.get_source_segment(src, n) or "")[:120]}')
    return hits


def label_rows(truth: dict, ev: pd.DataFrame, clean_truth: pd.DataFrame | None = None) -> None:
    """Set ev['use'] (rows that can be scored: after the warm-up, not on low-volume series, not near company-wide natural
    breaks, not on thin stretches) and ev['thin'] (a source's thin beginning, which must be dropped: a gate)."""
    D = lambda n: pd.Timedelta(days=n)  # noqa: E731
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
    for tk, s, m in thin_parts:           # thin beginnings not excluded for another reason: must be dropped (a gate)
        m = m & ~excluded_thin(truth, ev, tk, s) & (ev.date >= pd.Timestamp(truth['eval_start']))
        ev.loc[m, 'thin'] = True


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
    return 'one_day' if t in ONE_DAY else 'multi_day' if t in MULTI_DAY else t


def cleaned_right(truth, ev, scored_rows) -> tuple[pd.Series, pd.Series, pd.Series]:
    """What confidence is scored against: is the row's cleaned value right? Right (1): within the source's own noise
    of the truth in count and in ticket size; wrong (0): beyond NOISE_WRONG times it in either; between: too close to
    call (NaN). A blank cleaned value counts as the raw value. Returns (target, kind, scored): the kind of planted
    problem whose span (start to end plus AFTER_DAYS) covers the row, 'fine' outside every span; and the rows scored
    (the cleaned series' stretches, not the thin beginning, not a problem's days before it shows in the data)."""
    lg = lambda x: np.log(np.maximum(x.astype(float), 0.01))  # noqa: E731
    cc = ev.clean_ct.where(ev.clean_ct.notna(), ev.ct)
    ca = ev.clean_amt.where(ev.clean_amt.notna(), ev.amt)
    dc = (lg(cc) - lg(ev.tct)).abs() / ev.sig_c
    dt = ((lg(ca) - lg(cc)) - (lg(ev.tamt) - lg(ev.tct))).abs() / ev.sig_t
    worst = np.maximum(dc, dt)
    target = pd.Series(np.where(worst <= 1, 1.0, np.where(worst >= NOISE_WRONG, 0.0, np.nan)), index=ev.index)
    k = pd.Series('fine', index=ev.index)
    hidden = pd.Series(False, index=ev.index)
    D = pd.Timedelta(days=1)
    for e in sorted(truth['events'], key=lambda e: -(pd.Timestamp(e['end']) - pd.Timestamp(e['start'])).days):
        ser = (ev.ticker == e['ticker']) & (ev.source_id == e['source_id'])
        first = pd.Timestamp(e.get('shift_start', e['start']))
        span = ser & ev.date.between(first, pd.Timestamp(e['end']) + AFTER_DAYS * D)   # the problem and its aftermath
        k[span] = kind(e['type'])                       # longest first, so a one-day problem inside a shift keeps its own
        if e.get('unscored'):                            # never stands out from the source's noise
            hidden |= ser & ev.date.between(first, pd.Timestamp(e['end']))
        elif e.get('visible'):                           # before it shows in the data nobody can know
            hidden |= ser & ev.date.between(first, pd.Timestamp(e['visible']) - D)
    scored = scored_rows & ~ev.thin & ~hidden & target.notna()
    return target, k, scored


def confidence_score(ev, target, kinds, scored):
    """Confidence read as the probability that the row's cleaned value is right. Brier against right (1) or wrong (0)
    in strata fixed before the outcome is known, so a calibrated probability scores best: each kind of planted problem
    (every scored row in its spans, right or wrong) and the fine rows outside every span. Balanced Brier skill:
    1 - (mean over kinds of their Brier + Brier on fine rows) / 2 / 0.25, floored at 0 (a constant 0.5 scores 0),
    times (0.5 + 0.5 x alert precision): an alert is a run of distrusted scored days on a source (gaps up to ALERT_GAP
    days joined, split every ALERT_DAYS days), true if it touches a wrong row inside a problem's span. A panel without
    planted problems is scored on its fine rows alone."""
    c = ev.confidence.astype(float).clip(0, 1)
    b = (c - target) ** 2
    fine_rows = scored & (kinds == 'fine')
    prob_rows = scored & (kinds != 'fine')
    fine = float(b[fine_rows].mean()) if fine_rows.any() else 0.0
    if not prob_rows.any():
        return max(0.0, 1 - fine / 0.25), dict(no_problem_rows=True, brier_fine=round(fine, 4),
                                               distrusted_share=round(float(ev.flag[scored].mean()), 4) if scored.any() else 0.0)
    per_kind = b[prob_rows].groupby(kinds[prob_rows]).mean()
    problems = float(per_kind.mean())
    skill = max(0.0, 1 - (0.5 * problems + 0.5 * fine) / 0.25)
    e_ = ev[scored].assign(hit=(prob_rows & (target == 0))[scored])
    n_alerts, true_alerts = alerts(e_)
    prec = true_alerts / n_alerts if n_alerts else 1.0       # no alerts: no false alarms
    wrong = scored & (target == 0)
    by_kind = pd.DataFrame(dict(rows=prob_rows.groupby(kinds).sum(), wrong_rows=wrong.groupby(kinds).sum(), brier=per_kind,
                                mean_confidence=c[prob_rows].groupby(kinds[prob_rows]).mean())).dropna().round(4)
    return skill * (0.5 + 0.5 * prec), dict(brier_skill=round(skill, 4), brier_problems=round(problems, 4),
                                             brier_fine=round(fine, 4), damaged_fine_rows=int((fine_rows & (target == 0)).sum()),
                                             alert_precision=round(prec, 3), alerts=n_alerts, true_alerts=true_alerts,
                                             by_kind=by_kind.reset_index(names='kind').to_dict('records'))


def continuous(ev) -> tuple[bool, dict]:
    """Confidence is a probability on a continuous scale, not a few levels. Judged on the rows the code doubts
    (confidence under CONT_HI, thin beginning left out), once there are CONT_MIN_BETWEEN of them: at least CONT_DISTINCT
    distinct values (3 decimals), and, once CONT_MIN_BETWEEN fall strictly between CONT_LO and CONT_HI, no single
    value on more than CONT_TOP of those. A code confident almost everywhere passes."""
    allv = ev[ev.use & ~ev.thin].confidence.round(3)
    doubt = allv[allv < CONT_HI]                     # the rows the code doubts: where a few fixed levels would show
    if len(doubt) < CONT_MIN_BETWEEN:                # confident almost everywhere: nothing to judge
        return True, dict(rows_doubted=len(doubt))
    u = doubt[doubt > CONT_LO]
    distinct = int(doubt.nunique())
    top = float(u.value_counts(normalize=True).iloc[0]) if len(u) >= CONT_MIN_BETWEEN else 0.0
    return distinct >= CONT_DISTINCT and top <= CONT_TOP, dict(rows_doubted=len(doubt), rows_between=len(u),
                                                                distinct=distinct, top_share=round(top, 3))


def own_noise(truth_panel: pd.DataFrame, thin_ct: float = 20) -> pd.DataFrame:
    """Per series: the robust spread of its daily relation to its peers' median (log count: sig_c, log ticket: sig_t),
    around its own 28-day median: how far a value can sit from the truth and still be within the source's noise.
    Measured on usable data only: a source's days whose 28-day median count is under thin_ct (a thin start, a series
    too small to score) neither count toward its own noise nor enter its peers' median (a series with too few usable
    days falls back to all of its days)."""
    out = []
    for tk, g in truth_panel.groupby('ticker'):
        ct = g.pivot(index='date', columns='source_id', values='ct')
        lc = np.log(ct.clip(lower=0.01))
        lt = np.log(g.pivot(index='date', columns='source_id', values='amt').clip(lower=0.01)) - lc
        usable = ct.rolling(28, min_periods=1, center=True).median() >= thin_ct
        for s in lc.columns:
            peers = [c for c in lc.columns if c != s]
            row = dict(ticker=tk, source_id=s)
            for name, x in (('sig_c', lc), ('sig_t', lt)):
                for mask in (usable, None):
                    xm = x.where(mask) if mask is not None else x
                    rel = xm[s] - (xm[peers].median(axis=1) if peers else 0)
                    r = (rel - rel.rolling(28, min_periods=7, center=True).median()).dropna()
                    if len(r) > 60 or mask is None:
                        break
                row[name] = max(float(1.4826 * (r - r.median()).abs().median()), 0.02) if len(r) > 20 else 0.15
            out.append(row)
    return pd.DataFrame(out)


def clean_score(truth, ev, scored_rows):
    """ev carries raw ct/amt, truth tct/tamt and the cleaned values (blank = raw); scored_rows: the stretches scored."""
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
    label_rows(truth, ev, clean_truth)
    stretches = ev.use | ev.midthin                    # an established source's thin stretches count for the cleaned series
    target, kinds, scored = cleaned_right(truth, ev, stretches)
    conf, conf_d = confidence_score(ev, target, kinds, scored)
    cln, cln_d = clean_score(truth, ev, stretches)
    n_problems = sum(not e.get('unscored') for e in truth['events'])
    cons, cons_d = consistency_score(sol, data, clean_truth, full, ev, stretches, c_, n_problems)
    # low signal dropped: a source's thin beginning distrusted and left blank
    th = ev.thin
    dropped = (th & ev.flag & ev.clean_ct.isna() & ev.clean_amt.isna())
    low_share = float(dropped.sum() / th.sum()) if th.any() else 1.0
    gates['low_signal_dropped'] = low_share >= LOW_SIGNAL_SHARE
    gates['continuous'], cont_d = continuous(ev)
    ok = all(gates.values())
    reward = (W_CONF * conf + W_CLEAN * cln + W_STAB * cons) * ok           # headline: a weighted average
    geo = float(np.sqrt(max(conf, 0.0) * max(cln * cons, 0.0))) * ok      # reported: the geometric mean
    return reward, dict(gates=gates, ai_hits=hits, changed_on_truncation=leaks, rows_scored=int(ev.use.sum()),
                        reward_geometric=round(geo, 3),
                        low_signal=dict(rows=int(th.sum()), dropped_share=round(low_share, 3)), continuity=cont_d,
                        confidence_score=round(conf, 3),
                        clean_score=round(cln, 3), stability=round(cons, 3), confidence=conf_d, clean=cln_d,
                        consistency=cons_d)


def consistency_score(sol, data, clean_truth, full, ev, stretches, c_, n_problems):
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
    k = k[sc]
    n_c = alerts(k.assign(flag=k.confidence2 < 0.5, hit=False))[0]
    n_t = alerts(k.assign(flag=k.confidence_t < 0.5, hit=False))[0]
    # each alarm raised on its own cleaned output beyond those raised on clean data costs 1 / (the panel's problems)
    extra = max(0, n_c - n_t)
    return max(0.0, 1 - extra / max(1, n_problems)), dict(alerts_on_cleaned=n_c, alerts_on_truth=n_t,
                                                          extra_alerts=extra, problems=n_problems, rows=int(sc.sum()))


def alerts(e_: pd.DataFrame) -> tuple[int, int]:
    """Alerts: runs of distrusted scored days on a source (gaps of up to ALERT_GAP days joined), each split into pieces
    of at most ALERT_DAYS days (so distrusting a long stretch counts as many alerts, not one); and how many touch an
    wrong row (column hit)."""
    n = hit = 0
    for _, g in e_[e_.flag].sort_values('date').groupby(['ticker', 'source_id']):
        run_id = (g.date.diff().dt.days.fillna(999) > ALERT_GAP + 1).cumsum()
        piece = (g.date - g.groupby(run_id).date.transform('min')).dt.days // ALERT_DAYS
        runs = g.groupby([run_id, piece]).hit.any()
        n += len(runs); hit += int(runs.sum())
    return n, hit


INTEGRITY = ('format', 'point_in_time', 'no_ai', 'writeup')   # any panel failing one of these: reward 0


def panels(task: pathlib.Path) -> list[pathlib.Path]:
    """The task's hidden panels: tests/ itself, then tests/panel-2, panel-3, ..."""
    return [task / 'tests'] + sorted((p for p in (task / 'tests').glob('panel-*') if p.is_dir()),
                                     key=lambda p: int(p.name.split('-')[1]))


def grade_task(task: pathlib.Path, sol: pathlib.Path, writeup: pathlib.Path, cache: pathlib.Path | None = None,
               home: pathlib.Path | None = None):
    """Grade every hidden panel (data reward = the mean of their rewards, 0 if any fails an integrity gate), then the
    write-up on the visible panel of `home` (the task it was written for; default this task): reward = data reward x
    (0.5 + 0.5 x writeup_score), or the data reward alone when no judge can run. Panel 1's details stay at the top
    level; every panel's summary is in `panels`, the write-up's grade in `writeup`."""
    rows, first = [], None
    for k, tests in enumerate(panels(task), 1):
        truth = json.loads((tests / 'gold.json').read_text())
        data = pd.read_csv(tests / 'eval_panel.csv.gz', parse_dates=['date'])
        clean_truth = pd.read_csv(tests / 'truth_panel.csv.gz', parse_dates=['date'])
        os.environ['ORACLE_TESTS'] = str(tests.resolve())   # forwarded to the grader's own check solutions only
        try:
            reward, d = score(truth, data, clean_truth, sol, writeup, (cache / f'panel-{k}') if cache else None)
        finally:
            os.environ.pop('ORACLE_TESTS', None)
        first = first or d
        rows.append(dict(panel=k, reward=round(reward, 3), gates=d['gates'], **{x: d.get(x) for x in (
            'confidence_score', 'clean_score', 'stability', 'reward_geometric')}))
        if not all(d['gates'].get(g, True) for g in INTEGRITY):
            break                                         # an integrity failure ends grading
    ok = all(all(r['gates'].get(g, True) for g in INTEGRITY) for r in rows)
    data_reward = float(np.mean([r['reward'] for r in rows])) * ok
    mean = lambda x: round(float(np.mean([r[x] or 0 for r in rows])), 3)  # noqa: E731
    gates = {g: all(r['gates'].get(g, True) for r in rows) for g in first['gates']}
    w = None
    if ok and os.environ.get('WRITEUP_JUDGE') != 'skip':
        h = home or task
        try:
            w = writeup_grade.grade(h, sol, writeup, run, (cache.parent / f'writeup-{h.name}') if cache else None)
        except GateError as e:                 # the code failed on the visible panel: no report can be checked
            w = dict(writeup_score=0.0, judge=f'score.py failed on the visible panel: {str(e)[-300:]}')
        except RuntimeError as e:              # the judge itself could not run: the data reward stands alone
            w = dict(writeup_score=None, judge=f'not graded: {str(e)[-300:]}')
    ws = (w or {}).get('writeup_score')
    reward = data_reward * (0.5 + 0.5 * ws) if ws is not None else data_reward
    return reward, dict(first, gates=gates, data_reward=round(data_reward, 3), writeup=w,
                        confidence_score=mean('confidence_score'), clean_score=mean('clean_score'),
                        stability=mean('stability'), reward_geometric=mean('reward_geometric'), panels=rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('task'); ap.add_argument('solution'); ap.add_argument('--json')
    ap.add_argument('--writeup'); ap.add_argument('--cache')
    ap.add_argument('--home', help='the task the write-up was written for (default: TASK)')
    a = ap.parse_args()
    task, sol = pathlib.Path(a.task), pathlib.Path(a.solution).resolve()
    writeup = pathlib.Path(a.writeup) if a.writeup else sol.parent / 'output' / 'writeup.md'
    if ISOLATE:
        (task / 'tests').chmod(0o700)    # grader-only: out of reach of the scorer, which runs as nobody
    reward, d = grade_task(task, sol, writeup, pathlib.Path(a.cache) if a.cache else None,
                          pathlib.Path(a.home) if a.home else None)
    d['isolation'] = 'nobody, offline, no shared writable folders' if ISOLATE else 'off (not root): grading only'
    res = dict(task=task.name, solution=str(sol), reward=round(reward, 3), **d)
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, indent=1, default=str))
    short = {k: v for k, v in res.items() if k not in ('confidence', 'clean', 'solution', 'changed_on_truncation')}
    print(json.dumps(short, default=str))


if __name__ == '__main__':
    main()
