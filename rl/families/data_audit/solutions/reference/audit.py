"""Reference solution for the data-validation audit task.

A battery of independent, explainable checks over the full history (an audit may look at all of it):
  1. exact duplicate rows                       -> duplicate_rows
  2. implausible ticket size (amt / ct)         -> swapped_columns (ticket collapses) / unit_scale (x100 jump)
  3. runs of missing / near-zero days           -> outage (merged to ticker-wide when most sources go dark)
  4. weekly-cycle misalignment vs peer sources  -> dst_shift (per summer) / date_shift (CUSUM change-point)
  5. step changes in the ticker-wide level      -> ticker_remap
  6. step changes vs peer sources (same ticker) -> series_swap / double_count / level_shift
  7. ticket-size steps vs peer sources          -> amount_shift
Then repairs the panel from what it found (cleaned.csv): every fix in place, short gaps filled from the peer
sources, longer outages nulled.
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


LEVEL_STEP = np.log(1.38)   # the smallest step against the other sources worth flagging: below it, real
                            # sources in this panel step against each other several times a task
TICKET_STEP = np.log(1.22)  # the same for ticket size


def deseason(E):
    """Remove a source's usual seasonal swing against its peers (sources differ in how much their holiday
    seasons swing), measured by week of the year on the series with its slow level taken out."""
    slow = E.rolling(365, center=True, min_periods=120).median()
    woy = E.index.isocalendar().week.clip(upper=52)
    prof = (E - slow).groupby(woy).median().rolling(3, center=True, min_periods=1).mean()
    return E - woy.map(prof).astype(float)


def sharp(E, p, st):
    """An overnight step: a 7-day comparison sees most of the 28-day step, which slow drift between sources doesn't."""
    s7 = step_stat(E, w=7, min_obs=5).get(p, np.nan)
    return np.isfinite(s7) and np.sign(s7) == np.sign(st) and abs(s7) >= 0.8 * abs(st)


def dst_windows(d0, d1):
    """US summer time [second Sunday of March, first Sunday of November) inside [d0, d1]."""
    out = []
    for y in range(d0.year, d1.year + 1):
        mar, nov = pd.Timestamp(y, 3, 8), pd.Timestamp(y, 11, 1)
        a = mar + pd.Timedelta(days=(6 - mar.weekday()) % 7)
        b = nov + pd.Timedelta(days=(6 - nov.weekday()) % 7)
        if a - pd.Timedelta(days=1) >= d0 and b <= d1:
            out.append((a, b))
    return out


def temporary_steps(events, used, kind):
    """A step and a later opposite step of about the same size on one series are one problem with an end; a
    step near 2x that returns is a double count; any other step continues to the end."""
    fmt = lambda d: pd.Timestamp(d).strftime('%Y-%m-%d')  # noqa: E731
    out = []
    for i, a in enumerate(events):
        if i in used:
            continue
        backs = [j for j, b in enumerate(events) if j != i and j not in used and b['ticker'] == a['ticker'] and
                 b['source_id'] == a['source_id'] and 30 <= (b['date'] - a['date']).days <= 400 and
                 abs(a['size'] + b['size']) < 0.35 * abs(a['size'])]
        item = dict(type=kind, ticker=a['ticker'], source_id=a['source_id'], start=fmt(a['date']), end=None,
                    factor=float(np.exp(a['size'])))
        if backs:
            j = backs[0]; used |= {j}
            item['end'] = fmt(events[j]['date'] - pd.Timedelta(days=1))
            if kind == 'level_shift' and abs(a['size'] - np.log(2)) < 0.15:
                item['type'] = 'double_count'
        used |= {i}
        what = 'amounts (not counts)' if kind == 'amount_shift' else 'its level'
        item['evidence'] = f'{what} step {item["factor"]:.2f}x against the other sources' + (' and step back' if backs else '')
        out.append(item)
    return out


