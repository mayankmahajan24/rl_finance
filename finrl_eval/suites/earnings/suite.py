"""Earnings Report Recaps suite.

Three task types over synthetic press releases:
- headline_extraction: revenue, GAAP/non-GAAP EPS, YoY growth, FY revenue guidance.
- margin_analysis: gross and operating margin, operating-margin change in bps.
- gaap_reconciliation: one-time items, GAAP vs non-GAAP net income, guidance basis.
"""

from __future__ import annotations

import json

from finrl_eval.rubric import Criterion, Rubric
from finrl_eval.schema import Dimension, Sample, SuiteSpec
from finrl_eval.scorers import (
    ExactMatch,
    ForbiddenTerms,
    FuzzyMatch,
    LLMJudge,
    MaxWords,
    NumericTolerance,
    RequiredFields,
    ValidJson,
)
from finrl_eval.suites.base import TaskSuite

TASK_FIELDS: dict[str, list[str]] = {
    "headline_extraction": [
        "revenue_musd",
        "eps_gaap",
        "eps_non_gaap",
        "revenue_yoy_pct",
        "fy_revenue_guidance_low_musd",
        "fy_revenue_guidance_high_musd",
    ],
    "margin_analysis": ["gross_margin_pct", "operating_margin_pct", "operating_margin_change_bps"],
    "gaap_reconciliation": [
        "one_time_items",
        "one_time_items_net_musd",
        "sbc_is_one_time_item",
        "net_income_gaap_musd",
        "net_income_non_gaap_musd",
        "eps_gaap",
        "eps_non_gaap",
        "guidance_basis",
    ],
}

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
        tasks=list(TASK_FIELDS),
    )
    system_prompt = SYSTEM

    def load_samples(self) -> list[Sample]:
        data = json.loads((self.root / "fixtures" / "earnings.json").read_text())
        samples = [Sample.model_validate(s) for s in data["samples"]]
        for s in samples:
            s.inputs["answer_fields"] = TASK_FIELDS[s.task]
        return samples

    def rubric(self) -> Rubric:
        he, ma, gr = {"headline_extraction"}, {"margin_analysis"}, {"gaap_reconciliation"}
        return Rubric(
            [
                Criterion(
                    "valid_json",
                    Dimension.CONSTRAINT,
                    ValidJson(),
                    weight=0.5,
                    hard=True,
                    description="Answer ends with a parseable JSON object.",
                ),
                *[
                    Criterion(
                        f"fields_{task}",
                        Dimension.CONSTRAINT,
                        RequiredFields(fields),
                        weight=0.5,
                        tasks={task},
                        description=f"All requested fields present for {task}.",
                    )
                    for task, fields in TASK_FIELDS.items()
                ],
                Criterion(
                    "no_hedging",
                    Dimension.CONSTRAINT,
                    ForbiddenTerms(["i cannot", "unable to determine", "not disclosed"]),
                    weight=0.25,
                    description="Does not claim data is missing when it is in the release.",
                ),
                Criterion("concise", Dimension.CONSTRAINT, MaxWords(200), weight=0.25),
                # headline extraction
                Criterion(
                    "revenue",
                    Dimension.EXTRACTION,
                    NumericTolerance("revenue_musd", rel_tol=0.001),
                    weight=2.0,
                    tasks=he,
                    description="Quarterly revenue in $M (unit conversion required for "
                    "releases stated in thousands/billions).",
                ),
                Criterion(
                    "eps_gaap",
                    Dimension.EXTRACTION,
                    NumericTolerance("eps_gaap", abs_tol=0.005),
                    weight=1.5,
                    tasks=he | gr,
                    description="GAAP diluted EPS; sign matters for losses.",
                ),
                Criterion(
                    "eps_non_gaap",
                    Dimension.CONTEXT,
                    NumericTolerance("eps_non_gaap", abs_tol=0.005),
                    weight=1.5,
                    tasks=he | gr,
                    description="Non-GAAP EPS, not confused with GAAP.",
                ),
                Criterion(
                    "revenue_yoy",
                    Dimension.MATH,
                    NumericTolerance("revenue_yoy_pct", abs_tol=0.1),
                    weight=1.5,
                    tasks=he,
                    description="YoY growth in percent, computed when not stated.",
                ),
                Criterion(
                    "guidance_low",
                    Dimension.EXTRACTION,
                    NumericTolerance("fy_revenue_guidance_low_musd", rel_tol=0.001),
                    weight=1.0,
                    tasks=he,
                ),
                Criterion(
                    "guidance_high",
                    Dimension.EXTRACTION,
                    NumericTolerance("fy_revenue_guidance_high_musd", rel_tol=0.001),
                    weight=1.0,
                    tasks=he,
                ),
                # margins
                Criterion(
                    "gross_margin",
                    Dimension.MATH,
                    NumericTolerance("gross_margin_pct", abs_tol=0.1),
                    weight=1.5,
                    tasks=ma,
                ),
                Criterion(
                    "operating_margin",
                    Dimension.MATH,
                    NumericTolerance("operating_margin_pct", abs_tol=0.1),
                    weight=1.5,
                    tasks=ma,
                    description="GAAP operating margin including one-time items.",
                ),
                Criterion(
                    "operating_margin_change",
                    Dimension.MATH,
                    NumericTolerance("operating_margin_change_bps", abs_tol=10),
                    weight=1.5,
                    tasks=ma,
                    description="Change vs prior-year quarter in basis points.",
                ),
                # GAAP reconciliation
                Criterion(
                    "one_time_items",
                    Dimension.CONTEXT,
                    FuzzyMatch("one_time_items", threshold=0.6),
                    weight=2.0,
                    tasks=gr,
                    description="Identifies each one-time item (and nothing else).",
                ),
                Criterion(
                    "one_time_items_net",
                    Dimension.MATH,
                    NumericTolerance("one_time_items_net_musd", abs_tol=0.05),
                    weight=1.5,
                    tasks=gr,
                    description="Net of charges and gains in $M.",
                ),
                Criterion(
                    "sbc_not_one_time",
                    Dimension.CONTEXT,
                    ExactMatch("sbc_is_one_time_item"),
                    weight=1.0,
                    tasks=gr,
                    description="Recognises recurring SBC is not a one-time item.",
                ),
                Criterion(
                    "net_income_gaap",
                    Dimension.EXTRACTION,
                    NumericTolerance("net_income_gaap_musd", rel_tol=0.002),
                    weight=1.0,
                    tasks=gr,
                ),
                Criterion(
                    "net_income_non_gaap",
                    Dimension.CONTEXT,
                    NumericTolerance("net_income_non_gaap_musd", rel_tol=0.002),
                    weight=1.0,
                    tasks=gr,
                ),
                Criterion(
                    "guidance_basis",
                    Dimension.CONTEXT,
                    ExactMatch("guidance_basis"),
                    weight=1.0,
                    tasks=gr,
                    description="Whether guidance is on a GAAP or non-GAAP basis.",
                ),
                # optional qualitative check (only runs with --judge)
                Criterion(
                    "recap_quality",
                    Dimension.JUDGMENT,
                    LLMJudge(
                        "Does the prose correctly characterise the quarter (growth "
                        "direction, profitability, notable items) without "
                        "misattributing GAAP and non-GAAP figures?",
                        reference_fields=["eps_gaap", "eps_non_gaap"],
                    ),
                    weight=1.0,
                    pass_at=0.7,
                    tasks=he,
                    description="LLM-as-judge: qualitative accuracy of the recap prose.",
                ),
            ]
        )
