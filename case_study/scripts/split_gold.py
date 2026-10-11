"""Split gold prose critiques into discrete, classified gold issues.

Recall is defined in SCORING.md as *blocking gold issues surfaced / total
blocking gold issues*, but gold is written as prose and carries no severity.
This builds the denominator, and the denominator is the whole ballgame: get it
wrong and every recall number downstream is wrong in the same direction.

Two things have to be decided per paragraph, and neither is safe to assume:

  - **Is it even a criticism?** Gold paragraphs include praise ("the constraint
    layering is right", "simple-first is the right instinct"). A model cannot
    "surface" praise, so scoring it as a missed issue would penalise every model
    for a category error in the answer key.
  - **Blocking or secondary?** Only blocking counts toward recall. A model that
    misses the fatal flaw and catches three minor ones should not score well.

The classifier only labels text the human already wrote; it never invents,
merges or reworks an issue. Output is written for human review before scoring —
this sets the denominator, so it is the human's call, not the model's.

Usage:
    python scripts/split_gold.py                 # classify -> gold/_issues.json
    python scripts/split_gold.py --review        # print for sign-off, no API
"""

from __future__ import annotations

import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLD = ROOT / "part2" / "gold"
OUT = GOLD / "_issues.json"

SYSTEM = """You are classifying paragraphs from a senior reviewer's written critique of a
research plan. The reviewer wrote free prose; you are labelling what they wrote so it can
be used as an answer key. You are NOT reviewing the plan yourself.

For each numbered paragraph, return exactly one label:

- "blocking"  — a criticism the reviewer treats as decisive: it would stop the plan, change
                its design, or make its output untrustworthy. Phrases like "the real knock",
                "the horizon is wrong", "cannot be established cleanly" signal this.
- "secondary" — a real criticism, but one the reviewer treats as a refinement, a nice-to-have,
                or a smaller concern that would not by itself block the work.
- "anti_objection" — the reviewer is explicitly REJECTING a criticism someone might raise:
                "the objection that N is too small does not apply", "that is not a Type I
                failure", "the thinness of the sample is not an objection here". This is the
                reviewer pre-emptively ruling something OUT. It is the most important label:
                a reviewer bothered to say this objection is wrong, so a plan review that
                raises it anyway is manufacturing an objection the expert already dismissed.
- "praise"    — not a criticism at all. The reviewer is saying something is RIGHT, good, or
                the plan's best feature. Also use this for pure summary with no complaint.
                Use "anti_objection" instead whenever a specific criticism is being dismissed.

Rules:
- Judge what the REVIEWER thinks, from their own emphasis and wording. Do not substitute your
  own view of how serious the problem is.
- A paragraph that opens with praise and then pivots to a real complaint ("X is the right
  instinct, BUT...") is a criticism, not praise. Label it on the complaint.
- Do not merge, split or rewrite paragraphs. One label per paragraph, in order.
- Also return a short `gist`: the criticism in one clause, for matching later. For praise,
  give the gist of what is being praised. For anti_objection, state the OBJECTION being
  ruled out (not the reason), phrased as the criticism itself — that is what a model's issue
  will be matched against.
"""

USER = """Plan under review: plan {slot} for item {item}.

The reviewer's critique, split into numbered paragraphs:

{paragraphs}

Classify all {n} paragraphs, in order."""

SCHEMA = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "label": {"type": "string", "enum": ["blocking", "secondary", "anti_objection", "praise"]},
                    "gist": {"type": "string"},
                },
                "required": ["n", "label", "gist"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["labels"],
    "additionalProperties": False,
}


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def review() -> None:
    if not OUT.exists():
        raise SystemExit(f"{OUT} does not exist yet — run without --review first")
    d = json.loads(OUT.read_text())
    tot = {"blocking": 0, "secondary": 0, "anti_objection": 0, "praise": 0}
    for item in sorted(d["items"], key=lambda s: int(s[1:].rstrip("F"))):
        for slot in ("A", "B"):
            rows = d["items"][item][slot]
            print(f"\n{'=' * 74}\n{item} · plan {slot}\n{'=' * 74}")
            for r in rows:
                tot[r["label"]] += 1
                tag = {"blocking": "[BLOCKING]", "secondary": "[secondary]",
                       "anti_objection": "[ANTI-OBJ]", "praise": "[  praise ]"}[r["label"]]
                print(f"  {tag} {r['gist']}")
                print(f"              {r['text'][:110]}...")
    print(f"\n{'=' * 74}")
    print(f"TOTAL  blocking={tot['blocking']}  secondary={tot['secondary']}  "
          f"anti_objection={tot['anti_objection']}  praise={tot['praise']}")
    print(f"\nRecall denominator = {tot['blocking']} blocking issues.")
    print("Sign off on this before scoring — it sets the denominator.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--model", default="claude-opus-5")
    args = ap.parse_args()
    if args.review:
        return review()

    import anthropic
    import run_eval as R

    client = anthropic.Anthropic()
    out: dict = {"model": args.model, "items": {}}
    for p in sorted(GOLD.glob("S*.json"), key=lambda x: (x.stem.endswith("F"),
                                                         int(x.stem[1:].rstrip("F")))):
        g = json.loads(p.read_text())
        if all(v in ("", [], None) for k, v in g.items() if not k.startswith("_")):
            continue
        item = p.stem
        out["items"][item] = {}
        for slot in ("A", "B"):
            ps = paragraphs(g[f"critique_{slot}"])
            numbered = "\n\n".join(f"[{i}] {t}" for i, t in enumerate(ps, 1))
            res, _ = R.call(client, args.model, SYSTEM,
                            USER.format(slot=slot, item=item, paragraphs=numbered, n=len(ps)),
                            SCHEMA, 8000)
            by_n = {x["n"]: x for x in res["labels"]}
            rows = []
            for i, t in enumerate(ps, 1):
                lab = by_n.get(i, {"label": "secondary", "gist": t[:80]})
                rows.append({"n": i, "text": t, "label": lab["label"], "gist": lab["gist"]})
            out["items"][item][slot] = rows
            n_block = sum(1 for r in rows if r["label"] == "blocking")
            print(f"  {item} {slot}: {len(ps)} paragraphs -> {n_block} blocking")
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\n-> {OUT.relative_to(ROOT)}   (review with --review before scoring)")


if __name__ == "__main__":
    main()
