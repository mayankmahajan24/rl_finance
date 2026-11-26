#!/usr/bin/env python
"""Reference solution for anomaly_hard: trust scores and cleaned series for a multi-source daily transaction panel.

For every ticker the sources are independent reads of the same company. Each source/day is compared with a robust
cross-source consensus (median of the sources after removing each source's own level), separately for log count and
log ticket size. A strictly causal state machine per source and channel flags one-day outliers and persistent level
shifts (CUSUM) and repairs them: outliers are replaced by the consensus of the other sources, level shifts by removing
the estimated shift so the source keeps its own day-to-day signal (its old basis). A level change is distrusted while
it settles, then trusted as the source's new normal. One-day moves far outside the source's own history that also
stand out against its peers are bad points too. A source's thin beginning (before its trailing 28-day median count
has held 20 for 90 days) is discarded, with hysteresis; a source that thins later is kept.

Everything for a row dated t uses only rows dated <= t.
"""
import argparse
import sys
from collections import deque

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- parameters
LOW_CT = 20.0          # low-signal threshold (transactions / day)
LOW_WIN = 28           # reports in the low-signal trailing median
ESTABLISHED = 90       # a source is established once that median has held LOW_CT this many reports running
KEEP_CT, DROP_CT = 20.0, 16.0   # before then: keep from KEEP_CT, drop again under DROP_CT (hysteresis)
OWN_Z, PEER_Z, OWN_N = 5.0, 2.5, 120   # own-history spike check: beyond OWN_Z of its own spread, and PEER_Z vs peers
RECUR_SLACK = 3        # days of slack when matching the same dates a year earlier
LONG_NOW, LONG_LO, LONG_HI = 28, 180, 365   # slow drift: last 28 observations against those 180-365 back
LONG_K = 3.0           # ... at least this many times the source's own noise, on two weekly checks running
WANDER_K = 3.0         # a level change must also be this many times the source's usual month-to-month wander
YOUNG_DAYS = 120       # days after a source is first kept before it helps set the company's move
LAG = 14               # most recent observations left out of the level baseline
SEASON_SLACK = 14      # days of slack when matching a drift alarm to the same dates a year earlier
FRESH = 90             # an episode younger than this counts toward the at-most-half-the-sources rule
SETTLE = 14            # days after a level change is detected before its new level is trusted
BASE_N = 42            # observations in a source's level baseline
SCALE_N = 120          # observations in a source's noise scale
SPIKE_Z = 5.5          # single-day outlier threshold (robust z)
CUSUM_K = 1.0          # CUSUM allowance (in sigmas)
CUSUM_H = 7.0          # CUSUM decision interval
Z_CLIP = 4.0           # clip z before feeding CUSUM
MIN_SHIFT = {"ct": 0.12, "tk": 0.10}   # smallest level shift worth repairing (log)
MIN_SPIKE = {"ct": 0.25, "tk": 0.20}   # smallest single-day error worth flagging (log)
EP_WIN = 14            # days used for the running shift estimate
EXIT_N = 5             # days used for the exit test
EXIT_SIG = 1.0         # exit when the recent median residual is within this many sigmas
EXIT_PEAK = 0.35       # ... or has fallen below this share of the episode's largest shift
WARMUP = 14            # days of history before CUSUM is armed
SIG_FLOOR = 0.02
ABNORMAL = 1.0         # |company move vs. same weekday in prior weeks| marking upheaval days
RECOV_LO, RECOV_HI, RECOV_BLK = 30, 400, 60   # past-year level blocks, to tell recoveries from new shifts
RECOV_FRAC = 0.3
HOLI_C = 0.3           # extra noise on days the whole company moves abnormally (holidays)
HOLI_A0 = 0.4          # ... beyond this size of move


def seen_before(hist, level, d):
    """Did the source sit at level + d (within RECOV_FRAC*|d|) in some 60-day block
    of the past year, while that block was clearly away from the current level?"""
    h = np.fromiter(hist, float)[:-RECOV_LO]
    for e in range(len(h), 29, -RECOV_BLK):
        b = float(np.median(h[max(0, e - RECOV_BLK):e]))
        if abs(level + d - b) < RECOV_FRAC * abs(d) and abs(b - level) > 0.5 * abs(d):
            return True
    return False


