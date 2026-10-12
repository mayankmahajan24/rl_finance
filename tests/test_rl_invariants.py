"""Invariants for the rl/ FORMAT tree. These sit on top of the finrl_eval suite tests
and must stay green when the case-study rebuild and instrumentation build run."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from finrl_eval.prompts import parse_json_answer
from finrl_eval.suites import get_suite, live_suites

REPO = Path(__file__).resolve().parents[1]
RL = REPO / "rl"
sys.path.insert(0, str(RL))

from graders import rubric  # noqa: E402
from lib import CASE_STUDY_WORKFLOWS, catalog_row, iter_tasks  # noqa: E402

CASE_STUDY_N = 52


def _mirror_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for cls in live_suites().values():
        counts[cls.mirror.workflow] = len(cls().load_samples())
    return counts


def _catalog() -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], json.loads((RL / "catalog.json").read_text()))


def test_catalog_matches_task_tree_and_counts() -> None:
    on_disk = [catalog_row(t) for _, t in iter_tasks()]
    catalog = _catalog()
    assert catalog == on_disk
    mirrors = _mirror_counts()
    assert len(catalog) == CASE_STUDY_N + sum(mirrors.values())
    by_wf = {
        wf: sum(1 for t in catalog if t["workflow"] == wf)
        for wf in {t["workflow"] for t in catalog}
    }
    assert by_wf["research_design"] + by_wf["research_funding"] == CASE_STUDY_N
    for workflow, n in mirrors.items():
        assert by_wf[workflow] == n


def test_case_study_tasks_are_untouched() -> None:
    catalog = _catalog()
    case = [t for t in catalog if t["workflow"] in CASE_STUDY_WORKFLOWS]
    assert len(case) == CASE_STUDY_N
    assert {t["mode"] for t in case} <= {"review", "compare", "produce"}
    produce = [t for t in case if t["mode"] == "produce"]
    assert all(t["status"] == "needs_rubric" for t in produce)
    # Human gold still lives only on graded review/compare case-study tasks.
    graded = [t for t in case if t["status"] == "graded"]
    assert len(graded) == 30


def test_instrumentation_tasks_are_synthetic_produce() -> None:
    for d, t in iter_tasks():
        if t["workflow"] in CASE_STUDY_WORKFLOWS:
            continue
        assert t["mode"] == "produce"
        assert t["status"] == "graded"
        assert t["grader"]["module"] == "graders/rubric.py"
        gold = json.loads((d / "grader" / "gold.json").read_text())
        assert gold["provenance"]["kind"] == "synthetic_pipeline"
        assert gold["provenance"]["suite"] in live_suites()
        assert (d / "prompt" / "system.md").read_text().strip()
        assert (d / "prompt" / "user.md").read_text().strip()
        # Gold expected must not be copied into the model-visible prompt JSON.
        inputs = json.loads((d / "prompt" / "inputs.json").read_text())
        assert "expected" not in inputs


def test_format_builder_reads_mirrors_from_the_registry() -> None:
    src = (REPO / "scripts" / "build_instrumentation_suites.py").read_text()
    assert "SUITE_LAYOUT" not in src
    assert "WORLDS_SPEC" not in src
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
    # The old "wipe worlds and all of roles/" loop is gone.
    assert "for p in (WORLDS, ROLES)" not in src


def test_produce_grader_reuses_suite_rubric() -> None:
    sample = get_suite("earnings").load_samples()[0]
    task_dir = None
    task = None
    for d, t in iter_tasks():
        if t.get("meta", {}).get("sample_id") == sample.id:
            task_dir, task = d, t
            break
    assert task_dir is not None and task is not None
    text = "```json\n" + json.dumps(sample.expected) + "\n```"
    out = rubric.grade(task_dir, task, text)
    assert out["reward"] == 1.0
    assert out["breakdown"]["failed"] == []
    broken = rubric.grade(task_dir, task, "I cannot produce JSON for this filing.")
    assert broken["reward"] <= 0.25
    assert broken["breakdown"]["hard_violation"] is True


def test_produce_grader_accepts_parsed_dict() -> None:
    sample = get_suite("fixed_income").load_samples()[0]
    task_dir = next(d for d, t in iter_tasks() if t.get("meta", {}).get("sample_id") == sample.id)
    task = yaml.safe_load((task_dir / "task.yaml").read_text())
    out = rubric.grade(task_dir, task, sample.expected)
    assert out["reward"] == 1.0
    assert parse_json_answer("```json\n" + json.dumps(sample.expected) + "\n```") == sample.expected


def test_replay_case_study_still_matches_graded_md() -> None:
    proc = subprocess.run(
        [sys.executable, str(RL / "replay_case_study.py")],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ok" in proc.stdout.lower() or "match" in proc.stdout.lower() or proc.returncode == 0
