import numpy as np
import pandas as pd

# ---------------------------------------------------------------- parameters
P = dict(
    MIN_CT=10,          # a sensor must have seen >= this many daily transactions (trailing 28d median) to be trusted
    ELIG_LOOKBACK=180,  # ... at some point within this many trailing days (so an outage doesn't instantly disqualify it)
    MIN_HISTORY=56,     # days of history before a sensor is considered "warmed up"
    REF_WIN=90,         # trailing window (clean days only) for the sensor-vs-peer offset and noise scale
    SHORT_WIN=7,        # window used to test whether a deviation is persistent (level shift) vs one-off
    Z_POINT=4.0,        # |z| at which point-anomaly probability = 50%
    Z_SLOPE=1.5,
    SHIFT_K=4.0,        # shift threshold: multiples of the robust spread of the 7-day median statistic
    MIN_REF=60,         # clean reference days required before level-shift detection switches on
    MIN_SHIFT=np.log(1.25),  # ...and never smaller than a 25% move
    ACCEPT_DAYS=90,     # after this long a shift is accepted as the new normal (offset re-based, cleaned series adjusted)
    DROPOUT_FRAC=0.25,  # 7d median count below 25% of the trailing-180d 75th percentile => sensor dropout
    SIGMA_FLOOR=0.03,
    SIGMA_PRIOR=0.35,
    CM_WIDEN_AT=0.4,    # ticker-wide moves beyond +/-0.4 log (~50%) widen the point-anomaly noise band proportionally   # noise assumed while a sensor has < 14 clean reference days
)



def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def prepare(flat):
    """Flat table -> per-ticker T x K (dates x sources) frames on a complete daily calendar."""
    flat = flat.copy()
    flat['date'] = pd.to_datetime(flat['date'])
    dates = pd.date_range(flat.date.min(), flat.date.max(), freq='D')
    sources = sorted(flat.source_id.unique())
    cube = {}
    for tk, g in flat.groupby('ticker'):
        ct = g.pivot(index='date', columns='source_id', values='ct').reindex(index=dates, columns=sources)
        amt = g.pivot(index='date', columns='source_id', values='amt').reindex(index=dates, columns=sources)
        missing = ct.isna()
        # a sensor that hasn't started yet stays NaN; a missing day after the first report = 0 transactions reported
        started = ct.notna().cummax()
        ct = ct.fillna(0).where(started)
        amt = amt.fillna(0).where(started)
        cube[tk] = dict(ct=ct, amt=amt, missing=missing & started, started=started)
    return dates, sources, cube


def eligibility(ct, p=P):
    """Programmatic junk filter. Causal: uses data up to t-1 only."""
    lam = ct.shift(1).rolling(28, min_periods=14).median()
    elig = lam.rolling(p['ELIG_LOOKBACK'], min_periods=1).max() >= p['MIN_CT']
    hist = ct.notna().cumsum()
    return elig & (hist >= p['MIN_HISTORY']), lam


def dropout_flag(ct, p=P):
    """Absolute 'sensor went dark' rule (catches outages that hit every sensor at once,
    which the cross-sensor comparison cannot see). Causal."""
    ref = ct.shift(1).rolling(180, min_periods=28).quantile(0.75)
    med7 = ct.rolling(7, min_periods=4).median()
    persistent = (med7 < p['DROPOUT_FRAC'] * ref) & (ref >= p['MIN_CT'])
    # single missing / zero day when we would have expected plenty of volume is also a dropout
    zero = (ct == 0) & (ref >= 3 * p['MIN_CT'])
    return persistent, zero


