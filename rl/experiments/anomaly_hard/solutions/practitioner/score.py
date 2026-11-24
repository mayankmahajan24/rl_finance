#!/usr/bin/env python
"""Practitioner reference for anomaly_hard: trust scores and a like-for-like cleaned series, written the way a data
scientist would for a downstream model (plain rules, few knobs, fast, every adjustment explained).

    python score.py --input IN.csv --output OUT.csv [--report REPORT.csv]

Per company, each source is compared with its sister sources, in log count and in log ticket size (dollars per
transaction):
  rel   = against each sister source, the day's difference from that pair's early level for that weekday (median
          over its first ANCHOR_DAYS days together); then the median over sisters (company-wide moves, weekday
          patterns and a sister's own problem all drop out)
  level = the median of rel over the trailing BASE_DAYS (lagged LAG_DAYS, so a fresh change does not drag it along)
  sigma = the source's robust day-to-day spread of rel around its level (trailing NOISE_DAYS)
  z     = (rel - level) / sigma
Rules:
  low_signal    before a source has held LOW_CT transactions a day (28-day median) for ESTABLISHED days, days under
                LOW_CT are discarded (distrusted, blank); a source that thins later is kept
  spike         |z| > SPIKE_Z on one day: distrusted, imputed from the sister sources at the source's own level,
                unless the same source moved the same way within 3 days of the same date a year or two earlier
                (yearly pattern: trusted, kept)
  level_change  a CUSUM on z (allowance 1, threshold CUSUM_H) opens a change: the source's level is frozen at its
                old value, and every later day is rescaled back to it by the trailing 14-day median offset; distrusted
                for DISTRUST_DAYS after detection, then trusted (the new level is the source's new normal, still
                rescaled); the change ends when the offset falls back under a third of its peak
Two passes: the second uses the first pass's cleaned values for the sister sources, so one source's problem does not
leak into its peers' comparison. Every output for day t uses rows dated <= t only.

Extra output columns for the analyst: reason (ok, low_signal, spike, level_change, rescaled, yearly_pattern) and
adj_ct, adj_ticket (log adjustment applied to count and ticket size). --report writes one line per flagged episode.
"""
import argparse

import numpy as np
import pandas as pd

LOW_CT, DROP_CT, ESTABLISHED = 20.0, 16.0, 90   # low signal: keep from LOW_CT, drop under DROP_CT, until established
BASE_DAYS, LAG_DAYS, NOISE_DAYS = 42, 14, 120   # level window, its lag, noise window (days of usable data)
ANCHOR_DAYS = 56                                # days a pair needs together before it is compared
SPIKE_Z, CUSUM_H, DISTRUST_DAYS = 5.0, 12.0, 14   # CUSUM_H: day-to-day noise is autocorrelated, so above textbook
YEARLY_SLACK = 3


def low_signal(ct: np.ndarray) -> np.ndarray:
    """True on days to discard: before the source is established, its 28-day median under the bar (hysteresis)."""
    med = pd.Series(ct).rolling(28, min_periods=1).median().to_numpy()
    out = np.zeros(len(ct), bool)
    kept, held, est = False, 0, False
    for t, m in enumerate(med):
        if np.isnan(m):
            out[t] = not est
            continue
        held = held + 1 if m >= LOW_CT else 0
        est = est or held >= ESTABLISHED
        kept = kept or m >= LOW_CT
        kept = kept and (est or m >= DROP_CT)
        out[t] = not (est or kept)
    return out


