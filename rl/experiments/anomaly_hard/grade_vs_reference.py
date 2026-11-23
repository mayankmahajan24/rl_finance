"""Experimental grader (feedback #37): score a solution by how closely it matches the reference solution's output.
    python grade_vs_reference.py TASK_DIR SOLUTION_DIR [--writeup PATH] [--json OUT]

The reference's output (its cleaned series and its flags, after it has flagged and fixed problems) is the answer key,
in place of the truth panel and gold. Same gates as grade.py (format, point in time, no model or network calls,
write-up). Then, on the scored rows (from eval_start, not on low-volume series):
  series:  a cleaned value is close when it is within the source's own noise (grade.own_noise) of the reference's, in
           count and in ticket size (blank matches blank only). Score = 0.5 x share close on the rows the reference
           repaired (moved beyond its noise from the raw value, or left blank) + 0.5 x share close on the rest.
  flags:   F1 of the solution's distrusted rows (confidence < 0.5) against the reference's.
  reward = 0.5 x flags + 0.5 x series.
For comparison with grade.py only; the reference scores 1.0 by construction.
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np
import pandas as pd

import grade

HERE = pathlib.Path(__file__).resolve().parent
REFERENCE = HERE / 'solutions' / 'reference'


def score(task: pathlib.Path, sol: pathlib.Path, writeup: pathlib.Path, ref_cache: pathlib.Path | None = None):
    truth = json.loads((task / 'tests' / 'gold.json').read_text())
    data = pd.read_csv(task / 'tests' / 'eval_panel.csv.gz', parse_dates=['date'])
    clean_truth = pd.read_csv(task / 'tests' / 'truth_panel.csv.gz', parse_dates=['date'])
    hits = grade.scan_no_ai(sol)
    gates = dict(no_ai=not hits, writeup=writeup.exists() and writeup.stat().st_size > 0)
    cuts = sorted(truth['truncation_cutoffs'])
    try:
        trunc = {c: grade.run(sol / 'score.py', data[data.date <= pd.Timestamp(c)]) for c in cuts}
        full = grade.run(sol / 'score.py', data)
        gates['format'] = True
    except grade.GateError as e:
        return 0.0, dict(gates=dict(gates, format=False), error=str(e)[-600:])
    leaks = 0
    for c in cuts:
        cmp = (data[data.date <= pd.Timestamp(c)][grade.KEYS].merge(trunc[c], on=grade.KEYS, how='left')
               .merge(full, on=grade.KEYS, how='left', suffixes=('_t', '_f')))
        for col in grade.OUT_COLS:
            a, b = cmp[f'{col}_t'].astype(float), cmp[f'{col}_f'].astype(float)
            leaks += int((~(((a - b).abs() <= 1e-6 * np.maximum(1, b.abs())) | (a.isna() & b.isna()))).sum())
    gates['point_in_time'] = leaks == 0
    ref = grade.run(REFERENCE / 'score.py', data, ref_cache)

    lg = lambda x: np.log(np.maximum(x.astype(float), 0.01))  # noqa: E731
    ev = data[grade.KEYS + ['ct', 'amt']].merge(full, on=grade.KEYS)
    ev = ev.merge(ref.rename(columns={c: 'r_' + c for c in grade.OUT_COLS}), on=grade.KEYS)
    ev = ev.merge(grade.own_noise(clean_truth), on=['ticker', 'source_id'], how='left')
    use = ev.date >= pd.Timestamp(truth['eval_start'])
    for i in truth['ignore_series']:
        use &= ~((ev.ticker == i['ticker']) & (ev.source_id == i['source_id']))

    def near(ct, amt, ct2, amt2):
        dc = (lg(ct) - lg(ct2)).abs()
        dt = ((lg(amt) - lg(ct)) - (lg(amt2) - lg(ct2))).abs()
        both = ct.notna() & amt.notna() & ct2.notna() & amt2.notna()
        blank = (ct.isna() | amt.isna()) & (ct2.isna() | amt2.isna())
        return (both & (dc <= ev.sig_c) & (dt <= ev.sig_t)) | blank

    repaired = ~near(ev.ct, ev.amt, ev.r_clean_ct, ev.r_clean_amt)      # the reference moved it beyond noise
    close = near(ev.clean_ct, ev.clean_amt, ev.r_clean_ct, ev.r_clean_amt)
    on_rep = float(close[use & repaired].mean()) if (use & repaired).any() else 1.0
    on_rest = float(close[use & ~repaired].mean()) if (use & ~repaired).any() else 1.0
    series = 0.5 * on_rep + 0.5 * on_rest
    f_sol, f_ref = (ev.confidence < 0.5) & use, (ev.r_confidence < 0.5) & use
    tp = int((f_sol & f_ref).sum())
    prec = tp / int(f_sol.sum()) if f_sol.any() else (1.0 if not f_ref.any() else 0.0)
    rec = tp / int(f_ref.sum()) if f_ref.any() else 1.0
    flags = grade.f1(prec, rec)
    reward = (0.5 * flags + 0.5 * series) * all(gates.values())
    return reward, dict(gates=gates, ai_hits=hits, flags=round(flags, 3), flag_precision=round(prec, 3),
                        flag_recall=round(rec, 3), series=round(series, 3), close_on_repaired=round(on_rep, 3),
                        close_on_rest=round(on_rest, 3), repaired_rows=int((use & repaired).sum()),
                        reference_flagged_rows=int(f_ref.sum()), solution_flagged_rows=int(f_sol.sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('task'); ap.add_argument('solution'); ap.add_argument('--json'); ap.add_argument('--writeup')
    ap.add_argument('--ref-cache')
    a = ap.parse_args()
    task, sol = pathlib.Path(a.task), pathlib.Path(a.solution).resolve()
    writeup = pathlib.Path(a.writeup) if a.writeup else sol.parent / 'output' / 'writeup.md'
    reward, d = score(task, sol, writeup, pathlib.Path(a.ref_cache) if a.ref_cache else None)
    res = dict(task=task.name, solution=str(sol), reward=round(reward, 3), **d)
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, default=str))


if __name__ == '__main__':
    main()
