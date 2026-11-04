"""Judge stability: grade the same saved answers several times and report how often each rubric item
gets the same verdict. Items that flip often need rubric work, not more votes.

Each answer is a built task plus the files the agent left in /app/output (a folder holding them).
The task's own verifier runs `--k` times in a scratch layout (local.py) with the judge cache off, so
every run is a fresh judge call; verdicts are read from its details.json. `--judge` swaps in another
judge model for the run (the verifier records the override).

    python rl/harness/judge_stability.py --k 3 \
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
import sys
from collections import defaultdict

RL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RL))
sys.path.insert(0, str(RL / "harness"))
import local  # noqa: E402
from lib import task_meta  # noqa: E402

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


def run_verifier(task: pathlib.Path, output: pathlib.Path, judge: str | None = None) -> dict:
    g = local.grade(task, lambda app, tests: shutil.copytree(output, app / "output", dirs_exist_ok=True),
                    {"JUDGE_CACHE": None, **({"JUDGE_MODEL": judge} if judge else {})})
    return g.details


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
    ap.add_argument("--k", type=int, default=3, help="verifier runs per answer")
    ap.add_argument("--judge", help="judge model in place of the family's pinned one")
    ap.add_argument("--out", type=pathlib.Path)
    a = ap.parse_args(argv)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("needs ANTHROPIC_API_KEY: every run is a fresh judge call")
    by_family = defaultdict(dict)
    for pair in a.answers:
        task, output = map(pathlib.Path, pair.split("=", 1))
        fam = task_meta(task)["family"]
        by_family[fam][task.name] = [verdicts(fam, run_verifier(task, output, a.judge)) for _ in range(a.k)]
    out = {fam: report(per) for fam, per in sorted(by_family.items())}
    text = json.dumps(out, indent=1)
    print(text)
    if a.out:
        a.out.write_text(text + "\n")


if __name__ == "__main__":
    main()
