"""Registry, fixtures, and FORMAT mirrors before any scorer exists."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from finrl_eval.cli import app
from finrl_eval.suites import get_suite, live_suites, planned

REPO = Path(__file__).resolve().parents[1]
RL = REPO / "rl"
sys.path.insert(0, str(RL))

from lib import CASE_STUDY_WORKFLOWS, catalog_row, iter_tasks  # noqa: E402

CASE_STUDY_N = 52


def _catalog() -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], json.loads((RL / "catalog.json").read_text()))


@pytest.mark.parametrize("suite_name", sorted(live_suites()))
def test_samples_render_without_leaking_gold(suite_name: str) -> None:
    suite = get_suite(suite_name)
    samples = suite.load_samples()
    assert samples
    assert len({s.id for s in samples}) == len(samples)
    engine = suite.prompt_engine()
    for sample in samples:
        assert sample.task in suite.spec.tasks
        assert sample.expected
        prompt = engine.render(sample)
        for field in sample.inputs["answer_fields"]:
            assert field in prompt
        assert "expected" not in sample.inputs


def test_planned_names_are_not_runnable() -> None:
    assert set(planned()) == {"quant_signal", "dataset_valuation"}
    assert set(live_suites()) == {"earnings", "fixed_income"}
    with pytest.raises(KeyError, match="planned, not implemented yet"):
        get_suite("quant_signal")
    with pytest.raises(KeyError, match="planned, not implemented yet"):
        get_suite("dataset_valuation")


def test_cli_lists_suites_and_runnable_names() -> None:
    runner = CliRunner()
    listed = runner.invoke(app, ["list", "--json"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    assert {s["name"] for s in payload["suites"]} == set(live_suites())
    assert payload["planned"] == planned()
    for cls in live_suites().values():
        assert payload["format_mirrors"][cls.mirror.workflow] == len(cls().load_samples())
    names = runner.invoke(app, ["runnable"])
    assert names.exit_code == 0, names.output
    assert names.output.splitlines() == list(live_suites())


def test_earnings_fixture_is_not_stale() -> None:
    spec = importlib.util.spec_from_file_location(
        "gen", REPO / "scripts" / "generate_earnings_fixtures.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["gen"] = module
    spec.loader.exec_module(module)
    checked_in = (REPO / "finrl_eval/suites/earnings/fixtures/earnings.json").read_text()
    assert module.render() == checked_in, "run scripts/generate_earnings_fixtures.py"


def test_catalog_matches_task_tree_and_counts() -> None:
    on_disk = [catalog_row(t) for _, t in iter_tasks()]
    catalog = _catalog()
    assert catalog == on_disk
    mirrors = {cls.mirror.workflow: len(cls().load_samples()) for cls in live_suites().values()}
    assert len(catalog) == CASE_STUDY_N + sum(mirrors.values())
    by_wf = {
        wf: sum(1 for t in catalog if t["workflow"] == wf)
        for wf in {t["workflow"] for t in catalog}
    }
    assert by_wf["research_design"] + by_wf["research_funding"] == CASE_STUDY_N
    for workflow, n in mirrors.items():
        assert by_wf[workflow] == n


def test_case_study_produce_stays_needs_rubric() -> None:
    catalog = _catalog()
    case = [t for t in catalog if t["workflow"] in CASE_STUDY_WORKFLOWS]
    assert len(case) == CASE_STUDY_N
    produce = [t for t in case if t["mode"] == "produce"]
    assert len(produce) == 10
    assert all(t["status"] == "needs_rubric" for t in produce)
    graded = [t for t in case if t["status"] == "graded"]
    assert len(graded) == 30


def test_instrumentation_tasks_are_graded_synthetic_produce() -> None:
    seen = 0
    for task_dir, task in iter_tasks():
        if task["workflow"] in CASE_STUDY_WORKFLOWS:
            continue
        seen += 1
        assert task["mode"] == "produce"
        assert task["status"] == "graded"
        assert task["grader"]["module"] == "graders/rubric.py"
        gold = json.loads((task_dir / "grader" / "gold.json").read_text())
        assert gold["provenance"]["kind"] == "synthetic_pipeline"
        assert gold["provenance"]["suite"] in live_suites()
        assert (task_dir / "grader" / "rubric.json").exists()
        inputs = json.loads((task_dir / "prompt" / "inputs.json").read_text())
        assert "expected" not in inputs
        assert (task_dir / "prompt" / "user.md").read_text().strip()
    assert seen == sum(len(cls().load_samples()) for cls in live_suites().values())


def test_format_builder_reads_mirrors_from_the_registry() -> None:
    src = (REPO / "scripts" / "build_instrumentation_suites.py").read_text()
    assert "SUITE_LAYOUT" not in src
    assert "WORLDS_SPEC" not in src
    assert "graders/rubric.py" in src
    registry = (REPO / "finrl_eval" / "suites" / "__init__.py").read_text()
    assert "_ENTRIES" in registry
    spec = importlib.util.spec_from_file_location(
        "build_instrumentation_suites", REPO / "scripts" / "build_instrumentation_suites.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(SystemExit, match="case-study"):
        module.materialize(protected=frozenset({"earnings_recap"}))


def test_build_from_case_study_does_not_wipe_other_workflows() -> None:
    src = (RL / "build_from_case_study.py").read_text()
    assert "wipe_case_study_workflows" in src
    assert "CASE_STUDY_WORKFLOWS" in src
    assert "for p in (WORLDS, ROLES)" not in src


def test_replay_case_study_still_matches_graded_md() -> None:
    proc = subprocess.run(
        [sys.executable, str(RL / "replay_case_study.py")],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_produce_hook_uses_the_suite_grader() -> None:
    assert (RL / "graders" / "rubric.py").exists()
    run_py = (RL / "run.py").read_text()
    assert "rubric.grade" in run_py
    assert "rl/run.py" not in (REPO / "finrl_eval" / "runner.py").read_text()
