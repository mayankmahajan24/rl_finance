"""Reference solution for the data-validation audit task.

A battery of independent, explainable checks over the full history (an audit may look at all of it):
  1. exact duplicate rows                       -> duplicate_rows
  2. implausible ticket size (amt / ct)         -> swapped_columns (ticket collapses) / unit_scale (x100 jump)
  3. runs of missing / near-zero days           -> outage (merged to ticker-wide when most sources go dark)
  4. weekly-cycle misalignment vs peer sensors  -> date_shift (CUSUM change-point on a lag statistic)
  5. step changes in the ticker-wide level      -> ticker_remap
  6. step changes vs peer sensors (same ticker) -> series_swap / double_count / level_shift
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

APP = Path(os.environ.get('APP_DIR', '/app'))
MIN_CT = 10


def runs(mask: pd.Series, min_len: int, max_gap: int = 2):
    """Contiguous True runs (allowing short gaps) of at least min_len days -> list of (start, end)."""
    idx = mask[mask].index
    out = []
    if len(idx) == 0:
        return out
    start = prev = idx[0]
    for d in idx[1:]:
        if (d - prev).days > max_gap + 1:
            if (prev - start).days + 1 >= min_len:
                out.append((start, prev))
            start = d
        prev = d
    if (prev - start).days + 1 >= min_len:
        out.append((start, prev))
    return out


def step_stat(x: pd.Series, w=28, min_obs=14):
    """median(next w days incl. t) - median(previous w days) for every t."""
    fwd = x[::-1].rolling(w, min_periods=min_obs).median()[::-1]
    back = x.shift(1).rolling(w, min_periods=min_obs).median()
    return fwd - back


def peaks(stat: pd.Series, thr: float, sep: int = 45):
    """Dates where |stat| is a local maximum above thr, at least `sep` days apart."""
    a = stat.abs()
    cand = a[a > thr].sort_values(ascending=False)
    chosen = []
    for d, v in cand.items():
        if all(abs((d - c).days) > sep for c in chosen):
            chosen.append(d)
    return sorted(chosen)


def refine(x: pd.Series, p, w=7, search=21):
    """Sharpen a step date: the day within +/-search days with the largest 7-day before/after change."""
    loc = step_stat(x, w=w, min_obs=4).loc[p - pd.Timedelta(days=search):p + pd.Timedelta(days=search)].abs()
    return loc.idxmax() if loc.notna().any() else p


def near(d, windows, pad):
    return any(s - pd.Timedelta(days=pad) <= d <= e + pd.Timedelta(days=pad) for s, e in windows)


def main():
    df = pd.read_csv(APP / 'data' / 'transactions.csv', parse_dates=['date'])
    issues = []
    fmt = lambda d: None if d is None else pd.Timestamp(d).strftime('%Y-%m-%d')  # noqa: E731

    # 1. duplicates --------------------------------------------------------------------------------
    dup = df.duplicated(['date', 'ticker', 'source_id'], keep='first')
    for (t, s), g in df[dup].groupby(['ticker', 'source_id']):
        issues.append(dict(type='duplicate_rows', ticker=t, source_id=int(s), start=fmt(g.date.min()),
                           end=fmt(g.date.max()), evidence=f'{len(g)} repeated (date, ticker, source) rows'))
    d = df[~dup]
    dates = pd.date_range(d.date.min(), d.date.max())
    ct = d.pivot_table(index='date', columns=['ticker', 'source_id'], values='ct', aggfunc='first').reindex(dates)
    amt = d.pivot_table(index='date', columns=['ticker', 'source_id'], values='amt', aggfunc='first').reindex(dates)
    started = ct.notna().cummax()
    med = ct.median()
    good = [c for c in ct.columns if med[c] >= MIN_CT]
    bad_days = {c: [] for c in ct.columns}          # windows to mask from the level analysis

    # 2. ticket-size checks -------------------------------------------------------------------------
    for c in good:
        tk = np.log((amt[c] / ct[c]).where(ct[c] >= 3))
        ref = tk.shift(1).rolling(90, min_periods=20).median()
        dev = tk - ref
        for s0, s1 in runs(dev < -np.log(20), 5):
            issues.append(dict(type='swapped_columns', ticker=c[0], source_id=int(c[1]), start=fmt(s0), end=fmt(s1),
                               evidence='ticket size (amt/ct) collapses by >20x: ct and amt look swapped'))
            bad_days[c].append((s0, s1))
            tk.loc[s0:s1] = np.nan
        dev = tk - tk.shift(1).rolling(90, min_periods=20).median()
        for s0, s1 in runs(dev > np.log(20), 10):
            issues.append(dict(type='unit_scale', ticker=c[0], source_id=int(c[1]), start=fmt(s0), end=None,
                               evidence='ticket size jumps ~100x and stays: amounts look like cents'))

    # 3. outages ------------------------------------------------------------------------------------
    filled = ct.fillna(0).where(started)
    for c in good:
        for s0, s1 in bad_days[c]:
            filled.loc[s0:s1, c] = np.nan
    out_series = {}
    for c in good:
        base = filled[c].rolling(240, center=True, min_periods=60).quantile(0.75)
        dark = (filled[c] < 0.15 * base) & (base >= MIN_CT)
        rr = [r for r in runs(dark, 7) if not any(r[0] <= e and r[1] >= s for s, e in bad_days[c])]
        out_series[c] = rr
        bad_days[c] += rr
    for t in sorted({c[0] for c in good}):
        cols = [c for c in good if c[0] == t]
        all_runs = [(c, r) for c in cols for r in out_series[c]]
        used = set()
        for c, (s0, s1) in all_runs:
            if (c, s0) in used:
                continue
            group = [(c2, r2) for c2, r2 in all_runs if abs((r2[0] - s0).days) <= 10]
            if len({g[0] for g in group}) >= max(2, int(np.ceil(0.6 * len(cols)))):
                issues.append(dict(type='outage', ticker=t, source_id=None, start=fmt(min(g[1][0] for g in group)),
                                   end=fmt(max(g[1][1] for g in group)), evidence='most sensors go dark together'))
                used |= {(g[0], g[1][0]) for g in group}
            else:
                issues.append(dict(type='outage', ticker=t, source_id=int(c[1]), start=fmt(s0), end=fmt(s1),
                                   evidence='sensor reports no / near-zero volume for 7+ days'))
                used.add((c, s0))

    # log level with problem days masked (x_raw keeps them, for ticker-wide break detection)
    x_raw = np.log(ct.clip(lower=1)); x_raw = x_raw - x_raw.median()
    x = np.log(ct.clip(lower=1))
    for c in ct.columns:
        for s0, s1 in bad_days[c]:
            x.loc[s0:s1, c] = np.nan
    x = x - x.median()          # put every sensor on a common scale before comparing with peers
    tickers = sorted({c[0] for c in good})

    # 4. date shift: does the sensor's weekly cycle line up with peers' cycle one day earlier? -------
    w = x - x.rolling(7, center=True, min_periods=5).mean()
    for t in tickers:
        cols = [c for c in good if c[0] == t]
        if len(cols) < 3:
            continue
        for c in cols:
            peer = w[[o for o in cols if o != c]].median(axis=1)
            z = (w[c] * (peer.shift(1) - peer)).fillna(0)
            cs = (z - z.mean()).cumsum()
            k = int(np.argmin(cs.values))
            after, before = z.iloc[k + 1:], z.iloc[:k + 1]
            if len(after) < 60 or len(before) < 60:
                continue
            tstat = after.mean() / (after.std() / np.sqrt(len(after)) + 1e-12)
            if after.mean() > 0 and before.mean() < 0 and tstat > 5:
                issues.append(dict(type='date_shift', ticker=t, source_id=int(c[1]), start=fmt(z.index[k + 1]), end=None,
                                   evidence='weekly pattern now matches peers one day earlier (dates off by a day)'))

    # 5. ticker-wide level breaks -------------------------------------------------------------------
    remaps = {}
    for t in tickers:
        cols = [c for c in good if c[0] == t]
        cons = x_raw[cols].median(axis=1)
        st = step_stat(cons)
        outs = [(pd.Timestamp(i['start']), pd.Timestamp(i['end'])) for i in issues
                if i['type'] == 'outage' and i['ticker'] == t]
        for p in peaks(st, np.log(3), sep=90):
            p = refine(cons, p)
            after = cons.loc[p + pd.Timedelta(days=7):p + pd.Timedelta(days=60)].median()
            before = cons.loc[p - pd.Timedelta(days=210):p - pd.Timedelta(days=30)].median()
            if after - before > np.log(3):            # an outage recovery returns to the old level; a re-map does not
                issues.append(dict(type='ticker_remap', ticker=t, source_id=None, start=fmt(p), end=None,
                                   evidence=f'every sensor steps up ~{np.exp(after - before):.1f}x on the same date'))
                remaps[t] = p
    # low volume before a re-map is not an outage
    issues = [i for i in issues if not (i['type'] == 'outage' and i['ticker'] in remaps and
                                        pd.Timestamp(i['end']) <= remaps[i['ticker']] + pd.Timedelta(days=30))]

    # 6. sensor-vs-peer steps -----------------------------------------------------------------------
    events = []
    for t in tickers:
        cols = [c for c in good if c[0] == t]
        if len(cols) < 3:
            continue
        outs = [(pd.Timestamp(i['start']), pd.Timestamp(i['end'])) for i in issues
                if i['type'] == 'outage' and i['ticker'] == t]
        for c in cols:
            E = x[c] - x[[o for o in cols if o != c]].median(axis=1)
            st = step_stat(E)
            st90 = step_stat(E, w=90, min_obs=40)           # the step must persist for months, not weeks
            valid = E.dropna().index
            if len(valid) == 0:
                continue
            for p in peaks(st, np.log(1.6)):
                if not np.sign(st90[p]) == np.sign(st[p]) or abs(st90[p]) < 0.6 * abs(st[p]):
                    continue
                if p < valid[0] + pd.Timedelta(days=30) or p > valid[-1] - pd.Timedelta(days=30):
                    continue
                if near(p, outs + bad_days[c], 20):
                    continue
                p = refine(E, p)
                events.append(dict(ticker=t, source_id=int(c[1]), date=p, size=float(st[p])))
    # a break in one sensor echoes weakly into its peers' comparison: keep the largest step per ticker and date
    events = [a for a in events if not any(b is not a and b['ticker'] == a['ticker'] and
                                           abs((b['date'] - a['date']).days) <= 7 and abs(b['size']) > abs(a['size'])
                                           for b in events)]
    used = set()
    for i, a in enumerate(events):            # series swap: same source, same date, opposite signs
        for j, b in enumerate(events):
            if j <= i or i in used or j in used:
                continue
            if a['source_id'] == b['source_id'] and a['ticker'] != b['ticker'] and \
                    abs((a['date'] - b['date']).days) <= 5 and a['size'] * b['size'] < 0:
                issues.append(dict(type='series_swap', ticker=a['ticker'], other_ticker=b['ticker'],
                                   source_id=a['source_id'], start=fmt(min(a['date'], b['date'])), end=None,
                                   evidence='two tickers in the same source break in opposite directions on the same day'))
                used |= {i, j}
    for i, a in enumerate(events):            # double count: up ~x2 then down ~x2
        if i in used or abs(a['size'] - np.log(2)) > 0.15:
            continue
        downs = [j for j, b in enumerate(events) if j not in used and b['ticker'] == a['ticker'] and
                 b['source_id'] == a['source_id'] and 30 <= (b['date'] - a['date']).days <= 200 and
                 abs(b['size'] + np.log(2)) < 0.15]
        if downs:
            j = downs[0]
            issues.append(dict(type='double_count', ticker=a['ticker'], source_id=a['source_id'], start=fmt(a['date']),
                               end=fmt(events[j]['date'] - pd.Timedelta(days=1)),
                               evidence='sensor runs at exactly 2x its peers for a period'))
            used |= {i, j}
    for i, a in enumerate(events):
        if i in used:
            continue
        issues.append(dict(type='level_shift', ticker=a['ticker'], source_id=a['source_id'], start=fmt(a['date']),
                           end=None, evidence=f'sensor steps {np.exp(a["size"]):.2f}x relative to peer sensors'))

    out = APP / 'output'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'issues.json').write_text(json.dumps(issues, indent=1))
    print(f'wrote {len(issues)} issues')


if __name__ == '__main__':
    main()
