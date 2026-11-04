"""Instrument freeze (rl/instrument.py): every family declares its instrument and has an approval
record; a change to any instrument file reopens the approval, blocks live runs and releases, and
shows up in the reviewer's diff."""

from __future__ import annotations

import subprocess

import pytest
import yaml

import instrument
import lib
from splits import check


def test_every_family_declares_its_instrument_and_has_an_approval_record():
    for fam in lib.families():
        assert instrument.files(fam), fam                       # every pattern matches a file
        assert "families/_shared/harbor.py" in instrument.files(fam), fam
        assert (instrument.RL / "families" / fam / "approval.yaml").exists(), fam
        assert set(instrument.approval(fam)) == {"approved", "history"}, fam


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A scratch git repo laid out like rl/, with one family whose instrument is two files plus the shared ones."""
    fam = tmp_path / "families" / "fam"
    fam.mkdir(parents=True)
    (fam / "family.yaml").write_text(yaml.safe_dump({"instrument": ["families/fam/prompt.md", "families/fam/grader.py",
                                                                    "families/_shared/harbor.py"]}))
    (fam / "prompt.md").write_text("Answer the question.\n")
    (fam / "grader.py").write_text("W = 0.1\n")
    for f in instrument.SHARED:
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / f).write_text("# shared\n")
    git = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)  # noqa: E731
    git("init", "-q")
    git("add", ".")
    git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "init")
    monkeypatch.setattr(instrument, "RL", tmp_path)
    monkeypatch.setattr(lib, "RL", tmp_path)
    monkeypatch.setattr(lib, "FAMILIES", tmp_path / "families")
    return fam


def test_approval_covers_exactly_the_current_instrument(repo):
    ok, why = instrument.status("fam")
    assert not ok and "never approved" in why
    with pytest.raises(SystemExit):
        instrument.require_approved("fam")
    e = instrument.approve("fam", "Reviewer", "first look")
    assert instrument.status("fam")[0] and set(e["files"]) == {"families/fam/prompt.md", "families/fam/grader.py",
                                                              *instrument.SHARED}   # shared ones added, listed once
    instrument.require_approved("fam")
    assert instrument.diff("fam").startswith("unchanged since")

    (repo / "grader.py").write_text("W = 0.2\n")                 # change the grader
    ok, why = instrument.status("fam")
    assert not ok and why.endswith("families/fam/grader.py")
    with pytest.raises(SystemExit, match="instrument changed since Reviewer approved"):
        instrument.require_approved("fam")
    d = instrument.diff("fam")
    assert "-W = 0.1" in d and "+W = 0.2" in d                  # the reviewer sees exactly what changed


def test_approving_uncommitted_files_is_refused(repo):
    (repo / "prompt.md").write_text("Answer carefully.\n")
    with pytest.raises(SystemExit, match="commit the instrument files first"):
        instrument.approve("fam", "Reviewer")


def test_reapproval_keeps_history(repo):
    first = instrument.approve("fam", "A")
    instrument.approve("fam", "B")
    a = instrument.approval("fam")
    assert a["approved"]["approved_by"] == "B" and a["history"] == [first]


def test_release_check_refuses_unapproved_instruments(tree):
    tree()
    assert not any("instrument" in p for p in check.check())
    assert any(p.startswith("data_audit: instrument never approved")
               for p in check.release_problems(list(lib.iter_tasks())))
