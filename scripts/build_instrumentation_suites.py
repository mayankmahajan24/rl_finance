"""Materialize finrl_eval suites as FORMAT task folders under rl/roles/.

Does not touch research_design / research_funding (those stay owned by
rl/build_from_case_study.py). Gold is synthetic: provenance.kind is
`synthetic_pipeline` so it is never confused with human case-study labels.
Written tasks stay `needs_rubric` and do not name a grader module.

Placement is each live suite's FormatMirror. Usage:

    python scripts/build_instrumentation_suites.py
"""

from __future__ import annotations

import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "rl"))

from lib import (  # noqa: E402
    CASE_STUDY_WORKFLOWS,
    ROLES,
    WORLDS,
    fingerprint,
    write_catalog,
    write_json,
    write_yaml,
)

from finrl_eval.schema import FormatMirror  # noqa: E402
from finrl_eval.suites import live_suites  # noqa: E402
from finrl_eval.suites.base import TaskSuite  # noqa: E402


def _task_id(mirror: FormatMirror, sample_id: str) -> str:
    if sample_id.startswith(mirror.id_prefix):
        return sample_id
    return f"{mirror.abbrev}-produce-{sample_id}"


def _write_world(mirror: FormatMirror) -> None:
    write_yaml(
        WORLDS / mirror.world / "world.yaml",
        {
            "id": mirror.world,
            "name": mirror.world_name,
            "kind": "fund",
            "status": "brief_only",
            "brief": mirror.world_brief,
            "to_become_a_full_world": [
                "mandate and risk limits",
                "current holdings with sizes",
                "point-in-time data snapshot and tool access",
            ],
            "sources": ["scripts/build_instrumentation_suites.py"],
        },
    )


def _write_tasks(suite: TaskSuite, samples: list[Any]) -> set[str]:
    mirror = suite.mirror
    name = suite.spec.name
    engine = suite.prompt_engine()
    written: set[str] = set()
    for sample in samples:
        tid = _task_id(mirror, sample.id)
        user = engine.render(sample)
        system = engine.system
        out = ROLES / mirror.role / mirror.workflow / tid
        (out / "prompt").mkdir(parents=True, exist_ok=True)
        (out / "prompt" / "system.md").write_text(system.rstrip() + "\n")
        (out / "prompt" / "user.md").write_text(user if user.endswith("\n") else user + "\n")
        write_json(out / "prompt" / "inputs.json", sample.inputs)
        write_json(
            out / "grader" / "gold.json",
            {
                "expected": sample.expected,
                "task": sample.task,
                "tags": sample.tags,
                "difficulty": sample.difficulty,
                "provenance": {
                    "kind": "synthetic_pipeline",
                    "labeller": "synthetic (not human)",
                    "generator": "scripts/build_instrumentation_suites.py",
                    "suite": name,
                    "sample_id": sample.id,
                    "suite_version": suite.spec.version,
                },
            },
        )
        template = (
            f"finrl_eval/suites/{name}/templates/default.j2"
            if (suite.template_dir / "default.j2").exists()
            else f"finrl_eval/suites/{name}/templates/{sample.task}.j2"
        )
        task: dict[str, Any] = {
            "id": tid,
            "role": mirror.role,
            "workflow": mirror.workflow,
            "mode": "produce",
            "world": mirror.world,
            "status": "needs_rubric",
            "split": "eval",
            "prompt": {
                "template": template,
                "fingerprint": fingerprint(system, user),
            },
            "sources": [
                f"finrl_eval/suites/{name}/",
                "scripts/build_instrumentation_suites.py",
            ],
            "output_schema": None,
            "meta": {
                "suite": name,
                "sample_id": sample.id,
                "task_type": sample.task,
                "tags": sample.tags,
                "difficulty": sample.difficulty,
            },
        }
        write_yaml(out / "task.yaml", task)
        written.add(tid)
    return written


def _prune(written: dict[tuple[str, str], set[str]], protected: frozenset[str]) -> None:
    """Drop stale task dirs after a successful write. Protected names stay."""
    if not ROLES.exists():
        return
    for role_dir in ROLES.iterdir():
        if not role_dir.is_dir():
            continue
        for (owner_role, workflow), ids in written.items():
            if workflow in protected:
                continue
            target = role_dir / workflow
            if not target.exists():
                continue
            if role_dir.name != owner_role:
                shutil.rmtree(target)
                continue
            for child in target.iterdir():
                if child.is_dir() and child.name not in ids:
                    shutil.rmtree(child)


def materialize(*, protected: frozenset[str]) -> dict[str, int]:
    """Write FORMAT trees for every live suite. Return suite name to sample count.

    Loads every suite before deleting anything. A workflow in `protected`
    or a suite with no samples aborts with the previous tree left in place.
    A second successful call writes the same bytes.
    """
    loaded: list[tuple[TaskSuite, list[Any]]] = []
    for cls in live_suites().values():
        suite = cls()
        workflow = suite.mirror.workflow
        if workflow in protected:
            raise SystemExit(
                f"{suite.spec.name}: workflow {workflow} is owned by the case-study rebuild"
            )
        samples = suite.load_samples()
        if not samples:
            raise SystemExit(f"{suite.spec.name}: no samples")
        loaded.append((suite, samples))

    written: dict[tuple[str, str], set[str]] = {}
    counts: dict[str, int] = {}
    worlds_written: set[str] = set()
    for suite, samples in loaded:
        mirror = suite.mirror
        if mirror.world not in worlds_written:
            _write_world(mirror)
            worlds_written.add(mirror.world)
        ids = _write_tasks(suite, samples)
        counts[suite.spec.name] = len(ids)
        written.setdefault((mirror.role, mirror.workflow), set()).update(ids)
    _prune(written, protected)
    return counts


def main() -> None:
    counts = materialize(protected=frozenset(CASE_STUDY_WORKFLOWS))
    catalog = write_catalog()
    print(
        f"instrumentation: {sum(counts.values())} FORMAT tasks "
        f"({', '.join(f'{k}={v}' for k, v in counts.items())}); "
        f"catalog now {len(catalog)}"
    )
    for (role, wf, mode, st), n in sorted(
        Counter((t["role"], t["workflow"], t["mode"], t["status"]) for t in catalog).items()
    ):
        print(f"  {role:<20}{wf:<18}{mode:<9}{st:<14}{n:>3}")


if __name__ == "__main__":
    main()
