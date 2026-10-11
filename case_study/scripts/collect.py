"""Build part1/raw.json from the per-seed plan/critique markdown files.

Reads part1/plans/<id>.md and part1/critiques/<id>.md, in seeds.json order.
Each file's own header records which harness produced it (see PROVENANCE.md);
that is carried through as a `source` field rather than encoded in the layout.

Usage:  python scripts/collect.py
"""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def body(text: str) -> str:
    """Strip the title/quote/rule header written by the generators."""
    return text.split("---", 1)[1].strip() if "---" in text else text.strip()


def source_of(text: str) -> str:
    """Harness that produced this file, read from its header line."""
    head = text.splitlines()[0] if text else ""
    return "subagent" if "subagent" in head else "api"


def main() -> None:
    seeds = json.loads((ROOT / "seeds.json").read_text())["seeds"]
    rows = []

    for seed in seeds:
        sid = seed["id"]
        plan_p = ROOT / "part1" / "plans" / f"{sid}.md"
        crit_p = ROOT / "part1" / "critiques" / f"{sid}.md"
        if not (plan_p.exists() and crit_p.exists()):
            print(f"  WARNING: {sid} missing plan or critique — skipped")
            continue
        plan_t, crit_t = plan_p.read_text(), crit_p.read_text()
        rows.append(
            {
                "id": sid,
                "source": source_of(plan_t),
                "plan": body(plan_t),
                "critique": body(crit_t),
            }
        )

    out = ROOT / "part1" / "raw.json"
    out.write_text(json.dumps(rows, indent=2))

    by_source: dict[str, int] = {}
    for r in rows:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    print(f"wrote {out.relative_to(ROOT)}: {len(rows)}/{len(seeds)} seeds {by_source}")


if __name__ == "__main__":
    main()