def score_series(X, s, elig, n_exp, cm_move, p=P):
    """Online (strictly causal) scoring of sensor s against its peers for one ticker/metric.

    X: T x K log1p values (NaN before a sensor starts)
    n_exp: expected count today (for the Poisson noise floor)
    cm_move: ticker-wide consensus move today (from common_mode); used to widen the point-noise band on
             big ticker-wide days (closures, Black Friday) where sensors legitimately capture traffic differently
    Returns dict of per-day arrays.
    """
    T, K = X.shape
    others = [j for j in range(K) if j != s]
    D = X[:, [s]] - X[:, others]            # pairwise log-ratios s vs each peer: shared seasonality cancels
    D[~elig[:, others]] = np.nan            # only compare with trustworthy peers
    own = X[:, s]

    ERAW = np.full(T, np.nan)
    E = np.full(T, np.nan)                  # excess move of s vs peers, relative to the reference offset
    Z = np.full(T, np.nan)                  # point z-score
    S = np.full(T, np.nan)                  # 7d persistent deviation (level-shift statistic)
    SIG = np.full(T, np.nan)
    p_point = np.zeros(T); p_shift = np.zeros(T)
    state = np.zeros(T, dtype=int)          # 0 normal, 1 in level shift, 2 just re-based after accepted shift
    shift_est = np.zeros(T); cum_adj = np.zeros(T)
    mode = np.full(T, 'none', dtype=object)
    nref = np.zeros(T)

    clean = np.zeros(T, dtype=bool)         # days usable as reference
    in_shift = False; frozen_off = None; frozen_sig = None; frozen_thr = None; shift_start = None
    adj = 0.0
    W, SW = p['REF_WIN'], p['SHORT_WIN']

    for t in range(T):
        if np.isnan(own[t]):
            continue
        lo = max(0, t - W)
        ref_mask = clean[lo:t]
        peers_ok = ~np.isnan(D[t])
        if peers_ok.sum() >= 1:
            # ---- cross-sensor mode
            mode[t] = 'peer' if peers_ok.sum() >= 2 else 'pair'
            if in_shift:
                off, sig = frozen_off, frozen_sig
            else:
                Dref = D[lo:t][ref_mask]
                off = np.nanmedian(Dref, axis=0) if len(Dref) >= 14 else np.full(len(others), np.nan)
                sig = None
            dev = D[t] - off
            if np.all(np.isnan(dev[peers_ok])):
                mode[t] = 'warmup'
                clean[t] = True
                continue
            E[t] = np.nanmedian(dev[peers_ok])
        else:
            # ---- fallback: own history only (no trustworthy peers)
            mode[t] = 'own'
            ref = own[lo:t][ref_mask]
            if len(ref) < 14:
                clean[t] = True
                continue
            E[t] = own[t] - (frozen_off if in_shift and np.ndim(frozen_off) == 0 else np.median(ref))
            sig = frozen_sig if in_shift else None

        # day-of-week adjustment: sensors differ in how strongly they see the weekly cycle, so remove the
        # typical excess on this weekday (median of the last 8 clean same-weekday values of the raw excess)
        ERAW[t] = E[t]
        same = np.arange(t - 7, max(-1, t - 57), -7)
        same = same[same >= 0]
        if len(same):
            vals = ERAW[same][clean[same] & ~np.isnan(ERAW[same])]
            allv = ERAW[max(0, t - 56):t][clean[max(0, t - 56):t] & ~np.isnan(ERAW[max(0, t - 56):t])]
            if len(vals) >= 4:
                # weekday effect only (weekday median minus overall median) so the level itself is not absorbed
                E[t] = ERAW[t] - (np.median(vals) - np.median(allv))

        # noise scale: robust MAD of recent clean E values, floored by Poisson noise
        Eref = E[lo:t][clean[lo:t] & ~np.isnan(E[lo:t])]
        nref[t] = len(Eref)
        if sig is None:
            if len(Eref) >= 14:
                sig = 1.4826 * np.median(np.abs(Eref - np.median(Eref)))
            else:
                sig = p['SIGMA_PRIOR']                     # not enough history yet: conservative prior noise level
        lam_s = n_exp[t] if not np.isnan(n_exp[t]) else 1.0   # expected count today
        floor = max(p['SIGMA_FLOOR'], np.sqrt(2.0 / max(lam_s, 1.0)))
        sig = floor if np.isnan(sig) else max(sig, floor)
        SIG[t] = sig

        # persistence statistic: median excess over the last SW days (includes today)
        recent = E[max(0, t - SW + 1):t + 1]
        recent = recent[~np.isnan(recent)]
        S[t] = np.median(recent) if len(recent) >= 4 else np.nan
        # shift threshold from the empirical spread of the 7d statistic itself on clean days (captures autocorrelation)
        if in_shift:
            thr = frozen_thr
        else:
            Sref = S[lo:t][clean[lo:t] & ~np.isnan(S[lo:t])]
            sdS = 1.4826 * np.median(np.abs(Sref - np.median(Sref))) if len(Sref) >= 30 else 1.2533 * sig / np.sqrt(SW)
            thr = max(p['SHIFT_K'] * max(sdS, 1.2533 * sig / np.sqrt(SW)), p['MIN_SHIFT'])
        # point z vs the current regime level (median of the previous week)
        prev = E[max(0, t - SW):t]; prev = prev[~np.isnan(prev)]
        level = np.median(prev) if len(prev) >= 3 else 0.0
        if not in_shift and abs(level) < thr:
            level = 0.0                                   # in a normal regime the expected excess is 0
        widen = 1.0 + max(0.0, abs(cm_move[t]) - p['CM_WIDEN_AT']) if not np.isnan(cm_move[t]) else 1.0
        Z[t] = (E[t] - level) / (sig * widen)
        p_point[t] = sigmoid(p['Z_SLOPE'] * (abs(Z[t]) - p['Z_POINT']))
        if not np.isnan(S[t]):
            p_shift[t] = sigmoid(4.0 * (abs(S[t]) / thr - 1.0))

        # ---- level-shift state machine
        if not in_shift:
            if not np.isnan(S[t]) and abs(S[t]) > thr and nref[t] >= p['MIN_REF']:
                in_shift = True; shift_start = t
                frozen_sig = sig; frozen_thr = thr
                if mode[t] == 'own':
                    frozen_off = np.median(own[lo:t][ref_mask]) if ref_mask.sum() else own[t]
                else:
                    frozen_off = off.copy()
        else:
            dur = t - shift_start
            if np.isnan(S[t]) or abs(S[t]) < 0.5 * thr:
                in_shift = False                          # returned to the old level -> temporary shift over
            elif dur >= p['ACCEPT_DAYS']:
                # accept the new level as the new normal; remember the size for the cleaned series
                tail = E[shift_start:t + 1]; tail = tail[~np.isnan(tail)]
                size = np.median(tail[-30:])
                adj += size
                in_shift = False; state[t] = 2
                # re-base: subsequent reference uses only post-shift data
                clean[:t] = False

        if in_shift:
            state[t] = 1
            shift_est[t] = S[t]
        cum_adj[t] = adj
        clean[t] = (not in_shift) and abs(Z[t]) < 3.0

    return dict(E=E, z=Z, S=S, sigma=SIG, p_point=p_point, p_shift=np.where(state == 1, p_shift, 0.5 * p_shift),  # half weight outside a confirmed shift
                state=state, shift_est=shift_est, cum_adj=cum_adj, mode=mode, nref=nref)


