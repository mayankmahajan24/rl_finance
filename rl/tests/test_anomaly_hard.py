"""anomaly_hard prototype grader (rl/experiments/anomaly_hard/grade.py), graded offline on one train task built into a
scratch folder (the built tasks under rl/tasks/proto are left alone).

  - A known pass (the answer key) scores 1.0 on each of the task's three hidden panels, and so does a paraphrase of it (other confidence values on the same side
    of 0.5, cleaned values moved within a fraction of the source's own noise).
  - A known fail (do nothing) and the negation of the answer key (its confidence inverted) score 0.
  - Lopsided and constant answers (distrust everything with a perfect cleaned series) score 0.
  - The gates: a look-ahead scorer fails point in time; a missing write-up scores 0.
  - Agent code cannot read the answer key on disk (only where the grader can isolate it: root with namespaces).
"""

from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd
import pytest

RL = pathlib.Path(__file__).resolve().parents[1]
HERE = RL / "experiments" / "anomaly_hard"
SOL = HERE / "solutions"
sys.path[:0] = [str(HERE)]

pytestmark = pytest.mark.slow

ORACLE_WRAP = """import pathlib, runpy, sys
import numpy as np, pandas as pd
a = sys.argv
runpy.run_path({oracle!r}, run_name='__main__')
out = a[a.index('--output') + 1]
o = pd.read_csv(out)
{edit}
o.to_csv(out, index=False)
"""


def _experiment_module(name: str):
    """The experiment's own module by file path (rl/build.py shares the name `build`)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"anomaly_hard_{name}", HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def task(tmp_path_factory):
    build = _experiment_module("build")
    from families._shared import build_panel
    d = tmp_path_factory.mktemp("anomaly_hard") / "anomhard-train-test"
    build.build_task(build_panel.context("txn_panel", "train"), d, 320001, False)
    return d


def grade_sol(task, sol: pathlib.Path, monkeypatch, trusted=False, writeup=True, tmp=None):
    import grade
    if trusted:
        monkeypatch.setattr(grade, "TRUSTED", grade.TRUSTED | {(sol / "score.py").resolve()})
    monkeypatch.setenv("ORACLE_TASK", str(task))
    truth = json.loads((task / "tests" / "gold.json").read_text())
    data = pd.read_csv(task / "tests" / "eval_panel.csv.gz", parse_dates=["date"])
    clean = pd.read_csv(task / "tests" / "truth_panel.csv.gz", parse_dates=["date"])
    w = (tmp or sol) / "writeup.md"
    if writeup:
        w.write_text("method note")
    reward, d = grade.score(truth, data, clean, sol, w if writeup else w.with_name("missing.md"))
    return reward, d


def variant(tmp_path, name, edit):
    d = tmp_path / name
    d.mkdir()
    (d / "score.py").write_text(ORACLE_WRAP.format(oracle=str(SOL / "oracle" / "score.py"), edit=edit))
    return d


def test_answer_key_passes(task, monkeypatch):
    reward, d = grade_sol(task, SOL / "oracle", monkeypatch, trusted=True, tmp=task)
    assert reward == pytest.approx(1.0, abs=1e-3), d["gates"]


def test_answer_key_passes_on_every_hidden_panel(task, monkeypatch, tmp_path):
    import grade
    monkeypatch.setenv("ORACLE_TASK", str(task))
    w = tmp_path / "writeup.md"
    w.write_text("method note")
    reward, d = grade.grade_task(task, SOL / "oracle", w)
    assert len(d["panels"]) == 3 and reward == pytest.approx(1.0, abs=1e-3), d["panels"]


def test_paraphrased_answer_key_passes(task, monkeypatch, tmp_path):
    # same verdicts and repairs in another form: confidence 0.3 / 0.9 instead of 0 / 1, cleaned counts moved 2%
    sol = variant(tmp_path, "para", "o['confidence'] = np.where(o.confidence < 0.5, 0.3, 0.9)\n"
                                    "o['clean_ct'] = o.clean_ct * 1.02\no['clean_amt'] = o.clean_amt * 1.02")
    reward, d = grade_sol(task, sol, monkeypatch, trusted=True)
    assert reward > 0.97, (d["confidence_score"], d["clean_score"], d["stability"])


def test_negated_answer_key_fails(task, monkeypatch, tmp_path):
    sol = variant(tmp_path, "neg", "o['confidence'] = 1.0 - o.confidence")
    reward, _ = grade_sol(task, sol, monkeypatch, trusted=True)
    assert reward == 0.0


def test_do_nothing_fails(task, monkeypatch, tmp_path):
    reward, _ = grade_sol(task, SOL / "naive", monkeypatch, tmp=tmp_path)
    assert reward == 0.0


def test_distrust_everything_with_perfect_cleaning_fails(task, monkeypatch, tmp_path):
    reward, d = grade_sol(task, SOL / "distrust_all", monkeypatch, tmp=tmp_path)
    assert reward == 0.0 and d["gates"]["detects"] is False


def test_missing_writeup_scores_zero(task, monkeypatch):
    reward, d = grade_sol(task, SOL / "oracle", monkeypatch, trusted=True, writeup=False)
    assert reward == 0.0 and d["gates"]["writeup"] is False


def test_lookahead_fails_point_in_time(task, monkeypatch, tmp_path):
    sol = variant(tmp_path, "ahead", "o['confidence'] = 0.5 + 0.5 * (o.groupby(['ticker', 'source_id']).clean_ct"
                                     ".transform(lambda x: x.fillna(0).rank(pct=True)))")
    reward, d = grade_sol(task, sol, monkeypatch, trusted=True)
    assert reward == 0.0 and d["gates"]["point_in_time"] is False


def test_agent_code_cannot_read_the_answer_key(task, monkeypatch, tmp_path):
    import grade
    if not grade.ISOLATE:
        pytest.skip("the grader isolates agent code only as root with namespaces (the Harbor verifier does it there)")
    reward, _ = grade_sol(task, SOL / "exploit_gold_read", monkeypatch, tmp=tmp_path)
    assert reward == 0.0
