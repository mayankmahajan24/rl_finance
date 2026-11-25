#!/usr/bin/env python
"""Practitioner reference for anomaly_hard: trust scores and a like-for-like cleaned series, written the way a data
scientist would for a downstream model (plain rules, few knobs, fast, every adjustment explained).

    python score.py --input IN.csv --output OUT.csv [--report REPORT.csv]

Per company, each source is compared with its sister sources, in log count and in log ticket size (dollars per
transaction):
  rel   = against each sister: the day's log difference minus that pair's level for the weekday, set over the first
          ANCHOR_DAYS days both sources are established (the source's original basis); the median over sisters.
          Company-wide moves, weekday patterns and one sister's own problem all drop out
  sigma = the source's robust day-to-day spread of rel (trailing NOISE_DAYS), widened on days when few transactions
          are expected (counting noise, about 1 / count, at the count expected from its own recent level and its
          sisters' move that day)
  z     = rel / sigma, or (rel - offset) / sigma inside a level change
Rules:
  low_signal    before a source has held LOW_CT transactions a day (28-day median) for ESTABLISHED days, days under
                LOW_CT are discarded (distrusted, blank); a source that thins later is kept
  spike         |z| > SPIKE_Z: distrusted and imputed from the sister sources at the source's own level, unless the
                same source made a spike-sized move the same way within YEARLY_SLACK days of the date a year or two
                earlier (a yearly pattern: trusted, kept). When several sources spike in a channel on one day, only
                the one furthest off is the problem
  level_change  a spike that lasts more than MAX_SPIKE_DAYS, or a CUSUM alarm on z (allowance 1, threshold CUSUM_H)
                confirmed by the last 7 days' median being CONFIRM_Z sigmas off, opens a change, unless the same source
                alarmed the same way within 14 days of the date a year or two earlier (its season). Every later day
                is rescaled back to the original basis by the trailing 14-day median offset; distrusted for
                DISTRUST_DAYS after detection, then trusted (the new level is the source's new normal, still
                rescaled). The change ends when the offset falls back under a third of its peak
Two passes: the second uses the first pass's cleaned values for the sister sources (their one-day problems left out),
so one source's problem does not leak into its sisters' comparison. Every output for day t uses rows dated <= t only.

Extra output columns for the analyst: reason (ok, low_signal, spike, level_change, rescaled, yearly_pattern) and
adj_ct, adj_ticket (log adjustment applied to count and ticket size). --report writes one line per flagged episode.
"""
import argparse

import numpy as np
import Rbeast as rb
import pandas as pd

LOW_CT, DROP_CT, ESTABLISHED = 20.0, 16.0, 90   # low signal: keep from LOW_CT, drop under DROP_CT, until established
WARMUP_DAYS, NOISE_DAYS = 56, 120               # usable days before a source is judged; noise window
ANCHOR_DAYS = 112                               # days a pair needs together (both established) to set its level
SPIKE_Z = 6.0                                   # one-day problem: this many sigmas off (as planted problems are sized)
MAX_SPIKE_DAYS = 3                              # a one-day problem lasts at most this long; longer is a level change
BREAK_WINDOW, RECENT_DAYS = 90, 14              # break search: last 90 usable days; the break in the last 14
BEAST_PR = 0.5                                  # posterior probability a trend change point needs
CONFIRM_Z = 2.0                                 # a change must hold: its last 7 days' median this many sigmas off
DISTRUST_DAYS = 14                              # a new level is distrusted this long, then trusted (still rescaled)
YEARLY_SLACK = 3                                # days of slack when looking up the same date a year or two earlier


def low_signal(ct: np.ndarray, established: bool = False) -> np.ndarray:
    """True on days to discard: before the source is established, its 28-day median under the bar (hysteresis).
    With established=True: True on every day before the source is established (still growing into coverage)."""
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
        out[t] = not est if established else not (est or kept)
    return out


rb.beast(np.r_[np.zeros(40), np.ones(10)], season='none', mcmc_seed=1, quiet=1, print_progress=0, print_options=0)
# a first call: Rbeast's first result in a process differs from every later one with the same seed


