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

import http.server
import importlib
import json
import os
import pathlib
import sys
import threading

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


def kn_answer(gold: dict, point: float, width: float = 0.1, history: bool = True) -> str:
    fc = {"target_period": gold["target_period"], "point": point, "low": point * (1 - width),
          "high": point * (1 + width), "interval_level": 0.95, "in_sample": [],
          "metric_history": [{"period_end": e, "value": v[-1]} for e, v in gold["metric_history"].items()] if history else []}
    return f"Write-up.\n\n```json\n{json.dumps(fc)}\n```\n"


def test_kpi_exact_forecast(offline):
    task = built("bench", KN)
    gold = json.loads((task / "tests" / "gold.json").read_text())
    rewards, details = run_verifier(task, output={"answer.md": kn_answer(gold, gold["actual"])})
    assert rewards["schema_ok"] == 1 and rewards["abs_pct_error"] == 0 and rewards["covered"] == 1
    assert rewards["metric_ok"] == 1 and rewards["skill_vs_naive"] == 1 and rewards["reward"] == 1
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


def test_kpi_writeup_scales_reward():
    from families.kpi_nowcast import grader as G
    assert G.blend({"accuracy_reward": 0.6, "writeup_score": 1.0})["reward"] == 0.6
    assert G.blend({"accuracy_reward": 0.6, "writeup_score": 0.0})["reward"] == 0.3
    assert G.blend({"accuracy_reward": 0.0, "writeup_score": 1.0})["reward"] == 0.0
    assert G.blend({"reward": 0.6, "accuracy_reward": 0.6})["reward"] == 0.6   # not judged: accuracy alone


def test_kpi_wrong_metric_earns_nothing(offline):
    task = built("bench", KN)
    gold = json.loads((task / "tests" / "gold.json").read_text())
    rewards, _ = run_verifier(task, output={"answer.md": kn_answer(gold, gold["actual"], history=False)})
    assert rewards["metric_ok"] == 0 and rewards["abs_pct_error"] == 0 and rewards["reward"] == 0


@pytest.mark.parametrize("answer", [None, "no json here", "```json\n{\"point\": 1}\n```",
                                    '```json\n{"target_period": "x", "point": 5, "low": 6, "high": 7, '
                                    '"interval_level": 0.95, "in_sample": []}\n```',
                                    '```json\n{"target_period": "x", "point": 5, "low": 4, "high": 6, '
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


@pytest.fixture
def rejecting_api(monkeypatch):
    """A local API that refuses every request with a 400, the way a key with no credit does."""
    class Reject(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("content-length", 0)))
            body = b'{"type": "error", "error": {"type": "invalid_request_error", "message": "credit balance too low"}}'
            self.send_response(400)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Reject)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.delenv("JUDGE", raising=False)
    yield
    server.shutdown()


REVIEW_ANSWER = json.dumps({"issues": [{"title": "t", "description": "d"}]})
THESIS_ANSWER = json.dumps({"fastest": "X", "growth": {}, "unreliable": []})


def test_rejected_judge_request_keeps_kpi_reward(rejecting_api):
    task = built("bench", KN)
    gold = json.loads((task / "tests" / "gold.json").read_text())
    rewards, details = run_verifier(task, output={"answer.md": kn_answer(gold, gold["actual"])})
    assert rewards["reward"] == 1 and "writeup_score" not in rewards
    assert details["judge"].startswith("not graded") and "credit balance" in details["judge"]


def test_rejected_judge_request_is_not_graded_on_thesis(rejecting_api):
    rewards, details = run_verifier(built("bench", "thesis-bench-001"),
                                    output={"answer.json": THESIS_ANSWER, "memo.md": "A memo."})
    assert rewards == {} and details["status"] == "not graded" and "credit balance" in details["note"]


def test_rejected_judge_request_is_not_graded_on_review(rejecting_api):
    rewards, details = run_verifier(rd_task("review"), output={"response.json": REVIEW_ANSWER})
    assert rewards == {} and details["status"] == "not graded" and "credit balance" in details["note"]


def test_every_built_task_is_graded():
    """No task ships without a grader: an ungraded one would hand a lab an empty reward."""
    for d in sorted((RL / "tasks").glob("*/*")):
        if (d / "task.toml").exists():
            assert (d / "tests" / "gold.json").exists() and lib.task_meta(d)["status"] == "graded", d.name


