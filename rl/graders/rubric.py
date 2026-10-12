"""Produce-mode grader: weighted rubric over a structured answer.

Instrumentation FORMAT tasks (earnings_recap, fixed_income) reuse the suite
rubric in `finrl_eval` rather than re-deriving scores. Case-study
research_design produce tasks stay `needs_rubric` until an expert rubric exists.

    reward   weighted criterion aggregate in [0, 1]
             (hard constraint violations cap the aggregate at 0.25)

Called from `rl/run.py` when `task.mode == produce` and `task.status == graded`.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any


def grade(task_dir: pathlib.Path, task: dict, response: Any) -> dict:
    """Score one produce-mode response with the suite rubric named on the task."""
    from finrl_eval.prompts import parse_json_answer
    from finrl_eval.schema import Sample
    from finrl_eval.scorers import ScoreContext
    from finrl_eval.suites import get_suite

    gold = json.loads((task_dir / "grader" / "gold.json").read_text())
    meta = task.get("meta") or {}
    provenance = gold.get("provenance") or {}
    suite_name = meta.get("suite") or provenance.get("suite")
    sample_id = meta.get("sample_id") or provenance.get("sample_id") or task["id"]
    if not suite_name:
        raise ValueError(f"{task['id']}: produce grader needs meta.suite")

    suite = get_suite(suite_name)
    sample = next((s for s in suite.load_samples() if s.id == sample_id), None)
    if sample is None:
        # FORMAT gold is enough to score even if the suite fixture id drifted.
        sample = Sample(
            id=sample_id,
            task=meta.get("task_type") or gold.get("task") or "unknown",
            inputs=json.loads((task_dir / "prompt" / "inputs.json").read_text()),
            expected=gold["expected"],
        )

    if isinstance(response, dict):
        parsed = response
        text = json.dumps(response)
    else:
        text = response if isinstance(response, str) else str(response)
        parsed = parse_json_answer(text)

    outcome = suite.rubric().evaluate(
        ScoreContext(sample=sample, response=text, parsed=parsed)
    )
    return {
        "reward": outcome.score,
        "breakdown": {
            "dimension_scores": outcome.dimension_scores,
            "failed": outcome.failed,
            "hard_violation": outcome.hard_violation,
            "criteria": [c.model_dump() for c in outcome.criteria],
        },
    }
