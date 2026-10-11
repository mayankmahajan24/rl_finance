"""Fixed Income Instrumentation suite.

Samples are derived from simulated Bloomberg-style feed rows; ground truth is computed by
`reference.py` at load time so fixtures never drift from the reference implementation.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from finrl_eval.rubric import Criterion, Rubric
from finrl_eval.schema import Dimension, Sample, SuiteSpec
from finrl_eval.scorers import (
    ExactMatch,
    ForbiddenTerms,
    MaxWords,
    NumericTolerance,
    RequiredFields,
    ScoreContext,
    ScoreOutcome,
    Scorer,
    ValidJson,
    ValueInRange,
    coerce_number,
)
from finrl_eval.suites.base import TaskSuite
from finrl_eval.suites.fixed_income.reference import Bond

TASK_FIELDS: dict[str, list[str]] = {
    "price_from_yield": ["clean_price", "accrued_interest", "dirty_price"],
    "ytm_from_price": ["ytm_pct", "accrued_interest"],
    "duration_convexity": ["macaulay_duration", "modified_duration", "convexity", "dv01"],
    "accrued_interest": ["days_accrued", "accrued_interest", "day_count_convention"],
}

SYSTEM = (
    "You are a fixed-income analyst working from a terminal feed. Use street convention "
    "(coupons discounted at (1 + y/f) per period, fractional first period per the stated day "
    "count), prices per 100 face, yields in percent. Finish with a single JSON object in a "
    "```json block containing exactly the requested fields as plain numbers."
)


def _ground_truth(row: dict[str, Any]) -> dict[str, Any]:
    bond = Bond(
        coupon_pct=float(row["CPN"]),
        maturity=date.fromisoformat(row["MATURITY"]),
        freq=int(row["CPN_FREQ"]),
        basis=row["DAY_CNT_DES"],
    )
    settle = date.fromisoformat(row["SETTLE_DT"])
    task = row["task"]
    accrued = bond.accrued_interest(settle)
    if task == "price_from_yield":
        y = float(row["YLD_YTM_MID"])
        dirty = bond.dirty_price(settle, y)
        return {
            "clean_price": round(dirty - accrued, 6),
            "accrued_interest": round(accrued, 6),
            "dirty_price": round(dirty, 6),
        }
    if task == "ytm_from_price":
        return {
            "ytm_pct": round(bond.ytm(settle, float(row["PX_CLEAN"])), 6),
            "accrued_interest": round(accrued, 6),
        }
    if task == "duration_convexity":
        y = float(row["YLD_YTM_MID"])
        mac, mod, conv = bond.durations(settle, y)
        return {
            "macaulay_duration": round(mac, 6),
            "modified_duration": round(mod, 6),
            "convexity": round(conv, 6),
            "dv01": round(bond.dv01(settle, y), 6),
        }
    if task == "accrued_interest":
        return {
            "days_accrued": bond.accrued_days(settle),
            "accrued_interest": round(accrued, 6),
            "day_count_convention": row["DAY_CNT_DES"],
        }
    raise ValueError(f"unknown task {task}")


class FixedIncomeSuite(TaskSuite):
    spec = SuiteSpec(
        name="fixed_income",
        title="Fixed Income Instrumentation",
        description=(
            "Bond price from yield, yield from price, duration/convexity and accrued interest "
            "across 30/360, ACT/360, ACT/365 and ACT/ACT conventions, from simulated "
            "Bloomberg-style feed rows."
        ),
        tasks=list(TASK_FIELDS),
    )
    system_prompt = SYSTEM

    def load_samples(self) -> list[Sample]:
        feed = json.loads((self.root / "fixtures" / "feed.json").read_text())
        samples: list[Sample] = []
        for row in feed["rows"]:
            feed_row = {k: v for k, v in row.items() if k.isupper()}
            given = "YLD_YTM_MID" if "YLD_YTM_MID" in row else "PX_CLEAN"
            samples.append(
                Sample(
                    id=f"fi-{row['task']}-{row['ID_ISIN'][-6:]}-{row['SETTLE_DT']}",
                    task=row["task"],
                    inputs={
                        "feed": feed_row,
                        "given_field": given,
                        "answer_fields": TASK_FIELDS[row["task"]],
                    },
                    expected=_ground_truth(row),
                    tags=list(row.get("tags", [])) + [row["task"]],
                    difficulty=row.get("difficulty", "medium"),
                )
            )
        return samples

    def rubric(self) -> Rubric:
        t = TASK_FIELDS
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
                    for task, fields in t.items()
                ],
                Criterion(
                    "no_hedging",
                    Dimension.CONSTRAINT,
                    ForbiddenTerms(["i cannot", "unable to", "not possible to"]),
                    weight=0.25,
                    description="Does not refuse or hedge on a fully specified calculation.",
                ),
                Criterion(
                    "concise",
                    Dimension.CONSTRAINT,
                    MaxWords(250),
                    weight=0.25,
                    description="Prose outside the JSON stays under 250 words.",
                ),
                # price_from_yield
                Criterion(
                    "clean_price",
                    Dimension.MATH,
                    NumericTolerance("clean_price", abs_tol=0.01),
                    weight=2.0,
                    tasks={"price_from_yield"},
                    description="Clean price within 1 cent per 100 face.",
                ),
                Criterion(
                    "dirty_price",
                    Dimension.MATH,
                    NumericTolerance("dirty_price", abs_tol=0.01),
                    weight=1.0,
                    tasks={"price_from_yield"},
                ),
                Criterion(
                    "price_sane",
                    Dimension.CONSTRAINT,
                    ValueInRange("clean_price", 20, 250),
                    weight=0.5,
                    tasks={"price_from_yield"},
                    description="Domain sanity: price per 100 in a plausible band.",
                ),
                # ytm_from_price
                Criterion(
                    "ytm",
                    Dimension.MATH,
                    NumericTolerance("ytm_pct", abs_tol=0.005),
                    weight=2.5,
                    tasks={"ytm_from_price"},
                    description="Yield within half a basis point.",
                ),
                Criterion(
                    "ytm_sane",
                    Dimension.CONSTRAINT,
                    ValueInRange("ytm_pct", -1, 40),
                    weight=0.5,
                    tasks={"ytm_from_price"},
                    description="Yield expressed in percent, not decimal.",
                ),
                # duration / convexity
                Criterion(
                    "macaulay_duration",
                    Dimension.MATH,
                    NumericTolerance("macaulay_duration", rel_tol=0.005),
                    weight=1.0,
                    tasks={"duration_convexity"},
                ),
                Criterion(
                    "modified_duration",
                    Dimension.MATH,
                    NumericTolerance("modified_duration", rel_tol=0.005),
                    weight=1.5,
                    tasks={"duration_convexity"},
                ),
                Criterion(
                    "convexity",
                    Dimension.MATH,
                    NumericTolerance("convexity", rel_tol=0.01),
                    weight=1.0,
                    tasks={"duration_convexity"},
                ),
                Criterion(
                    "dv01",
                    Dimension.MATH,
                    NumericTolerance("dv01", rel_tol=0.01),
                    weight=1.0,
                    tasks={"duration_convexity"},
                ),
                Criterion(
                    "duration_ordering",
                    Dimension.CONTEXT,
                    _DurationOrdering(),
                    weight=0.5,
                    tasks={"duration_convexity"},
                    description="Modified duration < Macaulay duration (positive yield).",
                ),
                # accrued interest (shared across tasks where requested)
                Criterion(
                    "accrued_interest",
                    Dimension.MATH,
                    NumericTolerance("accrued_interest", abs_tol=0.0005),
                    weight=1.5,
                    tasks={"price_from_yield", "ytm_from_price", "accrued_interest"},
                    description="Accrued interest within 0.05 cents per 100 face.",
                ),
                Criterion(
                    "days_accrued",
                    Dimension.CONTEXT,
                    NumericTolerance("days_accrued", abs_tol=0),
                    weight=1.0,
                    tasks={"accrued_interest"},
                    description="Day count under the stated convention is exact.",
                ),
                Criterion(
                    "day_count_convention",
                    Dimension.CONTEXT,
                    ExactMatch("day_count_convention"),
                    weight=0.5,
                    tasks={"accrued_interest"},
                    description="Echoes the convention actually applied.",
                ),
            ]
        )


class _DurationOrdering(Scorer):
    """Suite-specific scorer: modified duration must sit strictly below Macaulay for
    positive yields. Illustrates how a suite adds a domain-constraint check."""

    def score(self, ctx: ScoreContext) -> ScoreOutcome:
        if ctx.parsed is None:
            return ScoreOutcome(0.0, "mod < mac", None, "no JSON")
        mod = coerce_number(ctx.parsed.get("modified_duration"))
        mac = coerce_number(ctx.parsed.get("macaulay_duration"))
        if mod is None or mac is None:
            return ScoreOutcome(0.0, "mod < mac", [mod, mac], "missing")
        ok = 0 < mod < mac
        return ScoreOutcome(1.0 if ok else 0.0, "0 < mod < mac", [mod, mac])
