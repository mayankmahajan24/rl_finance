"""Harbor oracle run in Docker on a sample of built tasks, compared with the local reference rewards.

For each task, Harbor's oracle agent runs the task's solution/ in the task's own image and the
verifier grades it there. The reward must match the reference reward the local run records for the
same task (rl/tests/expected_rewards.json, pinned by pytest; tasks not pinned there are solved locally
with harness/run_solutions.py). A gap means the container and the local run disagree: a package
version, a file the image lacks, a path the verifier assumes.

    JUDGE=keyword python rl/harness/oracle_check.py                       # the default sample
    JUDGE=keyword python rl/harness/oracle_check.py rl/tasks/bench/audit-bench-001

JUDGE=keyword keeps growth_thesis's memo grading offline, as the pinned rewards were recorded. Needs
Docker and harbor. Run by .github/workflows/oracle.yml nightly and on demand.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile

RL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RL / "harness"))
import run_solutions  # noqa: E402

EXPECTED = RL / "tests" / "expected_rewards.json"
TOL = 0.002
# planted tasks and a control from every family with a reference solution, all pinned in EXPECTED
# (anomaly_scoring's reference takes ~50 s a task, so one planted task)
SAMPLE = ["audit-bench-001", "audit-bench-002", "audit-bench-control-01", "anomaly-bench-001",
          "anomaly-bench-control-01", "thesis-bench-001", "thesis-bench-002", "thesis-bench-control-01"]


def oracle_reward(task: pathlib.Path, jobs: pathlib.Path) -> tuple[float | None, str]:
    out = jobs / task.name
    r = subprocess.run([sys.executable, "-m", "harbor.cli.main", "run", "-p", str(task), "-a", "oracle",
                        "-o", str(out), "-n", "1", "-y"], capture_output=True, text=True)
    rewards = list(out.glob("*/*/verifier/reward.txt"))
    if len(rewards) != 1:
        return None, f"harbor gave {len(rewards)} rewards (rc {r.returncode}): {(r.stdout + r.stderr)[-1500:]}"
    return float(rewards[0].read_text()), str(rewards[0].parent)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tasks", nargs="*", type=pathlib.Path, help=f"built task folders (default: bench {', '.join(SAMPLE)})")
    ap.add_argument("--jobs-dir", type=pathlib.Path, help="where Harbor writes the runs (default: a temp folder)")
    a = ap.parse_args(argv)
    if os.environ.get("JUDGE") != "keyword":
        print("note: JUDGE is not 'keyword'; growth_thesis memos may be judged by a model and not match", file=sys.stderr)
    tasks = [t.resolve() for t in a.tasks] or [RL / "tasks" / "bench" / t for t in SAMPLE]
    jobs = a.jobs_dir or pathlib.Path(tempfile.mkdtemp(prefix="oracle_check_"))
    expected = json.loads(EXPECTED.read_text())
    failed = 0
    for task in tasks:
        if not (task / "task.toml").exists():
            print(f"FAIL {task.name}: not built")
            failed += 1
            continue
        local = (expected[task.name]["reference"] if task.name in expected
                 else run_solutions.run_one(str(task), "reference")["reward"])
        got, where = oracle_reward(task, jobs)
        ok = got is not None and abs(got - local) <= TOL
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {task.name}: oracle {got}, local reference {local}"
              + ("" if ok else f"\n       {where}"))
    print(f"run records: {jobs}")
    if failed:
        raise SystemExit(f"{failed} of {len(tasks)} tasks: the oracle in Docker disagrees with the local reference")


if __name__ == "__main__":
    main()