def track(rel: np.ndarray, usable: np.ndarray, dates: pd.DatetimeIndex):
    """One source, one channel: walk forward; return offset to remove, flag reason codes, and episodes."""
    T = len(rel)
    off, code = np.zeros(T), np.zeros(T, int)          # code: 0 ok, 1 spike, 2 level change (distrusted), 3 rescaled
    z_hist, hist, alarms = {}, [], {}                  # z and change alarms by date (yearly lookup); usable history
    level0, start, peak, pos, neg, episodes = None, None, 0.0, 0.0, 0.0, []
    for t in range(T):
        x = rel[t]
        if not usable[t] or np.isnan(x):
            continue
        if len(hist) < BASE_DAYS + LAG_DAYS:
            hist.append(x)
            continue
        h = np.asarray(hist)
        base = level0 if level0 is not None else np.median(h[-(BASE_DAYS + LAG_DAYS):-LAG_DAYS])
        resid = h[-NOISE_DAYS:] - np.median(h[-NOISE_DAYS:])
        sigma = max(1.4826 * np.median(np.abs(resid - np.median(resid))), 0.02)
        cur = (np.median(h[-14:]) - base) if level0 is not None else 0.0      # offset of an open change
        z = (x - base - cur) / sigma
        z_hist[dates[t]] = z
        if abs(z) > SPIKE_Z:
            yearly = any(np.sign(z_hist.get(dates[t] - pd.DateOffset(years=k) + pd.Timedelta(days=d), 0)) == np.sign(z)
                         and abs(z_hist.get(dates[t] - pd.DateOffset(years=k) + pd.Timedelta(days=d), 0)) > SPIKE_Z / 2
                         for k in (1, 2) for d in range(-YEARLY_SLACK, YEARLY_SLACK + 1))
            code[t] = -1 if yearly else 1
            off[t] = cur
            continue                                   # a one-day value does not enter the history
        hist.append(x)
        if level0 is None:
            zc = float(np.clip(z, -4, 4))
            pos, neg = max(0.0, pos + zc - 1.0), max(0.0, neg - zc - 1.0)
            if pos > CUSUM_H or neg > CUSUM_H:         # a level change: freeze the old level
                sign = 1 if pos > CUSUM_H else -1
                pos, neg = 0.0, 0.0
                if any(alarms.get(dates[t] - pd.DateOffset(years=k) + pd.Timedelta(days=d)) == sign
                       for k in (1, 2) for d in range(-14, 15)):
                    alarms[dates[t]] = sign                # the same move a year earlier: its season, not a change
                    continue
                alarms[dates[t]] = sign
                level0, start, peak = base, t, 0.0
                episodes.append(dict(start=dates[t]))
        if level0 is not None:
            o = float(np.median(np.asarray(hist)[-min(14, max(3, len(hist) - 1)):]) - level0)
            peak = o if abs(o) > abs(peak) else peak
            if t - start > DISTRUST_DAYS and abs(o) < abs(peak) / 3:   # back on its old level: the change is over
                episodes[-1].update(end=dates[t], peak=peak)
                level0 = None
                continue
            off[t] = o
            code[t] = 2 if t - start < DISTRUST_DAYS else 3
    if level0 is not None:
        episodes[-1].update(end=None, peak=peak)
    return off, code, episodes


def relation(x: pd.DataFrame, peers: pd.DataFrame, usable: pd.DataFrame, s) -> np.ndarray:
    """Source s against its sisters: per pair, the day's log difference minus the pair's early level (its first
    ANCHOR_DAYS days both usable, fixed from then on); the median over pairs. NaN before any pair is anchored."""
    devs = []
    for o in peers.columns:
        if o == s:
            continue
        both = usable[s] & usable[o]
        d = (x[s] - peers[o]).where(both)
        first = d.dropna()
        if len(first) < ANCHOR_DAYS:
            continue
        anchor_day = first.index[ANCHOR_DAYS - 1]
        early = first.iloc[:ANCHOR_DAYS]
        by_wd = early.groupby(early.index.dayofweek).median()             # each source has its own weekday pattern
        anchor = pd.Series(d.index.dayofweek, index=d.index).map(by_wd).fillna(early.median())
        devs.append((d - anchor).where(d.index >= anchor_day))
    return pd.concat(devs, axis=1).median(axis=1).to_numpy() if devs else np.full(len(x), np.nan)


def process(g: pd.DataFrame, peer_ct=None, peer_tk=None):
    ct = g.pivot(index='date', columns='source_id', values='ct').astype(float)
    amt = g.pivot(index='date', columns='source_id', values='amt').astype(float)
    lc, lt = np.log(ct.clip(lower=0.5)), np.log(amt.clip(lower=0.01)) - np.log(ct.clip(lower=0.5))
    usable = pd.DataFrame({s: ~low_signal(ct[s].to_numpy()) & ct[s].notna().to_numpy() for s in ct.columns}, index=ct.index)
    pc = lc if peer_ct is None else peer_ct
    pt = lt if peer_tk is None else peer_tk
    res = {}
    for s in ct.columns:
        out = dict(low=~usable[s].to_numpy())
        for ch, x, p in (('c', lc, pc), ('t', lt, pt)):
            rel = relation(x, p, usable, s)
            out[ch] = track(rel, usable[s].to_numpy(), ct.index) + (x[s].to_numpy() - rel,)
        res[s] = out
    return ct, amt, lc, lt, res


