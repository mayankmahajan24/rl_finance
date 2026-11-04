"""Memorisation probe: for families that ship disguised variants of the same case, compare a model's
scores across them. Disguise doesn't change what the task asks, so a model doing markedly better
with more of the real company in view is likely drawing on memory. kpi_nowcast has three variants:
named, coded (names hidden, dollars real) and anon (names hidden, dollars rescaled). Named vs coded
is what the name adds, coded vs anon what the real numbers add, named vs anon both.

    python rl/harness/memorisation.py rl/runs/api/bench/<run_id>/records.jsonl

Reads run records (records.py). Each record's task is looked up among the built tasks: its
`case` (task.toml metadata, shared by a case's variants) and variant (from its tags). Pairs the
records of each case per model (first scored attempt of each), and reports, per metric, the mean
difference over the paired cases for each comparison.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import defaultdict

RL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RL))
sys.path.insert(0, str(RL / "harness"))
import records  # noqa: E402
from lib import iter_tasks  # noqa: E402

LOWER_IS_BETTER = {"abs_pct_error", "interval_score_pct"}
NOT_A_SCORE = {"signed_pct_error"}       # direction, not quality
COMPARISONS = {"name": ("named", "coded"), "numbers": ("coded", "anon"), "both": ("named", "anon")}


def cases() -> dict[str, tuple[str, str]]:
    """{task_id: (case, "named", "coded" or "anon")} for every built task that names its case."""
    return {m["id"]: (m["case"], next((v for v in ("coded", "anon") if v in m.get("tags", [])), "named"))
            for _, m in iter_tasks() if "case" in m}


def pairs(recs: list[dict], case_of: dict[str, tuple[str, str]], more: str = "named",
          less: str = "anon") -> dict[str, list[tuple[dict, dict]]]:
    """{model: [(rewards with more shown, with less)]} over cases run in both variants (first scored attempt of each)."""
    seen = defaultdict(dict)
    for r in sorted(recs, key=lambda r: r["attempt"]):
        if r["status"] != "ok" or r["task_id"] not in case_of:
            continue
        case, variant = case_of[r["task_id"]]
        seen[(r["model"], case)].setdefault(variant, r["rewards"])
    out = defaultdict(list)
    for (model, _), v in sorted(seen.items()):
        if {more, less} <= set(v):
            out[model].append((v[more], v[less]))
    return out


def gaps(paired: list[tuple[dict, dict]]) -> dict[str, dict]:
    """Per metric: mean difference, oriented so positive means the variant showing more did better."""
    out = {}
    for k in sorted({k for n, a in paired for k in n if k in a} - NOT_A_SCORE):
        d = [(n[k] - a[k]) * (-1 if k in LOWER_IS_BETTER else 1) for n, a in paired
             if isinstance(n[k], (int, float)) and isinstance(a[k], (int, float))]
        if d:
            out[k] = {"advantage": round(sum(d) / len(d), 4), "cases": len(d)}
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("records", nargs="+", type=pathlib.Path)
    a = ap.parse_args(argv)
    recs, case_of = records.load(a.records), cases()
    by = {name: pairs(recs, case_of, *pair) for name, pair in COMPARISONS.items()}
    if not any(by.values()):
        raise SystemExit("no case was run in two of its variants")
    print(json.dumps({name: {m: gaps(p) for m, p in v.items()} for name, v in by.items() if v}, indent=1))


if __name__ == "__main__":
    main()
