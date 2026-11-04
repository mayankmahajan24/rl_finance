"""Calibration (rl/harness/calibrate.py): infrastructure errors are counted but never scored, a model's
failures score 0, recommendations follow the pass rates, separation is per family and needs a real
gap, and a re-run resumes the job only with the same arguments."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from conftest import RL

sys.path.insert(0, str(RL / "harness"))
import calibrate  # noqa: E402


def rec(task, model, reward, status="ok", agent=None, family="data_audit"):
    return {"family": family, "task_id": task, "model": model, "status": status,
            "rewards": {} if reward is None else {"reward": reward}, "runner": {"name": "harbor", "agent": agent}}


def test_errors_counted_not_scored():
    rs = [rec("t", "m", 1.0), rec("t", "m", 1.0), rec("t", "m", None, status="error")]
    st = calibrate.report(rs, k=2)["tasks"]["data_audit/t"]["models"]["m"]
    assert (st["attempts"], st["n"], st["errored"], st["pass_rate"], st["pass@2"]) == (3, 2, 0.333, 1.0, 1.0)


@pytest.mark.parametrize("status", ["parse_error", "refusal", "truncated", "timeout"])
def test_model_failures_score_zero(status):
    rs = [rec("t", "m", 1.0), rec("t", "m", None, status=status)]
    st = calibrate.report(rs, k=2)["tasks"]["data_audit/t"]["models"]["m"]
    assert (st["n"], st["mean"], st["pass_rate"], st["best"]) == (2, 0.5, 0.5, 1.0)


def test_tasks_are_keyed_by_family():
    rs = [rec("t", "m", 1.0), rec("t", "m", 0.0, family="growth_thesis")]
    rep = calibrate.report(rs, k=1)
    assert set(rep["tasks"]) == {"data_audit/t", "growth_thesis/t"}
    assert rep["families"]["data_audit"]["ceiling_best_model"] == 1.0


def test_recommendations():
    rs = ([rec("easy", m, 1.0) for m in ("a", "b") for _ in range(3)]
          + [rec("hard", m, 0.0) for m in ("a", "b") for _ in range(3)]
          + [rec("noisy", "a", x) for x in (0.0, 1.0, 0.0, 1.0)] + [rec("noisy", "b", 0.9)]
          + [rec("ok", "a", 0.9), rec("ok", "a", 0.85), rec("ok", "b", 0.1), rec("ok", "b", 0.2)]
          + [rec("broken", "a", 0.9), rec("broken", None, 0.3, agent="reference")])
    got = {v["task_id"]: v["recommendation"] for v in calibrate.report(rs, k=2)["tasks"].values()}
    assert got == {"easy": "too_easy", "hard": "too_hard", "noisy": "noisy", "ok": "keep", "broken": "broken"}


def test_noisy_is_relative_to_the_family():
    """0/1 rewards are all equally noisy: none is flagged when every task's noise is at the floor."""
    rs = [rec(f"t{i}", "a", x) for i in range(5) for x in (0.0, 1.0, 1.0, 0.0)]
    assert {v["recommendation"] for v in calibrate.report(rs, k=2)["tasks"].values()} == {"keep"}


def test_separation_needs_a_real_gap_within_a_family():
    strong = [rec(f"t{i}", "strong", 0.9) for i in range(20)] + [rec(f"t{i}", "weak", 0.1) for i in range(20)]
    tied = [rec(f"t{i}", "x", 0.5 + (i % 2) * 0.1) for i in range(20)] + [rec(f"t{i}", "y", 0.6 - (i % 2) * 0.1) for i in range(20)]
    assert calibrate.report(strong, k=1)["families"]["data_audit"]["separation"][0]["separated"]
    assert not calibrate.report(tied, k=1)["families"]["data_audit"]["separation"][0]["separated"]
    other = [dict(r, family="growth_thesis") for r in tied]
    seps = {f: v["separation"] for f, v in calibrate.report(strong + other, k=1)["families"].items()}
    assert seps["data_audit"][0]["separated"] and not seps["growth_thesis"][0]["separated"]


@pytest.fixture
def harbor(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(calibrate, "RL", tmp_path)
    monkeypatch.setattr(calibrate.local, "tasks", lambda split: [])
    monkeypatch.setattr(calibrate.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or SimpleNamespace(returncode=0))
    return calls


def test_rerun_resumes(tmp_path, harbor):
    calibrate.run("bench", ["m"], 5, "claude-code", "r1", 10.0, [])
    (tmp_path / "runs" / "calibration" / "bench" / "r1" / "jobs" / "m" / "2026-11-03__10-00-00").mkdir(parents=True)
    calibrate.run("bench", ["m"], 5, "claude-code", "r1", 10.0, [])
    assert harbor[0][3] == "run" and "-k" in harbor[0]
    assert harbor[1][3:5] == ["job", "resume"] and harbor[1][-1].endswith("2026-11-03__10-00-00")
    with pytest.raises(SystemExit, match="started with"):
        calibrate.run("bench", ["m"], 3, "claude-code", "r1", 10.0, [])      # other k: refused


def test_harbor_failure_stops_the_run(monkeypatch, harbor):
    monkeypatch.setattr(calibrate.subprocess, "run", lambda cmd, **kw: SimpleNamespace(returncode=1))
    with pytest.raises(SystemExit, match="harbor failed"):
        calibrate.run("bench", ["m"], 5, "claude-code", "r1", 10.0, [])


def test_budget_stops_the_next_model(monkeypatch, harbor):
    imported = iter([[], [{"cost_usd": 6.0, "judge_cost_usd": 4.5}]])        # before m1, after m1
    monkeypatch.setattr(calibrate.records, "import_harbor", lambda jobs, run_id: next(imported))
    monkeypatch.setattr(calibrate.records, "write", lambda path, recs: None)
    with pytest.raises(SystemExit, match="budget"):
        calibrate.run("bench", ["m1", "m2"], 5, "claude-code", "r1", 10.0, [])
    assert len(harbor) == 1 and "m1" in harbor[0]


def test_run_needs_a_budget():
    with pytest.raises(SystemExit):
        calibrate.main(["run", "--model", "m"])