def kept_since(valid, gap=7):
    """For each day and source, the day its current kept stretch began (gaps of up to gap days do not end a stretch):
    a source settles in again every time it comes back after being dropped."""
    T, S = valid.shape
    out = np.full((T, S), -10**6)
    for j in range(S):
        start, last = None, None
        for t in range(T):
            if valid[t, j]:
                if start is None or t - last > gap:
                    start = t
                last = t
            if start is not None:
                out[t, j] = start
    return out


def recurs(zs, t, z):
    """Did this source move the same way (beyond half the spike threshold) within RECUR_SLACK days of the same date a
    year or two earlier?"""
    for yrs in (1, 2):
        c = t - 364 * yrs
        if c - RECUR_SLACK < 0:
            continue
        w = zs[c - RECUR_SLACK:c + RECUR_SLACK + 1]
        if np.any((np.sign(w) == np.sign(z)) & (np.abs(w) > SPIKE_Z / 2)):
            return True
    return False


def wander(hist) -> float:
    """How much the source's level against the company normally wanders from month to month, as reported: the robust
    spread of the changes between consecutive 28-day medians over its last year (0 if too little history)."""
    h = np.asarray(hist, float)[-364:]
    h = h[np.isfinite(h)]
    if len(h) < 4 * 28:
        return 0.0
    med = np.array([np.median(h[i:i + 28]) for i in range(len(h) % 28, len(h), 28)])
    dif = np.diff(med)
    return float(1.4826 * np.median(np.abs(dif - np.median(dif))))


def seasonal(fires, t):
    """Did the drift detector fire on this source within SEASON_SLACK days of the same date a year or two earlier?"""
    return any(abs(t - f - 364 * y) <= SEASON_SLACK for f in fires for y in (1, 2))


def moved_alone(Y, t, s, d):
    """The source moved by d against most of its peers one by one (all of them when it has two or fewer): its relation to
    each peer now (last LONG_NOW days) against 6-12 months ago."""
    votes = []
    for p in range(Y.shape[1]):
        if p == s:
            continue
        rel = Y[:t + 1, s] - Y[:t + 1, p]
        now, then = rel[-LONG_NOW:], rel[-LONG_HI:-LONG_LO]
        now, then = now[np.isfinite(now)], then[np.isfinite(then)]
        if len(now) >= 14 and len(then) >= 60:
            sh = float(np.median(now) - np.median(then))
            votes.append(np.sign(sh) == np.sign(d) and abs(sh) >= abs(d) / 2)
    if not votes:
        return False
    need = len(votes) if len(votes) <= 2 else int(np.ceil(2 * len(votes) / 3))
    return sum(votes) >= need


