"""The shared model judge (families/_shared/judge.py): it records what it graded with, re-grades from
cache without a call, combines votes, and never quietly swaps in another grader."""

from __future__ import annotations

import contextlib
import json
import sys
from types import SimpleNamespace

import pytest

from conftest import RL, built, run_verifier
from families._shared import judge

sys.path.insert(0, str(RL / "harness"))
import judge_stability  # noqa: E402

CFG = {"model": "claude-opus-5-5", "effort": "medium", "votes": 1, "max_tokens": 1000}
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}}


class FakeClient:
    """Answers every judge call with the next of `texts`, served as `served`."""

    def __init__(self, *texts, served="claude-opus-5-5-20261001", stop="end_turn"):
        self.texts, self.calls, self.served, self.stop = list(texts), [], served, stop
        self.messages = self

    @contextlib.contextmanager
    def stream(self, **req):
        self.calls.append(req)
        msg = SimpleNamespace(model=self.served, stop_reason=self.stop,
                              content=[SimpleNamespace(type="text", text=self.texts[len(self.calls) - 1])])
        yield SimpleNamespace(get_final_message=lambda: msg)


def test_records_what_it_graded_with():
    outs, meta = judge.judge("Grade it.", "the answer", SCHEMA, CFG, FakeClient('{"ok": true}'))
    assert outs == [{"ok": True}]
    assert meta == {"requested_model": "claude-opus-5-5", "served_model": ["claude-opus-5-5-20261001"],
                    "effort": "medium", "votes": 1, "prompt_fingerprint": judge.fingerprint("Grade it.", SCHEMA),
                    "cached_votes": 0}


def test_regrading_from_cache_needs_no_call(tmp_path, monkeypatch):
    monkeypatch.setenv("JUDGE_CACHE", str(tmp_path))
    first = judge.judge("Grade it.", "the answer", SCHEMA, CFG, FakeClient('{"ok": true}'))
    again = FakeClient()                                           # would fail if called
    second = judge.judge("Grade it.", "the answer", SCHEMA, CFG, again)
    assert again.calls == [] and second[0] == first[0] and second[1]["cached_votes"] == 1
    other = FakeClient('{"ok": false}')                            # a different answer is a different key
    assert judge.judge("Grade it.", "another answer", SCHEMA, CFG, other)[0] == [{"ok": False}]


def test_votes_and_majority():
    outs, meta = judge.judge("g", "a", SCHEMA, dict(CFG, votes=3),
                             FakeClient(*['{"ok": true}', '{"ok": false}', '{"ok": true}']))
    assert len(outs) == 3 and meta["votes"] == 3
    v = [{"C1": {"verdict": "pass"}, "C2": {"verdict": "fail"}},
         {"C1": {"verdict": "fail"}, "C2": {"verdict": "fail"}},
         {"C1": {"verdict": "pass"}, "C2": {"verdict": "pass"}}]
    m = judge.majority(v, "verdict")
    assert m["C1"]["verdict"] == "pass" and m["C1"]["votes"] == {"pass": 2, "fail": 1}
    assert m["C2"]["verdict"] == "fail"
    tie = judge.majority(v[:2], "verdict")["C1"]
    assert tie["verdict"] == "pass"                                # a tie takes the first vote


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_refusal_and_truncation_are_errors(stop):
    with pytest.raises(judge.JudgeError):
        judge.judge("g", "a", SCHEMA, CFG, FakeClient('{"ok": true}', stop=stop))


def test_overrides_are_recorded(tmp_path, monkeypatch):
    (tmp_path / "judge.json").write_text(json.dumps(CFG))
    monkeypatch.setenv("JUDGE_MODEL", "claude-sonnet-5-5")
    cfg = judge.config(tmp_path / "judge.json")
    assert cfg["model"] == "claude-sonnet-5-5" and cfg["overridden"] == ["model"]


def test_no_key_means_not_graded(tmp_path, monkeypatch):
    """Without a key, the memo is not graded: no reward, and no silent switch to the keyword grader."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("JUDGE", raising=False)
    task = built("bench", "thesis-bench-001")
    memo = "Airline X grew fastest; the panel ramp on one source is an artifact."
    answer = json.dumps({"fastest": "X", "growth": {}, "unreliable": []})
    rewards, details = run_verifier(task, tmp_path, output={"answer.json": answer, "memo.md": memo})
    assert rewards == {} and details["status"] == "not graded" and "JUDGE=keyword" in details["note"]
    monkeypatch.setenv("JUDGE", "keyword")
    rewards, details = run_verifier(task, tmp_path / "kw", output={"answer.json": answer, "memo.md": memo})
    assert "reward" in rewards and details["judge"] == "keyword"


def test_every_judged_task_carries_the_pinned_judge():
    for split, tid in (("bench", "thesis-bench-001"), ("eval", "rd-review-S1-A")):
        d = built(split, tid)
        assert (d / "tests" / "judge.py").read_text() == (RL / "families" / "_shared" / "judge.py").read_text()
        fam = json.loads((d / "tests" / "judge.json").read_text())
        assert set(fam) == {"model", "effort", "votes", "max_tokens"}
    assert not (built("eval", "rd-funding-S1") / "tests" / "judge.py").exists()   # compare tasks call no judge


def test_stability_report_flags_flaky_items():
    r = judge_stability.report({"a": [{"C1": "pass", "C2": "pass"}, {"C1": "pass", "C2": "fail"}],
                                "b": [{"C1": "fail", "C2": "pass"}, {"C1": "fail", "C2": "fail"}]})
    assert r["item_agreement"] == {"C1": 1.0, "C2": 0.5} and r["flaky_items"] == ["C2"]