def common_mode(X, elig, p=P):
    """Ticker-level detector for breaks that hit *every* sensor at once (e.g. a ticker re-mapping, or an
    upstream outage). Cross-sensor comparison is blind to these, so we look at the consensus move of all
    sensors vs. their own trailing level, seasonally adjusted with the same window one year earlier
    (only when that year-ago window was itself clean). Strictly causal."""
    T, K = X.shape
    W = p['REF_WIN']
    c = np.full(T, np.nan); cs = np.full(T, np.nan); S = np.full(T, np.nan)
    state = np.zeros(T, dtype=int); pcm = np.zeros(T); thr_used = np.full(T, np.nan)
    usable = np.zeros(T, bool)
    in_shift = False; frozen_off = None; start = None
    for t in range(T):
        ok = elig[t] & ~np.isnan(X[t])
        if ok.sum() == 0:
            continue
        lo = max(0, t - W)
        ref = X[lo:t][usable[lo:t]]
        if in_shift:
            off = frozen_off
        else:
            if len(ref) < 28:
                usable[t] = True
                continue
            off = np.nanmedian(ref, axis=0)
        dev = X[t] - off
        okd = ok & ~np.isnan(dev)
        if okd.sum() == 0:
            usable[t] = True
            continue
        c[t] = np.median(dev[okd])
        # seasonal adjustment: subtract what the consensus did around the same date last year (if that was clean)
        y = t - 364
        if y >= 3 and not np.isnan(c[y - 3:y + 4]).all() and (state[y - 3:y + 4] == 0).all():
            cs[t] = c[t] - np.nanmedian(c[y - 3:y + 4]); thr = np.log(2.0)
        else:
            cs[t] = c[t]; thr = np.log(4.0)       # no clean seasonal reference yet: only catch very large breaks
        thr_used[t] = thr
        win = cs[max(0, t - 6):t + 1]; win = win[~np.isnan(win)]
        S[t] = np.median(win) if len(win) >= 4 else np.nan
        if not np.isnan(S[t]):
            pcm[t] = sigmoid(4.0 * (abs(S[t]) / thr - 1.0))
        if not in_shift:
            if not np.isnan(S[t]) and abs(S[t]) > thr:
                in_shift = True; start = t; frozen_off = off.copy()
        else:
            if np.isnan(S[t]) or abs(S[t]) < 0.5 * thr:
                in_shift = False
            elif t - start >= p['ACCEPT_DAYS']:
                in_shift = False
                usable[:t] = False                   # re-base on post-break data
        state[t] = int(in_shift)
        usable[t] = not in_shift
    pcm = np.where(state == 1, pcm, 0.5 * pcm)
    return dict(cm_c=c, cm_S=S, cm_state=state, cm_p=pcm)