def repair(df, issues, ct, good):
    """The panel with every problem found repaired in place, short gaps filled from the other sources and
    outages over 7 days nulled; everything else as it came."""
    d = df.drop_duplicates(['date', 'ticker', 'source_id'], keep='first')
    end = ct.index[-1]
    S = {k: g.set_index('date')[['ct', 'amt']].astype(float) for k, g in d.groupby(['ticker', 'source_id'])}
    span = lambda i: (pd.Timestamp(i['start']), pd.Timestamp(i['end']) if i['end'] else end)  # noqa: E731
    fill = {k: set() for k in S}          # days to fill in from the other sources at the end
    order = ['swapped_columns', 'unit_scale', 'amount_shift', 'series_swap', 'date_shift', 'dst_shift',
             'double_count', 'level_shift', 'ticker_remap']
    for i in sorted([i for i in issues if i['type'] in order], key=lambda i: order.index(i['type'])):
        a, b = span(i)
        keys = [k for k in S if k[0] == i['ticker'] and i['source_id'] in (None, k[1])]
        for k in keys:
            x = S[k]; m = (x.index >= a) & (x.index <= b)
            if i['type'] == 'swapped_columns':
                x.loc[m, ['ct', 'amt']] = x.loc[m, ['amt', 'ct']].values
            elif i['type'] == 'unit_scale':
                x.loc[m, 'amt'] /= 100
            elif i['type'] == 'amount_shift':
                x.loc[m, 'amt'] /= i['factor']
            elif i['type'] == 'series_swap':
                o = (i['other_ticker'], k[1])
                if o in S:
                    y = S[o]; my = (y.index >= a) & (y.index <= b)
                    S[k] = pd.concat([x[~m], y[my]]).sort_index(); S[o] = pd.concat([y[~my], x[m]]).sort_index()
            elif i['type'] == 'date_shift':
                k_ = i['shift_days']
                lo = a if k_ > 0 else a + pd.Timedelta(days=1)
                mm = x.index >= lo
                moved = x[mm].copy(); moved.index = moved.index - pd.Timedelta(days=k_)
                S[k] = x[~mm].combine_first(moved) if k_ > 0 else pd.concat([x[~mm], moved]).sort_index()
                fill[k] |= {a, end} if k_ > 0 else {a, a + pd.Timedelta(days=1)}
            elif i['type'] == 'dst_shift':
                k_ = i['shift_days']
                mm = (x.index > a) & (x.index < b)
                moved = x[mm].copy(); moved.index = moved.index - pd.Timedelta(days=k_)
                S[k] = pd.concat([x[~mm & ~((x.index >= a) & (x.index <= b))], moved,
                                  x[(x.index == a) | (x.index == b)]]).groupby(level=0).first().sort_index()
                fill[k] |= {b - pd.Timedelta(days=1), b} if k_ > 0 else {a, a + pd.Timedelta(days=1)}
            else:                       # a step against the other sources: rescale by its measured size
                x.loc[m, ['ct', 'amt']] /= ratio_step(ct, k, a, b, good)
                x['ct'] = x['ct'].round()
    nulls = {k: set() for k in S}
    for i in issues:
        if i['type'] != 'outage':
            continue
        a, b = span(i)
        days = set(pd.date_range(a, b))
        for k in S:
            if k[0] == i['ticker'] and i['source_id'] in (None, k[1]):
                (nulls if len(days) > 7 else fill)[k] |= days
    out = []
    for k, x in S.items():
        x = x.copy()
        for day in sorted(fill[k] - nulls[k]):
            est = peer_estimate(ct, k, day, good, x)
            if est is not None:
                x.loc[day] = est
        if nulls[k]:
            x = x.reindex(x.index.union(pd.DatetimeIndex(sorted(nulls[k]))))
            x.loc[sorted(nulls[k])] = np.nan
        x = x.sort_index()
        out.append(x.reset_index(names='date').assign(ticker=k[0], source_id=k[1]))
    res = pd.concat(out, ignore_index=True)[['date', 'ticker', 'source_id', 'ct', 'amt']]
    res['ct'] = res['ct'].round().astype('Int64')
    return res.sort_values(['date', 'ticker', 'source_id'])


def ratio_step(ct, k, a, b, good):
    """How many times higher the series ran against its peer sources in [a, b] than outside it."""
    peers = [c for c in good if c[0] == k[0] and c != k]
    if not peers or k not in ct.columns:
        return 1.0
    r = np.log(ct[k].clip(lower=1)) - np.log(ct[peers].clip(lower=1)).mean(axis=1)
    inside = r.loc[a:b].median()
    before = r.loc[a - pd.Timedelta(days=120):a - pd.Timedelta(days=1)].median()
    after = r.loc[b + pd.Timedelta(days=1):b + pd.Timedelta(days=120)].median()
    base = np.nanmean([before, after]) if not (np.isnan(before) and np.isnan(after)) else np.nan
    return float(np.exp(inside - base)) if np.isfinite(inside - base) else 1.0


