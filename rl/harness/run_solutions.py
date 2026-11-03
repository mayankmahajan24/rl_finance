"""Run the reference and naive solutions against built Harbor tasks locally (no Docker),
emulating the container layout with temp directories. Ported from ~/altdata_evals/run_local.py.

Covers the families that ship baseline solutions (solutions/reference and solutions/naive). The
reference solver should score well and the naive one badly; if they don't, the verifier is not
separating quality. Results go to rl/runs/solutions/<split>.csv, and as run records
(records.py) to rl/runs/solutions/<split>.records.jsonl.

    python rl/harness/run_solutions.py --split bench             # both solvers, every task in the split
    python rl/harness/run_solutions.py --split bench --family data_audit --solvers naive
    JUDGE=keyword python rl/harness/run_solutions.py --split bench   # thesis memo by keyword fallback (no API calls)
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd
import tomllib

RL = Path(__file__).resolve().parents[1]


def family_of(task: Path) -> dict:
    import yaml
    fam = tomllib.loads((task / 'task.toml').read_text())['metadata']['family']
    return dict(yaml.safe_load((RL / 'families' / fam / 'family.yaml').read_text()), dir=RL / 'families' / fam)


def run_one(task_dir: str, solver: str):
    task = Path(task_dir).resolve(); fam = family_of(task)
    tmp = Path(tempfile.mkdtemp(prefix=f'{task.name}-{solver}-'))
    app, logs, sol = tmp / 'app', tmp / 'logs', tmp / 'solver'
    shutil.copytree(task / 'environment' / 'data', app / 'data')
    (app / 'output').mkdir(); (app / 'solution').mkdir()
    src = task / 'solution' if solver == 'reference' else fam['dir'] / 'solutions' / 'naive'
    shutil.copytree(src, sol)
    if (task / 'solution' / 'params.json').exists():
        shutil.copy(task / 'solution' / 'params.json', sol)
    env = dict(os.environ, APP_DIR=str(app), TESTS_DIR=str(task / 'tests'), LOGS_DIR=str(logs),
               PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'])
    r = subprocess.run(['bash', str(sol / 'solve.sh')], env=env, capture_output=True, text=True, cwd=app)
    if r.returncode != 0:
        return dict(task=task.name, solver=solver, reward=0.0, note=f'solve failed: {r.stderr[-300:]}')
    v = subprocess.run([sys.executable, str(task / 'tests' / Path(fam['verifier']).name)], env=env, capture_output=True,
                       text=True, cwd=task / 'tests')
    import json
    if (logs / 'verifier' / 'reward.json').exists() and not json.loads((logs / 'verifier' / 'reward.json').read_text()):
        note = json.loads((logs / 'verifier' / 'details.json').read_text()).get('note', 'not graded')
        return dict(task=task.name, solver=solver, reward=None, note=note)
    try:
        reward = float((logs / 'verifier' / 'reward.txt').read_text())
    except FileNotFoundError:
        return dict(task=task.name, solver=solver, reward=0.0, note=f'verifier failed: {v.stderr[-300:]}')
    det = json.loads((logs / 'verifier' / 'details.json').read_text())
    keep = {k: det[k] for k in ('precision', 'recall', 'f1', 'no_foresight', 'fastest_correct', 'growth_score',
                                'unreliable_f1', 'rubric_score', 'judge', 'flagged_share', 'error') if k in det}
    shutil.rmtree(tmp, ignore_errors=True)
    return dict(task=task.name, solver=solver, family=fam['id'], reward=round(reward, 3), **keep)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', required=True)
    ap.add_argument('--family', default=None, help='family id, e.g. data_audit')
    ap.add_argument('--solvers', default='reference,naive')
    ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()
    tasks = sorted(p for p in (RL / 'tasks' / a.split).iterdir()
                   if p.is_dir() and (family_of(p)['dir'] / 'solutions').is_dir()   # families with baseline solvers
                   and (a.family is None or family_of(p)['id'] == a.family))
    jobs = [(str(t), s) for t in tasks for s in a.solvers.split(',')]
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(run_one, *zip(*jobs)))
    res = pd.DataFrame(rows).sort_values(['task', 'solver'])
    pd.set_option('display.width', 220); pd.set_option('display.max_columns', 20)
    print(res.to_string(index=False))
    print('\nMean reward by family and solver:')
    print(res.pivot_table(index='family', columns='solver', values='reward', aggfunc='mean').round(3).to_string())
    out = RL / 'runs' / 'solutions' / f'{a.split}.csv'
    out.parent.mkdir(parents=True, exist_ok=True); res.to_csv(out, index=False)
    import csv
    import records
    records.write(out.with_suffix('.records.jsonl'),
                  [records.from_solutions(r, runner={'name': 'rl/harness/run_solutions.py'}) for r in csv.DictReader(out.open())])
    print(f'\nsaved {out}')