def run_model(flat, p=P, metrics=('ct', 'amt')):
    dates, sources, cube = prepare(flat)
    out = []
    for tk, d in cube.items():
        elig_df, lam_df = eligibility(d['ct'], p)
        drop_pers, drop_zero = dropout_flag(d['ct'], p)
        elig = elig_df.values; lam = lam_df.values
        cm = common_mode(np.log1p(d['ct'].values.astype(float)), elig, p)
        # expected count today = trailing level x today's ticker-wide move (so closure days get a wide noise band)
        n_exp = lam * np.exp(np.nan_to_num(np.minimum(cm['cm_c'], 0.0)))[:, None]
        per_metric = {}
        for m in metrics:
            v = d[m].astype(float)
            if m == 'amt':
                # express dollars in "typical tickets" (causal trailing median ticket) so that log1p treats a
                # $0 day like a zero-count day instead of an enormous drop from e.g. $5,000
                ticket = (d['amt'] / d['ct']).replace([np.inf, -np.inf], np.nan)
                ticket = ticket.shift(1).rolling(90, min_periods=7).median().fillna(
                    ticket.shift(1).expanding().median()).fillna(ticket)
                v = v / ticket
            X = np.log1p(v.values)
            per_metric[m] = [score_series(X, s, elig, n_exp[:, s], cm['cm_c'], p) for s in range(len(sources))]
        for k, src in enumerate(sources):
            frame = pd.DataFrame({'date': dates, 'ticker': tk, 'source_id': src,
                                  'ct': d['ct'].iloc[:, k].values, 'amt': d['amt'].iloc[:, k].values,
                                  'was_missing': d['missing'].iloc[:, k].values,
                                  'eligible': elig[:, k], 'lam28': lam[:, k],
                                  'dropout_persistent': drop_pers.iloc[:, k].values,
                                  'dropout_zero': drop_zero.iloc[:, k].values})
            for key, v in cm.items():
                frame[key] = v
            for m in metrics:
                r = per_metric[m][k]
                for key in ('E', 'z', 'S', 'sigma', 'p_point', 'p_shift', 'state', 'shift_est', 'cum_adj', 'mode', 'nref'):
                    frame[f'{m}_{key}'] = r[key]
            out.append(frame[frame.ct.notna()])
    res = pd.concat(out, ignore_index=True)
    return finalize(res, p, metrics)


