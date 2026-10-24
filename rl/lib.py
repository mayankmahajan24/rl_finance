"""Shared helpers for the rl/ task tree.

Every built task lives at rl/tasks/<split>/<task_id>/ in Harbor layout (families/_shared/harbor.py).
What the model sees (instruction.md, environment/, prompt/) and what only the grader sees (tests/)
must never mix. See FORMAT.md for the full spec.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import tomllib

import yaml

RL = pathlib.Path(__file__).resolve().parent
ROOT = RL.parent
TASKS = RL / "tasks"
WORLDS = RL / "worlds"


def fingerprint(*parts: str) -> str:
    """Same hash the case study's scripts/run_eval.py used, so a task rendered here can be
    proven to use the identical instrument as the baseline runs in sources/research_design_case/."""
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode())
    return h.hexdigest()[:12]


def split_prompt(text: str) -> tuple[str, str]:
    """Split a prompt file into (system, user_template) on its ## SYSTEM / ## USER markers."""
    m = re.search(r"^## SYSTEM\s*$(.*?)^## USER\s*$(.*)", text, re.S | re.M)
    if not m:
        raise SystemExit("prompt file must contain '## SYSTEM' and '## USER' markers")
    return m.group(1).strip(), m.group(2).strip()


def load_prompt(path: pathlib.Path) -> tuple[str, str]:
    return split_prompt(path.read_text())


def write_json(path: pathlib.Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def write_yaml(path: pathlib.Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100))


def task_meta(task_dir: pathlib.Path) -> dict:
    """The [metadata] table of a task's task.toml."""
    return tomllib.loads((task_dir / "task.toml").read_text())["metadata"]


def iter_tasks(family: str | None = None):
    """Yield (task_dir, metadata) for every built task, optionally one family's."""
    for p in sorted(TASKS.glob("*/*/task.toml")):
        m = task_meta(p.parent)
        if family is None or m.get("family") == family:
            yield p.parent, m


def load_task(task_id: str) -> tuple[pathlib.Path, dict]:
    for d, t in iter_tasks():
        if t["id"] == task_id:
            return d, t
    raise KeyError(task_id)
