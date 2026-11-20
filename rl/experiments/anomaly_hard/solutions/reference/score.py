"""Reference solution for anomaly_hard (work in progress): confidence and a like-for-like cleaned series, point in time.

    python score.py --input IN.csv --output OUT.csv

Honest: reads only its input (no gold, no truth panel). Built from the reviewer's rules:

* Each source is read against the median of its company's other sources (put on a common level first), in log count
  and log ticket size, so company-wide moves cancel. Two passes: the second compares against the peers as corrected by
  the first, so a source whose peers are broken is not blamed for them.
* Size is judged against the source's own noise (trailing robust spread of its residuals, with its weekday pattern).
* A one-to-three-day move beyond POINT_K units is a bad point: distrusted and imputed from the peers.
* A move that persists past MAX_POINT_DAYS, or a drift a CUSUM picks up, goes pending: distrusted, cleaned to the old
  level. If it comes back it is cancelled; if it lasts CONFIRM_DAYS and the source moved against most of its peers
  one by one, it is committed as an offset: trusted after SETTLE_DAYS, and removed from the cleaned series for as long
  as it lasts (a later change back removes it).
* A move on the same dates a year or two earlier is recurring: trusted and left as reported.
* Low-signal stretches (trailing 28-day median count under THIN_CT) are discarded: confidence 0, blank.
Each series is walked forward one day at a time, so every output for day t uses only rows dated t or earlier.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

THIN_CT = 20            # discard below this trailing 28-day median count
WARMUP = 28             # days of history before a series is judged
BASE_DAYS = 56          # trailing window for the source's relation to its peers
NOISE_DAYS = 120        # trailing window for the source's own noise
POINT_K = 5.0           # a day beyond this many noise units is a bad point
MAX_POINT_DAYS = 3      # outliers on more consecutive days than this are a level change
CUSUM_K, CUSUM_H = 1.0, 10.0   # drift detector, in noise units
SHIFT_MIN, SHIFT_MIN_K = 0.15, 2.0   # a level change must be at least this big (log units, and noise units)
SETTLE_DAYS = 30        # from a level change's start, days distrusted before the new level is trusted
CONFIRM_DAYS = 21       # a pending change that lasts this long is committed
CALM_DAYS, CALM_SHARE = 5, 0.4   # a pending change is cancelled when the median of its last 5 days is back within
# 40% of the move that set it off
RECUR_SLACK = 3         # days of slack when matching the same dates a year earlier
NOISE_FLOOR = 0.02
PASSES = 2              # walks per company: later ones compare against peers as corrected by the previous
WD_WEEKS = 8            # same-weekday history for the source's weekday pattern


def mad(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    if len(x) < 8:
        return np.nan
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def walk(dates: pd.DatetimeIndex, rel: np.ndarray, thin: np.ndarray, pairs: np.ndarray | None = None):
    """One channel of one series: rel is the source's log value minus its peers' median. Walks forward one day at a
    time. Returns per day (state, offset, expected): state 0 ok, 1 bad point, 2 settling after a committed level
    change, 3 recurring, 4 thin or warm-up, 5 pending level change; offset is the source's committed shift from its old basis (removed in the cleaned
    series); expected is the old-basis relation the cleaned series falls back to on distrusted days. pairs (days x
    peers) is the source against each peer on its own: a level change is only put on this source if it moved against
    most of its peers one by one (all of them when it has two or fewer), not just against their median."""
    n = len(rel)
    state = np.zeros(n, int)
    offset = np.zeros(n)
    expected = np.full(n, np.nan)
    bhist = np.full(n, np.nan)       # the baseline each day, so a drift is measured from before it began
    zhist = np.full(n, np.nan)       # residuals in noise units, for the recurring check
    adj = np.full(n, np.nan)         # rel - offset on accepted days: the old-basis relation the baseline is built from
    day_idx = {d: i for i, d in enumerate(dates)}
    O, run, seen, cp, cn, cp_start, cn_start = 0.0, [], 0, 0.0, 0.0, 0, 0
    pend = None                      # (start index, frozen baseline, frozen noise) while a change is pending
    prs = []                         # residuals since a change went pending
    settle_until = -1

    wdcache = {}

    def wd_term(i, b0):
        # the source's own weekday pattern against its peers: median over the last WD_WEEKS same weekdays
        vals = []
        for w in range(1, WD_WEEKS + 1):
            j = day_idx.get(dates[i] - pd.Timedelta(days=7 * w))
            if j is not None and np.isfinite(adj[j]):
                vals.append(adj[j])
        t = float(np.median(vals)) - b0 if len(vals) >= 3 else 0.0
        wdcache[i] = t
        return t

    def agree(p0, i, d):
        if pairs is None or pairs.shape[1] == 0:
            return True
        pre = pairs[max(0, p0 - 28):p0]
        post = pairs[max(p0, i - 13):i + 1]
        votes = []
        for k in range(pairs.shape[1]):
            a, b_ = pre[:, k], post[:, k]
            a, b_ = a[np.isfinite(a)], b_[np.isfinite(b_)]
            if len(a) >= 7 and len(b_) >= 3:
                sh = float(np.median(b_) - np.median(a))
                votes.append(np.sign(sh) == np.sign(d) and abs(sh) >= abs(d) / 2)
        if not votes:
            return True
        need = len(votes) if len(votes) <= 2 else int(np.ceil(2 * len(votes) / 3))
        return sum(votes) >= need

    def recurs(i, z):
        for yrs in (1, 2):
            for k in range(-RECUR_SLACK, RECUR_SLACK + 1):
                j = day_idx.get(dates[i] - pd.Timedelta(days=364 * yrs + k))
                if j is not None and np.isfinite(zhist[j]) and abs(zhist[j]) > POINT_K / 2 \
                        and np.sign(zhist[j]) == np.sign(z):
                    return True
        return False

    for i in range(n):
        offset[i] = O
        if not np.isfinite(rel[i]) or thin[i]:
            state[i] = 4
            continue
        seen += 1
        hist = adj[max(0, i - BASE_DAYS):i]
        hist = hist[np.isfinite(hist)]
        if seen <= WARMUP or len(hist) < 7:
            adj[i] = rel[i] - O
            expected[i] = adj[i]
            state[i] = 4
            continue
        if pend is not None:
            p0, b0, sig, d0 = pend
            b = b0 + wd_term(i, b0)
        else:
            b0 = float(np.median(hist))
            b = b0 + wd_term(i, b0)
            lo = max(0, i - NOISE_DAYS)
            res = adj[lo:i] - b0 - np.array([wdcache.get(j, 0.0) for j in range(lo, i)])
            sig = mad(res)
            sig = max(sig if np.isfinite(sig) else 0.1, NOISE_FLOOR)
        expected[i] = b
        bhist[i] = b0
        r = rel[i] - O - b
        z = r / sig
        zhist[i] = z
        if pend is not None:
            # a change is pending: hold the old basis until it either comes back (cancel) or lasts (commit)
            state[i] = 5
            prs.append(r)
            if len(prs) >= CALM_DAYS and abs(np.median(prs[-CALM_DAYS:])) < CALM_SHARE * abs(d0):
                pend = None
                adj[i] = rel[i] - O
            elif i - p0 >= CONFIRM_DAYS:
                seg = [rel[j] - O - expected[j] for j in range(i - 13, i + 1) if np.isfinite(expected[j])]
                d = float(np.median(seg)) if seg else 0.0
                if abs(d) >= max(SHIFT_MIN, 2 * sig) and agree(p0, i, d):
                    O += d
                    offset[i] = O
                    settle_until = p0 + SETTLE_DAYS
                pend = None
                adj[i] = rel[i] - O
            continue
        if abs(z) > POINT_K:
            if recurs(i, z):
                state[i] = 3
                run = []
                continue
            run.append(i)
            state[i] = 1
            if len(run) > MAX_POINT_DAYS and len({np.sign(zhist[j]) for j in run}) == 1:
                pend, prs = (run[0], b0, sig, float(np.median([zhist[j] for j in run])) * sig), []
                state[run] = 5
                run = []
            continue
        run = []
        # drift: a CUSUM in noise units; when it fires, the shift is measured from the baseline before it started
        if cp == 0:
            cp_start = i
        if cn == 0:
            cn_start = i
        cp = max(0.0, cp + min(z, POINT_K) - CUSUM_K)
        cn = max(0.0, cn - max(z, -POINT_K) - CUSUM_K)
        if cp > CUSUM_H or cn > CUSUM_H:
            j0 = cp_start if cp > CUSUM_H else cn_start
            bref = bhist[j0] if np.isfinite(bhist[j0]) else b0
            seg = [rel[j] - offset[j] - (expected[j] - bhist[j] + bref) for j in range(max(j0, i - 6), i + 1)
                   if np.isfinite(expected[j]) and np.isfinite(bhist[j]) and state[j] in (0, 2)]
            d = float(np.median(seg)) if seg else 0.0
            cp = cn = 0.0
            if abs(d) >= max(SHIFT_MIN, SHIFT_MIN_K * sig) and not recurs(i, d / sig):
                pend, prs = (j0, bref, sig, d), []
                state[i] = 5
                continue
        adj[i] = rel[i] - O
        if i <= settle_until:
            state[i] = 2
    return state, offset, expected


def score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    out = []
    for tk, g in df.groupby('ticker'):
        ct = g.pivot(index='date', columns='source_id', values='ct').astype(float)
        amt = g.pivot(index='date', columns='source_id', values='amt').astype(float)
        dates, srcs = ct.index, list(ct.columns)
        lc = np.log(ct.clip(lower=0.01))
        lt = np.log(amt.clip(lower=0.01)) - lc
        thin = (ct.rolling(28, min_periods=1).median() < THIN_CT) | ct.isna()    # trailing: point in time

        def common(x, use):
            # peers on a common level: each source's log value less its trailing one-year relation to the company
            # average (sources have their own scales; without this the median would jump between sources)
            avg = x.where(use).mean(axis=1)
            rel = x.sub(avg, axis=0).where(use)
            return x - rel.rolling(365, min_periods=28).median().shift(1)

        # PASSES walks: the first compares each source with its peers as reported; later ones with its peers as
        # corrected by the previous pass (their committed offsets removed, their distrusted days left out), so a source
        # whose peers are themselves broken is not mistaken for the broken one. Each pass is point in time.
        oc = pd.DataFrame(0.0, index=dates, columns=srcs)
        ot = pd.DataFrame(0.0, index=dates, columns=srcs)
        bad = pd.DataFrame(False, index=dates, columns=srcs)
        for _ in range(PASSES):
            use = ~thin & ~bad
            nc, nt = common(lc - oc, use), common(lt - ot, use)
            res = {}
            for s in srcs:
                peers = [c for c in srcs if c != s]
                if peers:
                    pc = nc[peers].where(use[peers]).median(axis=1)
                    pt = nt[peers].where(use[peers]).median(axis=1)
                else:                       # a single source: judged against its own history only
                    pc = pt = pd.Series(0.0, index=dates)
                th = thin[s].to_numpy()
                pair_c = (lc[s].to_numpy()[:, None] - nc[peers].where(use[peers]).to_numpy()) if peers else None
                pair_t = (lt[s].to_numpy()[:, None] - nt[peers].where(use[peers]).to_numpy()) if peers else None
                res[s] = (pc, pt, walk(dates, (lc[s] - pc).to_numpy(), th, pair_c),
                          walk(dates, (lt[s] - pt).to_numpy(), th, pair_t))
            for s, (pc, pt, (sc, o_c, _), (st, o_t, _)) in res.items():
                oc[s], ot[s] = o_c, o_t
                bad[s] = np.isin(sc, (1, 5)) | np.isin(st, (1, 5))
        for s, (pc, pt, (sc, o_c, ec), (st, o_t, et)) in res.items():
            has = ct[s].notna().to_numpy()
            bad_pt_c, bad_pt_t = sc == 1, st == 1
            # distrusted days (bad points, pending changes) fall back to the old-basis expectation; the rest keep the
            # raw value less any committed offset. Count and ticket are handled apart, so a problem in one keeps the other.
            imp_c = (bad_pt_c | (sc == 5)) & np.isfinite(pc.to_numpy() + ec)
            imp_t = (bad_pt_t | (st == 5)) & np.isfinite(pt.to_numpy() + et)
            clc = np.where(imp_c, pc.to_numpy() + ec, lc[s].to_numpy() - o_c)
            clt = np.where(imp_t, pt.to_numpy() + et, lt[s].to_numpy() - o_t)
            conf = np.ones(len(dates))
            conf[np.isin(sc, (2, 5)) | np.isin(st, (2, 5))] = 0.3
            conf[bad_pt_c | bad_pt_t] = 0.05
            discard = thin[s].to_numpy() & has
            conf[discard] = 0.0
            cct, camt = np.exp(clc), np.exp(clc + clt)
            cct[discard] = np.nan
            camt[discard] = np.nan
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
    df = pd.read_csv(a.input)
    res = score(df)
    res['date'] = res.date.dt.strftime('%Y-%m-%d')
    res.to_csv(a.output, index=False, float_format='%.6g')


if __name__ == '__main__':
    main()
