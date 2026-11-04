"""Verifiers, graded offline: no model calls.

  - Pinned rewards: the reference and naive solvers' rewards on a sample of bench tasks are recorded in
    expected_rewards.json. A change to a generator, verifier or solver that moves any of them fails
    here; if the change is intended, re-record with `UPDATE_EXPECTED=1 pytest rl/tests/test_verifiers.py`
    and commit the file, so the shift shows up in review.
  - Separation: on every planted task the reference beats naive by a clear margin.
  - Bad output: missing, malformed or empty answers score 0 (or near it) and never crash the verifier.
  - kpi_nowcast and research_design compare: hand-written answers graded against the task's gold.
  - One reward scale: every graded task's reward is in [0, 1].
"""

from __future__ import annotations

import json
import os
import pathlib

import pytest

import lib
import run_solutions
from conftest import RL, built, run_verifier
from oracle_check import SAMPLE as ORACLE_SAMPLE, TOL


EXPECTED = pathlib.Path(__file__).with_name("expected_rewards.json")
MARGIN = 0.3       # reference minus naive on planted tasks; the smallest bench gap today is about 0.4

# the oracle's Docker sample plus the rest of the fast families' bench tasks (anomaly_scoring's
# reference takes ~50 s a task, so only the oracle's two), a sample of kpi_nowcast's bench cases and
# research_design's compare tasks (eval)
SAMPLE = (ORACLE_SAMPLE + [f"audit-bench-{i:03d}" for i in range(3, 11)] + ["audit-bench-control-02"]
          + [f"thesis-bench-{i:03d}" for i in range(3, 11)] + ["thesis-bench-control-02"]
          + ["kn-produce-SAVE-2018Q2", "kn-produce-DAL-2018Q4", "kn-produce-M-FY2017Q3", "kn-produce-RET04-FY2018Q1-anon"]
          + ["rd-funding-S1", "rd-funding-S4", "rd-funding-S7"])


@pytest.fixture(scope="module")
def expected():
    exp = json.loads(EXPECTED.read_text()) if EXPECTED.exists() else {}
    yield exp
    if os.environ.get("UPDATE_EXPECTED"):
        EXPECTED.write_text(json.dumps(dict(sorted(exp.items())), indent=1) + "\n")


@pytest.mark.slow
@pytest.mark.parametrize("task_id", SAMPLE)
def test_solver_rewards(task_id, expected, offline):
    task = built("eval" if task_id.startswith("rd-") else "bench", task_id)
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
        "not an object": {"answer.json": "[1, 2]", "memo.md": "memo"},
        "wrong types": {"answer.json": '{"fastest": 3, "growth": [1], "unreliable": 5}', "memo.md": ""},
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
def test_bad_output_scores_zero(task_id, case, offline):
    rewards, details = run_verifier(built("bench", task_id), output=BAD[task_id][case])
    assert rewards["reward"] <= 0.1, details


# a scorer that hides lookahead: it scores like the reference on the full data, but leaves out the last
# day it is given, so a truncated run has unscored rows exactly where future data would show
DROPS_LAST_DAY = ("import argparse, subprocess, sys\nimport pandas as pd\nap = argparse.ArgumentParser()\n"
                  "ap.add_argument('--input')\nap.add_argument('--output')\na = ap.parse_args()\n"
                  "subprocess.run([sys.executable, 'solution/reference_score.py', '--input', a.input, '--output', "
                  "a.output], check=True)\ns = pd.read_csv(a.output)\n"
                  "s[s.date < s.date.max()].to_csv(a.output, index=False)\n")


@pytest.mark.slow
def test_scorer_dropping_truncated_rows_fails_no_foresight(offline):
    task = built("bench", "anomaly-bench-001")
    ref = {f.name: f.read_text() for f in (task / "solution").iterdir() if f.suffix == ".py"}
    rewards, details = run_verifier(task, solution={**ref, "reference_score.py": ref["score.py"],
                                                               "score.py": DROPS_LAST_DAY})
    assert rewards["reward"] == 0 and details["no_foresight"] is False, details


@pytest.mark.parametrize("case", BAD_SCORERS)
def test_bad_scorer_scores_zero(case, offline):
    script = BAD_SCORERS[case]
    rewards, details = run_verifier(built("bench", "anomaly-bench-001"),
                                    solution=None if script is None else {"score.py": script})
    assert rewards["reward"] == 0, details


# ---- kpi_nowcast: forecast accuracy is graded in code ---------------------------------------------

KN = "kn-produce-SAVE-2018Q2"


