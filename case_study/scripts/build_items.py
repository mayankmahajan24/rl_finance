"""Assemble Part 2 eval items from blind-generated plans.

Reads part2/plans/raw/<token>.md, maps tokens to (seed, slot) via the manifest,
and writes one item per seed to part2/items/<id>.json with the gold fields left
empty for the human.

Generators never saw a seed id or slot — only their token. See ISOLATION.md.

Usage:  python scripts/build_items.py
"""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
P2 = ROOT / "part2"

GOLD_TEMPLATE = {
    # frame — condition everything else
    "goal_type": "",
    "error_asymmetry": "",
    # the call
    "preference": "",
    "preference_strength": "",          # strong | weak
    "decisive_tenets": "",              # which tenets drove it, most important first
    "preference_rationale": "",
    # per-plan desk review, as prose
    "critique_A": "",
    "critique_B": "",
    "why_loser_was_defensible": "",
}

def body(text: str) -> str:
    """Drop the token header line the generator was told to write."""
    lines = text.splitlines()
    return "\n".join(lines[1:]).strip() if lines and lines[0].startswith("#") else text.strip()


def main() -> None:
    forks = json.loads((P2 / "forks.json").read_text())["forks"]
    tokens = json.loads((P2 / "plans" / "_manifest.json").read_text())["tokens"]
    ctx = json.loads((P2 / "contexts.json").read_text())
    firms, assign, flips = ctx["firms"], ctx["assignment"], ctx["flips"]

    # Prefer the condensed edit (part2/plans/short/) over the full generation.
    # Condensing was a length edit only — see ISOLATION.md, "Condensation pass".
    by_seed: dict[str, dict[str, str]] = {}
    missing = []
    for tok, m in tokens.items():
        short_p = P2 / "plans" / "short" / f"{tok}.md"
        raw_p = P2 / "plans" / "raw" / f"{tok}.md"
        p = short_p if short_p.exists() else raw_p
        if not p.exists():
            missing.append(tok)
            continue
        by_seed.setdefault(m["seed_id"], {})[m["slot"]] = body(p.read_text())

    if missing:
        print(f"  WARNING: missing generated plans for tokens: {missing}")

    order = sorted(forks, key=lambda s: int(s[1:]))
    built = 0
    for sid in order:
        slots = by_seed.get(sid, {})
        if not {"A", "B"} <= slots.keys():
            print(f"  WARNING: {sid} incomplete — skipped")
            continue
        gold_path = P2 / "gold" / f"{sid}.json"
        gold = json.loads(gold_path.read_text()) if gold_path.exists() else dict(GOLD_TEMPLATE)
        item = {
            "id": sid,
            "firm": assign[sid],
            "context": firms[assign[sid]],
            "seed": forks[sid]["seed"],
            "plan_A": slots["A"],
            "plan_B": slots["B"],
            "gold": gold,
        }
        (P2 / "items" / f"{sid}.json").write_text(json.dumps(item, indent=2) + "\n")
        if not gold_path.exists():
            gold_path.write_text(json.dumps(dict(GOLD_TEMPLATE), indent=2) + "\n")
        built += 1

    # Context-flip items: same seed and plans, different firm (see contexts.json).
    for fid, spec in flips.items():
        if fid.startswith("_"):
            continue
        base = spec["base"]
        if base not in by_seed:
            continue
        gold_path = P2 / "gold" / f"{fid}.json"
        gold = json.loads(gold_path.read_text()) if gold_path.exists() else dict(GOLD_TEMPLATE)
        item = {
            "id": fid,
            "firm": spec["firm"],
            "context": firms[spec["firm"]],
            "flip_of": base,
            "seed": forks[base]["seed"],
            "plan_A": by_seed[base]["A"],
            "plan_B": by_seed[base]["B"],
            "gold": gold,
        }
        (P2 / "items" / f"{fid}.json").write_text(json.dumps(item, indent=2) + "\n")
        if not gold_path.exists():
            gold_path.write_text(json.dumps(dict(GOLD_TEMPLATE), indent=2) + "\n")
        built += 1
        print(f"  flip {fid}: {base} under {spec['firm']}")

    print(f"built {built} items -> part2/items/")
    print(f"gold stubs -> part2/gold/<id>.json  (empty; yours to fill)")


if __name__ == "__main__":
    main()
