"""Run records (rl/harness/records.py) and the report over them (rl/harness/report.py): every record
fits the schema, rl/runs/ commits records only and none carries answers or gold, Harbor imports
number their attempts, and a report never averages results measured with different instruments."""

from __future__ import annotations

import json
import pathlib

import pytest

import records
import report
from conftest import RL, built


RUNNER = {"name": "test"}
IDENT = {"task_id": "audit-bench-001", "family": "data_audit", "split": "bench", "mode": "review",
         "content_sha256": "c" * 64, "fingerprint": "f" * 12}


def rec(**kw):
    return records.make(**{**IDENT, "attempt": 0, "runner": RUNNER, "status": "ok", "rewards": {"reward": 0.5}, **kw})


def test_identity_is_hashed_from_the_task_folder(tmp_path):
    import shutil
    task = built("bench", "audit-bench-001")
    ident = records.identity(task)
    assert (ident["task_id"], ident["family"], ident["split"], ident["mode"]) == ("audit-bench-001", "data_audit",
                                                                                  "bench", "review")
    copy = tmp_path / task.name
    shutil.copytree(task, copy)
    (copy / "instruction.md").write_text("changed")
    assert records.identity(copy)["content_sha256"] != ident["content_sha256"]   # the folder run, not the manifest
    r = records.make(**ident, attempt=0, runner=RUNNER, status="ok")
    assert r["instrument_sha256"] == records.instrument.sha256("data_audit")


@pytest.mark.parametrize("status, score", [("ok", 0.5), ("refusal", 0.0), ("timeout", 0.0), ("error", None),
                                           ("not_graded", None)])
def test_score(status, score):
    r = rec(status=status, rewards={"reward": 0.5} if status == "ok" else {})
    assert records.score(r) == score


@pytest.mark.parametrize("bad, problem", [
    ({"status": "fine"}, "status 'fine' not in"),
    ({"latency": 3}, "unknown field latency"),
    ({"attempt": "0"}, "attempt has type str"),
    ({"rewards": {"reward": "high"}}, "reward reward is not a number"),
])
def test_invalid_records_are_rejected(bad, problem):
    r = dict(rec(), **bad)
    assert any(p.startswith(problem) for p in records.validate(r)), records.validate(r)
    with pytest.raises(ValueError):
        records.make(**{**IDENT, "attempt": 0, "runner": RUNNER, "status": "ok", **bad})


def test_cost_and_budget():
    usage = {"input_tokens": 1_000_000, "output_tokens": 100_000, "cache_read_input_tokens": 0}
    p = records.PRICES["claude-opus-5-5"]
    assert records.cost("claude-opus-5-5", usage) == pytest.approx(p["input"] + p["output"] / 10)
    assert records.cost("not-a-model", usage) is None
    b = records.Budget(1.0, "claude-opus-5-5")
    b.spend(0.6, None)
    assert not b.exhausted
    b.spend(0.5)
    assert b.exhausted
    with pytest.raises(SystemExit):
        records.Budget(1.0, "not-a-model")
    assert not records.Budget(None, "not-a-model").exhausted      # no budget, no price needed


def test_runs_commit_records_only():
    """No raw outputs in rl/runs/: no transcripts, native result files, answers or gold."""
    jsonl = [p for p in (RL / "runs").rglob("*.jsonl") if not {"traces", "jobs"} & set(p.parts)]
    assert jsonl and all(p.name.endswith("records.jsonl") for p in jsonl), [str(p) for p in jsonl]
    for f in jsonl:
        for i, r in enumerate(records.load([f])):
            assert records.validate(r) == [], f"{f.relative_to(RL)}:{i + 1}"
            assert "gold" not in json.dumps(r) and "trace" not in r, f"{f.relative_to(RL)}:{i + 1}"


def harbor_trial(jobs: pathlib.Path, name: str, started: str, task: pathlib.Path, reward: float) -> None:
    t = jobs / name
    (t / "verifier").mkdir(parents=True)
    (t / "verifier" / "reward.txt").write_text(f"{reward}\n")
    (t / "verifier" / "judge_usage.json").write_text(json.dumps({"claude-opus-5-5": {"input_tokens": 1_000_000}}))
    (t / "result.json").write_text(json.dumps({"started_at": started, "config": {
        "task": {"path": str(task)}, "agent": {"name": "claude-code", "model_name": "claude-opus-5-5"}}}))


def test_harbor_import_numbers_attempts(tmp_path):
    task = built("bench", "audit-bench-001")
    for name, started, reward in (("b", "2026-11-03T10:05", 0.2), ("a", "2026-11-03T10:00", 0.9), ("c", "2026-11-03T10:09", 0.4)):
        harbor_trial(tmp_path, name, started, task, reward)
    recs = records.import_harbor(tmp_path, "r1")
    assert [(r["attempt"], r["rewards"]["reward"]) for r in recs] == [(0, 0.9), (1, 0.2), (2, 0.4)]
    assert recs[0]["runner"]["run_id"] == "r1" and recs[0]["content_sha256"] == records.identity(task)["content_sha256"]
    assert recs[0]["judge_cost_usd"] == records.PRICES["claude-opus-5-5"]["input"]


def write(path: pathlib.Path, recs) -> pathlib.Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in recs))
    return path


def test_report_refuses_to_mix_instruments(tmp_path, capsys):
    a = rec(model="m1")
    b = dict(rec(model="m2"), fingerprint="000000000000")        # same task, another prompt
    f = write(tmp_path / "r.jsonl", [a, b])
    with pytest.raises(SystemExit) as e:
        report.main([str(f), "--split", "bench"])
    assert "data_audit/audit-bench-001: 2 instruments" in str(e.value)
    report.main([str(f), "--split", "bench", "--mix"])
    out = capsys.readouterr().out
    assert "/000000000000" in out and "warning: 1 tasks span instruments" in out


def test_report_separates_conditions(tmp_path, capsys):
    rs = [rec(model="m1"), dict(rec(model="m1"), attempt=1, rewards={"reward": 1.0}),
          rec(model="m1", skills={"enabled": True, "profile": "buy_side_core"})]
    report.main([str(write(tmp_path / "r.jsonl", rs)), "--split", "bench"])
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("data_audit")]
    assert len(lines) == 2                                         # skills on and off never share a row
    assert any("0.75" in ln and "buy_side_core" not in ln for ln in lines)
