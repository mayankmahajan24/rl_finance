"""Leaderboards over run records (records.py), refusing to mix instruments.

A row is one condition: family, mode, runner and agent, model, skills, effort, max_tokens and judge. Its
`reward` is the mean over the condition's scored records: a model's failures (refusal, truncated,
timeout, parse_error) count 0, infrastructure errors and ungraded records are left out
(records.score). Other metrics are diagnostics, averaged where the verifier reported them. Before anything is averaged, every
task in a family must have been measured with one instrument (content_sha256 and prompt
fingerprint) across every row of the report; a task run on two versions, or on an unrecorded one
next to a recorded one, stops the report. --mix reports anyway, with each instrument as its own row.

    python rl/harness/report.py --split bench                       # every records file under rl/runs/
    python rl/harness/report.py --split eval --family research_design --metric reward
    python rl/harness/report.py --split bench --by model --by skills rl/runs/x/records.jsonl
    python rl/harness/report.py --split train --family kpi_nowcast --mix
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter, defaultdict

RL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RL / "harness"))
import records  # noqa: E402

CONDITION = ("family", "mode", "runner", "model", "skills", "effort", "max_tokens", "judge_model")


def key(r: dict, by: tuple[str, ...]) -> tuple:
    def v(k):
        x = r.get(k)
        if k == "runner" and isinstance(x, dict):
            return " ".join(str(x[f]) for f in ("name", "agent", "run_id") if x.get(f))
        if k == "skills" and isinstance(x, dict):
            return x.get("profile") if x.get("enabled") else "off"
        return json.dumps(x, sort_keys=True) if isinstance(x, (dict, list)) else x
    return tuple(v(k) for k in by)


def instrument(r: dict) -> tuple:
    return r.get("content_sha256"), r.get("fingerprint")


def conflicts(recs: list[dict]) -> list[str]:
    """Tasks measured with more than one instrument among these records."""
    seen = defaultdict(set)
    for r in recs:
        seen[(r["family"], r["task_id"])].add(instrument(r))
    return [f"{fam}/{tid}: {len(v)} instruments ({', '.join(f'{c and c[:12]}/{f}' for c, f in sorted(v, key=str))})"
            for (fam, tid), v in sorted(seen.items()) if len(v) > 1]


def table(recs: list[dict], by: tuple[str, ...], metrics: list[str] | None, mix: bool) -> list[dict]:
    if mix:
        by = (*by, "instrument")
        recs = [dict(r, instrument=f"{(r.get('content_sha256') or '-')[:12]}/{r.get('fingerprint') or '-'}")
                for r in recs]
    groups = defaultdict(list)
    for r in recs:
        groups[key(r, by)].append(r)
    rows = []
    for k, rs in sorted(groups.items(), key=lambda kv: [str(x) for x in kv[0]]):
        names = metrics or sorted({m for r in rs for m in r["rewards"]} | {"reward"})
        row = dict(zip(by, k), tasks=len({r["task_id"] for r in rs}), attempts=len(rs),
                   status=", ".join(f"{s} {n}" for s, n in sorted(Counter(r["status"] for r in rs).items())))
        for m in names:
            vals = [v for v in (records.score(r, m) if m == "reward" else r["rewards"].get(m) for r in rs)
                    if v is not None]
            row[m] = round(sum(vals) / len(vals), 4) if vals else None
        costs = [r.get("cost_usd") for r in rs]
        row["cost_usd"] = round(sum(c for c in costs if c is not None), 4) if any(c is not None for c in costs) else None
        rows.append(row)
    return rows


def render(rows: list[dict]) -> str:
    if not rows:
        return "(no records)"
    cols = list(dict.fromkeys(c for r in rows for c in r))
    cells = [[("" if r.get(c) is None else str(r.get(c))) for c in cols] for r in rows]
    w = [max(len(c), *(len(x[i]) for x in cells)) for i, c in enumerate(cols)]
    line = lambda xs: "  ".join(x.ljust(n) for x, n in zip(xs, w))  # noqa: E731
    return "\n".join([line(cols), line(["-" * n for n in w]), *map(line, cells)])


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", type=pathlib.Path, help="records files (default: every one under rl/runs/)")
    ap.add_argument("--split", help="only this split (a report never spans splits unless this is omitted)")
    ap.add_argument("--family", action="append")
    ap.add_argument("--by", action="append", help=f"group by these record fields (default: {', '.join(CONDITION)})")
    ap.add_argument("--metric", action="append", help="only these rewards (default: every reward recorded)")
    ap.add_argument("--mix", action="store_true", help="report tasks measured with different instruments, each as its own row")
    a = ap.parse_args(argv)
    files = a.files or sorted((RL / "runs").rglob("*records.jsonl"))
    recs = [r for r in records.load(files)
            if (a.split is None or r.get("split") == a.split) and (not a.family or r["family"] in a.family)]
    by = tuple(a.by or CONDITION)
    if "family" not in by:
        by = ("family", *by)          # rewards of different families are never one number
    if a.split is None:
        by = ("split", *by)
    bad = conflicts(recs)
    if bad and not a.mix:
        raise SystemExit("REFUSED: these tasks were measured with different instruments (content_sha256/fingerprint); "
                         "rerun on one, narrow with --family/--split, or pass --mix to see them side by side:\n  "
                         + "\n  ".join(bad))
    for fam in sorted({r["family"] for r in recs}):
        print(f"\n## {fam}" + (f" ({a.split})" if a.split else ""))
        print(render(table([r for r in recs if r["family"] == fam], by, a.metric, a.mix)))
    if bad:
        print(f"\nwarning: {len(bad)} tasks span instruments; rows are split by instrument (--mix)")


if __name__ == "__main__":
    main()
