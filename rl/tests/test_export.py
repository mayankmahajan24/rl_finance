"""rl/export.py: what must never leave the repo is refused, and the archive is reproducible."""

from __future__ import annotations

import hashlib
import shutil
import tarfile

import pytest

import export
import lib
from conftest import built
from families._shared import harbor
from test_check import edit

TASK = "audit-bench-001"


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """One built bench task in a scratch tasks/ tree."""
    monkeypatch.setattr(lib, "TASKS", tmp_path / "tasks")
    d = tmp_path / "tasks" / "bench" / TASK
    shutil.copytree(built("bench", TASK), d)
    return d


def licence(monkeypatch, status: str) -> None:
    real = export.source_yaml
    monkeypatch.setattr(export, "source_yaml", lambda s: dict(real(s), licence={"status": status, "note": "test"}))


def stamped(monkeypatch, tasks) -> None:
    """Treat the tasks' build time as their commit's, as a SOURCE_DATE_EPOCH build would stamp it."""
    monkeypatch.setattr(export, "commit_timestamp", lambda c: tasks[0][1]["build"]["built_at"])


def test_heldout_and_retired_are_never_exported(tree):
    for split in ("heldout", "retired"):
        assert export.refusals(split, "eval", export.select("bench", None), "0.1.0", False) == [
            f"{split} tasks are never exported"]


def test_uncleared_source_is_refused(tree, monkeypatch):
    tasks = export.select("bench", None)
    stamped(monkeypatch, tasks)
    clean = dict(run_check=lambda release: [])
    licence(monkeypatch, "unknown")
    assert export.refusals("bench", "eval", tasks, "0.1.0", False, **clean) == [
        "source txn_panel: licence.status unknown does not clear eval use "
        "(needs licensed_for_eval or licensed_for_training or public)"]
    assert export.refusals("bench", "eval", tasks, "0.1.0", True, **clean) == []       # --preview only
    licence(monkeypatch, "licensed_for_eval")
    assert export.refusals("bench", "eval", tasks, "0.1.0", False, **clean) == []
    assert export.refusals("bench", "training", tasks, "0.1.0", False, **clean)[0].startswith(
        "source txn_panel: licence.status licensed_for_eval does not clear training use")


def test_dirty_build_is_refused(tree, monkeypatch):
    edit(tree, "task.toml", "repo_dirty = false", "repo_dirty = true")
    licence(monkeypatch, "public")
    tasks = export.select("bench", None)
    stamped(monkeypatch, tasks)
    assert export.refusals("bench", "eval", tasks, "0.1.0", False) == [
        f"split check --release: {TASK}: built with uncommitted changes to tracked files"]


def test_unstamped_build_and_missing_changelog_are_refused(tree, monkeypatch):
    tasks = export.select("bench", None)
    licence(monkeypatch, "public")
    monkeypatch.setattr(export, "commit_timestamp", lambda c: "2000-01-01T00:00:00+00:00")
    p = export.refusals("bench", "eval", tasks, "9.9.9", False, run_check=lambda release: [])
    assert p[0] == "release/CHANGELOG.md has no '## 9.9.9' entry"
    assert p[1].startswith("tasks are stamped") and "SOURCE_DATE_EPOCH" in p[1]


def test_archive_is_byte_identical(tree, monkeypatch, tmp_path):
    monkeypatch.setattr(export, "refusals", lambda *a, **k: [])
    outs = []
    for name in ("a", "b"):
        manifest, files = export.bundle("bench", None, "eval")
        out = tmp_path / name / "bundle.tar.gz"
        export.write_tar(out, "rl_finance-test", files, 1_700_000_000)
        outs.append(out)
    assert outs[0].read_bytes() == outs[1].read_bytes()
    assert (outs[0].parent / "bundle.tar.gz.sha256").read_text().split()[0] == hashlib.sha256(
        outs[0].read_bytes()).hexdigest()
    with tarfile.open(outs[0]) as tar:
        names = tar.getnames()
        assert names == sorted(names) and {m.mtime for m in tar.getmembers()} == {1_700_000_000}
        assert tar.getmember(f"rl_finance-test/tasks/{TASK}/tests/test.sh").mode == 0o755
    assert manifest["tasks"][TASK]["content_sha256"] == harbor.content_sha256(tree)
    assert {"release.json", "CHANGELOG.md", "DATASHEET.md", "cards/data_audit.md",
            f"tasks/{TASK}/checksums.sha256"} <= set(files)
