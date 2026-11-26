#!/usr/bin/env python
"""Trust scores and a like-for-like cleaned series for a multi-source daily transaction panel.

    python score.py --input IN.csv --output OUT.csv

Each source of a company is a separate read of the same business, so each is judged against its sister sources, in
log count and in log ticket size (dollars per transaction):

  relation   for each sister: the day's log difference minus that pair's usual difference for the weekday, fixed over
             the first ANCHOR_DAYS days both are established (the source's original basis); the median over sisters.
             Company-wide moves, holidays and weekday patterns cancel; one sister's own problem is outvoted.
  sigma      the source's robust day-to-day spread of its relation over the trailing NOISE_DAYS normal days, widened
             on days when few transactions are expected (counting noise, about 1 / count).

Two questions are asked every day, and confidence is the probability that both answers are "no":
  one-off    is today a one-off error? Today's deviation from the source's current level, z, against two
             explanations: normal noise (standard normal) or an error (normal, ERR_SD sigmas wide), with prior odds
             ERR_PRIOR. The posterior probability of an error.
  shift      has the source moved to a new level? For each window of the last 3 to SHIFT_WINDOW days whose median sits at
             least MIN_SHIFT_SD sigmas off the current level (smaller moves are a source's own slow drift), the evidence
             that it does (Gaussian likelihood ratio, w x median(z)^2 / 2), against a
             prior SHIFT_PRIOR per window; the posterior probability that some window has shifted.
A shift is confirmed when that probability passes CONFIRM_P: the source's level is moved to the window's median and
its days are distrusted until DISTRUST_DAYS after its level stops moving (moved under SETTLED_SD sigmas further from the original basis in a week) (confidence under 0.5, lower the larger the move), then the new level is its
normal and is trusted again (still rescaled to the original basis). A move back to within RETURN_SD sigmas of the
original basis ends the change and is trusted at once. While a change is open its level follows the trailing
LEVEL_DAYS median (so a ramp is followed as it builds).

A one-off whose source made the same move (same sign) within YEARLY_SLACK days of the date a year or two earlier is
that source's yearly pattern (a closure, a holiday): trusted and kept.

Thin beginning: until a source's trailing 28-day median count has held LOW_CT for ESTABLISHED days, its days with a
median under LOW_CT are discarded (blank), confidence 0.45 x median / LOW_CT. A source that thins later is kept.

Cleaned series, on the source's original basis: a one-off error day is rebuilt from its sisters that day at the
source's recent level; on a shifted source every day is moved back by the change's level (while the change is new, the
level of a robust straight line through its last LEVEL_DAYS days, so a ramp is followed without lag). Count and ticket are
cleaned separately; dollars = count x ticket. Confidence comes from a second pass that compares each source with its sisters' cleaned values (so one
source's problem does not make its sisters look wrong); the cleaned series from the first. Every output for day t
uses rows dated <= t only.
"""
import argparse

import numpy as np
import pandas as pd

LOW_CT, ESTABLISHED = 20.0, 90       # low signal: transactions a day (28-day median), and days held to be established
ANCHOR_DAYS = 112                    # days a pair needs together to fix its usual difference
NOISE_DAYS, WARMUP = 120, 56         # noise window; normal days needed before a source is judged
SIG_FLOOR = 0.02                     # sigma floor (log)
ERR_SD, ERR_PRIOR = 6.0, 1e-5       # one-off error model: width in sigmas; prior probability a day is an error
SHIFT_WINDOW, SHIFT_PRIOR = 14, 1e-7 # shift windows of 3..14 days; prior probability per window
MIN_SHIFT_SD = 2.5                   # a window's move must be at least this many sigmas to count as a change
CONFIRM_P = 0.99                     # posterior that confirms a shift
DISTRUST_DAYS = 14                   # a new level is distrusted this long after confirmation
RETURN_SD = 2.0                      # a move back within this many sigmas of the original basis ends the change
SETTLED_SD = 99.0                    # an open change's level has settled once it moved under this many sigmas in a week
LEVEL_DAYS = 14                      # an open change's level: the trailing median of this many days
YEARLY_SLACK = 3                     # days of slack when matching the same date a year or two earlier
IMPUTE_DAYS = 42                     # the source's recent level for rebuilding a one-off error day


def phi(z, sd=1.0):
    return np.exp(-0.5 * (z / sd) ** 2) / sd