def peer_estimate(ct, k, day, good, x):
    """A day's ct and amt from the other sources that day, at the series' usual ratio to them nearby."""
    peers = [c for c in good if c[0] == k[0] and c != k]
    if not peers or day not in ct.index:
        return None
    near_ = slice(day - pd.Timedelta(days=28), day + pd.Timedelta(days=28))
    own = x['ct'].loc[near_].drop(day, errors='ignore')
    tot = ct[peers].sum(axis=1).loc[near_]
    ratio = (own / tot.reindex(own.index)).median()
    ticket = (x['amt'] / x['ct']).loc[near_].median()
    if not np.isfinite(ratio) or not np.isfinite(ticket) or not np.isfinite(ct[peers].sum(axis=1).loc[day]):
        return None
    c = max(1.0, round(ratio * ct[peers].sum(axis=1).loc[day]))
    return [c, round(c * ticket, 2)]


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
                                   end=fmt(max(g[1][1] for g in group)), evidence='most sources go dark together'))
                used |= {(g[0], g[1][0]) for g in group}
            else:
                issues.append(dict(type='outage', ticker=t, source_id=int(c[1]), start=fmt(s0), end=fmt(s1),
                                   evidence='source reports no or near-zero volume for 7+ days'))
                used.add((c, s0))

    # log level with problem days masked (x_raw keeps them, for ticker-wide break detection)
    x_raw = np.log(ct.clip(lower=1)); x_raw = x_raw - x_raw.median()
    x = np.log(ct.clip(lower=1))
    for c in ct.columns:
        for s0, s1 in bad_days[c]:
            x.loc[s0:s1, c] = np.nan
    x = x - x.median()          # put every sensor on a common scale before comparing with peers
    tickers = sorted({c[0] for c in good})

    # 4. date shifts: does the source's weekly cycle line up with its peers' cycle a day off? ---------
    #    z_k > 0 on days where the source matches its peers shifted by k days (its dates are off by k)
    w = x - x.rolling(7, center=True, min_periods=5).mean()
    summers = dst_windows(dates[0], dates[-1])
    for t in tickers:
        cols = [c for c in good if c[0] == t]
        if len(cols) < 3:
            continue
        for c in cols:
            peer = w[[o for o in cols if o != c]].median(axis=1)
            zs = {k: (w[c] * (peer.shift(k) - peer)).fillna(0) for k in (1, -1)}
            # summer-only offsets first: strongly aligned inside the summer, not outside it
            hit = False
            for k, z in zs.items():
                inside = [z.loc[a:b - pd.Timedelta(days=1)] for a, b in summers]
                outside = z[~np.any([(z.index >= a) & (z.index < b) for a, b in summers], axis=0)] if summers else z
                if outside.mean() > 0:
                    continue
                for (a, b), zin in zip(summers, inside):
                    if zin.mean() / (zin.std() / np.sqrt(len(zin)) + 1e-12) > 5:
                        lo, hi = (a, b) if k > 0 else (a - pd.Timedelta(days=1), b - pd.Timedelta(days=1))
                        issues.append(dict(type='dst_shift', ticker=t, source_id=int(c[1]), start=fmt(lo), end=fmt(hi),
                                           shift_days=k, evidence=f'only in summer, its weekly pattern matches the other '
                                                                  f'sources {abs(k)} day {"later" if k > 0 else "earlier"}'))
                        hit = True
            if hit:
                continue
            for k, z in zs.items():
                cs = (z - z.mean()).cumsum()
                j = int(np.argmin(cs.values))
                after, before = z.iloc[j + 1:], z.iloc[:j + 1]
                if len(after) < 60 or len(before) < 60:
                    continue
                tstat = after.mean() / (after.std() / np.sqrt(len(after)) + 1e-12)
                if after.mean() > 0 and before.mean() < 0 and tstat > 5:
                    start = z.index[j + 1] + pd.Timedelta(days=min(k, 0))
                    issues.append(dict(type='date_shift', ticker=t, source_id=int(c[1]), start=fmt(start), end=None,
                                       shift_days=k, evidence=f'from this date its weekly pattern matches the other sources '
                                                              f'{abs(k)} day {"later" if k > 0 else "earlier"}'))
                    break

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
                                   evidence=f'every source steps up ~{np.exp(after - before):.1f}x on the same date'))
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
            E = deseason(x[c] - x[[o for o in cols if o != c]].median(axis=1))
            st = step_stat(E)
            st90 = step_stat(E, w=90, min_obs=40)           # the step must persist for months, not weeks
            valid = E.dropna().index
            if len(valid) == 0:
                continue
            for p in peaks(st, LEVEL_STEP):
                if not np.sign(st90[p]) == np.sign(st[p]) or abs(st90[p]) < 0.6 * abs(st[p]):
                    continue
                if p < valid[0] + pd.Timedelta(days=30) or p > valid[-1] - pd.Timedelta(days=30):
                    continue
                if near(p, outs + bad_days[c], 20):
                    continue
                size = float(st[p]); p = refine(E, p)
                if not sharp(E, p, size):
                    continue
                events.append(dict(ticker=t, source_id=int(c[1]), date=p, size=size))
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
    issues += temporary_steps(events, used, 'level_shift')

    # 7. amount-only steps: the ticket size moves against the other sources' while counts don't ---------
    tk = np.log(amt / ct.where(ct >= 3))
    tsteps = []
    for t in tickers:
        cols = [c for c in good if c[0] == t]
        if len(cols) < 3:
            continue
        for c in cols:
            E = tk[c] - tk[[o for o in cols if o != c]].median(axis=1)
            for s0, s1 in bad_days[c]:
                E.loc[s0:s1] = np.nan
            E = deseason(E)
            st, st90 = step_stat(E), step_stat(E, w=90, min_obs=40)
            valid = E.dropna().index
            for p in peaks(st, TICKET_STEP, sep=60):
                if abs(st[p]) > np.log(1.3) or np.sign(st90[p]) != np.sign(st[p]) or abs(st90[p]) < 0.6 * abs(st[p]):
                    continue
                if len(valid) == 0 or p < valid[0] + pd.Timedelta(days=30) or p > valid[-1] - pd.Timedelta(days=30):
                    continue
                size = float(st[p]); p = refine(E, p)
                if sharp(E, p, size):
                    tsteps.append(dict(ticker=t, source_id=int(c[1]), date=p, size=size))
    issues += temporary_steps(tsteps, set(), 'amount_shift')

    out = APP / 'output'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'issues.json').write_text(json.dumps(issues, indent=1))
    repair(df, issues, ct, good).to_csv(out / 'cleaned.csv', index=False, date_format='%Y-%m-%d')
    verdicts = usability(issues, ct)
    (out / 'usability.json').write_text(json.dumps(verdicts, indent=1))
    chart = flags_chart(ct, issues, out / 'figures' / 'flags.png')
    (out / 'writeup.md').write_text(note(issues, verdicts, ct, good, d) + chart)
    print(f'wrote {len(issues)} issues')


