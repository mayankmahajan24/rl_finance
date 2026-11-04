"""Memorisation probe: for families that ship named and anonymised variants of the same case, compare
a model's scores on the two. Disguise doesn't change what the task asks, so a model doing markedly
better when it sees the real company is likely drawing on memory of that company.

    python rl/harness/memorisation.py rl/runs/kpi_nowcast/baseline/results.jsonl

Reads kpi_nowcast runner results (rows with `meta.series`, `meta.target_period`, `meta.variant` and
`grade`), pairs the named and anon rows of each case per model, and reports, per metric, the mean
named-minus-anon difference over the paired cases. Only cases run in both variants count.
"""

from __future__ import annotations

import argparse
import json
import pathlib
from collections import defaultdict

LOWER_IS_BETTER = {"abs_pct_error", "interval_score_pct"}
NOT_A_SCORE = {"signed_pct_error"}       # direction, not quality


def pairs(rows: list[dict]) -> dict[str, list[tuple[dict, dict]]]:
    """{model: [(named grade, anon grade)]} over cases run in both variants (first rep of each)."""
    seen = defaultdict(dict)
    for r in rows:
        if r.get("status") != "ok":
            continue
        m = r["meta"]
        seen[(r["model"], m["series"], m["target_period"])].setdefault(m["variant"], r["grade"])
    out = defaultdict(list)
    for (model, *_), v in sorted(seen.items()):
        if {"named", "anon"} <= set(v):
            out[model].append((v["named"], v["anon"]))
    return out


def gaps(paired: list[tuple[dict, dict]]) -> dict[str, dict]:
    """Per metric: mean named - anon, oriented so positive means the named variant did better."""
    out = {}
    for k in sorted({k for n, a in paired for k in n if k in a} - NOT_A_SCORE):
        d = [(n[k] - a[k]) * (-1 if k in LOWER_IS_BETTER else 1) for n, a in paired
             if isinstance(n[k], (int, float)) and isinstance(a[k], (int, float))]
        if d:
            out[k] = {"named_advantage": round(sum(d) / len(d), 4), "cases": len(d)}
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="+", type=pathlib.Path)
    a = ap.parse_args(argv)
    rows = [json.loads(line) for f in a.results for line in f.read_text().splitlines() if line.strip()]
    by = pairs(rows)
    if not by:
        raise SystemExit("no case was run in both its named and anonymised variant")
    print(json.dumps({m: gaps(p) for m, p in by.items()}, indent=1))


if __name__ == "__main__":
    main()