def break_sign(hist, sigma, since):
    """Bayesian change-point model (Rbeast, piecewise-linear trend, no season) on the last BREAK_WINDOW usable days
    after the last change ended: the sign of the move if a change point with posterior probability BEAST_PR or more
    falls in the last RECENT_DAYS days. Screened first by the recent median being CONFIRM_Z sigmas off (cheap)."""
    n = min(BREAK_WINDOW, len(hist) - since)
    if n < 30:
        return 0
    w = np.asarray(hist[-n:])
    d = np.median(w[-7:]) - np.median(w[:-RECENT_DAYS])
    if abs(d) / sigma < CONFIRM_Z:
        return 0
    o = rb.beast(w, season='none', tcp_minmax=[0, 3], mcmc_seed=1, quiet=1, print_progress=0, print_options=0)
    cp, pr = np.asarray(o.trend.cp, float), np.asarray(o.trend.cpPr, float)
    ok = np.isfinite(cp) & (pr >= BEAST_PR) & (cp - 1 >= n - RECENT_DAYS)
    return int(np.sign(d)) if ok.any() else 0


def track(rel: np.ndarray, usable: np.ndarray, dates: pd.DatetimeIndex, cnt_var: np.ndarray):
    """One source, one channel: walk forward; return offset to remove, flag reason codes, and episodes."""
    T = len(rel)
    off, code, zs = np.zeros(T), np.zeros(T, int), np.zeros(T)   # code: 0 ok, 1 spike, 2 change (distrusted), 3 rescaled
    z_hist, hist, alarms = {}, [], {}                  # z and change alarms by date (yearly lookup); usable history
    level0, start, peak, pos, neg, episodes = None, None, 0.0, 0.0, 0.0, []
    since = 0                                          # history index where the last change ended
    run = []                                           # the current run of consecutive spike days, same sign
    for t in range(T):
        x = rel[t]
        if not usable[t] or np.isnan(x):
            continue
        if len(hist) < WARMUP_DAYS:
            hist.append(x)
            continue
        h = np.asarray(hist)
        base = 0.0                                      # the source's original basis: its early relation to its sisters
        resid = h[-NOISE_DAYS:] - np.median(h[-NOISE_DAYS:])
        sigma = max(1.4826 * np.median(np.abs(resid - np.median(resid))), 0.02)
        vt = cnt_var[t] - np.median(cnt_var[max(0, t - NOISE_DAYS):t + 1])   # counting noise beyond its usual
        if vt > 0:                                     # a day when few transactions are expected is noisier
            sigma = float(np.sqrt(sigma ** 2 + vt))
        cur = (np.median(h[-14:]) - base) if level0 is not None else 0.0      # offset of an open change
        z = (x - base - cur) / sigma
        z_hist[dates[t]] = z
        zs[t] = z
        if abs(z) > SPIKE_Z:
            run = run + [t] if run and np.sign(zs[run[-1]]) == np.sign(z) else [t]
            if len(run) > MAX_SPIKE_DAYS:              # off for longer than a one-day problem lasts: a level change
                hist.extend(rel[i] for i in run)
                if level0 is None:
                    level0, start, peak = 0.0, run[0], 0.0
                    episodes.append(dict(start=dates[run[0]]))
                    pos, neg = 0.0, 0.0
                o = float(np.median(np.asarray(hist)[-min(14, len(run)):]) - level0)
                peak = o if abs(o) > abs(peak) else peak
                code[t], off[t] = 2, o                 # earlier days of the run keep what was output then
                run = []
                continue
            yearly = any(np.sign(z_hist.get(dates[t] - pd.DateOffset(years=k) + pd.Timedelta(days=d), 0)) == np.sign(z)
                         and abs(z_hist.get(dates[t] - pd.DateOffset(years=k) + pd.Timedelta(days=d), 0)) > SPIKE_Z
                         for k in (1, 2) for d in range(-YEARLY_SLACK, YEARLY_SLACK + 1))
            code[t] = -1 if yearly else 1
            off[t] = cur
            continue                                   # a one-day value does not enter the history
        run = []
        hist.append(x)
        if level0 is None:
            sign = break_sign(hist, sigma, since)      # a level change: a recent break in the source's relation
            if sign:
                if sign * (np.median(hist[-7:]) - base) / sigma < CONFIRM_Z:
                    continue                           # a burst of noisy days, not a level that holds
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
                since = len(hist)
                continue
            off[t] = o
            code[t] = 2 if t - start < DISTRUST_DAYS else 3
    if level0 is not None:
        episodes[-1].update(end=None, peak=peak)
    return off, code, episodes, zs