FIXES = {'duplicate_rows': 'drop the duplicate rows', 'swapped_columns': 'swap the columns back',
         'unit_scale': 'divide amounts by 100', 'date_shift': 'move the dates back a day', 'series_swap': 'swap the series back',
         'double_count': 'halve the double-counted periods', 'level_shift': 'rescale level shifts to the other sources',
         'ticker_remap': 'rescale the re-mapped ticker', 'dst_shift': 'move summer dates back',
         'amount_shift': 'rescale the amounts'}
WORDS = {'duplicate_rows': ('run of duplicated rows', 'runs of duplicated rows'),
         'swapped_columns': ('period of swapped count and amount columns', 'periods of swapped count and amount columns'),
         'unit_scale': ('switch of amounts to cents', 'switches of amounts to cents'),
         'date_shift': ('series with dates shifted by a day', 'series with dates shifted by a day'),
         'series_swap': ('pair of swapped series', 'pairs of swapped series'),
         'double_count': ('period of double counting', 'periods of double counting'),
         'outage': ('outage', 'outages'), 'level_shift': ('level shift', 'level shifts'),
         'ticker_remap': ('re-mapping of a whole ticker', 're-mappings of whole tickers'),
         'dst_shift': ('summer of dates off by a day', 'summers of dates off by a day'),
         'amount_shift': ('step in amounts only', 'steps in amounts only')}


def listing(parts):
    return parts[0] if len(parts) == 1 else ', '.join(parts[:-1]) + ' and ' + parts[-1]


