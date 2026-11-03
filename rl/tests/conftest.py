"""Shared fixtures. Tests that need built tasks use the ones under rl/tasks/ (CI builds them first:
`python rl/build.py research_design kpi_nowcast panel --split bench`) and skip when they are missing."""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

RL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RL))
import lib  # noqa: E402

TASKS = lib.TASKS          # tests may point lib.TASKS at a scratch tree; built tasks stay here


def built(split: str, task_id: str) -> pathlib.Path:
    d = TASKS / split / task_id
    if not (d / "task.toml").exists():
        pytest.skip(f"{split}/{task_id} not built (python rl/build.py ... --split {split})")
    return d


def run_verifier(task: pathlib.Path, tmp: pathlib.Path, output: dict[str, str] | None = None,
                 solution: dict[str, str] | None = None) -> tuple[dict, dict]:
    """Grade `output` (files written to /app/output) and `solution` (files in /app/solution) with the
    task's own verifier, the one its tests/test.sh runs, in a local copy of the container layout.
    Returns (rewards, details); rewards is {"reward": x} for verifiers that write reward.txt."""
    app, logs = tmp / "app", tmp / "logs"
    shutil.copytree(task / "environment" / "data", app / "data")
    for sub, files in (("output", output), ("solution", solution)):
        (app / sub).mkdir()
        for name, text in (files or {}).items():
            (app / sub / name).write_text(text)
    verifier = re.search(r"^python /tests/(\S+)", (task / "tests" / "test.sh").read_text(), re.M).group(1)
    env = dict(os.environ, APP_DIR=str(app), TESTS_DIR=str(task / "tests"), LOGS_DIR=str(logs),
               PATH=str(pathlib.Path(sys.executable).parent) + os.pathsep + os.environ["PATH"])
    r = subprocess.run([sys.executable, verifier], cwd=task / "tests", env=env, capture_output=True, text=True)
    assert r.returncode == 0, f"verifier crashed:\n{r.stderr[-2000:]}"
    out = logs / "verifier"
    rewards = (json.loads((out / "reward.json").read_text()) if (out / "reward.json").exists()
               else {"reward": float((out / "reward.txt").read_text())})
    return rewards, json.loads((out / "details.json").read_text())


@pytest.fixture
def offline(monkeypatch):
    """No model calls: verifiers fall back to their offline graders (keyword judge, no write-up score)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("JUDGE", "keyword")