def relation(x: pd.DataFrame, peers: pd.DataFrame, usable: pd.DataFrame, s, settled: pd.DataFrame) -> np.ndarray:
    """Source s against its sisters: per pair, the day's log difference minus the pair's early level (its first
    ANCHOR_DAYS days both usable, fixed from then on); the median over pairs. NaN before any pair is anchored."""
    devs = []
    for o in peers.columns:
        if o == s:
            continue
        both = usable[s] & usable[o]
        d = (x[s] - peers[o]).where(both)
        first = d.where(settled[s] & settled[o]).dropna()   # the pair's level once both are established
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
    settled = pd.DataFrame({s: ~low_signal(ct[s].to_numpy(), established=True) for s in ct.columns}, index=ct.index)
    pc = lc if peer_ct is None else peer_ct
    pt = lt if peer_tk is None else peer_tk
    res = {}
    for s in ct.columns:
        out = dict(low=~usable[s].to_numpy())
        for ch, x, p in (('c', lc, pc), ('t', lt, pt)):
            rel = relation(x, p, usable, s, settled)
            # counting noise of a log count, about 1 / count, at the count expected today (not today's own, which a
            # dropout would distort): the source's recent typical count, moved as its sisters moved today
            others = [c for c in ct.columns if c != s]
            peer = ct[others].where(usable[others]).median(axis=1) if others else ct[s]
            expect = ct[s].rolling(28, min_periods=7).median().shift(1) * peer / peer.rolling(28, min_periods=7).median().shift(1)
            cnt_var = (1 / expect.clip(lower=1) + 1 / peer.clip(lower=1)).fillna(0).to_numpy()
            out[ch] = track(rel, usable[s].to_numpy(), ct.index, cnt_var) + (x[s].to_numpy() - rel,)
        res[s] = out
    return ct, amt, lc, lt, res


def clean_ticker(g: pd.DataFrame):
    ct, amt, lc, lt, res = process(g)                  # pass 1
    for ch in ('c', 't'):                              # several sources off on one day: the one furthest off is the culprit
        spk = pd.DataFrame({s: r[ch][1] == 1 for s, r in res.items()}, index=ct.index)
        z = pd.DataFrame({s: np.abs(r[ch][3]) for s, r in res.items()}, index=ct.index).where(spk, 0)
        many = spk.sum(axis=1) > 1
        culprit = z.eq(z.max(axis=1), axis=0)
        for s, r in res.items():
            code = r[ch][1].copy()
            code[(many & ~culprit[s] & spk[s]).to_numpy()] = 0
            r[ch] = (r[ch][0], code) + r[ch][2:]
    cl_c = lc.copy(); cl_t = lt.copy()
    for s, r in res.items():                           # a sister's one-day problems are left out of pass 2
        spike = (r['c'][1] == 1) | (r['t'][1] == 1)
        cl_c[s] = (lc[s] - r['c'][0]).where(~spike)
        cl_t[s] = (lt[s] - r['t'][0]).where(~spike)
    ct, amt, lc, lt, res = process(g, cl_c, cl_t)      # pass 2: peers on their cleaned values
    rows, report = [], []
    for s, r in res.items():
        oc, cc, ec, _, refc = r['c']
        ot, ctk, et, _, reft = r['t']
        x_c, x_t = lc[s].to_numpy(), lt[s].to_numpy()
        new_c, new_t = x_c - oc, x_t - ot
        # a one-day problem: the source's own level against its sisters that day
        lvl_c = pd.Series(x_c - refc).where(cc == 0).ffill().rolling(WARMUP_DAYS - 14, min_periods=1).median().shift(1).to_numpy()
        lvl_t = pd.Series(x_t - reft).where(ctk == 0).ffill().rolling(WARMUP_DAYS - 14, min_periods=1).median().shift(1).to_numpy()
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