ANOMALY_CHEAT = """import argparse, json, pathlib
import pandas as pd
a = argparse.ArgumentParser(); a.add_argument('--input'); a.add_argument('--output'); x = a.parse_args()
df = pd.read_csv(x.input)[['date', 'ticker', 'source_id']]
gold = pathlib.Path.cwd().parent / 'tests' / 'gold.json'
df['anomaly_score'] = 0.0
if gold.exists():
    t = json.loads(gold.read_text())
    for p in t['points']:
        df.loc[(df.ticker == p['ticker']) & (df.source_id == p['source_id']) & (df.date == p['date']), 'anomaly_score'] = 1.0
df.to_csv(x.output, index=False)
"""
ANOMALY_REPLAY = """import argparse, pathlib
import pandas as pd
a = argparse.ArgumentParser(); a.add_argument('--input'); a.add_argument('--output'); x = a.parse_args()
df = pd.read_csv(x.input)
seen = pathlib.Path.cwd().parent / 'seen.csv'
if seen.exists() and len(pd.read_csv(seen)) > len(df):
    df = pd.read_csv(seen)
df.to_csv(seen, index=False)
df['anomaly_score'] = float(df.ct.mean() > 100) * 0.0 + len(df) % 97 / 97
df[['date', 'ticker', 'source_id', 'anomaly_score']].to_csv(x.output, index=False)
"""


def test_anomaly_scorer_cannot_read_the_gold_or_replay_the_future():
    task = built("bench", "anomaly-bench-001")
    assert not (task / "environment" / "data" / "eval_panel.csv.gz").exists()
    rewards, details = run_verifier(task, solution={"score.py": ANOMALY_CHEAT})
    assert rewards["reward"] == 0 and details["tp"] == 0
    rewards, details = run_verifier(task, solution={"score.py": ANOMALY_REPLAY})
    assert details["no_foresight"] is False and rewards["reward"] == 0


# ---- write-ups (a separate metric: the reward never depends on them) ------------------------------

def writeup_module(monkeypatch, tmp_path):
    task = built("bench", "audit-bench-001")
    monkeypatch.syspath_prepend(str(task / "tests"))
    monkeypatch.setenv("TESTS_DIR", str(task / "tests"))
    monkeypatch.setenv("LOGS_DIR", str(tmp_path / "logs"))
    for m in ("common", "judge", "writeup", "client"):
        sys.modules.pop(m, None)
    return importlib.import_module("writeup")


def test_audit_reward_ignores_the_write_up(offline):
    task = built("bench", "audit-bench-001")
    ref, naive = (run_solutions.run_one(str(task), s) for s in ("reference", "naive"))
    assert "writeup_score" not in ref["rewards"]          # written, but no judge here to grade it
    assert naive["rewards"]["writeup_score"] == 0.0       # nothing written: no judge needed
    assert ref["reward"] > naive["reward"]


def test_write_up_score_counts_applicable_items(monkeypatch, tmp_path):
    w = writeup_module(monkeypatch, tmp_path)
    monkeypatch.setattr(w.judge, "unavailable", lambda: None)
    items = {f"W{i}": {"verdict": "pass", "reason": "x"} for i in range(1, 10)}
    items |= {"W2": {"verdict": "fail", "reason": "x"}, "W3": {"verdict": "na", "reason": "x"}}
    monkeypatch.setattr(w.judge, "judge", lambda *a, **k: ([items], {}))
    metrics, _ = w.grade("A note.", {}, {})
    assert metrics["writeup_score"] == 0.875 and metrics["w_W2"] == 0.0 and "w_W3" not in metrics


def test_failed_judge_leaves_the_write_up_ungraded(monkeypatch, tmp_path):
    w = writeup_module(monkeypatch, tmp_path)
    monkeypatch.setattr(w.judge, "unavailable", lambda: None)

    def fail(*a, **k):
        raise w.judge.JudgeError("down")
    monkeypatch.setattr(w.judge, "judge", fail)
    metrics, why = w.grade("A note.", {}, {})
    assert metrics == {} and why.startswith("not graded")
