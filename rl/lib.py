"""Shared helpers for the rl/ task tree.

A task lives at rl/roles/<role>/<workflow>/<task_id>/ and has two halves that
must never mix:

  prompt/   what the model sees — rendered system and user messages
  grader/   what only the grader sees — gold labels, rubrics, reference outputs

See FORMAT.md for the full spec.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

import yaml

RL = pathlib.Path(__file__).resolve().parent
ROOT = RL.parent
CASE = ROOT / "case_study"   # the original take-home: part0-3, scripts, seeds
ROLES = RL / "roles"
WORLDS = RL / "worlds"

# Workflows regenerated from case_study/. Everything else under roles/ is left alone
# by build_from_case_study.py so instrumentation FORMAT mirrors survive a rebuild.
CASE_STUDY_WORKFLOWS = ("research_design", "research_funding")
CATALOG_FIELDS = ("id", "role", "workflow", "mode", "world", "status", "split")


def fingerprint(*parts: str) -> str:
    """Same hash as case_study/scripts/run_eval.py, so a task rendered here can be proven to
    use the identical instrument the case-study runs used."""
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


def iter_tasks():
    """Yield (task_dir, task_yaml) for every task in the tree."""
    for p in sorted(ROLES.glob("*/*/*/task.yaml")):
        yield p.parent, yaml.safe_load(p.read_text())


def load_task(task_id: str) -> tuple[pathlib.Path, dict]:
    for d, t in iter_tasks():
        if t["id"] == task_id:
            return d, t
    raise KeyError(task_id)


def catalog_row(task: dict) -> dict:
    return {k: task[k] for k in CATALOG_FIELDS}


def write_catalog() -> list[dict]:
    """Rewrite rl/catalog.json from every task folder currently on disk."""
    catalog = [catalog_row(t) for _, t in iter_tasks()]
    write_json(RL / "catalog.json", catalog)
    return catalog
