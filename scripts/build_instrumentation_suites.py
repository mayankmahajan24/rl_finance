"""Materialize finrl_eval suites as FORMAT task folders under rl/roles/.

Does not touch research_design / research_funding (those stay owned by
rl/build_from_case_study.py). Gold is synthetic: provenance.kind is
`synthetic_pipeline` so it is never confused with human case-study labels.

Usage:
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
    ROLES,
    WORLDS,
    fingerprint,
    write_catalog,
    write_json,
    write_yaml,
)

from finrl_eval.suites import SUITES, get_suite  # noqa: E402

# Suite name -> FORMAT role / workflow / world.
SUITE_LAYOUT: dict[str, dict[str, str]] = {
    "earnings": {
        "role": "fundamental_analyst",
        "workflow": "earnings_recap",
        "world": "earnings_desk",
        "abbrev": "er",
    },
    "fixed_income": {
        "role": "quant_researcher",
        "workflow": "fixed_income",
        "world": "rates_desk",
        "abbrev": "fi",
    },
}

WORLDS_SPEC: dict[str, dict[str, str]] = {
    "earnings_desk": {
        "name": "Equity earnings desk",
        "brief": (
            "A long/short equity desk that writes same-day recaps of quarterly "
            "prints for the PM. Tasks here are synthetic press-release recaps, "
            "not live EDGAR filings."
        ),
    },
    "rates_desk": {
        "name": "Rates and credit desk",
        "brief": (
            "A rates/credit desk that prices and risks fixed-coupon bonds from a "
            "terminal feed. Feed rows and issuers are fictional."
        ),
    },
}


def _task_id(abbrev: str, sample_id: str) -> str:
    # Keep the suite sample id if it already carries a stable prefix; otherwise
    # wrap it. Existing sample ids are unique and human-readable.
    if sample_id.startswith(("earn-", "fi-")):
        return sample_id
    return f"{abbrev}-produce-{sample_id}"


def build_worlds() -> None:
    for wid, spec in WORLDS_SPEC.items():
        write_yaml(
            WORLDS / wid / "world.yaml",
            {
                "id": wid,
                "name": spec["name"],
                "kind": "fund",
                "status": "brief_only",
                "brief": spec["brief"],
                "to_become_a_full_world": [
                    "mandate and risk limits",
                    "current holdings with sizes",
                    "point-in-time data snapshot and tool access",
                ],
                "sources": ["scripts/build_instrumentation_suites.py"],
            },
        )


def wipe_instrumentation_workflows() -> None:
    workflows = {layout["workflow"] for layout in SUITE_LAYOUT.values()}
    if not ROLES.exists():
        return
    for role_dir in ROLES.iterdir():
        if not role_dir.is_dir():
            continue
        for wf in workflows:
            target = role_dir / wf
            if target.exists():
                shutil.rmtree(target)


def build_suite(name: str) -> int:
    layout = SUITE_LAYOUT[name]
    suite = get_suite(name)
    engine = suite.prompt_engine()
    n = 0
    for sample in suite.load_samples():
        tid = _task_id(layout["abbrev"], sample.id)
        user = engine.render(sample)
        system = engine.system
        out = ROLES / layout["role"] / layout["workflow"] / tid
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
        write_json(out / "grader" / "rubric.json", suite.rubric().describe())
        template = (
            f"finrl_eval/suites/{name}/templates/default.j2"
            if (suite.template_dir / "default.j2").exists()
            else f"finrl_eval/suites/{name}/templates/{sample.task}.j2"
        )
        task: dict[str, Any] = {
            "id": tid,
            "role": layout["role"],
            "workflow": layout["workflow"],
            "mode": "produce",
            "world": layout["world"],
            "status": "graded",
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
            "grader": {
                "type": "rubric",
                "module": "graders/rubric.py",
            },
            "meta": {
                "suite": name,
                "sample_id": sample.id,
                "task_type": sample.task,
                "tags": sample.tags,
                "difficulty": sample.difficulty,
            },
        }
        write_yaml(out / "task.yaml", task)
        n += 1
    return n


def main() -> None:
    wipe_instrumentation_workflows()
    build_worlds()
    counts: dict[str, int] = {}
    for name in SUITES:
        counts[name] = build_suite(name)
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
