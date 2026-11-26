"""Trust scores and cleaned series for a daily card-transaction panel.

    python score.py --input IN.csv --output OUT.csv

Every source of a company follows the same business, so each source is read against its sister sources. For each
company and each of two measures (log count, log ticket = log dollars per transaction):

  gap    how far the source sits today from its usual relation to its sisters: the median, over sisters, of
         (source - sister) minus the median of that difference on the same weekday over the trailing year of
         cleaned values.
  level  the source's standing gap: the median gap of the last 28 days if that agrees with the last 14 and 7, else of
         the last 14 or 7; zero unless it is clear of the noise of such a median.
  day    a day whose gap is far from the level is imputed from the sisters; a day that did the same on the same
         date a year ago is kept as reported. A third identical report in a row (count and dollars) is imputed, and each one after it.

cleaned = reported - level (or the sisters' value on an imputed day). Everything for day t uses days <= t only.
"""
import argparse

import numpy as np
import pandas as pd

YEAR = 365           # trailing window for the usual relation and for noise (days)
WEEKS = 52           # same-weekday observations in the usual relation
K_DAY = 4.0          # a day's gap beyond this many noise sds is imputed
LONE = 2.0           # times K_DAY to impute a day when only one sister vouches or several sources are off
K_FLAKY = 2.5        # the day bar once FLAKY_N days were imputed in the last FLAKY_DAYS
FLAKY_N, FLAKY_DAYS = 3, 14
NEAR, STEADY = 2.5, 0.7   # a level needs this share of the last week within NEAR spreads of it
FAINT = 2.0          # under a level, a count whose counting noise exceeds this many spreads is imputed, not rescaled
K_LEVEL = 4.0        # a 7- or 28-day median gap beyond this many of its own sds is a level change
AGREE = 1.5          # the 28-day median is used while within this many 7-day sds of the 7-day median
SHORT, MID, LONG = 7, 14, 28  # windows of the level medians (days)
MIN_SD = 0.02        # floor on a source's noise sd (log units)
DEFAULT_SD = 0.15    # noise sd before there is history to measure it
MIN_HIST = 30        # observations needed to measure a noise sd
STUCK_DAYS = 3       # identical reports in a row before a feed counts as stuck
STUCK_ONE_DAYS = 4   # identical reports in a row of one measure alone (count or dollars) before it counts as stuck
STUCK_ONE_MIN = 30   # a count repeating on its own counts as stuck from this many transactions (chance repeats below)
SWAP_TICKET = 1.0    # dollars per transaction under this: the two columns may be swapped
SWAP_BAND = 3.0      # ... if the reverse ratio is within this factor of the sisters' ticket that day
POOL_OFF = 3.0       # a level this many day-spreads from zero is far enough for "back at zero" to mean something
POOL_BACK = 1.5      # back at the usual relation: the day's gap within this many spreads of zero
POOL_MIN, POOL_SHARE = 2, 0.75   # a source is released when this many of its shifted companies, and this share, are back
STUCK_MIN = 5        # a repeat of count and dollars counts as stuck from this many transactions
THIN_CT = 20         # transactions a day below which a new source carries no signal
THIN_EDGE = 0.8      # 7- and 28-day medians both at this share of THIN_CT already count as growing out of thin
THIN_DAYS = 90       # days at or above THIN_CT (28-day median) before a source counts as established
RECUR_SHARE = 0.5    # a gap at least this share of today's, same sign, a year ago: a yearly pattern, kept
MAD = 1.4826         # median absolute deviation -> standard deviation, for normal noise


