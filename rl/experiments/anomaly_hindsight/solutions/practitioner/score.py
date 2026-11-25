#!/usr/bin/env python
"""Practitioner reference for anomaly_hindsight (the anomaly_hard practitioner plus hindsight discards, 2026-11-25): trust scores and a like-for-like cleaned series, written the way a data
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

Hindsight (cleaned series only; confidence stays point in time): a final pass blanks what cannot be put like for like
(hindsight_discards): a company-wide coverage break's shorter side, a company-wide outage, a source's history before it
reaches steady coverage, and a source that never does.

Extra output columns for the analyst: reason (ok, low_signal, spike, level_change, rescaled, yearly_pattern, discarded) and
adj_ct, adj_ticket (log adjustment applied to count and ticket size). --report writes one line per flagged episode.
"""
import argparse

import numpy as np
import pandas as pd

LOW_CT, DROP_CT, ESTABLISHED = 20.0, 16.0, 90   # low signal: keep from LOW_CT, drop under DROP_CT, until established
WARMUP_DAYS, NOISE_DAYS = 56, 120               # usable days before a source is judged; noise window
ANCHOR_DAYS = 112                               # days a pair needs together (both established) to set its level
SPIKE_Z = 6.0                                   # one-day problem: this many sigmas off (as planted problems are sized)
MAX_SPIKE_DAYS = 3                              # a one-day problem lasts at most this long; longer is a level change
CUSUM_H = 12.0                                  # change alarm (allowance 1); day-to-day noise is autocorrelated
CONFIRM_Z = 2.0                                 # a change must hold: its last 7 days' median this many sigmas off
DISTRUST_DAYS = 14                              # a new level is distrusted this long, then trusted (still rescaled)
YEARLY_SLACK = 3                                # days of slack when looking up the same date a year or two earlier

# hindsight discards (the cleaned series may use the whole panel)
STEADY_FRAC, STEADY_AHEAD = 0.7, 180      # steady once the 28-day median reaches 70% of the next 180 days' level
OUTAGE_FRAC, OUTAGE_DAYS = 0.3, 4         # company-wide outage: every source under 30% of its yearly level, 4+ days
BREAK_X, BREAK_WIN = 3.0, 60              # coverage break: every source x3 (or /3) across 60 days either side, lasting


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


def track(rel: np.ndarray, usable: np.ndarray, dates: pd.DatetimeIndex, cnt_var: np.ndarray):
    """One source, one channel: walk forward; return offset to remove, flag reason codes, and episodes."""
    T = len(rel)
    off, code, zs = np.zeros(T), np.zeros(T, int), np.zeros(T)   # code: 0 ok, 1 spike, 2 change (distrusted), 3 rescaled
    z_hist, hist, alarms = {}, [], {}                  # z and change alarms by date (yearly lookup); usable history
    level0, start, peak, pos, neg, episodes = None, None, 0.0, 0.0, 0.0, []
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
            zc = float(np.clip(z, -4, 4))
            pos, neg = max(0.0, pos + zc - 1.0), max(0.0, neg - zc - 1.0)
            if pos > CUSUM_H or neg > CUSUM_H:         # a level change: freeze the old level
                sign = 1 if pos > CUSUM_H else -1
                pos, neg = 0.0, 0.0
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


def hindsight_discards(df: pd.DataFrame) -> pd.Series:
    """Rows whose cleaned values cannot be put like for like with the rest of their series, decided from the whole
    panel: a company-wide coverage break (its shorter side), a company-wide outage, a source's history before it
    reaches steady coverage, and a source that never does. Returns a boolean Series aligned with df."""
    drop = pd.Series(False, index=df.index)
    for tk, g in df.groupby('ticker'):
        ct = g.pivot(index='date', columns='source_id', values='ct').astype(float)
        days = pd.date_range(ct.index.min(), ct.index.max())
        ct = ct.reindex(days)
        keep_from, keep_to = days[0], days[-1]
        # coverage break: every source moves together by BREAK_X or more, and the move lasts for the rest of the series
        before = ct.rolling(BREAK_WIN, min_periods=20).median().shift(1)
        after = ct[::-1].rolling(BREAK_WIN, min_periods=20).median()[::-1]
        lr = np.log(after / before)
        up = (lr > np.log(BREAK_X)).all(axis=1) & lr.notna().all(axis=1)
        dn = (lr < -np.log(BREAK_X)).all(axis=1) & lr.notna().all(axis=1)
        for cand in (up, dn):
            if not cand.any():
                continue
            d = lr[cand].abs().mean(axis=1).idxmax()
            pre = ct[(ct.index < d) & (ct.index >= d - pd.Timedelta(days=365))].median()
            post = ct[(ct.index >= d) & (ct.index < d + pd.Timedelta(days=365))].median()
            ratio = np.log(post / pre)
            if (ratio.abs() > np.log(BREAK_X)).all() and (np.sign(ratio) == np.sign(ratio.iloc[0])).all():
                if (d - days[0]) < (days[-1] - d):
                    keep_from = max(keep_from, d)
                else:
                    keep_to = min(keep_to, d - pd.Timedelta(days=1))
        cut = (ct.index < keep_from) | (ct.index > keep_to)
        # company-wide outage: every reporting source far under its own yearly level for several days running
        yearly = ct.rolling(365, min_periods=60, center=True).median()
        low = ((ct / yearly) < OUTAGE_FRAC) | ct.isna()
        out = low.all(axis=1)                    # a day no source reports counts as dark too
        run = out.groupby((~out).cumsum()).transform('sum')
        outage = out & (run >= OUTAGE_DAYS)
        for s in ct.columns:
            x = ct[s].where(~pd.Series(cut, index=ct.index) & ~outage)
            m28 = x.rolling(28, min_periods=7, center=True).median()
            held = (m28 >= LOW_CT).astype(int).rolling(ESTABLISHED).sum() >= ESTABLISHED
            if not held.any():
                bad = pd.Series(True, index=ct.index)            # never reaches steady coverage
            else:
                ahead = m28[::-1].rolling(STEADY_AHEAD, min_periods=28).median()[::-1]
                steady = (m28 >= STEADY_FRAC * ahead) & (m28 >= LOW_CT)
                start = steady.idxmax() if steady.any() else ct.index[-1]
                bad = (ct.index < start) | pd.Series(cut, index=ct.index) | outage
            bad = pd.Series(np.asarray(bad), index=ct.index)
            rows = g.index[g.source_id == s]
            drop.loc[rows] = bad.reindex(g.loc[rows, 'date']).fillna(False).to_numpy()
    return drop


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
    gone = hindsight_discards(df).to_numpy()                 # hindsight: stretches that cannot be made like for like
    out.loc[gone, ['clean_ct', 'clean_amt']] = np.nan
    out.loc[gone & (out.reason == 'ok'), 'reason'] = 'discarded'
    out['date'] = out.date.dt.strftime('%Y-%m-%d')
    out.to_csv(a.output, index=False)
    if a.report:
        pd.DataFrame(report, columns=['ticker', 'source_id', 'channel', 'start', 'end', 'shift_log']).to_csv(a.report, index=False)


if __name__ == '__main__':
    main()
