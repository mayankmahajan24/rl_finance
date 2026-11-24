"""Grader check, not a solution: the best a point-in-time scorer could plausibly do (a ceiling for the task).

Like the oracle it reads the task's gold and truth panel (ORACLE_TASK), but it only acts the way an excellent past-only
detector could:

* It knows what each row should read (the truth panel), and judges a row by its deviation from that in units of
  the source's own noise against its peers (sigma, per series and channel: log count and log ticket).
* A one-day problem is caught on the day only if it stands out: more than POINT_K sigma. Smaller ones are missed.
* A level change is caught once its deviation's trailing 3-day median (a step) or 14-day median (a slow ramp) passes
  SHIFT_K sigma, so ramps are caught late. Inside a change, one-day problems are judged against the shifted level so
  far, caught or not. From then on its onset is distrusted (until DISTRUST_DAYS after its start) and the cleaned
  series is rescaled to the old level; after that the new level is trusted, still rescaled.
* When a temporary shift ends, the correction carries on for RETURN_DAYS before the return is noticed.
* Imputed and rescaled values carry the source's own noise (a deterministic draw per row, clipped at 2 sigma, times
  NOISE): the best a peer-based estimate can do. NOISE = 0 (solutions/ceiling_ideal) is the ideal variant with exact
  imputation.
* The thin beginning is dropped as the grader expects; yearly closures and real company events are left alone (they
  do not deviate from the truth).
"""
import argparse
import json
import os
import pathlib
import sys

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from grade import KEYS, label_rows  # noqa: E402

POINT_K, SHIFT_K = 3.0, 2.0
DISTRUST_DAYS = 30
RETURN_DAYS = 3
NOISE = globals().get('NOISE_OVERRIDE', 1.0)


def own_noise(truth: pd.DataFrame) -> pd.DataFrame:
    """sigma per series and channel: robust spread of the source's daily relation to its peers' median, around its
    own 28-day median (from the truth panel)."""
    out = []
    for tk, g in truth.groupby('ticker'):
        lc = np.log(g.pivot(index='date', columns='source_id', values='ct').clip(lower=0.01))
        lt = np.log(g.pivot(index='date', columns='source_id', values='amt').clip(lower=0.01)) - lc
        for s in lc.columns:
            peers = [c for c in lc.columns if c != s]
            row = dict(ticker=tk, source_id=s)
            for name, x in (('sig_c', lc), ('sig_t', lt)):
                rel = x[s] - (x[peers].median(axis=1) if peers else 0)
                r = (rel - rel.rolling(28, min_periods=7, center=True).median()).dropna()
                row[name] = max(float(1.4826 * (r - r.median()).abs().median()), 0.02) if len(r) > 20 else 0.15
            out.append(row)
    return pd.DataFrame(out)


def draw(df: pd.DataFrame, salt: int) -> np.ndarray:
    """A deterministic standard normal per row (same row, same draw, whatever else is in the input), clipped at 2."""
    h = pd.util.hash_pandas_object(df[KEYS].assign(_s=salt), index=False).to_numpy()
    u1 = ((h >> np.uint64(11)) & np.uint64((1 << 26) - 1)).astype(float) / (1 << 26) + 1e-9
    u2 = ((h >> np.uint64(37)) & np.uint64((1 << 26) - 1)).astype(float) / (1 << 26)
    return np.clip(np.sqrt(-2 * np.log(u1)) * np.cos(2 * np.pi * u2), -2, 2)


ap = argparse.ArgumentParser(); ap.add_argument('--input'); ap.add_argument('--output'); a = ap.parse_args()
df = pd.read_csv(a.input, parse_dates=['date'])
task = pathlib.Path(os.environ['ORACLE_TASK'])
gold = json.loads((task / 'tests' / 'gold.json').read_text())
truth = pd.read_csv(task / 'tests' / 'truth_panel.csv.gz', parse_dates=['date'])
label_rows(gold, df, truth)                       # sets df.thin (stretches the grader expects dropped)

# what each row should read
df = df.merge(truth[KEYS + ['ct', 'amt']].rename(columns={'ct': 'xct', 'amt': 'xamt'}), on=KEYS, how='left')
df = df.merge(own_noise(truth), on=['ticker', 'source_id'], how='left')
df = df.sort_values(['ticker', 'source_id', 'date']).reset_index(drop=True)
dev_c = np.log(df.ct.clip(lower=0.01) / df.xct)
dev_t = np.log(df.amt.clip(lower=0.01) / df.ct.clip(lower=0.01)) - np.log(df.xamt / df.xct)
df['z'] = np.maximum(dev_c.abs() / df.sig_c, dev_t.abs() / df.sig_t)

