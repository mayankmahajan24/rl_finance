"""Calibration (rl/harness/calibrate.py): errored trials are counted but never scored, recommendations
follow the pass rates, separation needs a real gap, and a re-run resumes the job."""

from __future__ import annotations

import sys

from conftest import RL

sys.path.insert(0, str(RL / "harness"))
import calibrate  # noqa: E402


def rec(task, model, reward, status="ok", agent=None):
    return {"family": "data_audit", "task_id": task, "model": model, "status": status,
            "rewards": {} if reward is None else {"reward": reward}, "runner": {"name": "harbor", "agent": agent}}


def test_errors_counted_not_scored():
    rs = [rec("t", "m", 1.0), rec("t", "m", 1.0), rec("t", "m", None, status="error")]
    st = calibrate.report(rs, k=2)["tasks"]["t"]["models"]["m"]
    assert (st["attempts"], st["n"], st["errored"], st["pass_rate"], st["pass@2"]) == (3, 2, 0.333, 1.0, 1.0)


def test_recommendations():
    rs = ([rec("easy", m, 1.0) for m in ("a", "b") for _ in range(3)]
          + [rec("hard", m, 0.0) for m in ("a", "b") for _ in range(3)]
          + [rec("noisy", "a", x) for x in (0.0, 1.0, 0.0, 1.0)] + [rec("noisy", "b", 0.9)]
          + [rec("ok", "a", 0.9), rec("ok", "a", 0.85), rec("ok", "b", 0.1), rec("ok", "b", 0.2)]
          + [rec("broken", "a", 0.9), rec("broken", None, 0.3, agent="reference")])
    got = {t: v["recommendation"] for t, v in calibrate.report(rs, k=2)["tasks"].items()}
    assert got == {"easy": "too_easy", "hard": "too_hard", "noisy": "noisy", "ok": "keep", "broken": "broken"}


def test_separation_needs_a_real_gap():
    strong = [rec(f"t{i}", "strong", 0.9) for i in range(20)] + [rec(f"t{i}", "weak", 0.1) for i in range(20)]
    tied = [rec(f"t{i}", "x", 0.5 + (i % 2) * 0.1) for i in range(20)] + [rec(f"t{i}", "y", 0.6 - (i % 2) * 0.1) for i in range(20)]
    assert calibrate.report(strong, k=1)["separation"][0]["separated"]
    assert not calibrate.report(tied, k=1)["separation"][0]["separated"]


def test_rerun_resumes(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(calibrate, "RL", tmp_path)
    monkeypatch.setattr(calibrate.instrument, "require_approved", lambda f: None)
    monkeypatch.setattr(calibrate.subprocess, "run", lambda cmd, **kw: calls.append(cmd))
    (tmp_path / "tasks" / "bench").mkdir(parents=True)
    calibrate.run("bench", ["m"], 5, "claude-code", "r1", [])
    (tmp_path / "runs" / "calibration" / "bench" / "r1" / "jobs" / "m" / "2026-11-03__10-00-00").mkdir(parents=True)
    calibrate.run("bench", ["m"], 5, "claude-code", "r1", [])
    assert calls[0][3] == "run" and "-k" in calls[0]
    assert calls[1][3:5] == ["job", "resume"] and calls[1][-1].endswith("2026-11-03__10-00-00")
