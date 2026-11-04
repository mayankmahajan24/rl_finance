"""Gold provenance (rl/provenance.py), its enforcement in splits/check.py, and the review queue
(rl/review/review.py). Most tests run on a scratch rl/ tree with one family and one gold file."""

from __future__ import annotations

import json

import pytest
import yaml

import lib
import provenance
import review as review_queue
from splits import check
from test_check import edit

GOLD = "sources/s/gold.json"


@pytest.fixture
def rl(tmp_path, monkeypatch):
    """A scratch rl/ with family `fam` whose one gold input has a draft provenance entry."""
    (tmp_path / "families" / "fam").mkdir(parents=True)
    (tmp_path / "families" / "fam" / "family.yaml").write_text(yaml.safe_dump({"gold_inputs": [GOLD]}))
    (tmp_path / "sources" / "s").mkdir(parents=True)
    (tmp_path / GOLD).write_text('{"answer": 1}\n')
    (tmp_path / "sources" / "s" / "provenance.yaml").write_text(yaml.safe_dump([{
        "path": GOLD, "kind": "gold", "produced_by": {"type": "model", "model": "m", "prompt_fingerprint": "f"},
        "produced_at": "2026-11-01", "sha256": None,
        "review": {"status": "draft", "reviewer": None, "reviewed_at": None, "reason": None},
        "blind": {"question": "What is the answer?"}}]))
    monkeypatch.setattr(provenance, "RL", tmp_path)
    monkeypatch.setattr(lib, "FAMILIES", tmp_path / "families")
    monkeypatch.setattr(review_queue, "RL", tmp_path)
    monkeypatch.setattr(review_queue, "DECISIONS", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(review_queue, "EXAMPLES", tmp_path / "examples.jsonl")
    monkeypatch.setattr(review_queue.splits, "manifest", lambda f: {"t1": {"split": "bench"}} if f == "fam" else {})
    provenance._cached.cache_clear()
    yield tmp_path
    provenance._cached.cache_clear()


def test_approval_binds_to_the_content(rl):
    assert provenance.summary(provenance.for_family("fam")) == {
        "status": "unapproved", "files": 1, "unapproved": [GOLD]}
    provenance.review(GOLD, "approved", "Reviewer")
    assert provenance.summary(provenance.for_family("fam"))["status"] == "approved"
    (rl / GOLD).write_text('{"answer": 2}\n')
    assert provenance.for_family("fam")[0]["state"] == "changed"


def test_index_problems(rl):
    assert provenance.problems() == []
    (rl / "families" / "fam" / "family.yaml").write_text(yaml.safe_dump({"gold_inputs": [GOLD, "sources/s/other.json"]}))
    assert provenance.problems() == ["fam: gold input sources/s/other.json has no provenance entry"]


def test_review_session(rl):
    """Blind label first, then the draft; approve needs no reason, reject needs one; both are logged."""
    (rl / "sources" / "s" / "z.json").write_text("{}\n")
    idx = yaml.safe_load((rl / "sources" / "s" / "provenance.yaml").read_text())
    idx.append(dict(idx[0], path="sources/s/z.json", blind=None))
    (rl / "sources" / "s" / "provenance.yaml").write_text(yaml.safe_dump(idx))
    (rl / "families" / "fam" / "family.yaml").write_text(yaml.safe_dump({"gold_inputs": [GOLD, "sources/s/z.json"]}))
    answers, shown = iter(["1", "a", "", "r", "", "wrong field"]), []
    done = review_queue.review("Reviewer", 10, ask=lambda prompt: (shown.append(prompt), next(answers))[1],
                               out=shown.append)
    assert [d["decision"] for d in done] == ["approved", "rejected"]
    text = "\n".join(map(str, shown))
    assert text.index("your answer>") < text.index('| {"answer": 1}')            # blind label before the draft
    log = [json.loads(x) for x in (rl / "decisions.jsonl").read_text().splitlines()]
    assert [x["decision"] for x in log] == ["blind_label", "approved", "rejected"]
    assert log[1]["blind_label"] == "1" and log[2]["reason"] == "wrong field"
    assert [json.loads(x)["path"] for x in (rl / "examples.jsonl").read_text().splitlines()] == ["sources/s/z.json"]
    assert review_queue.items() == []
    assert provenance.for_family("fam")[1]["state"] == "rejected"


def test_edit_and_reject_need_a_reason(rl):
    with pytest.raises(ValueError):
        review_queue.decide(GOLD, "rejected", "Reviewer")


TASK = "audit-bench-001"


def test_release_refuses_unapproved_gold(tree):
    d = tree()
    assert check.provenance_problems(d, lib.task_meta(d)) == []
    p = check.gold_approval_problems(d, lib.task_meta(d))
    assert p and p[0].startswith(f"{TASK}: gold not approved: ")


def test_task_built_as_approved_after_approval_was_lost(tree):
    d = tree()
    edit(d, "task.toml", 'status = "unapproved"', 'status = "approved"')
    assert check.provenance_problems(d, lib.task_meta(d))[0].startswith(
        f"{TASK}: built as approved, but ")


def test_task_without_provenance(tree):
    d = tree()
    (d / "tests" / "provenance.json").unlink()
    assert check.provenance_problems(d, lib.task_meta(d)) == [
        f"{TASK}: no gold provenance recorded (rebuild)"]
