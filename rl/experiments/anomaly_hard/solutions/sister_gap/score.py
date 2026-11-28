"""Trust scores and cleaned series for a daily card-transaction panel.

    python score.py --input IN.csv --output OUT.csv

Every source of a company follows the same business, so each source is read against its sister sources. For each
company and each of two measures (log count, log ticket = log dollars per transaction):

  gap    how far the source sits today from its usual relation to its sisters. Each sister gives a reading:
         (source - sister) minus the median of that difference on the same weekday over the trailing year of
         cleaned values. The day is judged on the mean of the readings, weighted by how tightly each sister tracks
         the source; the level is measured on their median, which one sister's own slow shift cannot move.
  fault  when a gap is over the day bar, the source at fault is the one without which the others agree best; it is
         left out and the others are read again.
  level  the source's standing gap: the median gap of the last 28 days if that agrees with the last 14 and 7, else of
         the last 14 or 7; zero unless it is clear of the noise of such a median (in part while the evidence is
         partial). A level is dropped on the second day running that the source is back towards its usual relation.
  day    a day whose gap is far from the level is imputed from the sisters (their weighted mean); a day that did the
         same on the same date a year ago is kept as reported. A third identical report in a row (count and dollars,
         or a fourth of either alone) is imputed, and each one after it. A count imputed while the ticket stands out
         the opposite way (or the reverse) is read as a wrong count under good dollars.
  pair   with only two usable sources neither can say which of them moved: the day's move of the gap is shared
         between them by how far each moved against its own last weeks.
  trust  a row kept as reported or rescaled is trusted less the further its gap is from the level (two days running
         on the same side count as more than either); an imputed row is trusted more the further it was over the bar.

cleaned = reported - level (or the sisters' value on an imputed day). Everything for day t uses days <= t only.
"""
import argparse

import numpy as np
import pandas as pd

YEAR = 365           # trailing window for the usual relation and for noise (days)
WEEKS = 52           # same-weekday observations in the usual relation
K_DAY = 4.0          # a day's gap beyond this many noise sds is imputed
LONE = 2.0           # times K_DAY to impute a day when only one sister vouches
K_FLAKY = 2.5        # the day bar once FLAKY_N days were imputed in the last FLAKY_DAYS
FLAKY_N, FLAKY_DAYS = 3, 14
NEAR, STEADY = 2.5, 0.7   # a level needs this share of the last week within NEAR spreads of it
K_LO, K_HI = 2.5, 6.0   # a 7- or 14-day median gap this many of its own sds from zero starts to count as a level; in full from K_HI
K_LONG = 3.5         # a 28-day median gap beyond this many of its own sds is a level, in full (see standing level below)
AGREE = 1.5          # the 28-day median is used while within this many 7-day sds of the 7-day median
SHORT, MID, LONG = 7, 14, 28  # windows of the level medians (days)
OWN_WEEKS = 4        # weeks of a source's own same-weekday values that say what it should read today
MIN_WEEK = 4         # days a 7-day median needs: a majority of the week
MIN_SD = 0.02        # floor on a source's noise sd (log units)
DEFAULT_SD = 0.15    # noise sd before there is history to measure it
PAIR_MIN = 8         # same-weekday weeks needed to measure how tightly a pair of sources tracks
MIN_HIST = 30        # observations needed to measure a noise sd
STUCK_DAYS = 3       # identical reports in a row before a feed counts as stuck
MIRROR = 2.0         # spreads the other measure must stand out, the opposite way, to be read as the mirror of a wrong count
K_RUN = 3.0          # a gap this many spreads off stands out (who is at fault, a level's end)
STUCK_ONE_DAYS = 4   # identical reports in a row of one measure alone (count or dollars) before it counts as stuck
STUCK_ONE_MIN = 30   # a count repeating on its own counts as stuck from this many transactions (chance repeats below)
SWAP_TICKET = 1.0    # dollars per transaction under this: the two columns may be swapped
SWAP_BAND = 3.0      # ... if the reverse ratio is within this factor of the sisters' ticket that day
STUCK_MIN = 5        # a repeat of count and dollars counts as stuck from this many transactions
THIN_CT = 20         # transactions a day below which a new source carries no signal
THIN_EDGE = 0.8      # 7- and 28-day medians both at this share of THIN_CT already count as growing out of thin
THIN_CONF = 0.05     # confidence of a discarded row
THIN_DAYS = 90       # days at or above THIN_CT (28-day median) before a source counts as established
YEARLY_CONF = 0.8    # confidence of a row kept as reported because it stood out the same way a year ago
RECUR_SHARE = 0.5    # a gap at least this share of today's, same sign, a year ago: a yearly pattern, kept
MAJORITY_OF = 4      # sources needed to tell 'most moved together' from 'one moved': with three, two sisters cannot outvote
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