def detect(Y, valid, channel, want=None):
    """Causal detector on a (T days x S sources) log matrix.

    Model: Y[t,s] = m[t] + L[s,t] + noise, where m is the company's common daily
    move (median across sources) and L the source's level relative to
    it (trailing median of its *cleaned* history, so a repaired level shift does
    not leak into the baseline). Cells in `want` (rows whose value is unusable,
    e.g. a zero or missing amount) are imputed from the consensus.
    Returns clean values, flag and |z|.
    """
    T, S = Y.shape
    Y = np.where(valid, Y, np.nan)
    run_start = kept_since(valid)                  # start of each source's current kept stretch, per day
    clean = np.full((T, S), np.nan)
    innov = np.full((T, S), np.nan)    # residual minus current shift, on usable days
    M = np.full(T, np.nan)
    flag = np.zeros((T, S), bool)
    age = np.full((T, S), -1)          # days since the current level-change episode opened (-1: none)
    zabs = np.zeros((T, S))
    zsig = np.zeros((T, S))
    fired = [[] for _ in range(S)]     # days the drift detector fired on each source
    long_prev = np.zeros(S)            # last weekly slow-drift reading that passed the bar (0: none)
    long_open = np.zeros(S, bool)      # current episode was opened by the slow-drift check            # signed residual (noise units) on judged days, for the recurring test
    mode = np.zeros(S, int)            # 0 normal, 1 shift
    delta = np.zeros(S)
    peak = np.zeros(S)
    nep = np.zeros(S, int)             # days since the episode was opened
    ep = [[] for _ in range(S)]
    sp = np.zeros(S)
    sn = np.zeros(S)
    run = [[] for _ in range(S)]
    nhist = np.zeros(S, int)
    last_val = np.full(S, np.nan)      # last clean value of each source
    lv = [deque(maxlen=BASE_N) for _ in range(S)]    # clean - common factor, last valid days
    iv = [deque(maxlen=SCALE_N) for _ in range(S)]   # leave-one-out innovations, normal days
    lt = [deque(maxlen=RECOV_HI) for _ in range(S)]  # longer level history (recovery test)
    min_shift = MIN_SHIFT[channel]
    min_spike = MIN_SPIKE[channel]

    for t in range(T):
        avail = np.isfinite(Y[t])
        if not avail.any():
            if want is not None:
                for s in np.where(want[t] & np.isfinite(last_val))[0]:
                    clean[t, s] = last_val[s]        # nothing to compare with: carry
                    flag[t, s] = True
                    zabs[t, s] = 10.0
            continue
        # the source's level from its history LAG observations back and earlier: a ramp cannot drag it along
        L = np.array([np.median(list(lv[j])[:-LAG]) if len(lv[j]) > LAG + 7 else (np.median(lv[j]) if lv[j] else np.nan)
                      for j in range(S)])
        sig = np.full(S, 0.3)
        for j in range(S):
            if len(iv[j]) >= 10:
                x = np.fromiter(iv[j], float)
                sig[j] = 1.4826 * np.median(np.abs(x - np.median(x)))
        sig = np.maximum(sig, SIG_FLOOR)

        # guardrail: shifts are a minority phenomenon. If most usable sources look
        # shifted, the company itself moved: drop all open episodes.
        usable = avail & np.isfinite(L)
        fresh = (mode == 1) & (nep < FRESH)          # changes happening now (old, settled ones do not count)
        if usable.sum() >= 2 and 2 * fresh[usable].sum() > usable.sum():
            for j in np.where(fresh)[0]:
                mode[j] = 0
                delta[j] = peak[j] = 0.0
                nep[j] = 0
                ep[j] = []
                sp[j] = sn[j] = 0.0
                run[j] = []
        ycorr = Y[t] - np.where(mode == 1, delta, 0.0)
        v = ycorr - L
        use = avail & np.isfinite(v)
        # a source still settling in after it was first kept (a thin start growing into coverage) does not set the
        # company's move yet: its own growth would read as everyone else's shift
        settled = use & (t - run_start[t] >= YOUNG_DAYS)
        if settled.sum() >= 2:
            use = settled
        # a peer that is itself far off today (its own one-day problem) does not set the company's move either
        if use.sum() >= 3:
            m0 = float(np.median(v[use]))
            calm_src = use & (np.abs(v - m0) <= SPIKE_Z * sig)
            if calm_src.sum() >= 2:
                use = calm_src
        n = use.sum()
        prev = [M[t - k] for k in (7, 14, 21) if t - k >= 0 and np.isfinite(M[t - k])]
        mref = float(np.median(prev)) if prev else np.nan
        if n >= 3:
            m = float(np.median(v[use]))
        elif n == 2:
            vv = v[use]
            if np.isfinite(mref):
                m = vv[np.argmin(np.abs(vv - mref))]
            else:
                m = float(np.mean(vv))
        elif n == 1:
            m = float(v[use][0])
        else:
            m = float(np.nanmedian(Y[t]))   # gauge for the very first day(s)
        M[t] = m
        A = abs(m - mref) if np.isfinite(mref) else 0.0
        decide = n >= 2   # with a single source we cannot tell who is wrong
        calm = A < ABNORMAL  # company-wide upheaval days do not move episodes

        for s in range(S):
            if not avail[s]:
                continue
            if mode[s] == 0:
                long_open[s] = False
            y = Y[t, s]
            if not np.isfinite(L[s]) or not decide:
                clean[t, s] = y - (delta[s] if mode[s] == 1 else 0.0)
                flag[t, s] = mode[s] == 1
                continue
            yhat = m + L[s]
            r = y - yhat
            oth = use.copy()
            oth[s] = False
            if not oth.any():
                oth = avail & np.isfinite(v)
                oth[s] = False
            m_loo = float(np.median(v[oth])) if oth.any() else m
            r_loo = y - L[s] - m_loo
            # one-day problems are judged and imputed against the other sources only (with few sources the median
            # includes this one, and its own problem drags the reference); level changes use the full median
            yhat_loo, z_loo = m_loo + L[s], r_loo / np.sqrt(sig[s] ** 2 + (HOLI_C * max(A - HOLI_A0, 0.0)) ** 2)
            se = np.sqrt(sig[s] ** 2 + (HOLI_C * max(A - HOLI_A0, 0.0)) ** 2)
            nhist[s] += 1
            armed = nhist[s] > WARMUP
            settling = t - run_start[t, s] < YOUNG_DAYS  # still growing into coverage: no level-change episodes yet
            z = r / se
            is_spike = max(abs(z), abs(z_loo)) > SPIKE_Z and max(abs(r), abs(r_loo)) > min_spike and (armed or abs(r) > 0.7)
            if abs(z_loo) > abs(z):
                yhat_spike, zz = yhat_loo, z_loo
            else:
                yhat_spike, zz = yhat, z
            if armed:
                zsig[t, s] = zz
            # recurring: the same source moved the same way on the same dates a year (or two) earlier: a pattern of
            # this source, not a problem (trusted, kept as reported)
            if is_spike and recurs(zsig[:, s], t, zz):
                is_spike = False
            entered = False

            if mode[s] == 0:
                if armed and calm and not settling:
                    zc = np.clip(z, -Z_CLIP, Z_CLIP)
                    sp[s] = max(0.0, sp[s] + zc - CUSUM_K)
                    sn[s] = max(0.0, sn[s] - zc - CUSUM_K)
                    if sp[s] == 0 and sn[s] == 0:
                        run[s] = []
                    else:
                        run[s] = (run[s] + [r])[-EP_WIN:]
                    # slow drift: the source's relation to the company now against 6-12 months ago, which a ramp
                    # over months cannot drag along (the CUSUM's baseline follows it)
                    if (not entered and t % 7 == 0 and len(lt[s]) >= LONG_HI and sp[s] <= CUSUM_H
                            and sn[s] <= CUSUM_H):
                        h = np.fromiter(lt[s], float)
                        d = float(np.median(h[-LONG_NOW:]) - np.median(h[-LONG_HI:-LONG_LO]))
                        room = 2 * (((mode == 1) & (nep < FRESH))[use].sum() + 1) <= n
                        # against the noise of the two medians compared (not of one day)
                        sd = 1.25 * sig[s] * np.sqrt(1 / LONG_NOW + 1 / (LONG_HI - LONG_LO))
                        big = abs(d) >= LONG_K * sd and abs(d) > max(min_shift, WANDER_K * wander(Y[:t + 1, s] - M[:t + 1]))
                        same = big and np.sign(d) == np.sign(long_prev[s])
                        long_prev[s] = d if big else 0.0
                        if same and room and moved_alone(Y, t, s, d):
                            # its onset is long past: rescaled to the old basis from now on, trusted (not distrusted)
                            long_open[s] = True
                            mode[s] = 1
                            delta[s] = d
                            ep[s] = [d]
                            entered = True
                            base = [x - d for x in lv[s]]       # the baseline back on the old basis
                            lv[s].clear()
                            lv[s].extend(base)
                            sp[s] = sn[s] = 0.0
                            run[s] = []
                    if (sp[s] > CUSUM_H or sn[s] > CUSUM_H) and seasonal(fired[s], t):
                        fired[s].append(t)                 # this source's own season: no episode
                        sp[s] = sn[s] = 0.0
                        run[s] = []
                    if sp[s] > CUSUM_H or sn[s] > CUSUM_H:
                        fired[s].append(t)
                        d = float(np.median(run[s]))
                        room = 2 * (((mode == 1) & (nep < FRESH))[use].sum() + 1) <= n
                        # a jump back to where the source sat a few months ago is a
                        # recovery from a problem we missed, not a new problem
                        recov = seen_before(lt[s], L[s], d)
                        if recov:
                            keep = list(lv[s])[-len(run[s]):] if run[s] else []
                            lv[s].clear()
                            lv[s].extend(keep)
                        elif abs(d) > max(min_shift, WANDER_K * wander(Y[:t + 1, s] - M[:t + 1])) and room:
                            mode[s] = 1
                            delta[s] = d
                            ep[s] = list(run[s])
                            entered = True
                            # part of a slow build-up (the source had already moved a third of the way, the same way,
                            # 45-90 days ago): rescale it, but there is no fresh onset to distrust
                            h = np.fromiter(lt[s], float)
                            if len(h) >= 120:
                                early = float(np.median(h[-90:-45]) - np.median(h[-120:-90]))
                                if np.sign(early) == np.sign(d) and abs(early) >= abs(d) / 3:
                                    long_open[s] = True
                        sp[s] = sn[s] = 0.0
                        run[s] = []
                if mode[s] == 0:
                    if is_spike and not settling:            # a source still growing into coverage is left as it is
                        clean[t, s] = yhat_spike
                        flag[t, s] = True
                    else:
                        clean[t, s] = y
                        innov[t, s] = r_loo
                    zabs[t, s] = abs(z)
                    continue

            # ---- shift mode
            if not calm:
                # hold the current shift through upheaval days
                u = r - delta[s]
                off = abs(u) / se > SPIKE_Z and abs(u) > min_spike
                clean[t, s] = yhat if off else y - delta[s]
                flag[t, s] = True
                if not off:
                    age[t, s] = SETTLE if long_open[s] else nep[s]     # a settled change is trusted on these days too
                zabs[t, s] = abs(delta[s]) / se
                continue
            if not entered:
                ep[s].append(r)
                recent = ep[s][-3:]
                if len(ep[s]) > 6 and abs(np.median(recent) - delta[s]) > 2.5 * se:
                    ep[s] = list(recent)              # level moved again: restart estimate
                ep[s] = ep[s][-EP_WIN:]
                delta[s] = float(np.median(ep[s]))
            nep[s] += 1
            last = ep[s][-min(EXIT_N, nep[s]):]
            peak[s] = max(peak[s], abs(delta[s]))
            back = nep[s] >= EXIT_N and abs(np.median(last)) < max(
                EXIT_SIG * sig[s], 0.5 * min_shift, EXIT_PEAK * peak[s])
            # an old episode whose raw level is one the source already held in the
            # past year was the end of a problem we missed: re-anchor instead
            stale = (nep[s] >= 28 and nep[s] % 7 == 0 and
                     seen_before(lt[s], L[s], delta[s]))
            if stale:
                lv[s].clear()
                lv[s].extend([L[s] + x for x in ep[s][-EXIT_N:]])
            if back or stale or abs(delta[s]) < 0.5 * min_shift:
                mode[s] = 0
                delta[s] = 0.0
                peak[s] = 0.0
                nep[s] = 0
                ep[s] = []
                sp[s] = sn[s] = 0.0
                run[s] = []
                if is_spike:
                    clean[t, s] = yhat_spike
                    flag[t, s] = True
                else:
                    clean[t, s] = y
                zabs[t, s] = abs(z)
                continue
            u = r - delta[s]
            if abs(u) / se > SPIKE_Z and abs(u) > min_spike:
                clean[t, s] = yhat                    # off the shifted level: use consensus
                flag[t, s] = True
                zabs[t, s] = abs(z)
            else:
                clean[t, s] = y - delta[s]
                flag[t, s] = True
                age[t, s] = SETTLE if long_open[s] else nep[s]
                innov[t, s] = r_loo - delta[s]
                zabs[t, s] = abs(delta[s]) / se
        if want is not None:
            for s in np.where(want[t] & ~avail)[0]:
                if decide and np.isfinite(L[s]):
                    clean[t, s] = m + L[s]
                elif np.isfinite(last_val[s]):
                    clean[t, s] = last_val[s]            # no consensus: carry the last clean value
                else:
                    continue
                flag[t, s] = True
                zabs[t, s] = 10.0
        for s in range(S):
            if avail[s] and np.isfinite(clean[t, s]):
                last_val[s] = clean[t, s]
                lv[s].append(clean[t, s] - m)
                lt[s].append(clean[t, s] - m)
            if np.isfinite(innov[t, s]):
                iv[s].append(innov[t, s])
    return clean, flag, zabs, age