def kn_answer(gold: dict, point: float, width: float = 0.1) -> str:
    fc = {"target_period": gold["target_period"], "point": point, "low": point * (1 - width),
          "high": point * (1 + width), "interval_level": 0.8, "in_sample": []}
    return f"Write-up.\n\n```json\n{json.dumps(fc)}\n```\n"


def test_kpi_exact_forecast(offline):
    task = built("bench", KN)
    gold = json.loads((task / "tests" / "gold.json").read_text())
    rewards, details = run_verifier(task, output={"answer.md": kn_answer(gold, gold["actual"])})
    assert rewards["schema_ok"] == 1 and rewards["abs_pct_error"] == 0 and rewards["covered"] == 1
    assert rewards["skill_vs_naive"] == 1 and rewards["reward"] == 1
    assert "writeup_score" not in rewards and details["judge"].startswith("not graded")


def test_kpi_bad_forecast(offline):
    task = built("bench", KN)
    gold = json.loads((task / "tests" / "gold.json").read_text())
    rewards, _ = run_verifier(task, output={"answer.md": kn_answer(gold, 2 * gold["actual"])})
    assert rewards["abs_pct_error"] == pytest.approx(1) and rewards["covered"] == 0
    assert rewards["skill_vs_naive"] < 0 and rewards["reward"] == 0


def test_kpi_naive_forecast_earns_nothing(offline):
    task = built("bench", KN)
    gold = json.loads((task / "tests" / "gold.json").read_text())
    rewards, _ = run_verifier(task, output={"answer.md": kn_answer(gold, gold["naive_forecast"])})
    assert rewards["skill_vs_naive"] == 0 and rewards["reward"] == 0


@pytest.mark.parametrize("answer", [None, "no json here", "```json\n{\"point\": 1}\n```",
                                    '```json\n{"target_period": "x", "point": 5, "low": 6, "high": 7, '
                                    '"interval_level": 0.8, "in_sample": []}\n```'])
def test_kpi_invalid_forecast(answer, offline):
    task = built("bench", KN)
    rewards, details = run_verifier(task, output=None if answer is None else {"answer.md": answer})
    assert rewards == {"reward": 0.0, "schema_ok": 0.0}, details


# ---- research_design: compare picks are graded in code; review needs the scorer model ------------

def rd_task(mode: str) -> pathlib.Path:
    for d in sorted((RL / "tasks" / "eval").glob("rd-*")):
        if json.loads((d / "tests" / "grader.json").read_text())["mode"] == mode:
            return d
    pytest.skip(f"no built research_design {mode} task")


def compare_answer(ab: str, ba: str, gold: dict) -> str:
    return json.dumps({o: {"winner": w, "goal_type": gold["goal_type"]} for o, w in (("AB", ab), ("BA", ba))})


def test_compare_pick(offline):
    task = rd_task("compare")
    gold = json.loads((task / "tests" / "gold.json").read_text())
    right = gold["preference"]
    wrong = "B" if right == "A" else "A"
    # (AB pick, BA pick): BA shows the plans swapped, so the gold plan is the other letter there
    cases = [((right, wrong), 1.0), ((wrong, right), 0.0), (("A", "A"), 0.0), (("B", "B"), 0.0)]
    for picks, want in cases:
        rewards, details = run_verifier(task, output={"response.json": compare_answer(*picks, gold)})
        assert rewards["reward"] == want, (picks, details)


@pytest.mark.parametrize("response", ["[]", '{"AB": {"winner": "A"}}', '{"AB": {"winner": "A"}, "BA": "B"}',
                                      '{"AB": {"winner": "C"}, "BA": {"winner": "A"}}'])
def test_compare_malformed_response(response, offline):
    rewards, details = run_verifier(rd_task("compare"), output={"response.json": response})
    assert rewards["reward"] == 0 and "error" in details


def test_compare_missing_response(offline):
    rewards, _ = run_verifier(rd_task("compare"))
    assert rewards["reward"] == 0


@pytest.mark.parametrize("response", ["[]", "{}", '{"issues": "none"}', '{"issues": [1]}'])
def test_review_malformed_response(response, offline):
    rewards, details = run_verifier(rd_task("review"), output={"response.json": response})
    assert rewards["reward"] == 0 and "error" in details


def test_review_without_scorer_is_not_graded(offline):
    rewards, details = run_verifier(rd_task("review"), output={"response.json": '{"issues": []}'})
    assert rewards == {} and details["status"] == "not graded"


def test_every_built_task_is_graded():
    """No task ships without a grader: an ungraded one would hand a lab an empty reward."""
    for d in sorted((RL / "tasks").glob("*/*")):
        if (d / "task.toml").exists():
            assert (d / "tests" / "gold.json").exists() and lib.task_meta(d)["status"] == "graded", d.name
