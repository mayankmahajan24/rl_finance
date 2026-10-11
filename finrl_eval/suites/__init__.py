"""Suite registry. Add a suite by importing its class here and adding it to SUITES.

Planned suites (not yet implemented, see their README.md):
- quant_signal: Quantitative Signal Research
- dataset_valuation: Dataset Valuation & Analysis
"""

from __future__ import annotations

from finrl_eval.suites.base import TaskSuite
from finrl_eval.suites.earnings.suite import EarningsSuite
from finrl_eval.suites.fixed_income.suite import FixedIncomeSuite

SUITES: dict[str, type[TaskSuite]] = {
    EarningsSuite.spec.name: EarningsSuite,
    FixedIncomeSuite.spec.name: FixedIncomeSuite,
}

PLANNED_SUITES: dict[str, str] = {
    "quant_signal": "Quantitative Signal Research (planned; see finrl_eval/suites/quant_signal)",
    "dataset_valuation": (
        "Dataset Valuation & Analysis (planned; see finrl_eval/suites/dataset_valuation)"
    ),
}


def get_suite(name: str) -> TaskSuite:
    try:
        return SUITES[name]()
    except KeyError as exc:
        hint = " (planned, not implemented yet)" if name in PLANNED_SUITES else ""
        raise KeyError(f"Unknown suite {name!r}{hint}. Available: {sorted(SUITES)}") from exc


__all__ = ["PLANNED_SUITES", "SUITES", "TaskSuite", "get_suite"]
