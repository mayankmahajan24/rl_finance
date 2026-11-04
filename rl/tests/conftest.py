"""Shared fixtures. Tests that need built tasks use the ones under rl/tasks/ (CI builds them first:
`python rl/build.py research_design kpi_nowcast panel --split bench`); they skip when the tasks are
missing, and fail instead when CI is set."""

from __future__ import annotations

import os
import pathlib
import shutil

import pytest

import lib
import local

RL = pathlib.Path(__file__).resolve().parents[1]
TASKS = lib.TASKS          # tests may point lib.TASKS at a scratch tree; built tasks stay here


def built(split: str, task_id: str) -> pathlib.Path:
    d = TASKS / split / task_id
    if not (d / "task.toml").exists():
        (pytest.fail if os.environ.get("CI") else pytest.skip)(
            f"{split}/{task_id} not built (python rl/build.py ... --split {split})")
    return d


def run_verifier(task: pathlib.Path, output: dict[str, str] | None = None,
                 solution: dict[str, str] | None = None) -> tuple[dict, dict]:
    """Grade `output` (files written to /app/output) and `solution` (files in /app/solution) with the
    task's own verifier (local.grade). Returns (rewards, details)."""
    def write(app: pathlib.Path, tests: pathlib.Path) -> None:
        for sub, files in (("output", output), ("solution", solution)):
            for name, text in (files or {}).items():
                (app / sub / name).write_text(text)

    g = local.grade(task, write)
    assert g.error is None and g.rewards is not None, f"verifier crashed:\n{g.error}"
    return g.rewards, g.details


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A scratch tasks/ tree in place of rl/tasks: `tree(folder, task, split, name)` copies the built
    task `split`/`task` (default bench/audit-bench-001) to tasks/<folder>/<name or task> and returns it."""
    monkeypatch.setattr(lib, "TASKS", tmp_path / "tasks")

    def put(folder: str = "bench", task: str = "audit-bench-001", split: str = "bench",
            name: str | None = None) -> pathlib.Path:
        d = tmp_path / "tasks" / folder / (name or task)
        shutil.copytree(built(split, task), d)
        return d
    return put


@pytest.fixture
def offline(monkeypatch):
    """No model calls: verifiers fall back to their offline graders (keyword judge, no write-up score)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("JUDGE", "keyword")
