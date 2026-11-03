"""Provenance for every gold-bearing file: who or what produced it, when, and whether it was approved.

Gold is what we sell, so each file a grader trusts (gold labels, rubrics, grader facts, annotations,
generators whose output is ground truth) has an entry in a provenance index: `provenance.yaml` in
its source's or family's folder. A family's `gold_inputs` in family.yaml lists the files its tasks'
gold comes from; the shared task writer copies their entries into each task's
tests/provenance.json and summarizes them in [metadata.provenance].

    path         the file, or a glob for a set reviewed as one item, relative to rl/
    kind         gold | rubric | grader_facts | annotation | generator | reference
    produced_by  {type: human, who} | {type: model, model, prompt_fingerprint} | {type: code, ref, commit}
                 | {type: unrecorded}: nobody wrote it down; the reviewer settles it
    produced_at  when
    sha256       of the content the review applies to (a glob: of every matching file, path and content)
    review       {status: draft | approved | rejected, reviewer, reviewed_at, reason}
    evidence     optional: where each claim in the file can be checked, shown beside it in the queue
    blind        optional: {question}: the reviewer labels blind before the draft is shown

An approval binds to `sha256`: a file that changed after review counts as unreviewed again.
`rl/review/review.py` is where entries get reviewed; splits/check.py --release (and so export) refuses a
bench or held-out task whose gold is not all approved and current.
"""

from __future__ import annotations

import functools
import hashlib
import pathlib
from datetime import datetime, timezone

import yaml

RL = pathlib.Path(__file__).resolve().parent
KINDS = ("gold", "rubric", "grader_facts", "annotation", "generator", "reference")
STATUSES = ("draft", "approved", "rejected")
HEADER = ("# Provenance index (rl/provenance.py): one entry per gold-bearing file. Review entries with\n"
          "# rl/review/review.py, which rewrites this file; don't hand-edit `review` or `sha256`.\n")


def indexes() -> list[pathlib.Path]:
    return sorted([*RL.glob("sources/*/provenance.yaml"), *RL.glob("families/*/provenance.yaml")])


def load() -> dict[str, dict]:
    """{path: entry} over every index, each entry carrying the index file it lives in."""
    out = {}
    for f in indexes():
        for e in yaml.safe_load(f.read_text()) or []:
            if e["path"] in out:
                raise SystemExit(f"{e['path']}: in two provenance indexes")
            out[e["path"]] = dict(e, index=str(f.relative_to(RL)))
    return out


def files(path: str) -> list[pathlib.Path]:
    return sorted(p for p in RL.glob(path) if p.is_file()) if any(c in path for c in "*?[") else [RL / path]


def sha256(path: str) -> str | None:
    """Content hash of one file, or of every file a glob matches (path and content); None if missing."""
    fs = [p for p in files(path) if p.exists()]
    if not fs:
        return None
    if len(fs) == 1 and fs[0] == RL / path:
        return hashlib.sha256(fs[0].read_bytes()).hexdigest()
    h = hashlib.sha256()
    for p in fs:
        h.update(str(p.relative_to(RL)).encode() + b"\0" + hashlib.sha256(p.read_bytes()).hexdigest().encode() + b"\n")
    return h.hexdigest()


def gold_inputs(family: str) -> list[str]:
    f = RL / "families" / family / "family.yaml"
    return list((yaml.safe_load(f.read_text()) or {}).get("gold_inputs", [])) if f.exists() else []


def state(entry: dict | None, path: str) -> str:
    """approved | draft | rejected | changed (approved, but the file changed since) | missing (no entry)."""
    if entry is None:
        return "missing"
    status = entry["review"]["status"]
    if status == "approved" and entry.get("sha256") != sha256(path):
        return "changed"
    return status


@functools.cache
def _cached() -> dict[str, dict]:
    return load()


def for_family(family: str, fresh: bool = False) -> list[dict]:
    """The provenance entries of a family's gold inputs, with each one's current state."""
    idx = load() if fresh else _cached()
    return [{**{k: v for k, v in (idx.get(p) or {"path": p}).items() if k != "index"}, "state": state(idx.get(p), p)}
            for p in gold_inputs(family)]


def summary(entries: list[dict]) -> dict:
    """[metadata.provenance]: approved only when every gold input is approved and unchanged."""
    open_ = sorted(e["path"] for e in entries if e["state"] != "approved")
    return {"status": "approved" if entries and not open_ else "unapproved", "files": len(entries),
            **({"unapproved": open_} if open_ else {})}


def review(path: str, status: str, reviewer: str, reason: str = "") -> dict:
    """Record a decision on one entry, binding it to the content as it is now; returns the entry."""
    if status not in STATUSES:
        raise ValueError(status)
    idx = load()
    if path not in idx:
        raise KeyError(path)
    f = RL / idx[path]["index"]
    entries = yaml.safe_load(f.read_text())
    e = next(x for x in entries if x["path"] == path)
    e["sha256"] = sha256(path)
    e["review"] = {"status": status, "reviewer": reviewer,
                   "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "reason": reason or None}
    f.write_text(HEADER + yaml.safe_dump(entries, sort_keys=False, allow_unicode=True, width=100))
    _cached.cache_clear()
    return e


def problems() -> list[str]:
    """Index entries that are malformed, or whose files are gone; every family's gold inputs indexed."""
    out, idx = [], load()
    for p, e in idx.items():
        if e.get("kind") not in KINDS:
            out.append(f"{p}: kind {e.get('kind')!r} not one of {', '.join(KINDS)}")
        if (e.get("review") or {}).get("status") not in STATUSES:
            out.append(f"{p}: review status {(e.get('review') or {}).get('status')!r} not one of {', '.join(STATUSES)}")
        if (e.get("produced_by") or {}).get("type") not in ("human", "model", "code", "unrecorded"):
            out.append(f"{p}: produced_by.type must be human, model, code or unrecorded")
        if sha256(p) is None:
            out.append(f"{p}: in {e['index']} but no such file")
    for fam in sorted(d.name for d in (RL / "families").iterdir() if (d / "family.yaml").exists()):
        out += [f"{fam}: gold input {p} has no provenance entry" for p in gold_inputs(fam) if p not in idx]
    return out
