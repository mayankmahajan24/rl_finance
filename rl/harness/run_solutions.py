"""Run the reference and naive solutions against built tasks locally (no Docker), graded by each
task's own verifier (local.py).

Covers every family that ships baseline solutions (families/<family>/solutions/naive; the reference
is the built task's solution/). The reference should score well and the naive one badly; if they
don't, the verifier is not separating quality. Writes run records (records.py) to
rl/runs/solutions/<split>.records.jsonl and prints the mean reward per family and solver.

    python rl/harness/run_solutions.py --split bench             # both solvers, every task in the split
    python rl/harness/run_solutions.py --split bench --family data_audit --solvers naive
    JUDGE=keyword python rl/harness/run_solutions.py --split bench   # judged families by keyword fallback (no API calls)
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

RL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RL))
sys.path.insert(0, str(RL / "harness"))
import local  # noqa: E402
import records  # noqa: E402
from lib import task_meta  # noqa: E402

RUNNER = "rl/harness/run_solutions.py"


def solver_dir(task: pathlib.Path, family: str, solver: str) -> pathlib.Path:
    return task / "solution" if solver == "reference" else RL / "families" / family / "solutions" / solver


def solve(task: pathlib.Path, solver: str, app: pathlib.Path) -> str | None:
    """Run a solver's solve.sh in a scratch layout (local.layout); returns why it failed, if it did."""
    sol = app.parent / "solver"
    shutil.copytree(solver_dir(task, task_meta(task)["family"], solver), sol)
    if (task / "solution" / "params.json").exists():
        shutil.copy(task / "solution" / "params.json", sol)
    env = dict(os.environ, APP_DIR=str(app), PATH=str(pathlib.Path(sys.executable).parent) + os.pathsep + os.environ["PATH"])
    r = subprocess.run(["bash", str(sol / "solve.sh")], env=env, cwd=app, capture_output=True, text=True)
    return f"solve failed: {r.stderr[-300:]}" if r.returncode else None


def run_one(task_dir: str, solver: str) -> dict:
    """One solver on one task: {task, solver, family, status, rewards, reward, judge_usage}, and a
    note when it didn't grade."""
    task = pathlib.Path(task_dir).resolve()
    family = task_meta(task)["family"]
    failed = None

    def write(app: pathlib.Path, tests: pathlib.Path) -> None:
        nonlocal failed
        failed = solve(task, solver, app)

    g = local.grade(task, write)
    rewards = records.numbers(g.rewards)
    row = {"task": task.name, "solver": solver, "family": family, "status": "ok", "rewards": rewards,
           "reward": rewards.get("reward"), "judge_usage": g.judge_usage}
    if failed:
        row.update(status="error", note=failed)
    elif g.rewards is None:
        row.update(status="error", note=f"verifier failed: {(g.error or '')[-300:]}")
    elif not rewards:
        row.update(status="not_graded", note=g.details.get("note", "not graded"))
    return row


def record(row: dict, task: pathlib.Path) -> dict:
    return records.make(**records.identity(task), attempt=0, runner={"name": RUNNER, "agent": row["solver"]},
                        status=row["status"], rewards=row["rewards"], **records.judge_fields(row["judge_usage"]),
                        **({"error": row["note"]} if row["status"] == "error" else {}))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", required=True)
    ap.add_argument("--family", action="append", help="only these families")
    ap.add_argument("--solvers", default="reference,naive")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    tasks = [d for d, m in local.tasks(a.split, a.family) if (RL / "families" / m["family"] / "solutions").is_dir()]
    if not tasks:
        raise SystemExit(f"no built tasks with solutions under tasks/{a.split}/")
    jobs = [(str(t), s) for t in tasks for s in a.solvers.split(",")]
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(run_one, *zip(*jobs)))
    by = defaultdict(list)
    for r in rows:
        print(f"{r['task']:<36} {r['solver']:<10} {r['status']:<10} {r['reward']}  {r.get('note', '')}")
        if r["reward"] is not None:
            by[(r["family"], r["solver"])].append(r["reward"])
    print("\nMean reward by family and solver:")
    for (fam, solver), v in sorted(by.items()):
        print(f"  {fam:<18} {solver:<10} {sum(v) / len(v):.3f}  ({len(v)} tasks)")
    out = RL / "runs" / "solutions" / f"{a.split}.records.jsonl"
    records.write(out, [record(r, pathlib.Path(t)) for r, (t, _) in zip(rows, jobs)])
    print(f"\nsaved {out.relative_to(RL.parent)}")


if __name__ == "__main__":
    main()