def gaps(x, adj, base, spread, bad, middle=False):
    """Gap of each source to its sisters today, from the readings x[s] - adj[j] - base[s, j] of its sisters j: their
    mean weighted by 1 / spread[s, j] squared (the noise sd of that pair's difference), or with `middle` their median
    (two sisters have no middle one: the weighted mean again). Sisters must report today, be established and not
    be marked bad; if none qualifies, any established sister. Also returns the number of sisters used and, where
    it is one, which."""
    S = len(x)
    g = np.full(S, np.nan)
    n = np.zeros(S, int)
    only = np.full(S, -1)
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
            n[s] = pick.sum()
            if n[s] == 2 or (n[s] > 2 and not middle):
                w = 1.0 / spread[s, pick] ** 2
                g[s] = (w * d[pick]).sum() / w.sum()
            else:
                g[s] = np.median(d[pick])
            if n[s] == 1:
                only[s] = int(np.argmax(pick))
    return g, n, only


def standing_level(G, t, since, sd, sd7, sd14, sd28, prev, sh_prev):
    """The level each source stands at on day t, from the medians of its gap over the last SHORT, MID and LONG days.
    Returns the three medians, the level, the share of it taken and whether it is on."""
    # the standing level, from the gap's recent medians
    r0 = max(t - LONG + 1, 0)
    w28 = G[r0:t + 1]
    if (since > r0).any():                 # after a level's end, earlier days no longer count towards the level
        w28 = w28.copy()
        for s in np.flatnonzero(since > r0):
            w28[:since[s] - r0, s] = np.nan
    w7, w14 = w28[-SHORT:], w28[-MID:]
    q7 = np.where((~np.isnan(w7)).sum(axis=0) >= MIN_WEEK, nanmed(w7, axis=0), np.nan)
    q14 = np.where((~np.isnan(w14)).sum(axis=0) >= 8, nanmed(w14, axis=0), np.nan)
    q28 = np.where((~np.isnan(w28)).sum(axis=0) >= 14, nanmed(w28, axis=0), np.nan)
    # the longest window that still agrees with the last week gives the level; its own noise sets the bar
    ok14 = ~np.isnan(q14) & (np.abs(q14 - q7) <= AGREE * sd7)
    agree = ok14 & ~np.isnan(q28) & (np.abs(q28 - q7) <= AGREE * sd7) & (np.abs(q28 - q14) <= AGREE * sd14)
    lvl = np.where(agree, q28, np.where(ok14, q14, q7))
    # a fresh level (short windows) between K_LO and K_HI is partial evidence, and so is the correction: a share
    # of the level, rising to all. A level four weeks agree on is taken in full from K_LONG: what is left
    # uncorrected for long is learnt as the usual relation, so a lasting level must not be corrected in part
    far = np.abs(lvl) / np.where(agree, sd28, np.where(ok14, sd14, sd7))
    share = np.where(agree, far > K_LONG, np.clip((far - K_LO) / (K_HI - K_LO), 0, 1))
    # a level that stands keeps the share it has reached
    share = np.where((share > 0) & (prev * lvl > 0), np.maximum(share, sh_prev), share)
    on = ~np.isnan(lvl) & (share > 0)
    # a level is a state the source sits in: most of the last week must be near it (a fault that comes and goes
    # leaves the week split between two values, and is treated day by day instead)
    near = (np.abs(w7 - lvl) <= NEAR * sd).sum(axis=0) / np.maximum((~np.isnan(w7)).sum(axis=0), 1)
    on &= near >= STEADY
    return q7, q14, q28, lvl, share, on


