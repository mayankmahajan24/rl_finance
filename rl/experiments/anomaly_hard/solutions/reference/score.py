"""Reference solution for anomaly_hard: per-row confidence and a like-for-like cleaned series, point in time.

    python score.py --input IN.csv --output OUT.csv

Honest: reads only its input. One model, run separately on log count and log ticket size (dollars per transaction):

    x[s, t] = m[t] + L[s] + w[s, weekday] + noise

m is the company's move that day (median over its other usable sources, each less its own level), L the source's
level (trailing median of its cleaned relation to the company), w its weekday pattern. Residuals are measured in the
source's own noise (trailing robust spread). Every company's sources are walked forward together, one day at a time,
so every output for day t uses only rows dated t or earlier.

* Bad point: |z| > POINT_K. Distrusted; the cleaned value is the model's expectation. A peer that is itself an outlier
  today is left out of the company move.
* Level change: more than MAX_POINT_DAYS outliers of one sign in a row, or a CUSUM (k=CUSUM_K, h=CUSUM_H) firing,
  opens an episode with offset delta (the median residual since it began). Rows become raw - delta, so the cleaned
  series stays on the source's old basis for as long as the change lasts; delta follows a running 14-day median (a ramp
  keeps growing it); the episode closes when the 5-day median residual against the old basis is back near zero. Rows
  are distrusted until SETTLE_DAYS after the change began, then trusted (the new level is the new normal).
  Safeguards: a change must be at least SHIFT_MIN and SHIFT_K noise units; the source must have moved against most of
  its peers one by one (all of them when it has two or fewer); at most half a company's usable sources may be in an
  episode at once (more is a company-wide move: all reset); on upheaval days (the company's move against the same
  weekday in recent weeks is over UPHEAVAL log units: holidays, closures) noise is widened and no episode opens; a jump
  back to a level the source held in the past year is a recovery from a problem that was missed, so the baseline is
  re-anchored instead of opening an episode.
* Recurring: an outlier on dates where the same source moved the same way a year (or two) earlier is trusted and kept.
* Low signal: until a source is established (its trailing 28-day median count has held THIN_CT for ESTABLISHED days
  running) it is discarded (confidence 0, blank) while thin, with hysteresis: kept from KEEP_CT, dropped again under
  DROP_CT. A source that never gets there stays discarded; one that dips later is kept.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

THIN_CT, ESTABLISHED = 20, 90
KEEP_CT, DROP_CT = 25, 16   # before a source is established: keep from KEEP_CT, drop again under DROP_CT
LEVEL_OBS, NOISE_OBS, WD_WEEKS = 42, 90, 8
WARMUP = 28
GAP_RESET = 60          # a source back after this many days without usable data starts its warm-up again
POINT_K, MAX_POINT_DAYS = 4.5, 3
CUSUM_K, CUSUM_H = 1.0, 7.0
SHIFT_MIN, SHIFT_K = 0.15, 2.0
SETTLE_DAYS = 30
UPHEAVAL = 1.0
RECUR_SLACK = 3
NOISE_FLOOR = 0.03


def mad(v) -> float:
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    return float(1.4826 * np.median(np.abs(v - np.median(v)))) if len(v) >= 8 else np.nan


class Channel:
    """State of one channel (log count or log ticket) of one source."""

    def __init__(self, n):
        self.rel = []            # (day, cleaned relation to the company) on trusted days, for the level L
        self.res = []            # residuals on ok days, for the noise
        self.wd = {}             # weekday -> recent residual-from-level values
        self.z = np.full(n, np.nan)
        self.delta = 0.0         # current episode offset (0: none)
        self.peak = 0.0          # the largest offset the current episode has reached
        self.ep_start = None     # day index the current change began
        self.ep_res = []         # residuals against the old basis during the episode
        self.cp = self.cn = 0.0
        self.cp0 = self.cn0 = 0
        self.run = []            # consecutive outlier days (index, residual)
        self.seen = 0

    def level(self):
        v = [r for _, r in self.rel[-LEVEL_OBS:]]
        return float(np.median(v)) if len(v) >= 5 else np.nan

    def weekday(self, wd):
        v = self.wd.get(wd, [])[-WD_WEEKS:]
        return float(np.median(v)) if len(v) >= 3 else 0.0

    def noise(self):
        s = mad(self.res[-NOISE_OBS:])
        return max(s if np.isfinite(s) else 0.15, NOISE_FLOOR)


def walk_company(dates, X, usable):
    """X: days x sources log values of one channel (nan where missing); usable: days x sources (not discarded).
    Returns state (0 ok, 1 bad point, 2 episode distrusted, 3 recurring, 4 warm-up/discarded), cleaned log values."""
    n, S = X.shape
    ch = [Channel(n) for _ in range(S)]
    state = np.full((n, S), 4, int)
    clean = X.copy()
    comp = np.full(n, np.nan)            # the company's move each day, for the upheaval test
    idx = {d: i for i, d in enumerate(dates)}
    wdays = dates.dayofweek.to_numpy()
    last_seen = [None] * S
    for t in range(n):
        live = [s for s in range(S) if usable[t, s] and np.isfinite(X[t, s])]
        L = {s: ch[s].level() for s in live}
        W = {s: ch[s].weekday(wdays[t]) for s in live}
        base = {s: X[t, s] - ch[s].delta - L[s] - W[s] for s in live if np.isfinite(L[s])}
        if base:
            comp[t] = float(np.median(list(base.values())))
        prior = [comp[j] for j in (idx.get(dates[t] - pd.Timedelta(days=7 * k)) for k in range(1, 5)) if j is not None]
        prior = [v for v in prior if np.isfinite(v)]
        upheaval = bool(prior) and np.isfinite(comp[t]) and abs(comp[t] - np.median(prior)) > UPHEAVAL

        def move(s, drop=()):
            v = [base[p] for p in base if p != s and p not in drop]
            return float(np.median(v)) if v else (0.0 if S == 1 else np.nan)

        # stage 1: company move from all peers; stage 2: without peers that are outliers today
        z1 = {}
        for s in base:
            m = move(s)
            if np.isfinite(m):
                z1[s] = (X[t, s] - ch[s].delta - L[s] - W[s] - m) / ch[s].noise()
        out = {s for s, z in z1.items() if abs(z) > POINT_K}
        n_live = max(len(live), 1)
        for s in live:
            if last_seen[s] is not None and t - last_seen[s] > GAP_RESET:
                ch[s] = Channel(n)                        # back after a long gap: its old level is stale, start over
            last_seen[s] = t
            c = ch[s]
            c.seen += 1
            if s not in base or c.seen <= WARMUP:
                m = move(s) if s in base else np.nan
                if np.isfinite(L.get(s, np.nan)) and np.isfinite(m):
                    c.rel.append((t, X[t, s] - c.delta - m))
                elif np.isfinite(X[t, s]):
                    c.rel.append((t, X[t, s] - (comp[t] if np.isfinite(comp[t]) else 0.0)))
                state[t, s] = 4
                continue
            m = move(s, out - {s})
            if not np.isfinite(m):
                m = move(s)
            sig = c.noise() * (3.0 if upheaval else 1.0)
            exp_old = m + L[s] + W[s]                     # expectation on the source's old basis
            r = X[t, s] - c.delta - exp_old               # residual after the current episode's offset
            z = r / sig
            c.z[t] = z
            st = 0
            if c.delta != 0.0:
                # in an episode: follow the offset, close it when the source is back on its old basis
                c.ep_res.append(X[t, s] - exp_old)
                # back on the old basis (against the largest offset the episode reached, so a gradual return closes)
                if len(c.ep_res) >= 5 and abs(np.median(c.ep_res[-5:])) < 0.4 * c.peak:
                    c.delta, c.ep_start, c.ep_res, c.peak = 0.0, None, [], 0.0
                else:
                    c.delta = float(np.median(c.ep_res[-14:]))
                    c.peak = max(c.peak, abs(c.delta))
                    r = X[t, s] - c.delta - exp_old
                    z = r / sig
                    c.z[t] = z
                    if t - c.ep_start < SETTLE_DAYS:
                        st = 2
            if abs(z) > POINT_K and st == 0:
                if recurs(c, dates, idx, t, z):
                    st = 3
                else:
                    c.run.append((t, r))
                    st = 1
                    signs = {np.sign(v) for _, v in c.run}
                    if len(c.run) > MAX_POINT_DAYS and len(signs) == 1 and not upheaval:
                        d = float(np.median([v for _, v in c.run]))
                        if opens(c, s, X, usable, t, c.run[0][0], d, sig, base):
                            start_episode(c, c.run[0][0], d, X, t, s, exp_old, state)
                            st = 2
                        c.run = []
            else:
                c.run = []
            if st == 0 and c.delta == 0.0:
                if c.cp == 0:
                    c.cp0 = t
                if c.cn == 0:
                    c.cn0 = t
                zc = float(np.clip(z, -POINT_K, POINT_K))
                c.cp, c.cn = max(0.0, c.cp + zc - CUSUM_K), max(0.0, c.cn - zc - CUSUM_K)
                if (c.cp > CUSUM_H or c.cn > CUSUM_H) and not upheaval:
                    j0 = c.cp0 if c.cp > CUSUM_H else c.cn0
                    d = float(np.median([v for v in (X[j, s] - clean_rel_exp(ch[s], j) for j in range(max(j0, t - 13), t + 1))
                                         if np.isfinite(v)] or [r]))
                    c.cp = c.cn = 0.0
                    if opens(c, s, X, usable, t, j0, d, sig, base):
                        start_episode(c, j0, d, X, t, s, exp_old, state)
                        st = 2
            # cleaned value and the state the next days learn from
            if st == 1:
                clean[t, s] = exp_old
            else:
                clean[t, s] = X[t, s] - c.delta
            if st in (0, 2, 3):
                c.rel.append((t, clean[t, s] - m))
                c.wd.setdefault(wdays[t], []).append(clean[t, s] - m - L[s])
            if st == 0:
                c.res.append(r)
            c.exp = getattr(c, 'exp', {})
            c.exp[t] = exp_old
            state[t, s] = st
        # at most half the usable sources may be in an episode: more is a company-wide move
        in_ep = [s for s in live if ch[s].delta != 0.0]
        if len(in_ep) > max(1, n_live // 2):
            for s in in_ep:
                ch[s].delta, ch[s].ep_start, ch[s].ep_res, ch[s].peak = 0.0, None, [], 0.0
                clean[t, s] = X[t, s]
                state[t, s] = 0
    return state, clean


def clean_rel_exp(c, j):
    return getattr(c, 'exp', {}).get(j, np.nan)


def recurs(c, dates, idx, t, z):
    for yrs in (1, 2):
        for k in range(-RECUR_SLACK, RECUR_SLACK + 1):
            j = idx.get(dates[t] - pd.Timedelta(days=364 * yrs + k))
            if j is not None and np.isfinite(c.z[j]) and abs(c.z[j]) > POINT_K / 2 and np.sign(c.z[j]) == np.sign(z):
                return True
    return False


def opens(c, s, X, usable, t, j0, d, sig, base):
    """Whether a candidate change of size d (begun at j0) on source s should open an episode."""
    # big enough: against the noise of a median over the days it has lasted, not of one day
    n_days = max(1, t - j0 + 1)
    if abs(d) < max(SHIFT_MIN, SHIFT_K * sig * 1.25 / np.sqrt(n_days)):
        return False
    # the source moved against most of its peers one by one
    votes = []
    for p in range(X.shape[1]):
        if p == s:
            continue
        pre = [X[j, s] - X[j, p] for j in range(max(0, j0 - 28), j0) if usable[j, p] and np.isfinite(X[j, p])]
        post = [X[j, s] - X[j, p] for j in range(j0, t + 1) if usable[j, p] and np.isfinite(X[j, p])]
        pre, post = [v for v in pre if np.isfinite(v)], [v for v in post if np.isfinite(v)]
        if len(pre) >= 7 and len(post) >= 2:
            sh = float(np.median(post) - np.median(pre))
            votes.append(np.sign(sh) == np.sign(d) and abs(sh) >= abs(d) / 2)
    if votes:
        need = len(votes) if len(votes) <= 2 else int(np.ceil(2 * len(votes) / 3))
        if sum(votes) < need:
            return False
    # recovery: the jump takes the source back to a relation it held in the past year (a missed problem ending)
    past = [r for j, r in c.rel if t - 365 <= j < t - 90]
    recent = [r for j, r in c.rel if j >= t - 28]
    if len(past) >= 60 and recent:
        before, now, held = float(np.median(recent)), float(np.median(recent)) + d, float(np.median(past))
        # it had been well away from that relation, and the jump lands close to it
        if abs(before - held) >= 0.75 * abs(d) and abs(now - held) < 0.25 * abs(d):
            c.rel = [(j, r + d) for j, r in c.rel if j >= t - LEVEL_OBS]      # re-anchor the level instead
            return False
    return True


def start_episode(c, j0, d, X, t, s, exp_old, state):
    c.delta, c.ep_start, c.ep_res, c.peak = d, j0, [d], abs(d)


def score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    out = []
    for tk, g in df.groupby('ticker'):
        ct = g.pivot(index='date', columns='source_id', values='ct').astype(float)
        amt = g.pivot(index='date', columns='source_id', values='amt').astype(float)
        dates, srcs = ct.index, list(ct.columns)
        med = ct.rolling(28, min_periods=14).median()        # needs two weeks of data to count
        held = (med >= THIN_CT).astype(int).rolling(ESTABLISHED, min_periods=ESTABLISHED).sum() >= ESTABLISHED
        established = held.cummax()                      # once established, always (point in time)
        # a source's thin beginning is dropped; with hysteresis (start keeping at KEEP_CT, drop again under DROP_CT
        # until established) so a median hovering at the line doesn't leave a patchy series
        discard = np.zeros(ct.shape, bool)
        for k, s in enumerate(srcs):
            dropping = True
            for i, (mv, est, has) in enumerate(zip(med[s].to_numpy(), established[s].to_numpy(), ct[s].notna().to_numpy())):
                if est or (np.isfinite(mv) and mv >= KEEP_CT):
                    dropping = False
                elif not est and np.isfinite(mv) and mv < DROP_CT:
                    dropping = True
                discard[i, k] = dropping and has and not est
        usable = ct.notna().to_numpy() & ~discard
        lc = np.log(ct.clip(lower=0.01)).to_numpy()
        lt = (np.log(amt.clip(lower=0.01)) - np.log(ct.clip(lower=0.01))).to_numpy()
        sc, cc = walk_company(dates, lc, usable)
        st, ctk = walk_company(dates, lt, usable)
        for k, s in enumerate(srcs):
            has = ct[s].notna().to_numpy()
            conf = np.ones(len(dates))
            conf[(sc[:, k] == 2) | (st[:, k] == 2)] = 0.3
            conf[(sc[:, k] == 1) | (st[:, k] == 1)] = 0.05
            conf[discard[:, k]] = 0.0
            cct, camt = np.exp(cc[:, k]), np.exp(cc[:, k] + ctk[:, k])
            cct[discard[:, k]] = np.nan
            camt[discard[:, k]] = np.nan
            o = pd.DataFrame(dict(date=dates, ticker=tk, source_id=s, confidence=conf, clean_ct=cct, clean_amt=camt))
            out.append(o[has])
    res = pd.concat(out, ignore_index=True)
    res = df[['date', 'ticker', 'source_id']].merge(res, on=['date', 'ticker', 'source_id'], how='left')
    res['confidence'] = res.confidence.fillna(1.0)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    res = score(pd.read_csv(a.input))
    res['date'] = res.date.dt.strftime('%Y-%m-%d')
    res.to_csv(a.output, index=False, float_format='%.6g')


if __name__ == '__main__':
    main()
