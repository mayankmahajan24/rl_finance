"""Run records (rl/harness/records.py) and the report over them (rl/harness/report.py): every record
fits the schema, every run file in rl/runs/ has its records, and a report never averages
results measured with different instruments."""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

from conftest import RL

sys.path.insert(0, str(RL / "harness"))
import records  # noqa: E402
import report  # noqa: E402

RUNNER = {"name": "test"}


def rec(task="audit-bench-001", family="data_audit", **kw):
    return records.make(task_id=task, family=family, attempt=0, runner=RUNNER, status="ok",
                        rewards={"reward": 0.5}, **kw)


def test_identity_comes_from_the_manifest():
    r = rec()
    m = records.splits.manifest("data_audit")["audit-bench-001"]
    assert (r["split"], r["content_sha256"], r["fingerprint"], r["mode"]) == (
        "bench", m["content_sha256"], m["fingerprint"], "review")


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
        records.make(**{"task_id": "audit-bench-001", "family": "data_audit", "attempt": 0, "runner": RUNNER,
                        "status": "ok", **bad})


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


def test_kpi_errors_and_refusals_keep_their_class():
    t = records.from_kpi({"prompt_id": "kn-produce-UAL-2018Q4", "rep": 0, "failure_class": "timeout", "error": "x"},
                         runner=RUNNER, model="claude-opus-5-5")
    assert t["status"] == "timeout" and t["rewards"] == {}
    r = records.from_kpi({"prompt_id": "kn-produce-UAL-2018Q4", "rep": 1, "status": "refusal", "model": "m",
                          "grade": {"refused": 1.0}, "usage": {}}, runner=RUNNER)
    assert r["status"] == "refusal" and r["rewards"] == {}


def test_every_run_file_has_valid_records():
    committed = sorted((RL / "runs").rglob("*records.jsonl"))
    assert committed, "no committed records"
    for f in committed:
        for i, r in enumerate(records.load([f])):
            assert records.validate(r) == [], f"{f.relative_to(RL)}:{i + 1}"
    # every run file in rl/runs/ has its records (a re-import would stamp old runs with today's
    # instruments, so the committed records are not regenerated here)
    sources = ([f for f in (RL / "runs" / "research_design").glob("*/*.jsonl") if not f.name.endswith("records.jsonl")]
               + [f.parent for f in (RL / "runs" / "kpi_nowcast").glob("*/results.jsonl")]
               + list((RL / "runs" / "solutions").glob("*.csv")))
    for s in sources:
        target = (s / "records.jsonl" if s.is_dir() else
                  s.with_suffix(".records.jsonl"))
        assert target in committed, f"{s.relative_to(RL)} has no records"


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
