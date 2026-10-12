"""Earnings Report Recaps suite.

Three task types over synthetic press releases:
- headline_extraction: revenue, GAAP/non-GAAP EPS, YoY growth, FY revenue guidance.
- margin_analysis: gross and operating margin, operating-margin change in bps.
- gaap_reconciliation: one-time items, GAAP vs non-GAAP net income, guidance basis.
"""

from __future__ import annotations

import json

from finrl_eval.schema import FormatMirror, Sample, SuiteSpec, TaskFields
from finrl_eval.suites.base import TaskSuite

_EARNINGS_BRIEF = (
    "A long/short equity desk that writes same-day recaps of quarterly "
    "prints for the PM. Tasks here are synthetic press-release recaps, "
    "not live EDGAR filings."
)

SYSTEM = (
    "You are an equity research associate preparing an earnings recap. Read the press release "
    "carefully, distinguish GAAP from non-GAAP figures, and report every monetary amount in "
    "USD millions regardless of how the release states it. Finish with a single JSON object in "
    "a ```json block containing exactly the requested fields."
)


class EarningsSuite(TaskSuite):
    spec = SuiteSpec(
        name="earnings",
        title="Earnings Report Recaps",
        description=(
            "Extraction accuracy (revenue, EPS, guidance), mathematical correctness (YoY, margins) "
            "and nuanced context (GAAP vs non-GAAP, one-time items) on synthetic press releases."
        ),
        task_fields=(
            TaskFields(
                name="headline_extraction",
                fields=(
                    "revenue_musd",
                    "eps_gaap",
                    "eps_non_gaap",
                    "revenue_yoy_pct",
                    "fy_revenue_guidance_low_musd",
                    "fy_revenue_guidance_high_musd",
                ),
            ),
            TaskFields(
                name="margin_analysis",
                fields=(
                    "gross_margin_pct",
                    "operating_margin_pct",
                    "operating_margin_change_bps",
                ),
            ),
            TaskFields(
                name="gaap_reconciliation",
                fields=(
                    "one_time_items",
                    "one_time_items_net_musd",
                    "sbc_is_one_time_item",
                    "net_income_gaap_musd",
                    "net_income_non_gaap_musd",
                    "eps_gaap",
                    "eps_non_gaap",
                    "guidance_basis",
                ),
            ),
        ),
        forbidden=("i cannot", "unable to determine", "not disclosed"),
        max_words=200,
        hedging_note="Does not claim data is missing when it is in the release.",
    )
    mirror = FormatMirror(
        role="fundamental_analyst",
        workflow="earnings_recap",
        world="earnings_desk",
        abbrev="er",
        id_prefix="earn-",
        world_name="Equity earnings desk",
        world_brief=_EARNINGS_BRIEF,
    )
    system_prompt = SYSTEM

    def read_samples(self) -> list[Sample]:
        data = json.loads((self.root / "fixtures" / "earnings.json").read_text())
        return [Sample.model_validate(s) for s in data["samples"]]
