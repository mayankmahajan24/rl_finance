"""Review queue for gold-bearing files: approve, edit or reject each provenance entry, highest value first.

An item is one entry of a provenance index (rl/provenance.py). The queue shows what produced it, its
note and evidence beside the content, and takes one key per decision. Every decision is appended to
rl/review/decisions.jsonl and rebinds the entry's review to the content as it is now. Edits and
rejections are also appended to rl/review/examples.jsonl, as labelled examples for later
generation prompts. An entry with `blind: {question}` asks the reviewer for their own answer
before showing the draft, and saves it first.

Value: how many bench, held-out and eval tasks use the item (from the families' manifests), then kind
(gold before rubrics, grader facts, annotations, generators, reference outputs).

    python rl/review/review.py list                                  # open items, highest value first
    python rl/review/review.py review --reviewer "Mayank Mahajan" --batch 10
    python rl/review/review.py decide sources/x/gold/S1.json approve --reviewer "Mayank Mahajan" --reason "re-read"

Rebuild after a session (python rl/build.py) so tasks record the new review state.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

RL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RL))
import lib  # noqa: E402
import provenance  # noqa: E402
import splits  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
DECISIONS = HERE / "decisions.jsonl"
EXAMPLES = HERE / "examples.jsonl"
PREVIEW_LINES = 60
KEYS = {"a": "approved", "e": "edited", "r": "rejected", "s": "skip", "q": "quit"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(path: pathlib.Path, row: dict) -> None:
    with open(path, "a") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def value(path: str) -> int:
    """Bench, held-out and eval tasks whose family's gold comes from this item."""
    fams = [f for f in lib.families() if path in lib.family(f).get("gold_inputs", [])]
    return sum(v["split"] in ("bench", "heldout", splits.UNSPLIT) for f in fams for v in splits.manifest(f).values())


def items(include_closed: bool = False) -> list[dict]:
    idx = provenance.load()
    out = [dict(e, state=provenance.state(e, p), value=value(p)) for p, e in idx.items()]
    if not include_closed:
        out = [e for e in out if e["state"] not in ("approved", "rejected")]
    return sorted(out, key=lambda e: (-e["value"], provenance.KINDS.index(e["kind"]), e["path"]))


def show(e: dict) -> str:
    by = e["produced_by"]
    who = {"human": by.get("who"), "model": f"{by.get('model')} (prompt {by.get('prompt_fingerprint')})",
           "code": f"{by.get('ref')} at {by.get('commit')}"}.get(by["type"], by["type"])
    lines = [f"== {e['path']}  [{e['kind']}, {e['state']}, used by {e['value']} bench/held-out/eval tasks]",
             f"   produced by {by['type']}: {who}, {e.get('produced_at')}"]
    if e.get("note"):
        lines.append(f"   note: {e['note']}")
    lines += [f"   evidence: {x}" for x in e.get("evidence", [])]
    return "\n".join(lines)


def content(path: str) -> str:
    fs = provenance.files(path)
    if len(fs) > 1 or fs[0] != RL / path:
        return "\n".join(f"   {p.relative_to(RL)}" for p in fs) + f"\n   ({len(fs)} files, reviewed as one item)"
    text = fs[0].read_text(errors="replace").splitlines()
    more = f"\n   ... {len(text) - PREVIEW_LINES} more lines in {path}" if len(text) > PREVIEW_LINES else ""
    return "\n".join(f"   | {x}" for x in text[:PREVIEW_LINES]) + more


def decide(path: str, decision: str, reviewer: str, reason: str = "", blind_label: str | None = None,
           before: str | None = None) -> dict:
    """Record one decision (approved, edited, rejected); an edit is an approval of the edited content."""
    if decision in ("edited", "rejected") and not reason:
        raise ValueError(f"{decision} needs a reason")
    e = provenance.review(path, "rejected" if decision == "rejected" else "approved", reviewer,
                          f"edited: {reason}" if decision == "edited" else reason)
    row = {"at": now(), "path": path, "decision": decision, "reviewer": reviewer, "reason": reason or None,
           "sha256": e["sha256"], **({"blind_label": blind_label} if blind_label is not None else {})}
    log(DECISIONS, row)
    if decision in ("edited", "rejected"):
        ex = {**row, "kind": e["kind"], "produced_by": e["produced_by"]}
        if before is not None:
            after = (RL / path).read_text()
            ex["diff"] = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), path, path))
        log(EXAMPLES, ex)
    return row


def review(reviewer: str, batch: int, ask=input, out=print) -> list[dict]:
    """The interactive loop: one key per item. Returns the decisions made."""
    done = []
    todo = items()[:batch]
    out(f"{len(todo)} items (of {len(items())} open). Keys: a approve, e edit, r reject, s skip, q quit.")
    for e in todo:
        out("\n" + show(e))
        blind = None
        if e.get("blind"):
            blind = ask(f"   blind first: {e['blind']['question']}\n   your answer> ")
            log(DECISIONS, {"at": now(), "path": e["path"], "decision": "blind_label", "reviewer": reviewer,
                            "blind_label": blind})
        out(content(e["path"]))
        while (k := ask("   [a/e/r/s/q]> ").strip().lower()[:1]) not in KEYS:
            pass
        if KEYS[k] == "quit":
            break
        if KEYS[k] == "skip":
            continue
        before = None
        if KEYS[k] == "edited":
            if len(provenance.files(e["path"])) != 1:
                out("   a set of files is approved or rejected as a whole; edit the files, then approve")
                continue
            before = (RL / e["path"]).read_text()
            subprocess.run([os.environ.get("EDITOR", "vi"), str(RL / e["path"])])
        reason = ask("   reason> " if KEYS[k] != "approved" else "   reason (optional)> ").strip()
        while KEYS[k] != "approved" and not reason:
            reason = ask("   a reason is required> ").strip()
        done.append(decide(e["path"], KEYS[k], reviewer, reason, blind, before))
        out(f"   recorded: {KEYS[k]}")
    out(f"\n{len(done)} decisions recorded in {DECISIONS.relative_to(RL.parent)}. Rebuild: python rl/build.py")
    return done


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list")
    ls.add_argument("--all", action="store_true", help="also approved and rejected items")
    r = sub.add_parser("review")
    r.add_argument("--reviewer", required=True)
    r.add_argument("--batch", type=int, default=10)
    d = sub.add_parser("decide")
    d.add_argument("path")
    d.add_argument("decision", choices=["approve", "reject"])
    d.add_argument("--reviewer", required=True)
    d.add_argument("--reason", default="")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        for e in items(a.all):
            print(f"{e['value']:>4}  {e['state']:<9} {e['kind']:<12} {e['path']}")
    elif a.cmd == "review":
        review(a.reviewer, a.batch)
    else:
        decide(a.path, {"approve": "approved", "reject": "rejected"}[a.decision], a.reviewer, a.reason)
        print(f"{a.path}: {a.decision}d by {a.reviewer}")


if __name__ == "__main__":
    main()