def nanmed(a, axis=0):
    """Median along an axis ignoring blanks; blank where there is nothing."""
    a = np.sort(np.asarray(a, float), axis=axis)          # blanks sort last
    n = (~np.isnan(a)).sum(axis=axis, keepdims=True)
    if a.shape[axis] == 0:
        return np.full(np.delete(a.shape, axis), np.nan)
    lo = np.take_along_axis(a, np.maximum((n - 1) // 2, 0), axis=axis)
    hi = np.take_along_axis(a, np.maximum(n // 2, 0), axis=axis)
    return np.where(n > 0, (lo + hi) / 2, np.nan).squeeze(axis=axis)


def robust_sd(hist, default):
    """MAD-based sd of each column of hist (days x sources); default where under MIN_HIST observations."""
    n = (~np.isnan(hist)).sum(axis=0)
    sd = MAD * nanmed(np.abs(hist - nanmed(hist, axis=0)), axis=0)
    return np.where((n >= MIN_HIST) & np.isfinite(sd), np.maximum(sd, MIN_SD), default)


def gaps(x, adj, base, bad):
    """Gap of each source to its sisters today: median over sisters j of x[s] - adj[j] - base[s, j].
    Sisters must report today, be established and not be marked bad; if none qualifies, any established sister."""
    S = len(x)
    g = np.full(S, np.nan)
    n = np.zeros(S, int)
    for s in range(S):
        if np.isnan(x[s]):
            continue
        d = x[s] - adj - base[s]
        d[s] = np.nan
        ok = ~np.isnan(d)
        pick = ok & ~bad
        if not pick.any():
            pick = ok
        if pick.any():
            g[s] = np.median(d[pick])
            n[s] = pick.sum()
    return g, n


def one_measure(X, est, pred_ct=None, stuck=None, cnt=None, release=None):
    """X: days x sources, log values (blank where no row). Returns the cleaned log values, z (gap from level in
    noise sds), state (0 as reported, 1 imputed day, 2 rescaled level, 3 yearly pattern kept), moving (level taken
    from the 7-day median), n (sisters used), and for pooling across companies the raw gap, its spread and the
    level in force. `release` (days x sources): the source's level is dropped that day and measured afresh from
    there, because its other companies came back to their usual relation on the same day."""
    T, S = X.shape
    X = np.where(est, X, np.nan)               # a source has a usual level only once it is established
    C = X.copy()                               # cleaned history, feeds the usual relation
    G = np.full((T, S), np.nan)                # gap to sisters
    E = np.full((T, S), np.nan)                # gap minus level
    Q7 = np.full((T, S), np.nan)
    Q14 = np.full((T, S), np.nan)
    Q28 = np.full((T, S), np.nan)
    LV = np.zeros((T, S))                      # level in force
    Z = np.zeros((T, S))
    ST = np.zeros((T, S), int)
    MV = np.zeros((T, S), bool)
    NS = np.zeros((T, S), int)
    SD = np.full((T, S), np.nan)
    since = np.zeros(S, int)                   # first day the level may be measured from
    sd_e = sd_7 = sd_14 = sd_28 = None
    for t in range(T):
        x = X[t]
        if np.isnan(x).all():
            continue
        # usual relation between each pair: same weekday, trailing year, cleaned values
        idx = np.arange(t - 7, max(t - 7 * WEEKS, 0) - 1, -7)
        idx = idx[idx >= 0]
        H = C[idx]
        P = H[:, :, None] - H[:, None, :]
        base = nanmed(P, axis=0)
        few = (~np.isnan(P)).sum(axis=0) < 3
        if few.any():                          # under three same-weekday weeks: the last three weeks, any weekday
            H = C[max(t - 21, 0):t]
            P = H[:, :, None] - H[:, None, :]
            recent = np.where((~np.isnan(P)).sum(axis=0) >= 7, nanmed(P, axis=0), np.nan)
            base = np.where(few, recent, base)
        lo = max(t - YEAR, 0)
        if t % 7 == 0 or sd_e is None:         # noise sds, re-measured weekly on the trailing year
            sd_e = robust_sd(E[lo:t], DEFAULT_SD)
            sd_7 = robust_sd(Q7[lo:t] - LV[lo:t], np.nan)
            sd_14 = robust_sd(Q14[lo:t] - LV[lo:t], np.nan)
            sd_28 = robust_sd(Q28[lo:t] - LV[lo:t], np.nan)
        sd = sd_e
        if pred_ct is not None:                # counting noise of a small source
            sd = np.maximum(sd, 1.0 / np.sqrt(np.maximum(np.nan_to_num(pred_ct[t], nan=1.0), 1.0)))
        sd7 = np.maximum(np.where(np.isnan(sd_7), 0.6 * sd, sd_7), 0.4 * sd)
        sd14 = np.maximum(np.where(np.isnan(sd_14), 0.5 * sd, sd_14), 0.32 * sd)
        sd28 = np.maximum(np.where(np.isnan(sd_28), 0.4 * sd, sd_28), 0.25 * sd)
        prev = LV[t - 1] if t else np.zeros(S)
        if release is not None and release[t].any():
            since = np.where(release[t], t, since)
            prev = np.where(release[t], 0.0, prev)
        adj = x - prev                         # sisters at their usual level, by yesterday's level
        bad = np.zeros(S, bool)
        g, n = gaps(x, adj, base, bad)
        for _ in range(S - 1):                 # drop the worst sister and look again, until none stands out
            z0 = np.where(bad, 0, np.abs(np.nan_to_num(g - prev)) / sd)
            w = int(np.argmax(z0))
            if z0[w] <= K_DAY:
                break
            bad[w] = True
            g2, n2 = gaps(x, adj, base, bad)
            g = np.where(bad, g, g2)
            n = np.where(bad, n, n2)
        G[t], NS[t], SD[t] = g, n, sd
        # the standing level, from the gap's recent medians
        r0 = max(t - LONG + 1, 0)
        w28 = G[r0:t + 1]
        if (since > r0).any():                 # after a release, days before it no longer count towards the level
            w28 = w28.copy()
            for s in np.flatnonzero(since > r0):
                w28[:since[s] - r0, s] = np.nan
        w7, w14 = w28[-SHORT:], w28[-MID:]
        q7 = np.where((~np.isnan(w7)).sum(axis=0) >= 4, nanmed(w7, axis=0), np.nan)
        q14 = np.where((~np.isnan(w14)).sum(axis=0) >= 8, nanmed(w14, axis=0), np.nan)
        q28 = np.where((~np.isnan(w28)).sum(axis=0) >= 14, nanmed(w28, axis=0), np.nan)
        Q7[t], Q14[t], Q28[t] = q7, q14, q28
        # the longest window that still agrees with the last week gives the level; its own noise sets the bar
        ok14 = ~np.isnan(q14) & (np.abs(q14 - q7) <= AGREE * sd7)
        agree = ok14 & ~np.isnan(q28) & (np.abs(q28 - q7) <= AGREE * sd7) & (np.abs(q28 - q14) <= AGREE * sd14)
        lvl = np.where(agree, q28, np.where(ok14, q14, q7))
        thr = K_LEVEL * np.where(agree, sd28, np.where(ok14, sd14, sd7))
        on = ~np.isnan(lvl) & (np.abs(lvl) > thr)
        # a level is a state the source sits in: most of the last week must be near it (a fault that comes and goes
        # leaves the week split between two values, and is treated day by day instead)
        near = (np.abs(w7 - lvl) <= NEAR * sd).sum(axis=0) / np.maximum((~np.isnan(w7)).sum(axis=0), 1)
        on &= near >= STEADY
        # after several repaired days in two weeks, a further fault is likelier: a lower bar for the day
        flaky = (ST[max(t - FLAKY_DAYS, 0):t] == 1).sum(axis=0) >= FLAKY_N
        kday = np.where(flaky, K_FLAKY, K_DAY)
        lv = np.where(on, lvl, 0.0)
        LV[t] = lv
        MV[t] = on & ~agree
        e = g - lv
        E[t] = e
        z = np.nan_to_num(e / sd)
        Z[t] = z
        for s in range(S):
            if np.isnan(x[s]) or np.isnan(g[s]):
                continue
            lone = n[s] < 2 or bad.sum() > 1    # one sister only, or several sources off at once: less sure whose fault
            faint = on[s] and cnt is not None and 1.0 / np.sqrt(max(cnt[t, s], 1.0)) > FAINT * sd[s]
            if (stuck is not None and stuck[t, s]) or faint:
                ST[t, s] = 1                    # a repeated report, or too few transactions left to rescale: impute
                C[t, s] = x[s] - g[s]
                Z[t, s] = np.sign(z[s] or 1.0) * max(abs(z[s]), 1.5 * K_DAY)
            elif abs(z[s]) > kday[s] * (LONE if lone else 1):
                if recurs(E, t, s, e[s], sd[s]):
                    ST[t, s] = 3
                    C[t, s] = x[s] - lv[s]
                else:
                    ST[t, s] = 1
                    C[t, s] = x[s] - g[s]
            else:
                ST[t, s] = 2 if on[s] else 0
                C[t, s] = x[s] - lv[s]
    return C, Z, ST, MV, NS, (G, SD, LV)


def recurs(E, t, s, e, sd):
    """Did this source stand out the same way on this date a year ago (364 to 366 days back)?"""
    for back in (364, 365, 366):
        if t - back >= 0:
            p = E[t - back, s]
            if np.isfinite(p) and p * e > 0 and abs(p) >= max(RECUR_SHARE * abs(e), K_DAY * sd):
                return True
    return False


def confidence(z, st, mv, n):
    """Probability that the cleaned value is right, from how the row was treated and how far it stood out."""
    a = np.abs(z)
    asis = 0.995 - 0.005 * np.minimum(a, 2) / 2 - 0.22 * np.clip((a - 2) / (K_DAY - 2), 0, 1)   # 0.995 .. 0.77
    imputed = 0.52 + 0.40 * np.clip((a - K_DAY) / K_DAY, 0, 1)                                 # 0.52 .. 0.92
    scaled = np.where(mv, 0.90, 0.97) - 0.15 * np.clip(a / K_DAY, 0, 1)
    yearly = 0.80 - 0.05 * np.clip(a / (4 * K_DAY), 0, 1)
    c = np.select([st == 1, st == 2, st == 3], [imputed, scaled, yearly], asis)
    c = np.where((n == 1) & (st == 1), 0.51 + 0.1 * (c - 0.52), c)   # one sister: either of the two could be off
    return np.where(n >= 1, c, 0.97)                         # no sister to compare with: kept as reported


def score_company(g, release=None):
    """One company. `release`: (count, ticket) frames of days x sources on which a source's level is dropped (see
    pooled). Returns the output rows and, per measure, the gap, spread and level in force for pooling."""
    ct = g.pivot(index='date', columns='source_id', values='ct').astype(float)
    amt = g.pivot(index='date', columns='source_id', values='amt').astype(float)
    days = pd.date_range(ct.index.min(), ct.index.max(), freq='D')   # every calendar day, so weekdays line up
    ct, amt = ct.reindex(days).rename_axis('date'), amt.reindex(days).rename_axis('date')
    # columns swapped: dollars per transaction under SWAP_TICKET, and the reverse ratio in line with the other
    # sources that day (or, with none to compare, with this source's own earlier days): the row is swapped back
    # before anything else looks at it
    tk, back = amt / ct, ct / amt
    good = tk.where(tk >= SWAP_TICKET)
    ref = pd.DataFrame({s: good.drop(columns=s).median(axis=1) for s in good.columns})
    ref = ref.where(ref.notna(), good.shift(1).rolling(LONG, min_periods=1).median().ffill())
    swapped = (tk < SWAP_TICKET) & (back >= SWAP_TICKET) & (
        ref.isna() | ((back / ref >= 1 / SWAP_BAND) & (back / ref <= SWAP_BAND)))
    ct, amt = ct.where(~swapped, amt), amt.where(~swapped, ct)
    ct = ct.where(ct > 0)
    lc = np.log(ct)
    lt = np.log(amt.where(amt > 0)) - lc
    med28 = ct.rolling(LONG, min_periods=1).median()
    held = (med28 >= THIN_CT).astype(int)
    run = held.apply(lambda h: h.groupby((h == 0).cumsum()).cumsum())   # days running at or above THIN_CT
    established = (run >= THIN_DAYS).cummax()
    med7 = ct.rolling(SHORT, min_periods=1).median()
    growing = (med7 >= THIN_EDGE * THIN_CT) & (med28 >= THIN_EDGE * THIN_CT)   # both medians near the line: on its way up
    thin = (~established & ~(med28 >= THIN_CT) & ~growing).to_numpy()            # too few a day, not yet growing
    est = established.to_numpy()
    pred = ct.shift(1).rolling(LONG, min_periods=1).median().to_numpy()
    # a stuck feed: the same count and dollars, to the cent, for STUCK_DAYS days running (flagged from the last of them)
    same = (ct == ct.shift(1)) & (amt == amt.shift(1))
    stuck = (same.astype(int).rolling(STUCK_DAYS - 1).sum() == STUCK_DAYS - 1) & (ct >= STUCK_MIN)
    stuck = stuck.to_numpy()
    # one measure stuck while the other moves: the same count, or the same dollars to the cent, STUCK_ONE_DAYS running
    rep = lambda v: (v == v.shift(1)).astype(int).rolling(STUCK_ONE_DAYS - 1).sum() == STUCK_ONE_DAYS - 1   # noqa: E731
    stuck_c = (rep(ct) & (ct >= STUCK_ONE_MIN)).to_numpy() & ~stuck
    stuck_a = (rep(amt) & (ct >= STUCK_MIN)).to_numpy() & ~stuck
    rel_c, rel_t = (None, None) if release is None else (r.reindex(index=days, columns=ct.columns).fillna(False)
                                                         .to_numpy(bool) for r in release)
    Cc, Zc, Sc, Mc, Nc, Dc = one_measure(lc.to_numpy(), est, pred, stuck | stuck_c, ct.to_numpy(), rel_c)
    Ct, Zt, St, Mt, Nt, Dt = one_measure(lt.to_numpy(), est, None, stuck | stuck_c | stuck_a, None, rel_t)
    conf = np.minimum(confidence(Zc, Sc, Mc, Nc), confidence(Zt, St, Mt, Nt))
    same_c = np.isin(Sc, (0, 3))
    same_t = np.isin(St, (0, 3))
    clean_ct = np.where(same_c, ct.to_numpy(), np.exp(Cc))
    clean_amt = np.where(same_c & same_t, amt.to_numpy(), clean_ct * np.exp(Ct))
    one_c = stuck_c & (Sc == 1) & (St == 1)      # count stuck, dollars good: the count is dollars / usual ticket
    clean_ct = np.where(one_c, amt.to_numpy() / np.exp(Ct), clean_ct)
    clean_amt = np.where(one_c, amt.to_numpy(), clean_amt)
    conf = np.where(thin, 0.05, conf)
    clean_ct = np.where(thin, np.nan, clean_ct)
    clean_amt = np.where(thin, np.nan, clean_amt)
    # what was done to the row: the stronger of the two measures' treatments
    rank = np.array([0, 3, 2, 1])                                   # as reported < yearly < rescaled < imputed
    worst = np.where(rank[Sc] >= rank[St], Sc, St)
    treat = np.array(['as reported', 'imputed', 'rescaled', 'yearly pattern kept'], dtype=object)[worst]
    treat = np.where(swapped.to_numpy() & (worst == 0), 'columns swapped back', treat)
    treat = np.where(thin, 'discarded', treat)
    out = []
    for k, name in ((conf, 'confidence'), (clean_ct, 'clean_ct'), (clean_amt, 'clean_amt'), (treat, 'treatment')):
        out.append(pd.DataFrame(k, index=ct.index, columns=ct.columns).stack(future_stack=True).rename(name))
    diag = [tuple(pd.DataFrame(a, index=ct.index, columns=ct.columns) for a in d) for d in (Dc, Dt)]
    return pd.concat(out, axis=1).reset_index(), diag


def pooled(diags):
    """A source's problem that hits all its companies ends for all of them on one day. For each measure, day and
    source: of the companies whose series stood at a level well away from zero (POOL_OFF spreads) coming into the
    day, count those whose gap is back at zero today (within POOL_BACK spreads). With POOL_MIN or more back, and
    POOL_SHARE of them, every shifted series of that source that is nearer zero than its old level is released:
    its level is dropped that day instead of waiting for its own week of evidence. Uses the day and earlier only."""
    out = {tk: [] for tk in diags}
    for m in (0, 1):
        on, back, near = {}, {}, {}
        for tk, d in diags.items():
            G, SD, LV = d[m]
            prev = LV.shift(1)
            on[tk] = prev.abs() >= POOL_OFF * SD
            back[tk] = on[tk] & (G.abs() <= POOL_BACK * SD)
            near[tk] = (prev != 0) & prev.notna() & (G.abs() < (G - prev).abs())
        idx = sorted(set().union(*[x.index for x in on.values()]))
        cols = sorted(set().union(*[x.columns for x in on.values()]))
        tot = lambda d: sum(x.reindex(index=idx, columns=cols).fillna(False).astype(int) for x in d.values())   # noqa: E731
        n_on, n_back = tot(on), tot(back)
        go = (n_back >= POOL_MIN) & (n_back >= POOL_SHARE * n_on)
        for tk in diags:
            out[tk].append(near[tk] & go.reindex(index=near[tk].index, columns=near[tk].columns).fillna(False))
    return out


def score_panel(df):
    """Every company once; then again, with the pooled releases, for the companies that have one."""
    first = {tk: score_company(g) for tk, g in df.groupby('ticker', sort=False)}
    release = pooled({tk: d for tk, (_, d) in first.items()})
    parts = []
    for tk, g in df.groupby('ticker', sort=False):
        r = first[tk][0]
        if any(x.to_numpy().any() for x in release[tk]):
            r = score_company(g, release[tk])[0]
        r.insert(1, 'ticker', tk)
        parts.append(r)
    return pd.concat(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    df = pd.read_csv(a.input)
    df['date'] = pd.to_datetime(df['date'])
    res = score_panel(df)
    out = df[['date', 'ticker', 'source_id']].merge(res, on=['date', 'ticker', 'source_id'], how='left')
    out['confidence'] = out['confidence'].fillna(0.5).clip(0, 1).round(4)
    blank = out.clean_ct.isna() & (out.confidence >= 0.5)       # no usable reading (e.g. zero count): keep as reported
    out.loc[blank, 'clean_ct'] = df.loc[blank, 'ct'].to_numpy()
    out.loc[blank, 'clean_amt'] = df.loc[blank, 'amt'].to_numpy()
    out['clean_ct'] = out['clean_ct'].round(2)
    out['clean_amt'] = out['clean_amt'].round(2)
    out['date'] = out['date'].dt.strftime('%Y-%m-%d')
    out.to_csv(a.output, index=False)


if __name__ == '__main__':
    main()