def own_spikes(Lx, ok):
    """One-day moves against the source's own history (point in time): the log value against the median of the same
    weekday over the last 4 weeks, net of the trailing 28-day drift of that gap, in units of its own trailing robust
    spread. Returns |z| per cell (0 where it cannot be judged) and the own-history expectation."""
    T, S = Lx.shape
    z = np.zeros((T, S))
    expect = np.full((T, S), np.nan)
    for s in range(S):
        v = pd.Series(np.where(ok[:, s], Lx[:, s], np.nan))
        wd = pd.Series(np.arange(T) % 7)
        base = v.groupby(wd).transform(lambda x: x.shift(1).rolling(4, min_periods=2).median())
        gap = v - base
        drift = gap.rolling(28, min_periods=7).median().shift(1).fillna(0)
        dev = gap - drift
        spread = (1.4826 * (dev - dev.rolling(OWN_N, min_periods=20).median().shift(1)).abs()
                  .rolling(OWN_N, min_periods=20).median().shift(1)).clip(lower=SIG_FLOOR)
        z[:, s] = (dev.abs() / spread).fillna(0).to_numpy()
        expect[:, s] = (base + drift).to_numpy()
    return z, expect


def yearly(oz):
    """Days whose own-history move also happened within RECUR_SLACK days of the same date a year or two earlier (the
    recurring rule for the own-history check)."""
    T = oz.shape[0]
    big = oz > OWN_Z / 2
    out = np.zeros_like(big)
    for yrs in (1, 2):
        lag = 364 * yrs
        for k in range(-RECUR_SLACK, RECUR_SLACK + 1):
            sh = lag + k
            if 0 < sh < T:
                out[sh:] |= big[:-sh]
    return out


