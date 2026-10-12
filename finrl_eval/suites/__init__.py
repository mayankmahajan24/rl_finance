"""Suite registry.

Add a runnable workflow by importing its TaskSuite subclass and appending
one Live line to _ENTRIES. A planned name is a Planned line: name and blurb
only. live_suites() and planned() are readers. Do not keep a second list.
"""

from __future__ import annotations

from dataclasses import dataclass

from finrl_eval.schema import FormatMirror
from finrl_eval.suites.base import TaskSuite
from finrl_eval.suites.earnings.suite import EarningsSuite
from finrl_eval.suites.fixed_income.suite import FixedIncomeSuite

_RESERVED = frozenset({"valid_json", "no_hedging", "concise"})


@dataclass(frozen=True, slots=True)
class Live:
    """A runnable suite. The name is suite.spec.name."""

    suite: type[TaskSuite]


@dataclass(frozen=True, slots=True)
class Planned:
    """A named extension point. No tasks, fixtures, scorers, or formulas."""

    name: str
    blurb: str


Entry = Live | Planned


def _validate(entries: tuple[Entry, ...]) -> tuple[Entry, ...]:
    """Reject a bad registry at import. Do not load fixtures."""
    live_names: list[str] = []
    planned_names: list[str] = []
    workflows: list[str] = []
    worlds: dict[str, tuple[str, str]] = {}
    for entry in entries:
        if isinstance(entry, Planned):
            if not entry.name.strip() or not entry.blurb.strip():
                raise ValueError("a planned entry needs a name and a blurb")
            planned_names.append(entry.name)
            continue
        if not isinstance(entry.suite, type) or not issubclass(entry.suite, TaskSuite):
            raise TypeError(f"{entry!r} is not a TaskSuite class")
        spec = entry.suite.spec
        mirror = getattr(entry.suite, "mirror", None)
        if not isinstance(mirror, FormatMirror):
            raise TypeError(f"{spec.name} needs a FormatMirror on the class")
        live_names.append(spec.name)
        workflows.append(mirror.workflow)
        brief = (mirror.world_name, mirror.world_brief)
        previous = worlds.get(mirror.world)
        if previous is not None and previous != brief:
            raise ValueError(f"{spec.name}: world {mirror.world} brief disagrees")
        worlds[mirror.world] = brief
        reserved = _RESERVED | {f"fields_{task}" for task in spec.tasks}
        allowed = set(spec.tasks)
        for criterion in entry.suite().domain_criteria():
            if criterion.name in reserved or criterion.name.startswith("fields_"):
                raise ValueError(
                    f"{spec.name}: {criterion.name} is reserved for answer constraints"
                )
            if criterion.tasks is not None and not set(criterion.tasks) <= allowed:
                raise ValueError(f"{spec.name}: {criterion.name} names an unknown task")
    if len(live_names) != len(set(live_names)):
        raise ValueError(f"duplicate live suite name in {live_names}")
    if len(planned_names) != len(set(planned_names)):
        raise ValueError(f"duplicate planned suite name in {planned_names}")
    overlap = set(live_names) & set(planned_names)
    if overlap:
        raise ValueError(f"suite listed as both live and planned: {sorted(overlap)}")
    if len(workflows) != len(set(workflows)):
        raise ValueError(f"duplicate FORMAT workflow in {workflows}")
    return entries


_ENTRIES: tuple[Entry, ...] = _validate(
    (
        Live(EarningsSuite),
        Live(FixedIncomeSuite),
        Planned(
            "quant_signal",
            "Quantitative Signal Research (planned; see finrl_eval/suites/quant_signal)",
        ),
        Planned(
            "dataset_valuation",
            "Dataset Valuation & Analysis (planned; see finrl_eval/suites/dataset_valuation)",
        ),
    )
)


def registry() -> tuple[Entry, ...]:
    """Membership tuple. Callers cannot append to it."""
    return _ENTRIES


def live_suites() -> dict[str, type[TaskSuite]]:
    """Live classes in registry order. A new dict each call."""
    return {entry.suite.spec.name: entry.suite for entry in registry() if isinstance(entry, Live)}


def planned() -> dict[str, str]:
    """Planned name to blurb, in registry order. A new dict each call."""
    return {entry.name: entry.blurb for entry in registry() if isinstance(entry, Planned)}


def get_suite(name: str) -> TaskSuite:
    suites = live_suites()
    try:
        return suites[name]()
    except KeyError as exc:
        hint = " (planned, not implemented yet)" if name in planned() else ""
        raise KeyError(f"Unknown suite {name!r}{hint}. Available: {sorted(suites)}") from exc


__all__ = [
    "Entry",
    "Live",
    "Planned",
    "TaskSuite",
    "get_suite",
    "live_suites",
    "planned",
    "registry",
]