def note(issues, verdicts, ct, good, d):
    """The note, three sentences under 120 words: verdict, findings and repair, and what was ruled out."""
    bad = [v for v in verdicts if not v['usable']]
    if bad:
        names = listing([f"{v['ticker']} source {v['source_id']}" for v in bad])
        s1 = f"{len(verdicts) - len(bad)} of the {len(verdicts)} series are usable once repaired; {names} {'is' if len(bad) == 1 else 'are'} not."
    else:
        s1 = f"All {len(verdicts)} series are usable once repaired."
    if issues:
        counts = pd.Series([i['type'] for i in issues]).value_counts()
        found = listing([f'{n} {WORDS[t][n > 1]}' for t, n in counts.items()])
        long_out = sum(1 for i in issues if i['type'] == 'outage' and
                       (pd.Timestamp(i['end'] or ct.index[-1]) - pd.Timestamp(i['start'])).days + 1 > 7)
        nulled = f"nulled only the {long_out} outages longer than a week" if long_out else "nulled nothing"
        s2 = f"Counting a move in only some of a ticker's sources as a collection problem, I found {found}, repaired them in place and {nulled}."
    else:
        s2 = "Counting a move in only some of a ticker's sources as a collection problem, I found nothing to repair."
    low = len(verdicts) - len(good)
    s3 = "Moves every source shared, such as holidays and promotions, I left as real" + \
         (f", and I did not check the {low} series under {MIN_CT} transactions a day." if low else ".")
    return ' '.join([s1, s2, s3]) + '\n'


def flags_chart(ct, issues, path):
    """One panel per ticker and source, weekly, with each flagged period shaded and labelled; returns the
    markdown line, or '' without matplotlib."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        return ''
    tickers = sorted({t for t, _ in ct.columns})
    sources = sorted({int(s) for _, s in ct.columns})
    fig, axes = plt.subplots(len(tickers), len(sources), figsize=(3.6 * len(sources), 1.9 * len(tickers) + 0.8),
                             sharex=True, squeeze=False)
    end = ct.index[-1]
    for r, t in enumerate(tickers):
        for c, s in enumerate(sources):
            ax = axes[r, c]
            ax.set_title(f'{t} source {s}', loc='left', fontsize=8)
            if (t, s) in ct.columns:
                ax.plot(ct[(t, s)].resample('W').sum(min_count=1).iloc[1:-1], lw=0.8, color='#2a78d6')   # whole weeks
                ax.set_yscale('log')
            hits = [i for i in issues if t in (i['ticker'], i.get('other_ticker')) and i['source_id'] in (None, s)]
            for k, i in enumerate(hits):
                a, b = pd.Timestamp(i['start']), pd.Timestamp(i['end']) if i['end'] else end
                ax.axvspan(a, max(b, a + pd.Timedelta(days=10)), color='#eb6834', alpha=0.3, lw=0)
                ax.text(a, 0.95 - 0.16 * k, ' ' + WORDS[i['type']][0], transform=ax.get_xaxis_transform(), fontsize=6.5,
                        va='top', color='#7a2e0e')
            ax.tick_params(labelsize=6.5)
            if c == 0:
                ax.set_ylabel('transactions\nper week', fontsize=7)
            if r == len(tickers) - 1:
                ax.set_xlabel('date', fontsize=7)
    fig.suptitle('Weekly transactions by ticker and source (log scale); flagged periods shaded and labelled',
                 x=0.01, ha='left', fontsize=10)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=90)
    return '\n![Weekly transactions by ticker and source, with every flagged period shaded](figures/flags.png)\n'


def usability(issues, ct):
    """A verdict per series: only gaps longer than a week are unrecoverable (every other problem has a fix);
    a series is not usable if one reaches its last 90 days, it has 3 or more, or they cover over 10% of it."""
    end = ct.index[-1]
    verdicts = []
    for t, s in ct.columns:
        first = ct[(t, s)].first_valid_index()
        gaps = [(pd.Timestamp(i['start']), pd.Timestamp(i['end']) if i['end'] else end) for i in issues
                if i['type'] == 'outage' and i['ticker'] == t and i['source_id'] in (None, s)]
        gaps = [(a, b) for a, b in gaps if (b - a).days + 1 > 7]
        recent = [b for _, b in gaps if b > end - pd.Timedelta(days=90)]
        share = sum((b - a).days + 1 for a, b in gaps) / ((end - first).days + 1)
        if recent:
            reason = f'unrecoverable gap up to {recent[0]:%Y-%m-%d}, within the last 90 days'
        elif len(gaps) >= 3:
            reason = f'{len(gaps)} unrecoverable gaps'
        elif share > 0.1:
            reason = f'unrecoverable gaps cover {share:.0%} of the history'
        else:
            reason = 'every problem found can be fixed' if gaps or any(i['ticker'] == t for i in issues) else 'no problems found'
        verdicts.append(dict(ticker=t, source_id=int(s), usable=not (recent or len(gaps) >= 3 or share > 0.1),
                             reason=reason))
    return verdicts


if __name__ == '__main__':
    main()
