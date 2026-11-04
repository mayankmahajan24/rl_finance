"""Grade a built task locally, without Docker, the way Harbor does: the one place that knows the
container layout.

`grade(task_dir, write_answer)` copies the task's data into a scratch /app (gzipped files unpacked,
as the image build does), lets `write_answer(app, tests)` play the agent, then merges the task's
tests/ into the scratch /tests (Harbor's upload merges into whatever the agent left there), runs
test.sh's cleanup and the verifier test.sh names, and reads /logs/verifier. The built task is never
written to, so its content_sha256 is unchanged.
"""

from __future__ import annotations

import contextlib
import gzip
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from typing import Callable, NamedTuple

RL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RL))
from families._shared import harbor  # noqa: E402
from lib import iter_tasks  # noqa: E402

OFFLINE = {"ANTHROPIC_API_KEY": None, "JUDGE": "keyword"}     # no model calls: keyword judge, no key


class Graded(NamedTuple):
    rewards: dict | None        # reward.json, or {"reward": x} from reward.txt; None if the verifier wrote neither
    details: dict
    judge_usage: dict           # {judge model: usage} the verifier's judge calls used
    error: str | None           # the verifier's stderr tail when it exited non-zero


def tasks(split: str, families: list[str] | None = None) -> list[tuple[pathlib.Path, dict]]:
    """(task_dir, metadata) of every built task in `split`, optionally of these families only."""
    return [(d, m) for d, m in iter_tasks() if d.parent.name == split and (not families or m["family"] in families)]


def verifier(tests: pathlib.Path) -> str:
    """The verifier file test.sh runs."""
    return re.search(r"^python /tests/(\S+)", (tests / "test.sh").read_text(), re.M).group(1)


@contextlib.contextmanager
def layout(task: pathlib.Path):
    """A scratch container layout for the task, removed afterwards: yields /app, with data/ (gzipped
    files unpacked, as the image build does), output/ and solution/; instruction.md sits beside it."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"grade-{task.name}-"))
    try:
        app = tmp / "app"
        shutil.copytree(task / "environment" / "data", app / "data")
        for gz in (app / "data").glob("*.gz"):
            gz.with_suffix("").write_bytes(gzip.decompress(gz.read_bytes()))
            gz.unlink()
        shutil.copy(task / "instruction.md", tmp / "instruction.md")
        (app / "output").mkdir()
        (app / "solution").mkdir()
        yield app
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def grade(task: pathlib.Path, write_answer: Callable[[pathlib.Path, pathlib.Path], None],
          env: dict | None = None) -> Graded:
    """Run the task's verifier on whatever `write_answer(app, tests)` leaves. `env` adds to the
    verifier's environment; a None value removes that variable."""
    with layout(task) as app:
        tests, logs = app.parent / "tests", app.parent / "logs"
        write_answer(app, tests)
        shutil.copytree(task / "tests", tests, dirs_exist_ok=True)
        if harbor.TEST_CLEANUP in (tests / "test.sh").read_text():
            subprocess.run(["bash", "-c", harbor.TEST_CLEANUP.replace("/tests", str(tests))], check=True)
        (logs / "verifier").mkdir(parents=True)
        e = {**os.environ, "APP_DIR": str(app), "TESTS_DIR": str(tests), "LOGS_DIR": str(logs),
             "PYTHONDONTWRITEBYTECODE": "1", "PATH": str(pathlib.Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]}
        for k, v in (env or {}).items():
            if v is None:
                e.pop(k, None)
            else:
                e[k] = v
        timeout = tomllib.loads((task / "task.toml").read_text())["verifier"]["timeout_sec"]
        r = subprocess.run([sys.executable, verifier(tests)], cwd=tests, env=e, capture_output=True, text=True,
                           timeout=timeout)
        out = logs / "verifier"
        read = lambda name: json.loads((out / name).read_text()) if (out / name).exists() else None  # noqa: E731
        rewards = read("reward.json")
        if rewards is None and (out / "reward.txt").exists():
            rewards = {"reward": float((out / "reward.txt").read_text())}
        return Graded(rewards, read("details.json") or {}, read("judge_usage.json") or {},
                      r.stderr[-2000:] if r.returncode else None)
