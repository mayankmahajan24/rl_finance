"""Reward-hacking suite (rl/harness/attacks.py) on a sample: every attack scores well below a good
answer on one bench task per family and every research_design compare task (eval), and nothing
planted in /tests before the grader's upload survives test.sh."""

from __future__ import annotations

import subprocess

import pytest

import attacks
from conftest import built
from local import harbor


@pytest.mark.slow
def test_attacks_score_well_below_good_answers():
    built("bench", "audit-bench-001")
    built("eval", "rd-funding-S1")
    # every compare task: one random pick scores 0 or 1, so its expected 0.25 needs the whole set
    rows, problems = attacks.run(attacks.select("bench", None, 1) + attacks.select("eval", ["research_design"], None))
    assert {r["family"] for r in rows} == {"data_audit", "anomaly_scoring", "growth_thesis", "kpi_nowcast",
                                           "research_design"}
    assert problems == [], "\n".join(problems)


def test_test_sh_removes_planted_files(tmp_path):
    """Harbor merges tests/ into /tests; test.sh's cleanup keeps only the files the task shipped."""
    task = built("bench", "audit-bench-001")
    t = tmp_path / "tests"
    (t / "reference").mkdir(parents=True)
    for planted in ("json.py", "pandas.py", "reference/x.py", "name with space.py"):
        (t / planted).write_text("raise SystemExit(0)\n")
    shipped = (task / "tests" / "FILES").read_text().split()
    assert sorted(shipped) == sorted(str(p.relative_to(task / "tests")) for p in (task / "tests").rglob("*") if p.is_file())
    for f in shipped:
        (t / f).parent.mkdir(parents=True, exist_ok=True)
        (t / f).write_bytes((task / "tests" / f).read_bytes())
    assert harbor.TEST_CLEANUP in (task / "tests" / "test.sh").read_text()
    subprocess.run(["bash", "-c", harbor.TEST_CLEANUP.replace("/tests", str(t))], check=True)
    assert sorted(str(p.relative_to(t)) for p in t.rglob("*") if p.is_file()) == sorted(shipped)