def process_ticker(g):
    dates = pd.date_range(g["date"].min(), g["date"].max(), freq="D")
    T = len(dates)
    srcs = sorted(g["source_id"].unique())
    S = len(srcs)
    sidx = {s: i for i, s in enumerate(srcs)}
    di = ((g["date"] - dates[0]).dt.days).to_numpy()
    si = g["source_id"].map(sidx).to_numpy()
    CT = np.full((T, S), np.nan)
    AMT = np.full((T, S), np.nan)
    CT[di, si] = g["ct"].to_numpy(float)
    AMT[di, si] = g["amt"].to_numpy(float)

    # low-signal mask: trailing median of the last LOW_WIN reported counts
    low = np.zeros((T, S), bool)
    for s in range(S):
        ok = np.isfinite(CT[:, s])
        if ok.any():
            med = pd.Series(CT[ok, s]).rolling(LOW_WIN, min_periods=14).median().to_numpy()
            held = pd.Series((med >= LOW_CT).astype(int)).rolling(ESTABLISHED, min_periods=ESTABLISHED).sum().to_numpy() >= ESTABLISHED
            est = np.maximum.accumulate(held)
            dropping, lo = True, np.zeros(len(med), bool)
            for i, (mv, e) in enumerate(zip(med, est)):
                if e or (np.isfinite(mv) and mv >= KEEP_CT):
                    dropping = False
                elif np.isfinite(mv) and mv < DROP_CT:
                    dropping = True
                lo[i] = dropping and not e
            low[ok, s] = lo
        low[~ok, s] = True     # rows without a usable count

    row = np.zeros((T, S), bool)
    row[di, si] = True
    ct_ok = np.isfinite(CT) & (CT > 0)
    tk_ok = ct_ok & np.isfinite(AMT) & (AMT > 0)
    with np.errstate(all="ignore"):
        LY = np.where(ct_ok, np.log(CT), np.nan)
        LK = np.where(tk_ok, np.log(AMT) - np.log(CT), np.nan)
    keep = row & ~low
    cy, fy, zy, ay = detect(LY, ct_ok & ~low, "ct", keep & ~ct_ok)
    ck, fk, zk, ak = detect(LK, tk_ok & ~low, "tk", keep & ~tk_ok)
    # one-day moves far outside the source's own history that also stand out against its peers: bad points
    oz_y, ox_y = own_spikes(LY, ct_ok & ~low)
    oz_k, ox_k = own_spikes(LK, tk_ok & ~low)
    young = (np.arange(T)[:, None] - kept_since(~low & row)) < YOUNG_DAYS   # settling in after being kept
    add_y = (oz_y > OWN_Z) & (zy > PEER_Z) & ~fy & np.isfinite(ox_y) & ~yearly(oz_y) & ~young
    add_k = (oz_k > OWN_Z) & (zk > PEER_Z) & ~fk & np.isfinite(ox_k) & ~yearly(oz_k) & ~young
    cy, fy = np.where(add_y, ox_y, cy), fy | add_y
    ck, fk = np.where(add_k, ox_k, ck), fk | add_k
    zy, zk = np.where(add_y, np.maximum(zy, SPIKE_Z + 0.5), zy), np.where(add_k, np.maximum(zk, SPIKE_Z + 0.5), zk)
    # a level change is distrusted while it settles; after SETTLE days its new level is the source's normal
    # (trusted, still rescaled in the cleaned series)
    fy_c = fy & ~(ay >= SETTLE)
    fk_c = fk & ~(ak >= SETTLE)

    # count: raw unless repaired; ticket: raw unless repaired; amount = count x ticket
    out_ct = np.where(fy, np.exp(cy), CT)
    tk = np.where(fk, ck, LK)
    with np.errstate(all="ignore"):
        out_amt = np.where(fy | fk, out_ct * np.exp(tk), AMT)
    blank = ~keep | ~np.isfinite(out_ct) | ~(out_ct > 0)
    out_amt = np.where(np.isfinite(out_amt), out_amt, np.nan)

    flag = fy_c | fk_c
    z = np.maximum(np.where(fy_c, zy, 0), np.where(fk_c, zk, 0))
    zall = np.maximum(zy, zk)
    conf = np.where(flag, 0.45 - 0.4 * (1 - np.exp(-np.maximum(z - 3, 0) / 5)),
                    0.5 + 0.5 * np.exp(-((zall / SPIKE_Z) ** 2) * 2))
    conf = np.where(blank, 0.05, conf)
    conf = np.where(~blank & ~np.isfinite(out_amt), np.minimum(conf, 0.3), conf)
    out_ct = np.where(blank, np.nan, out_ct)
    out_amt = np.where(blank, np.nan, out_amt)

    res = pd.DataFrame({
        "conf": conf[di, si],
        "clean_ct": out_ct[di, si],
        "clean_amt": out_amt[di, si],
    }, index=g.index)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    df = pd.read_csv(a.input)
    df["date"] = pd.to_datetime(df["date"])
    df["ct"] = pd.to_numeric(df["ct"], errors="coerce")
    df["amt"] = pd.to_numeric(df["amt"], errors="coerce")
    df = df.reset_index(drop=True)
    df["_row"] = np.arange(len(df))

    conf = np.full(len(df), 0.05)
    cct = np.full(len(df), np.nan)
    camt = np.full(len(df), np.nan)

    # duplicated (date, ticker, source) rows: keep the first for the model, distrust the rest
    dup = df.duplicated(["date", "ticker", "source_id"], keep="first").to_numpy()
    base = df[~dup]
    for _, g in base.groupby("ticker", sort=False):
        r = process_ticker(g)
        idx = g["_row"].to_numpy()
        conf[idx] = r["conf"].to_numpy()
        cct[idx] = r["clean_ct"].to_numpy()
        camt[idx] = r["clean_amt"].to_numpy()
    if dup.any():
        key = ["date", "ticker", "source_id"]
        firsts = df[~dup].set_index(key)["_row"]
        drow = df[dup]
        m = firsts.reindex(pd.MultiIndex.from_frame(drow[key])).to_numpy()
        cct[drow["_row"].to_numpy()] = cct[m]
        camt[drow["_row"].to_numpy()] = camt[m]
        conf[drow["_row"].to_numpy()] = np.minimum(conf[m], 0.3)

    out = pd.DataFrame({
        "date": df["date"].dt.strftime("%Y-%m-%d"),
        "ticker": df["ticker"],
        "source_id": df["source_id"],
        "confidence": np.clip(np.round(conf, 4), 0, 1),
        "clean_ct": cct,
        "clean_amt": camt,
    })
    out.to_csv(a.output, index=False)


if __name__ == "__main__":
    sys.exit(main())