# the best estimate of the right value: the truth, with the source's own noise
nz_c, nz_t = draw(df, 1) * NOISE, draw(df, 2) * NOISE
est_ct = df.xct * np.exp(df.sig_c * nz_c)
est_amt = est_ct * (df.xamt / df.xct) * np.exp(df.sig_t * nz_t)

conf = np.ones(len(df))
fix = df.z.to_numpy() > POINT_K                  # one-day problems that stand out are caught on the day
clean_ct, clean_amt = df.ct.to_numpy(float).copy(), df.amt.to_numpy(float).copy()
conf[fix] = 0.05
D = pd.Timedelta
for e in gold['events']:
    if not e.get('regime'):
        continue
    ser = ((df.ticker == e['ticker']) & (df.source_id == e['source_id'])).to_numpy()
    a0, b0 = pd.Timestamp(e.get('shift_start', e['start'])), pd.Timestamp(e['end'])
    span = ser & (df.date >= a0).to_numpy() & (df.date <= b0).to_numpy()
    # inside a level change, a one-day problem is judged against the shifted level so far (trailing 14 days), whether
    # or not the change has been caught: a real detector adapts to a level it missed
    lvl_c = dev_c.where(ser).rolling(14, min_periods=3).median().shift(1)
    lvl_t = dev_t.where(ser).rolling(14, min_periods=3).median().shift(1)
    zrel = np.maximum((dev_c - lvl_c).abs() / df.sig_c, (dev_t - lvl_t).abs() / df.sig_t).fillna(0).to_numpy()
    pt = span & (zrel > POINT_K)
    fix[span] = pt[span]
    conf[span] = np.where(pt[span], 0.05, 1.0)
    # caught once the deviation's trailing median passes SHIFT_K: 3 days for a step, 14 for a slow ramp
    z3 = df.z.where(ser).rolling(3, min_periods=3).median().to_numpy()
    z14 = df.z.where(ser).rolling(14, min_periods=7).median().to_numpy()
    hit = span & ((z3 > SHIFT_K) | (z14 > SHIFT_K))
    if not hit.any():
        continue
    td = df.date[hit].min()
    on = ser & (df.date >= td).to_numpy() & (df.date <= b0).to_numpy()
    fix |= on
    early = (df.date <= pd.Timestamp(e['start']) + D(days=DISTRUST_DAYS - 1)).to_numpy()
    conf[on & early] = 0.3
    # past the onset the new level is the source's normal (rescaled in the cleaned series): trusted, unless a one-day
    # problem stands out on top of the shifted level
    after = on & ~early
    if after.any():
        # the shifted level so far (trailing 14-day median of the deviation, point in time)
        lvl_c = dev_c.where(on).rolling(14, min_periods=3).median().shift(1)
        lvl_t = dev_t.where(on).rolling(14, min_periods=3).median().shift(1)
        # and its noise on the new level (trailing 56 days): a source at a lower level is noisier
        rc, rt = (dev_c - lvl_c).where(on), (dev_t - lvl_t).where(on)
        mad = lambda r: (1.4826 * r.abs().rolling(56, min_periods=7).median().shift(1))  # noqa: E731
        sc = np.maximum(mad(rc).fillna(df.sig_c), df.sig_c)
        st_ = np.maximum(mad(rt).fillna(df.sig_t), df.sig_t)
        zs = np.maximum(rc.abs() / sc, rt.abs() / st_).fillna(0).to_numpy()
        conf[after] = np.where(zs[after] > POINT_K, 0.05, 1.0)
    if not e.get('permanent'):
        # the return goes unnoticed for RETURN_DAYS: the old correction is still applied
        last = on & (df.date > b0 - D(days=7)).to_numpy()
        off_c, off_t = float(np.median(dev_c[last])), float(np.median(dev_t[last]))
        back = ser & (df.date > b0).to_numpy() & (df.date <= b0 + D(days=RETURN_DAYS)).to_numpy()
        clean_ct[back] = df.ct[back] * np.exp(-off_c)
        clean_amt[back] = clean_ct[back] * (df.amt[back] / df.ct[back]) * np.exp(-off_t)
        conf[back] = 0.3
clean_ct[fix], clean_amt[fix] = est_ct[fix], est_amt[fix]
thin = df.thin.to_numpy()
conf[thin] = 0.0
clean_ct[thin], clean_amt[thin] = np.nan, np.nan
df['confidence'], df['clean_ct'], df['clean_amt'] = conf, clean_ct, clean_amt
df['date'] = df.date.dt.strftime('%Y-%m-%d')
df[KEYS + ['confidence', 'clean_ct', 'clean_amt']].to_csv(a.output, index=False)
