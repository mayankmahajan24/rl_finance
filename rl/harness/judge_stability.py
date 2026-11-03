"""Judge stability: grade the same saved answers several times and report how often each rubric item
gets the same verdict. Items that flip often need rubric work, not more votes.

Each answer is a built task plus the files the agent left in /app/output (a folder holding them).
The task's own verifier runs `--times` times with the judge cache off, so every run is a fresh
judge call; verdicts are read from its details.json.

    python rl/harness/judge_stability.py --times 3 \
        rl/tasks/bench/kn-produce-DAL-2018Q2=runs/saved/kn-produce-DAL-2018Q2/output \
        rl/tasks/bench/thesis-bench-001=runs/saved/thesis-bench-001/output

Needs ANTHROPIC_API_KEY, and spends a judge call per answer per time. Writes the report as JSON to
--out (default: stdout only).
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections import defaultdict

FLAKY = 0.8    # items agreeing less often than this are flagged


def verdicts(family: str, details: dict) -> dict[str, str]:
    """Per-item verdicts from a verifier's details.json."""
    if family == "kpi_nowcast":
        j = details.get("judge")
        return {k: v.split(":")[0] for k, v in j.items() if k.startswith("C")} if isinstance(j, dict) else {}
    if family == "growth_thesis":
        return {k: str(v["passed"]) for k, v in (details.get("rubric") or {}).items()}
    if family == "research_design":
        return {g["gold_ref"]: str(g["surfaced"]) for g in (details.get("scorer_result") or {}).get("gold_recall", [])}
    raise SystemExit(f"{family}: no model-graded items to read")


def run_verifier(task: pathlib.Path, output: pathlib.Path) -> dict:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="stability_"))
    shutil.copytree(task / "environment" / "data", tmp / "app" / "data")
    shutil.copytree(output, tmp / "app" / "output")
    (tmp / "app" / "solution").mkdir()
    verifier = next(line.split()[1].split("/")[-1] for line in (task / "tests" / "test.sh").read_text().splitlines()
                    if line.startswith("python /tests/"))
    env = dict(os.environ, APP_DIR=str(tmp / "app"), TESTS_DIR=str(task / "tests"), LOGS_DIR=str(tmp / "logs"))
    env.pop("JUDGE_CACHE", None)
    subprocess.run([sys.executable, verifier], cwd=task / "tests", env=env, capture_output=True, text=True)
    details = json.loads((tmp / "logs" / "verifier" / "details.json").read_text())
    shutil.rmtree(tmp, ignore_errors=True)
    return details


def agreement(runs: list[dict[str, str]]) -> dict[str, float]:
    """Per item: the share of runs that gave the most common verdict."""
    by = defaultdict(list)
    for r in runs:
        for k, v in r.items():
            by[k].append(v)
    return {k: max(vs.count(x) for x in set(vs)) / len(vs) for k, vs in sorted(by.items())}


def report(per_answer: dict[str, list[dict[str, str]]]) -> dict:
    items = defaultdict(list)
    for runs in per_answer.values():
        for k, a in agreement(runs).items():
            items[k].append(a)
    mean = {k: round(sum(v) / len(v), 3) for k, v in sorted(items.items())}
    return {"answers": len(per_answer), "item_agreement": mean,
            "flaky_items": sorted(k for k, v in mean.items() if v < FLAKY),
            "per_answer": {a: agreement(r) for a, r in per_answer.items()}}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("answers", nargs="+", help="TASK_DIR=OUTPUT_DIR pairs")
    ap.add_argument("--times", type=int, default=3)
    ap.add_argument("--out", type=pathlib.Path)
    a = ap.parse_args(argv)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("needs ANTHROPIC_API_KEY: every run is a fresh judge call")
    by_family = defaultdict(dict)
    for pair in a.answers:
        task, output = map(pathlib.Path, pair.split("=", 1))
        fam = tomllib.loads((task / "task.toml").read_text())["metadata"]["family"]
        by_family[fam][task.name] = [verdicts(fam, run_verifier(task, output)) for _ in range(a.times)]
    out = {fam: report(per) for fam, per in sorted(by_family.items())}
    text = json.dumps(out, indent=1)
    print(text)
    if a.out:
        a.out.write_text(text + "\n")


if __name__ == "__main__":
    main()
