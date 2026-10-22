"""Difficulty calibration from repeated trials.

Reads every Harbor trial result under a jobs directory (each trial writes result.json with `task_name` and
`verifier_result.rewards.reward`), or a CSV with columns task,reward, and reports per task:

  n        trials run
  mean     mean continuous reward
  p        pass rate, where a trial "passes" if reward >= --pass-threshold
  pass@k   P(at least one of k fresh trials passes)  - unbiased estimator 1 - C(n-c,k)/C(n,k)
  pass^k   P(all k fresh trials pass)                - estimator C(c,k)/C(n,k)
  keep     True if --keep-lo <= p <= --keep-hi: the task discriminates for this model

    python calibrate.py jobs/                         # after: harbor run -p tasks -a claude-code -m <model> -k 10
    python calibrate.py results/trials.csv --k 5 --pass-threshold 0.7
"""
import argparse
import json
from math import comb
from pathlib import Path

import pandas as pd


def load(path: Path) -> pd.DataFrame:
    if path.is_file() and path.suffix == '.csv':
        return pd.read_csv(path)[['task', 'reward']]
    rows = []
    for f in path.rglob('result.json'):
        try:
            r = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        if 'task_name' not in r or 'trial_name' not in r:
            continue                                     # job-level summary, not a trial
        rewards = (r.get('verifier_result') or {}).get('rewards') or {}
        rows.append(dict(task=r['task_name'], reward=float(rewards.get('reward', 0.0))))
    return pd.DataFrame(rows, columns=['task', 'reward'])


def pass_at_k(n, c, k):
    return float('nan') if n < k else 1 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n, c, k):
    return float('nan') if n < k else comb(c, k) / comb(n, k)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path', type=Path)
    ap.add_argument('--k', type=int, default=5)
    ap.add_argument('--pass-threshold', type=float, default=0.8)
    ap.add_argument('--keep-lo', type=float, default=0.1)
    ap.add_argument('--keep-hi', type=float, default=0.8)
    a = ap.parse_args()
    df = load(a.path)
    if df.empty:
        raise SystemExit(f'no trial results found under {a.path}')
    out = []
    for task, g in df.groupby('task'):
        n = len(g); c = int((g.reward >= a.pass_threshold).sum()); p = c / n
        out.append(dict(task=task, family=task.split('-')[0], n=n, mean=g.reward.mean(), p=p,
                        **{f'pass@{a.k}': pass_at_k(n, c, a.k), f'pass^{a.k}': pass_hat_k(n, c, a.k)},
                        keep=a.keep_lo <= p <= a.keep_hi))
    res = pd.DataFrame(out)
    pd.set_option('display.width', 200)
    print(res.round(3).to_string(index=False))
    print('\nBy family:')
    print(res.groupby('family')[['mean', 'p', f'pass@{a.k}', f'pass^{a.k}', 'keep']].mean().round(3).to_string())
    print(f'\nKeep {int(res.keep.sum())} of {len(res)} tasks (pass rate in [{a.keep_lo}, {a.keep_hi}]).')


if __name__ == '__main__':
    main()