def established(ct: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(discard, settled): discard = thin days before the source is established; settled = established by then."""
    med = pd.Series(ct).rolling(28, min_periods=1).median().to_numpy()
    held, est = 0, False
    discard, settled = np.zeros(len(ct), bool), np.zeros(len(ct), bool)
    for t, m in enumerate(med):
        ok = np.isfinite(m) and m >= LOW_CT
        held = held + 1 if ok else 0
        est = est or held >= ESTABLISHED
        settled[t] = est
        discard[t] = not est and not ok
    return discard, settled


def relation(X: pd.DataFrame, s, use: pd.DataFrame, settled: pd.DataFrame, P: pd.DataFrame | None = None) -> np.ndarray:
    """Source s against its sisters (pairwise, weekday-anchored on the original basis), median over sisters; the
    sisters' values from P (their cleaned series) when given."""
    P = X if P is None else P
    devs = []
    wd = pd.Series(X.index.dayofweek, index=X.index)
    for o in X.columns:
        if o == s:
            continue
        d = (X[s] - P[o]).where(use[s] & use[o])
        first = d.where(settled[s] & settled[o]).dropna()
        if len(first) < ANCHOR_DAYS:
            continue
        early = first.iloc[:ANCHOR_DAYS]
        by_wd = early.groupby(early.index.dayofweek).median()
        devs.append((d - wd.map(by_wd).fillna(early.median())).where(d.index >= early.index[-1]))
    return pd.concat(devs, axis=1).median(axis=1).to_numpy() if devs else np.full(len(X), np.nan)


def trend_end(v) -> float:
    """Today's value of a robust straight line (Theil-Sen) through the last days: follows a ramp without the lag of a
    median, and is the median when the level is flat."""
    y = np.asarray(v, float)
    n = len(y)
    if n < 3:
        return float(np.median(y))
    i, j = np.triu_indices(n, 1)
    b = float(np.median((y[j] - y[i]) / (j - i)))
    return float(np.median(y - b * np.arange(n)) + b * (n - 1))


def track(e: np.ndarray, extra_var: np.ndarray, dates: pd.DatetimeIndex):
    """One source, one channel, walking forward. Returns per day: confidence (P fine), level to remove, one-off flag."""
    T = len(e)
    conf, level, oneoff = np.ones(T), np.zeros(T), np.zeros(T, bool)
    seen = {}                      # one-off days by date, with their sign (a yearly pattern is trusted)
    hist = []                      # normal days' relation, for sigma
    recent = []                    # every usable day's relation, for shift windows and an open change's level
    L, open_since = 0.0, None      # current level against the original basis; day the current change last moved
    lv = []                        # an open change's level by day
    for t in range(T):
        x = e[t]
        if not np.isfinite(x):
            continue
        if len(hist) < WARMUP:
            hist.append(x); recent.append(x)
            continue
        h = np.asarray(hist[-NOISE_DAYS:])
        sig = max(1.4826 * np.median(np.abs(h - np.median(h))), SIG_FLOOR)
        sig = float(np.sqrt(sig ** 2 + max(extra_var[t], 0.0)))
        recent.append(x)
        if open_since is not None:                       # an open change: its level follows the trailing median
            L = float(np.median(recent[-LEVEL_DAYS:]))
            lv.append(L)
            if len(lv) > 7 and abs(L) - abs(lv[-8]) > SETTLED_SD * sig:   # moving further from the original basis
                open_since = t                           # still moving (a ramp): it is new until it settles
        z = (x - L) / sig
        # one-off error today
        a = ERR_PRIOR * phi(z, ERR_SD)
        p_err = a / (a + (1 - ERR_PRIOR) * phi(z))
        # a shift: windows of the last 3..SHIFT_WINDOW days against the current level
        r = (np.asarray(recent[-SHIFT_WINDOW:]) - L) / sig
        odds, best = 0.0, None
        for w in range(3, len(r) + 1):
            m = float(np.median(r[-w:]))
            if abs(m) < MIN_SHIFT_SD:                    # smaller than a real change: a source's slow drift
                continue
            lr = min(w * m * m / 2, 50.0)
            odds += SHIFT_PRIOR * np.exp(lr)
            if best is None or lr > best[0]:
                best = (lr, w)
        p_shift = odds / (1 + odds)
        if p_shift >= CONFIRM_P and best is not None:
            newL = L + float(np.median(r[-best[1]:])) * sig
            if abs(newL) <= RETURN_SD * sig:              # back on the original basis: the change is over, trust it
                L, open_since = 0.0, None
            else:
                L, open_since = newL, t
                lv = []
            recent = recent[-best[1]:]
            z = (x - L) / sig
            a = ERR_PRIOR * phi(z, ERR_SD)
            p_err = a / (a + (1 - ERR_PRIOR) * phi(z))
            p_shift = 0.0
        # cleaning: while a change is new (still moving or just settled), follow it with a straight line, no lag
        level[t] = trend_end(recent[-LEVEL_DAYS:]) if open_since is not None and t - open_since < DISTRUST_DAYS else L
        if open_since is not None and t - open_since < DISTRUST_DAYS:
            size = abs(L) / sig                          # distrusted while new: lower the larger the move
            conf[t] = 0.5 / (1 + np.exp(size - RETURN_SD))
        else:
            conf[t] = (1 - p_err) * (1 - p_shift)
        if p_err > 0.5:
            sign = np.sign(z)
            seen[dates[t]] = sign
            if any(seen.get(dates[t] - pd.DateOffset(years=k) + pd.Timedelta(days=d)) == sign
                   for k in (1, 2) for d in range(-YEARLY_SLACK, YEARLY_SLACK + 1)):
                p_err = 0.0                              # the same move a year or two earlier: its yearly pattern
                if open_since is None or t - open_since >= DISTRUST_DAYS:
                    conf[t] = 1 - p_shift
        oneoff[t] = p_err > 0.5
        if p_err <= 0.5:
            hist.append(x - L)
    return conf, level, oneoff


def passes(ct, lc, lt, use, settled, P):
    """Track every source of a company on both channels: {source: {channel: (confidence, cleaned log value)}}."""
    res = {}
    for s in ct.columns:
        others = [o for o in ct.columns if o != s]
        peer = ct[others].where(use[others]).median(axis=1) if others else ct[s]
        expect = ct[s].rolling(28, min_periods=7).median().shift(1)
        extra = (1 / expect.clip(lower=1) - 1 / ct[s].rolling(NOISE_DAYS, min_periods=7).median().shift(1).clip(lower=1)
                 + 1 / peer.clip(lower=1)).fillna(0).to_numpy()
        out = {}
        for ch, X in (('c', lc), ('t', lt)):
            e = relation(X, s, use, settled, None if P is None else P[ch])
            c, L, one = track(e, extra if ch == 'c' else 0.5 * extra, X.index)
            x = X[s].to_numpy()
            new = x - L
            # a one-off error day: the sisters' value that day at the source's recent level
            recent_lvl = pd.Series(np.where(one, np.nan, e - L)).rolling(IMPUTE_DAYS, min_periods=1).median().shift(1).to_numpy()
            fix = one & np.isfinite(e) & np.isfinite(recent_lvl)
            new = np.where(fix, x - (e - L) + recent_lvl - L, new)
            out[ch] = (c, new)
        res[s] = out
    return res


def clean_ticker(g: pd.DataFrame) -> pd.DataFrame:
    ct = g.pivot(index='date', columns='source_id', values='ct').astype(float)
    amt = g.pivot(index='date', columns='source_id', values='amt').astype(float)
    lc = np.log(ct.clip(lower=0.5)); lt = np.log(amt.clip(lower=0.01)) - lc
    disc, sett = {}, {}
    for s in ct.columns:
        disc[s], sett[s] = established(ct[s].to_numpy())
    use = pd.DataFrame({s: ~disc[s] & ct[s].notna().to_numpy() for s in ct.columns}, index=ct.index)
    settled = pd.DataFrame(sett, index=ct.index)
    first = passes(ct, lc, lt, use, settled, None)          # pass 1: every source on raw sisters
    P = {ch: pd.DataFrame({s: first[s][ch][1] for s in ct.columns}, index=ct.index) for ch in ('c', 't')}
    second = passes(ct, lc, lt, use, settled, P)            # pass 2: sisters on their cleaned values
    res = {s: {ch: (second[s][ch][0], first[s][ch][1]) for ch in ('c', 't')} for s in ct.columns}   # confidence from pass 2, cleaning from pass 1
    rows = []
    for s in ct.columns:
        out = res[s]
        d = disc[s]
        m28 = ct[s].rolling(28, min_periods=1).median().to_numpy()
        conf = np.where(d, 0.45 * np.clip(np.nan_to_num(m28) / LOW_CT, 0, 1), np.minimum(out['c'][0], out['t'][0]))
        cc = np.where(d, np.nan, np.exp(out['c'][1]))
        ca = np.where(d, np.nan, np.exp(out['c'][1] + out['t'][1]))
        have = ct[s].notna().to_numpy()
        rows.append(pd.DataFrame(dict(date=ct.index[have], source_id=s, confidence=conf[have], clean_ct=cc[have],
                                      clean_amt=ca[have])))
    return pd.concat(rows, ignore_index=True)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--input', required=True); ap.add_argument('--output', required=True)
    a = ap.parse_args()
    df = pd.read_csv(a.input, parse_dates=['date'])
    outs = [clean_ticker(g).assign(ticker=tk) for tk, g in df.groupby('ticker')]
    out = df[['date', 'ticker', 'source_id', 'ct', 'amt']].merge(pd.concat(outs, ignore_index=True),
                                                                   on=['date', 'ticker', 'source_id'], how='left')
    out['confidence'] = out.confidence.fillna(1.0).clip(0, 1)
    blank = out.confidence < 0.5
    out['clean_ct'] = out.clean_ct.where(out.clean_ct.notna() | blank, out.ct)
    out['clean_amt'] = out.clean_amt.where(out.clean_amt.notna() | blank, out.amt)
    out['date'] = out.date.dt.strftime('%Y-%m-%d')
    out[['date', 'ticker', 'source_id', 'confidence', 'clean_ct', 'clean_amt']].to_csv(a.output, index=False)


if __name__ == '__main__':
    main()