def clean_ticker(g: pd.DataFrame):
    ct, amt, lc, lt, res = process(g)                  # pass 1
    cl_c = lc.copy(); cl_t = lt.copy()
    for s, r in res.items():                           # a sister's one-day problems are left out of pass 2
        spike = (r['c'][1] == 1) | (r['t'][1] == 1)
        cl_c[s] = (lc[s] - r['c'][0]).where(~spike)
        cl_t[s] = (lt[s] - r['t'][0]).where(~spike)
    ct, amt, lc, lt, res = process(g, cl_c, cl_t)      # pass 2: peers on their cleaned values
    rows, report = [], []
    for s, r in res.items():
        oc, cc, ec, refc = r['c']
        ot, ctk, et, reft = r['t']
        x_c, x_t = lc[s].to_numpy(), lt[s].to_numpy()
        new_c, new_t = x_c - oc, x_t - ot
        # a one-day problem: the source's own level against its sisters that day
        lvl_c = pd.Series(x_c - refc).where(cc == 0).ffill().rolling(BASE_DAYS, min_periods=1).median().shift(1).to_numpy()
        lvl_t = pd.Series(x_t - reft).where(ctk == 0).ffill().rolling(BASE_DAYS, min_periods=1).median().shift(1).to_numpy()
        spike = (cc == 1) | (ctk == 1)
        new_c = np.where(spike & np.isfinite(lvl_c), refc + lvl_c + oc * 0, new_c)
        new_t = np.where(spike & np.isfinite(lvl_t), reft + lvl_t, new_t)
        new_c = np.where(spike & ~np.isfinite(lvl_c), x_c, new_c)
        new_t = np.where(spike & ~np.isfinite(lvl_t), x_t, new_t)
        low = r['low']
        reason = np.where(low, 'low_signal', np.where(spike, 'spike', np.where((cc == 2) | (ctk == 2), 'level_change',
                          np.where((cc == 3) | (ctk == 3), 'rescaled', np.where((cc == -1) | (ctk == -1), 'yearly_pattern', 'ok')))))
        conf = np.where(low, 0.0, np.where(spike, 0.05, np.where(reason == 'level_change', 0.3, 1.0)))
        out_ct = np.where(low, np.nan, np.exp(new_c))
        out_amt = np.where(low, np.nan, np.exp(new_c + new_t))
        have = ct[s].notna().to_numpy()
        rows.append(pd.DataFrame(dict(date=ct.index[have], source_id=s, confidence=conf[have], clean_ct=out_ct[have],
                                      clean_amt=out_amt[have], reason=reason[have],
                                      adj_ct=np.round(x_c - new_c, 4)[have], adj_ticket=np.round(x_t - new_t, 4)[have])))
        for ch, eps in (('count', ec), ('ticket', et)):
            for e in eps:
                report.append(dict(source_id=s, channel=ch, start=e['start'].date(), end=e['end'].date() if e.get('end') is not None else '',
                                   shift_log=round(float(e.get('peak', 0.0)), 3)))
    return pd.concat(rows, ignore_index=True), report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True); ap.add_argument('--output', required=True); ap.add_argument('--report')
    a = ap.parse_args()
    df = pd.read_csv(a.input, parse_dates=['date'])
    outs, report = [], []
    for tk, g in df.groupby('ticker'):
        o, rep = clean_ticker(g)
        outs.append(o.assign(ticker=tk))
        report += [dict(r, ticker=tk) for r in rep]
    out = df[['date', 'ticker', 'source_id']].merge(pd.concat(outs, ignore_index=True), on=['date', 'ticker', 'source_id'], how='left')
    out['confidence'] = out.confidence.fillna(1.0)
    out['clean_ct'] = out.clean_ct.where(out.clean_ct.notna() | (out.reason == 'low_signal'), df.ct)
    out['clean_amt'] = out.clean_amt.where(out.clean_amt.notna() | (out.reason == 'low_signal'), df.amt)
    out['reason'] = out.reason.fillna('ok')
    out['date'] = out.date.dt.strftime('%Y-%m-%d')
    out.to_csv(a.output, index=False)
    if a.report:
        pd.DataFrame(report, columns=['ticker', 'source_id', 'channel', 'start', 'end', 'shift_log']).to_csv(a.report, index=False)


if __name__ == '__main__':
    main()