def finalize(res, p=P, metrics=('ct', 'amt')):
    # a single zero day only counts as a dropout if the ticker as a whole was not also down (store closures:
    # Thanksgiving / Christmas / Easter show up as zeros in some sensors and near-zeros in the others)
    res['dropout'] = res['dropout_persistent'] | (res['dropout_zero'] & ~(res['cm_c'] < -np.log(3)))
    # --- per-metric anomaly probability
    for m in metrics:
        pp = res[f'{m}_p_point'].fillna(0); ps = res[f'{m}_p_shift'].fillna(0)
        res[f'{m}_p_anom'] = 1 - (1 - pp) * (1 - ps)
    pd_ = res['dropout'].astype(float) * 0.98
    p_anom = 1 - (1 - pd_) * (1 - res['cm_p'].fillna(0)) * np.prod([1 - res[f'{m}_p_anom'] for m in metrics], axis=0)
    # --- reliability: how much does the model know about this sensor at this date?
    n = res['ct_nref'].fillna(0)
    rel_hist = np.clip(n / p['REF_WIN'], 0, 1)                  # grows as clean history accumulates
    rel_mode = res['ct_mode'].map({'peer': 1.0, 'pair': 0.85, 'own': 0.6}).fillna(0.0)
    rel_vol = np.where(res['eligible'], 1.0, 0.5)               # low-volume ("junk") sensors are less trustworthy
    rel = (0.3 + 0.7 * rel_hist) * rel_mode * rel_vol
    rel = np.where(res['dropout'], 1.0, rel)                    # we are sure about a dropout
    res['reliability'] = rel
    res['p_anomaly'] = p_anom
    # confidence = prob the datapoint is trustworthy; shrinks to 0.5 (no information) when reliability is low
    res['confidence'] = rel * (1 - p_anom) + (1 - rel) * 0.5
    res['label'] = label(res, metrics)
    return res


def label(res, metrics):
    lab = np.full(len(res), 'ok', dtype=object)
    shifted = np.zeros(len(res), bool); point = np.zeros(len(res), bool); post = np.zeros(len(res), bool)
    for m in metrics:
        shifted |= (res[f'{m}_state'] == 1).values
        point |= (res[f'{m}_p_point'] > 0.5).values
        post |= (res[f'{m}_cum_adj'].abs() > 0).values
    lab[post] = 'ok_post_shift_adjusted'
    lab[~res['eligible'].values] = 'low_volume'
    lab[point & ~shifted] = np.where(res.loc[point & ~shifted, 'ct_z'].fillna(res.loc[point & ~shifted, 'amt_z']) > 0,
                                     'point_spike', 'point_drop')
    lab[shifted] = np.where(res.loc[shifted, 'ct_shift_est'].fillna(0) + res.loc[shifted, 'amt_shift_est'].fillna(0) > 0,
                            'level_shift_up', 'level_shift_down')
    cm = (res['cm_state'] == 1).values
    lab[cm] = np.where(res.loc[cm, 'cm_S'] > 0, 'common_shift_up', 'common_shift_down')
    lab[res['dropout'].values] = 'dropout'
    return lab


def clean_series(res, m='ct'):
    """Cleaned value: remove level-shift effect; replace point anomalies / dropouts with the peer-implied value."""
    x = np.log1p(res[m].astype(float))
    shift = res[f'{m}_shift_est'].fillna(0) + res[f'{m}_cum_adj'].fillna(0)
    implied = x - res[f'{m}_E'].fillna(0) + res[f'{m}_shift_est'].fillna(0)  # what peers say, at the current regime
    xc = x - shift
    bad_point = res[f'{m}_p_point'] > 0.5
    xc = np.where(bad_point, implied - shift, xc)
    xc = np.where(res['dropout'], np.nan, xc)
    return np.expm1(xc)
