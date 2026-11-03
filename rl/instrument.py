"""Instrument freeze: a family's measuring instrument is hashed, and live use needs a human approval of
that exact hash.

The instrument is everything that decides what a model sees and how it is scored: prompts and
instructions, schemas, graders, judge rubrics, verifier, builder or generator, and the shared task
writer. Each family lists its files (globs allowed, relative to rl/) under `instrument` in
family.yaml. `families/<family>/approval.yaml` records the approved hash, who approved it, when,
at which commit, and each file's hash, so a reviewer can see exactly what changed since:

    approved:   {sha256, approved_by, approved_at, commit, note, files: {path: sha256}} or null
    history:    earlier approvals, newest first

Live API runs refuse to start, and `splits/check.py --release` (and so the export) fails, while a
family's current hash isn't the approved one. Dry runs and local solution runs are always allowed.
Review and approve with rl/harness/approve.py.
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
from datetime import datetime, timezone

import yaml

RL = pathlib.Path(__file__).resolve().parent
HEADER = ("# Instrument approval (rl/instrument.py). Written by rl/harness/approve.py; don't hand-edit.\n")


def family_yaml(family: str) -> dict:
    return yaml.safe_load((RL / "families" / family / "family.yaml").read_text())


def families() -> list[str]:
    return sorted(d.name for d in (RL / "families").iterdir() if (d / "family.yaml").exists())


def files(family: str) -> list[str]:
    """The family's instrument files, relative to rl/, globs expanded; a pattern matching nothing is an error."""
    out = []
    for pat in family_yaml(family).get("instrument", []):
        found = sorted(str(p.relative_to(RL)) for p in RL.glob(pat) if p.is_file())
        if not found:
            raise SystemExit(f"{family}: instrument entry {pat} matches no file")
        out += found
    return sorted(set(out))


def file_hashes(family: str) -> dict[str, str]:
    return {f: hashlib.sha256((RL / f).read_bytes()).hexdigest() for f in files(family)}


def sha256(family: str) -> str:
    h = hashlib.sha256()
    for f, s in file_hashes(family).items():
        h.update(f.encode() + b"\0" + s.encode() + b"\n")
    return h.hexdigest()


def approval(family: str) -> dict:
    f = RL / "families" / family / "approval.yaml"
    return (yaml.safe_load(f.read_text()) if f.exists() else None) or {"approved": None, "history": []}


def status(family: str) -> tuple[bool, str]:
    """(approved, one line saying why)."""
    a, now = approval(family)["approved"], sha256(family)
    if not a:
        return False, f"{family}: instrument never approved (now {now[:12]})"
    if a["sha256"] != now:
        changed = sorted(f for f, s in file_hashes(family).items() if a.get("files", {}).get(f) != s)
        gone = sorted(set(a.get("files", {})) - set(file_hashes(family)))
        return False, (f"{family}: instrument changed since {a['approved_by']} approved {a['sha256'][:12]} on "
                       f"{a['approved_at'][:10]}: {', '.join(changed + [f'{g} (removed)' for g in gone])}")
    return True, f"{family}: instrument {now[:12]} approved by {a['approved_by']} on {a['approved_at'][:10]}"


def require_approved(family: str) -> None:
    """Refuse live use of a family whose instrument isn't the approved one."""
    ok, why = status(family)
    if not ok:
        raise SystemExit(f"{why}.\nReview it (python rl/harness/approve.py --family {family} --show), then approve it.")


def _git(*a) -> str:
    return subprocess.run(["git", *a], cwd=RL, capture_output=True, text=True).stdout


def approve(family: str, by: str, note: str = "") -> dict:
    """Record approval of the family's current instrument. Its files must be committed, so the approved
    content can always be recovered from the recorded commit."""
    dirty = _git("status", "--porcelain", "--", *files(family)).strip()
    if dirty:
        raise SystemExit(f"{family}: commit the instrument files first:\n{dirty}")
    a = approval(family)
    entry = {"sha256": sha256(family), "approved_by": by,
             "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "commit": _git("rev-parse", "HEAD").strip(), "note": note or None, "files": file_hashes(family)}
    history = ([a["approved"]] if a["approved"] else []) + a.get("history", [])
    out = {"approved": entry, "history": history}
    (RL / "families" / family / "approval.yaml").write_text(HEADER + yaml.safe_dump(out, sort_keys=False, width=100))
    return entry


def diff(family: str) -> str:
    """What changed in the instrument since the approved commit (all files when never approved)."""
    a = approval(family)["approved"]
    if not a:
        return "never approved; the instrument is:\n" + "\n".join(f"  {f}" for f in files(family))
    changed = [f for f, s in file_hashes(family).items() if a["files"].get(f) != s]
    gone = sorted(set(a["files"]) - set(file_hashes(family)))
    if not changed and not gone:
        return f"unchanged since {a['commit'][:12]}"
    added = [f for f in changed if f not in a["files"]]
    text = _git("diff", a["commit"], "--", *[f for f in changed if f not in added], *gone)
    text += "".join(f"\n+++ new instrument file {f}\n" + (RL / f).read_text() for f in added)
    # uncommitted edits show too: git diff <commit> compares with the working tree
    return text
