"""Summarize the Part 1 scoring pass into a single table.

Reads part1/scores/*.json (one per seed, written by scoring subagents) and
emits part1/scorecard.md.

Usage:  python scripts/summarize.py
"""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

MARK = {"caught": "✅ caught", "partial": "🟡 partial", "missed": "❌ missed"}
PLAN = {"avoided": "✅ avoided", "partial": "🟡 partial", "built_on_flaw": "❌ built on it"}
SIZED = {
    "yes_both": "✅ both",
    "yes_critique": "🟡 critique only",
    "yes_plan": "🟡 plan only",
    "no": "❌ neither",
}


def main() -> None:
    seeds = {s["id"]: s for s in json.loads((ROOT / "seeds.json").read_text())["seeds"]}
    raw = {r["id"]: r for r in json.loads((ROOT / "part1" / "raw.json").read_text())}

    scores = {}
    for p in sorted((ROOT / "part1" / "scores").glob("*.json")):
        s = json.loads(p.read_text())
        scores[s["id"]] = s

    rows, tallies = [], {"caught": 0, "partial": 0, "missed": 0}
    manufactured_total = 0

    for sid, seed in seeds.items():
        sc = scores.get(sid)
        if not sc:
            continue
        got = sc.get("critique_caught_flaw", "?")
        tallies[got] = tallies.get(got, 0) + 1
        n_manf = len(sc.get("manufactured", []))
        manufactured_total += n_manf
        rows.append(
            "| {sid} | {bucket} | {src} | {plan} | {crit} | {manf} | {sized} |".format(
                sid=sid,
                bucket=seed["bucket"],
                src=raw.get(sid, {}).get("source", "?"),
                plan=PLAN.get(sc.get("plan_avoided_flaw", ""), sc.get("plan_avoided_flaw", "?")),
                crit=MARK.get(got, got),
                manf=n_manf if n_manf else "—",
                sized=SIZED.get(sc.get("right_sized", ""), "n/a"),
            )
        )

    n = len(rows)
    doc = [
        "# Part 1 — scorecard",
        "",
        f"{n} seeds. Each row scored by an independent subagent that saw only that seed's",
        "plan, its critique, and the gold flaw — no other seed, no sibling scores.",
        "",
        "**recall** = did the critique name the known flaw. **manufactured** = objections",
        "raised that are not real problems (precision). **right-sized** = did the work",
        "propose killing or shrinking a dead idea instead of scoping it (obviously-flawed tier only).",
        "",
        "| seed | bucket | source | plan | critique recall | manufactured | right-sized |",
        "|---|---|---|---|---|---|---|",
        *rows,
        "",
        f"**Recall:** {tallies['caught']} caught / {tallies['partial']} partial / "
        f"{tallies['missed']} missed of {n}.",
        f"**Precision:** {manufactured_total} manufactured objections across {n} critiques "
        f"({manufactured_total / n:.1f} per critique).",
        "",
        "Per-seed detail, including the quoted evidence and what each critique missed,",
        "is in `part1/scores/<id>.json`.",
        "",
    ]
    out = ROOT / "part1" / "scorecard.md"
    out.write_text("\n".join(doc))
    print("\n".join(doc[-6:-1]))
    print(f"\nwrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
