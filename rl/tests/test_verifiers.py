"""Verifiers, graded offline: no model calls.

  - Pinned rewards: the reference and naive solvers' rewards on a sample of bench tasks are recorded in
    expected_rewards.json. A change to a generator, verifier or solver that moves any of them fails
    here; if the change is intended, re-record with `UPDATE_EXPECTED=1 pytest rl/tests/test_verifiers.py`
    and commit the file, so the shift shows up in review.
  - Separation: on every planted task the reference beats naive by a clear margin.
  - Bad output: missing, malformed or empty answers score 0 (or near it) and never crash the verifier.
  - kpi_nowcast and research_design compare: hand-written answers graded against the task's gold.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

import pytest

from conftest import RL, built, run_verifier

sys.path.insert(0, str(RL / "harness"))
import run_solutions  # noqa: E402

EXPECTED = pathlib.Path(__file__).with_name("expected_rewards.json")
TOL = 0.002
MARGIN = 0.3       # reference minus naive on planted tasks; the smallest bench gap today is about 0.4

# every bench task of the fast families; anomaly_scoring's reference takes ~50 s a task, so two of its
SAMPLE = ([f"audit-bench-{i:03d}" for i in range(1, 11)] + ["audit-bench-control-01", "audit-bench-control-02"]
          + [f"thesis-bench-{i:03d}" for i in range(1, 11)] + ["thesis-bench-control-01", "thesis-bench-control-02"]
          + ["anomaly-bench-001", "anomaly-bench-control-01"])


@pytest.fixture(scope="module")
def expected():
    exp = json.loads(EXPECTED.read_text()) if EXPECTED.exists() else {}
    yield exp
    if os.environ.get("UPDATE_EXPECTED"):
        EXPECTED.write_text(json.dumps(dict(sorted(exp.items())), indent=1) + "\n")


@pytest.mark.slow
@pytest.mark.parametrize("task_id", SAMPLE)
def test_solver_rewards(task_id, expected, offline):
    task = built("bench", task_id)
    got = {s: run_solutions.run_one(str(task), s) for s in ("reference", "naive")}
    for s, r in got.items():
        assert "note" not in r, f"{s}: {r['note']}"
    rewards = {s: r["reward"] for s, r in got.items()}
    if os.environ.get("UPDATE_EXPECTED"):
        expected[task_id] = rewards
        return
    assert task_id in expected, "no recorded rewards: run with UPDATE_EXPECTED=1"
    for s in rewards:
        assert rewards[s] == pytest.approx(expected[task_id][s], abs=TOL), \
            f"{s} reward moved: {expected[task_id][s]} -> {rewards[s]}"
    if "control" not in task_id:
        assert rewards["reference"] - rewards["naive"] >= MARGIN, rewards


# ---- bad output scores nothing ----------------------------------------------------------------

BAD = {
    "audit-bench-001": {
        "missing": {}, "not json": {"issues.json": "not json"}, "not a list": {"issues.json": '{"a": 1}'},
        "junk items": {"issues.json": '[{"foo": 1}, 3, "x"]'}, "empty list": {"issues.json": "[]"},
    },
    "thesis-bench-001": {
        "missing": {}, "not json": {"answer.json": "not json", "memo.md": "memo"},
        "wrong keys": {"answer.json": '{"foo": 1}', "memo.md": ""},
    },
}
BAD_SCORERS = {      # anomaly_scoring grades a scorer script the agent leaves in /app/solution
    "missing": None,
    "crashes": "raise SystemExit(1)\n",
    "writes nothing": "pass\n",
    "copies the input": ("import argparse, shutil\nap = argparse.ArgumentParser()\nap.add_argument('--input')\n"
                         "ap.add_argument('--output')\na = ap.parse_args()\nshutil.copy(a.input, a.output)\n"),
}


@pytest.mark.parametrize("task_id,case", [(t, c) for t, cases in BAD.items() for c in cases])
def test_bad_output_scores_zero(task_id, case, tmp_path, offline):
    rewards, details = run_verifier(built("bench", task_id), tmp_path, output=BAD[task_id][case])
    assert rewards["reward"] <= 0.1, details


@pytest.mark.parametrize("case", BAD_SCORERS)
def test_bad_scorer_scores_zero(case, tmp_path, offline):
    script = BAD_SCORERS[case]
    rewards, details = run_verifier(built("bench", "anomaly-bench-001"), tmp_path,
                                    solution=None if script is None else {"score.py": script})
    assert rewards["reward"] == 0, details


# ---- kpi_nowcast: forecast accuracy is graded in code ---------------------------------------------

KN = "kn-produce-SAVE-2018Q2"


def kn_answer(gold: dict, point: float, width: float = 0.1) -> str:
    fc = {"target_period": gold["target_period"], "point": point, "low": point * (1 - width),
          "high": point * (1 + width), "interval_level": 0.8, "in_sample": []}
    return f"Write-up.\n\n```json\n{json.dumps(fc)}\n```\n"


def test_kpi_exact_forecast(tmp_path, offline):
    task = built("bench", KN)
    gold = json.loads((task / "tests" / "gold.json").read_text())
    rewards, details = run_verifier(task, tmp_path, output={"answer.md": kn_answer(gold, gold["actual"])})
    assert rewards["schema_ok"] == 1 and rewards["abs_pct_error"] == 0 and rewards["covered"] == 1
    assert rewards["skill_vs_naive"] == 1
    assert "writeup_score" not in rewards and details["judge"].startswith("not graded")


def test_kpi_bad_forecast(tmp_path, offline):
    task = built("bench", KN)
    gold = json.loads((task / "tests" / "gold.json").read_text())
    rewards, _ = run_verifier(task, tmp_path, output={"answer.md": kn_answer(gold, 2 * gold["actual"])})
    assert rewards["abs_pct_error"] == pytest.approx(1) and rewards["covered"] == 0
    assert rewards["skill_vs_naive"] < 0


@pytest.mark.parametrize("answer", [None, "no json here", "```json\n{\"point\": 1}\n```",
                                    '```json\n{"target_period": "x", "point": 5, "low": 6, "high": 7, '
                                    '"interval_level": 0.8, "in_sample": []}\n```'])
def test_kpi_invalid_forecast(answer, tmp_path, offline):
    task = built("bench", KN)
    rewards, details = run_verifier(task, tmp_path, output=None if answer is None else {"answer.md": answer})
    assert rewards == {"schema_ok": 0.0}, details


# ---- research_design: compare picks are graded in code; review needs the scorer model ------------

def rd_task(mode: str) -> pathlib.Path:
    for d in sorted((RL / "tasks" / "eval").glob("rd-*")):
        if json.loads((d / "tests" / "grader.json").read_text())["mode"] == mode:
            return d
    pytest.skip(f"no built research_design {mode} task")


def test_compare_pick(tmp_path, offline):
    task = rd_task("compare")
    gold = json.loads((task / "tests" / "gold.json").read_text())
    for pick, want in ((gold["preference"], 1.0), ("B" if gold["preference"] == "A" else "A", 0.0)):
        resp = {"winner": pick, "goal_type": gold["goal_type"], "error_asymmetry": gold["error_asymmetry"]}
        rewards, _ = run_verifier(task, tmp_path / pick, output={"response.json": json.dumps(resp)})
        assert rewards["reward"] == want


def test_compare_missing_response(tmp_path, offline):
    rewards, _ = run_verifier(rd_task("compare"), tmp_path)
    assert rewards["reward"] == 0


def test_review_without_scorer_is_not_graded(tmp_path, offline):
    rewards, details = run_verifier(rd_task("review"), tmp_path, output={"response.json": "{}"})
    assert rewards == {} and details["status"] == "not graded"


def test_no_grader_yet(tmp_path, offline):
    task = rd_task(None)          # no gold yet (ungraded) or no rubric yet (needs_rubric)
    rewards, details = run_verifier(task, tmp_path)
    assert rewards == {} and details["status"] == json.loads((task / "tests" / "grader.json").read_text())["status"]