def common_level(q7, lv):
    """The part of the levels shared by most of a company's sources: with MAJORITY_OF sources or more that have a
    week of gaps, the middle level (of the two middle ones, the one nearer zero) if both are on the same side."""
    v = np.sort(lv[~np.isnan(q7)])
    if len(v) < MAJORITY_OF:
        return 0.0
    lo, hi = v[(len(v) - 1) // 2], v[len(v) // 2]
    return 0.0 if lo * hi <= 0 else (lo if abs(lo) < abs(hi) else hi)


def one_measure(X, est, stuck, is_count=False):
    """X: days x sources, log values (blank where no row); stuck: days x sources, a repeated report. Returns the
    cleaned log values, the evidence against the row (gap from level in noise sds), state (0 as reported, 1 imputed
    day, 2 rescaled level, 3 yearly pattern kept), n (sisters used), and the day's gap, its spread and the level
    in force."""
    T, S = X.shape
    X = np.where(est, X, np.nan)               # a source has a usual level only once it is established
    C = X.copy()                               # cleaned history, feeds the usual relation
    G = np.full((T, S), np.nan)                # gap the level windows see (the middle sister's reading)
    GD = np.full((T, S), np.nan)               # gap the day is judged on (weighted mean of the sisters' readings)
    E = np.full((T, S), np.nan)                # gap minus level
    EN = np.full((T, S), np.nan)               # the same on the whole gap
    Q7 = np.full((T, S), np.nan)
    Q14 = np.full((T, S), np.nan)
    Q28 = np.full((T, S), np.nan)
    LV = np.zeros((T, S))                      # level in force
    Z = np.zeros((T, S))
    ST = np.zeros((T, S), int)
    NS = np.zeros((T, S), int)
    SD = np.full((T, S), np.nan)
    SH = np.zeros((T, S))                      # share of the level taken
    since = np.zeros(S, int)                   # first day the level may be measured from
    run = np.zeros(S, int)                     # days running far off the level, same side
    side_prev = np.zeros(S)                    # which side yesterday was off, 0 if it was not
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
        # how tightly each pair tracks: robust sd of the same differences about the usual relation
        spread = MAD * nanmed(np.abs(P - base), axis=0)
        spread = np.where((~np.isnan(P)).sum(axis=0) >= PAIR_MIN, np.maximum(spread, MIN_SD), DEFAULT_SD)
        few = (~np.isnan(P)).sum(axis=0) < 3
        if few.any():                          # under three same-weekday weeks: the last three weeks, any weekday
            H = C[max(t - 21, 0):t]
            P = H[:, :, None] - H[:, None, :]
            recent = np.where((~np.isnan(P)).sum(axis=0) >= 7, nanmed(P, axis=0), np.nan)
            base = np.where(few, recent, base)
        lo = max(t - YEAR, 0)
        if t % 7 == 0 or sd_e is None:         # noise sds, re-measured weekly on the trailing year
            sd_e = robust_sd(EN[lo:t], DEFAULT_SD)
            sd_7 = robust_sd(Q7[lo:t] - LV[lo:t], np.nan)
            sd_14 = robust_sd(Q14[lo:t] - LV[lo:t], np.nan)
            sd_28 = robust_sd(Q28[lo:t] - LV[lo:t], np.nan)
        sd = sd_e
        sd7 = np.maximum(np.where(np.isnan(sd_7), 0.6 * sd, sd_7), 0.4 * sd)
        sd14 = np.maximum(np.where(np.isnan(sd_14), 0.5 * sd, sd_14), 0.32 * sd)
        sd28 = np.maximum(np.where(np.isnan(sd_28), 0.4 * sd, sd_28), 0.25 * sd)
        prev = LV[t - 1] if t else np.zeros(S)
        adj = x - prev                         # sisters at their usual level, by yesterday's level
        bad = np.zeros(S, bool)
        g, n, only = gaps(x, adj, base, spread, bad)
        if is_count:                           # a quiet day for the business: counting noise at the count the sisters imply
            quiet = np.exp(np.where(np.isnan(g), x, x - g + prev))
            sd = np.maximum(sd, 1.0 / np.sqrt(np.maximum(np.nan_to_num(quiet, nan=1.0), 1.0)))
        for _ in range(S - 1):                 # drop the source at fault and look again, until none stands out
            z0 = np.where(bad, 0, np.abs(np.nan_to_num(g - prev)) / sd)
            if z0.max() <= K_DAY:
                break
            # the one at fault is the one without which the others agree best: a fault in one source pushes its
            # sisters' gaps the other way, and a sister with little noise of its own can then stand out the most
            best = None
            for w in np.flatnonzero(z0 > K_RUN):
                trial = bad.copy()
                trial[w] = True
                g2, n2, only2 = gaps(x, adj, base, spread, trial)
                left = np.where(trial, 0, np.abs(np.nan_to_num(g2 - prev)) / sd).max()
                if best is None or (left, -z0[w]) < best[0]:
                    best = ((left, -z0[w]), w, g2, n2, only2)
            _, w, g2, n2, only2 = best
            bad[w] = True
            g = np.where(bad, g, g2)
            n = np.where(bad, n, n2)
            only = np.where(bad, only, only2)
        # one sister only: the two cannot tell which of them moved, but each one's own recent weeks can. Today's
        # move of the gap is given to each in proportion to its squared own move (against its cleaned values on
        # the same weekday of the last OWN_WEEKS weeks), so the one that jumped takes it and the other is left alone
        whole = g.copy()                       # the gap before it is shared out: the noise is measured on this
        pair = np.flatnonzero(only >= 0) if (~np.isnan(x)).sum() == 2 else []
        if len(pair):
            own = x - prev - nanmed(C[[t - 7 * k for k in range(1, OWN_WEEKS + 1) if t >= 7 * k]], axis=0)
            for s in pair:
                a, b = own[s] ** 2, own[only[s]] ** 2
                if np.isfinite(a + b) and a + b > 0:
                    g[s] = prev[s] + (whole[s] - prev[s]) * a / (a + b)
        # the level windows see the middle sister's gap, which a sister's own slow shift cannot move; the day is
        # judged on the weighted mean, which is tighter
        steady = gaps(x, adj, base, spread, bad, middle=True)[0]
        G[t], NS[t], SD[t] = np.where(only >= 0, g, steady), n, sd
        if t:
            # a level that has ended: the second day running more than K_RUN spreads off the level in force, on the
            # same side and nearer the usual relation than the level. The level is measured afresh from the first
            # of the two days, so it is dropped now instead of when the week's median turns
            off = g - prev
            with np.errstate(invalid='ignore'):
                side = np.where(np.abs(off) > K_RUN * sd, np.sign(off), 0.0)
            run = np.where((side != 0) & (side == side_prev), run + 1, (side != 0).astype(int))
            side_prev = side
            home = (run == 2) & (prev != 0) & (np.abs(g) < np.abs(off))
            since = np.where(home, t - 1, since)
        sh_prev = SH[t - 1] if t else np.zeros(S)
        level = standing_level(G, t, since, sd, sd7, sd14, sd28, prev, sh_prev)
        # a level is the source against its sisters, so only a minority can have moved: when most of the company's
        # sources stand at a level on the same side, that common part is taken off all of them
        shared = common_level(level[0], np.where(level[5], level[3] * level[4], 0.0))
        if shared:
            G[max(t - LONG + 1, 0):t + 1] -= shared
            g = g - shared
            prev = prev - shared
            level = standing_level(G, t, since, sd, sd7, sd14, sd28, prev, sh_prev)
        Q7[t], Q14[t], Q28[t], lvl, share, on = level
        GD[t] = g
        # after several repaired days in two weeks, a further fault is likelier: a lower bar for the day
        flaky = (ST[max(t - FLAKY_DAYS, 0):t] == 1).sum(axis=0) >= FLAKY_N
        kday = np.where(flaky, K_FLAKY, K_DAY)
        lv = np.where(on, lvl * share, 0.0)
        LV[t] = lv
        SH[t] = np.where(on, share, 0.0)
        e = g - lv
        E[t] = e
        EN[t] = whole - lv
        z = np.nan_to_num(e / sd)
        Z[t] = z
        for s in range(S):
            if np.isnan(x[s]) or np.isnan(g[s]):
                continue
            lone = n[s] < 2                     # one sister only: less sure which of the two is off
            if stuck[t, s]:
                ST[t, s] = 1                    # a repeated report: impute
                C[t, s] = x[s] - g[s]
                Z[t, s] = np.sign(z[s] or 1.0) * max(abs(z[s]), 1.5 * K_DAY)
                G[t, s] = GD[t, s] = np.nan     # a repeated report says nothing of where the source stands: not for the level
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
    # two days running on the same side are stronger evidence than either: the weaker of the two counts sqrt(2) times
    A = np.abs(Z)
    A[1:] = np.maximum(A[1:], np.where(Z[1:] * Z[:-1] > 0, np.sqrt(2) * np.minimum(A[1:], A[:-1]), 0))
    return C, A, ST, NS, (GD, SD, LV)


def recurs(E, t, s, e, sd):
    """Did this source stand out the same way on this date a year ago (364 to 366 days back)?"""
    for back in (364, 365, 366):
        if t - back >= 0:
            p = E[t - back, s]
            if np.isfinite(p) and p * e > 0 and abs(p) >= max(RECUR_SHARE * abs(e), K_DAY * sd):
                return True
    return False


def confidence(a, st, n):
    """Probability that the cleaned value is right, from how the row was treated and the evidence against it (a)."""
    # a kept row (as reported or rescaled): sure up to 2 sds, 0.95 at 3, then falling fast to 0.20 at 4 and beyond
    kept = 0.995 - 0.045 * np.clip(a - 2, 0, 1) - 0.75 * np.clip(a - 3, 0, 1)
    scaled = kept - 0.01                                         # the level itself may be off
    imputed = 0.82 + 0.16 * np.clip((a - K_DAY) / K_DAY, 0, 1)   # just over the bar it may be a false alarm
    c = np.select([st == 1, st == 2, st == 3], [imputed, scaled, YEARLY_CONF], kept)
    return np.where(n >= 1, c, 0.99)                         # no sister to compare with: kept as reported


def score_company(g):
    """One company: the output rows of all its sources."""
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
    # a stuck feed: the same count and dollars, to the cent, for STUCK_DAYS days running (flagged from the last of them)
    same = (ct == ct.shift(1)) & (amt == amt.shift(1))
    stuck = (same.astype(int).rolling(STUCK_DAYS - 1).sum() == STUCK_DAYS - 1) & (ct >= STUCK_MIN)
    stuck = stuck.to_numpy()
    # one measure stuck while the other moves: the same count, or the same dollars to the cent, STUCK_ONE_DAYS running
    rep = lambda v: (v == v.shift(1)).astype(int).rolling(STUCK_ONE_DAYS - 1).sum() == STUCK_ONE_DAYS - 1   # noqa: E731
    stuck_c = (rep(ct) & (ct >= STUCK_ONE_MIN)).to_numpy() & ~stuck
    stuck_a = (rep(amt) & (ct >= STUCK_MIN)).to_numpy() & ~stuck
    Cc, Zc, Sc, Nc, Dc = one_measure(lc.to_numpy(), est, stuck | stuck_c, is_count=True)
    Ct, Zt, St, Nt, Dt = one_measure(lt.to_numpy(), est, stuck | stuck_c | stuck_a)
    conf = np.minimum(confidence(Zc, Sc, Nc), confidence(Zt, St, Nt))
    same_c = (Sc == 0) | ((Sc == 3) & (Dc[2] == 0))     # as reported, unless a level in force has to come off
    same_t = (St == 0) | ((St == 3) & (Dt[2] == 0))
    clean_ct = np.where(same_c, ct.to_numpy(), np.exp(Cc))
    clean_amt = np.where(same_c & same_t, amt.to_numpy(), clean_ct * np.exp(Ct))
    # a wrong count with good dollars shows as a ticket off by as much the other way. When one measure is imputed and
    # the other, left alone, stands out the opposite way and is nearer that mirror image than its usual place, or
    # both are imputed and the ticket is within noise of the mirror image, the count is the one at fault: it is
    # imputed and the dollars are kept as reported (at the levels in force)
    Ec, Et = Dc[0] - Dc[2], Dt[0] - Dt[2]
    with np.errstate(invalid='ignore'):
        mirror = (Ec * Et < 0) & (np.abs(Ec + Et) < np.minimum(np.abs(Ec), np.abs(Et))) & ~(stuck | stuck_c | stuck_a)
        mirror &= ((Sc == 1) & np.isin(St, (0, 2)) & (np.abs(Et) > MIRROR * Dt[1])) | (
            (St == 1) & np.isin(Sc, (0, 2)) & (np.abs(Ec) > MIRROR * Dc[1])) | (
            (Sc == 1) & (St == 1) & (np.abs(Ec + Et) <= MIRROR * Dt[1]))
    conf = np.where(mirror, confidence(np.maximum(Zc, Zt), 1, Nc), conf)   # the mirror explains the other measure
    clean_ct = np.where(mirror, np.exp(lc.to_numpy() - Dc[0]), clean_ct)
    clean_amt = np.where(mirror, amt.to_numpy() * np.exp(-Dc[2] - Dt[2]), clean_amt)
    one_c = stuck_c & (Sc == 1) & (St == 1)      # count stuck, dollars good: the count is dollars / usual ticket
    clean_ct = np.where(one_c, amt.to_numpy() / np.exp(Ct), clean_ct)
    clean_amt = np.where(one_c, amt.to_numpy(), clean_amt)
    conf = np.where(thin, THIN_CONF, conf)                # a discarded row is not trusted
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
    return pd.concat(out, axis=1).reset_index()


def score_panel(df):
    """Every company on its own."""
    parts = []
    for tk, g in df.groupby('ticker', sort=False):
        r = score_company(g)
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
