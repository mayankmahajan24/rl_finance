"""Pool independent detectors over the REAL data, once, to find candidate real problems:
    python pool.py OUT.json [LABEL=SCORE_PY ...]

All tasks are built from the bench companies' real panel (disguised, then planted), so its real problems are labelled
once, in original coordinates, and every task inherits the labels (reviewed.yaml -> build.py). One model's alerts
only ever show what that model flagged, so its misses stay unlabelled; a pool of different detectors finds them,
the way search benchmarks pool systems to build their answer keys.

Detectors (a flag = a day the detector distrusts):
  own_point   one-day move of count or ticket size against the source's own history (weekday-matched, trailing)
              beyond OWN_K x its own noise
  peer_point  one-day move of the source against the median of the company's other sources (relative to its own
              trailing 28-day relation) beyond PEER_K x the noise of that relation
  peer_drift  CUSUM of that relation (k=1, h=8 noise units, both ways): a slow drift away from the other sources
  LABEL       any scorer given on the command line (score.py with confidence, or an older anomaly_score scorer),
              run on the raw panel
A candidate is a run of days on one series (gaps of up to GAP days joined) that any detector flagged, with the
detectors that flagged it and its largest move against the source's own history and against the other sources.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
RL = HERE.parents[1]
sys.path.insert(0, str(RL))
OWN_K, PEER_K, DRIFT_K, DRIFT_H = 6.0, 6.0, 1.0, 8.0
GAP = 2
MAX_DAYS = 400     # per-series chart days are all kept; candidate runs longer than this are split for review


def mad(x):
    x = x.dropna()
    return float(1.4826 * (x - x.median()).abs().median()) if len(x) else np.nan


def own_dev(v: pd.Series) -> pd.Series:
    """Log value against the same weekday's trailing median (last 4 weeks), net of its trailing 28-day drift."""
    base = v.groupby(v.index.dayofweek).transform(lambda x: x.shift(1).rolling(4, min_periods=2).median())
    d = v - base
    return d - d.rolling(28, min_periods=7).median().shift(1).fillna(0)


def baselines(raw: pd.DataFrame) -> dict:
    """Per (ticker, source): DataFrame by date with the three baseline detectors' flags and the move sizes."""
    out = {}
    for tk, g in raw.groupby('ticker'):
        ct = np.log(g.pivot(index='date', columns='source_id', values='ct'))
        tk_ = np.log(g.pivot(index='date', columns='source_id', values='amt')) - ct
        for s in ct.columns:
            f = pd.DataFrame(index=ct[s].dropna().index)
            oc, ot = own_dev(ct[s].dropna()), own_dev(tk_[s].dropna())
            zc, zt = oc / mad(oc), ot / mad(ot)
            f['own_z'] = pd.concat([zc.abs(), zt.abs()], axis=1).max(axis=1)
            f['own_move'] = np.where(zc.abs() >= zt.abs(), oc, ot)
            f['own_point'] = f.own_z > OWN_K
            peers = [c for c in ct.columns if c != s]
            if peers:
                rel = (ct[s] - ct[peers].median(axis=1)).reindex(f.index)
                rr = rel - rel.rolling(28, min_periods=7).median().shift(1)
                sd = mad(rr)
                pz = rr / sd
                f['peer_z'] = pz.abs()
                f['peer_move'] = rr
                f['peer_point'] = pz.abs() > PEER_K
                cp = cn = 0.0
                drift = []
                for z in np.clip(pz.fillna(0).to_numpy(), -4, 4):
                    cp, cn = max(0.0, cp + z - DRIFT_K), max(0.0, cn - z - DRIFT_K)
                    on = cp > DRIFT_H or cn > DRIFT_H
                    drift.append(on)
                    if abs(z) < 1 and on:          # back in line: let the evidence decay
                        cp, cn = cp * 0.8, cn * 0.8
                f['peer_drift'] = drift
            else:
                f['peer_z'], f['peer_move'], f['peer_point'], f['peer_drift'] = np.nan, np.nan, False, False
            out[(tk, int(s))] = f
    return out


def run_scorer(score_py: pathlib.Path, raw: pd.DataFrame) -> pd.DataFrame:
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        raw.to_csv(d / 'in.csv', index=False, date_format='%Y-%m-%d')
        r = subprocess.run([sys.executable, str(score_py), '--input', str(d / 'in.csv'), '--output',
                            str(d / 'out.csv')], cwd=d, capture_output=True, text=True, timeout=3600)
        if r.returncode:
            raise SystemExit(f'{score_py} failed: {r.stderr[-800:]}')
        o = pd.read_csv(d / 'out.csv', parse_dates=['date'])
    flag = o.confidence < 0.5 if 'confidence' in o else o.anomaly_score > 0.5
    return o.assign(flag=flag)[['date', 'ticker', 'source_id', 'flag']]


def runs(dates: pd.DatetimeIndex) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    if len(dates) == 0:
        return []
    s = pd.Series(sorted(dates))
    rid = (s.diff().dt.days.fillna(999) > GAP + 1).cumsum()
    return [(g.iloc[0], g.iloc[-1]) for _, g in s.groupby(rid)]


def main():
    from families._shared import build_panel
    dest = pathlib.Path(sys.argv[1])
    scorers = dict(a.split('=', 1) for a in sys.argv[2:])
    raw = build_panel.context('txn_panel', 'bench').raw.copy()
    raw['date'] = pd.to_datetime(raw['date'])
    det = baselines(raw)
    names = ['own_point', 'peer_point', 'peer_drift']
    for lab, path in scorers.items():
        o = run_scorer(pathlib.Path(path), raw)
        for (tk, s), f in det.items():
            m = o[(o.ticker == tk) & (o.source_id == s)].set_index('date').flag
            f[lab] = m.reindex(f.index).fillna(False).astype(bool)
        names.append(lab)
        print(lab, 'flags', int(o.flag.sum()))
    series, cands = [], []
    for (tk, s), f in sorted(det.items()):
        g = raw[(raw.ticker == tk) & (raw.source_id == s)].set_index('date').reindex(f.index)
        any_flag = f[names].any(axis=1)
        for a, b in runs(f.index[any_flag]):
            w = f.loc[a:b]
            cands.append(dict(id=f'{tk}-{s}-{a.date()}', ticker=tk, source_id=s, start=str(a.date()), end=str(b.date()),
                              days=int(w[names].any(axis=1).sum()),
                              detectors={n: int(w[n].sum()) for n in names if w[n].any()},
                              own_z=round(float(w.own_z.max()), 1),
                              peer_z=None if w.peer_z.isna().all() else round(float(w.peer_z.max()), 1),
                              own_move_pct=round(float(np.expm1(w.own_move.loc[w.own_z.idxmax()])) * 100)
                              if w.own_z.notna().any() else None))
        r3 = lambda v: [None if not np.isfinite(x) else float(f'{x:.4g}') for x in v]  # noqa: E731
        series.append(dict(ticker=tk, source_id=s, industry=str(g.industry.dropna().iloc[0]),
                           dates=[str(d.date()) for d in f.index], ct=r3(g.ct.to_numpy(float)),
                           amt=r3(g.amt.to_numpy(float)),
                           flags={n: [i for i, v in enumerate(f[n].to_numpy()) if v] for n in names}))
    dest.write_text(json.dumps(dict(detectors=names, series=series, candidates=cands), separators=(',', ':')))
    n_det = pd.Series([len(c['detectors']) for c in cands]).value_counts().sort_index().to_dict()
    print(len(series), 'series;', len(cands), 'candidates; by number of detectors agreeing:', n_det)


if __name__ == '__main__':
    main()
