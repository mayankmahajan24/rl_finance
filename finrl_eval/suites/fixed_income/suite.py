"""Fixed Income Instrumentation suite.

Samples are derived from simulated Bloomberg-style feed rows; ground truth is computed by
`reference.py` at load time so fixtures never drift from the reference implementation.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from finrl_eval.schema import FormatMirror, Sample, SuiteSpec, TaskFields
from finrl_eval.suites.base import TaskSuite
from finrl_eval.suites.fixed_income.reference import Bond

_RATES_BRIEF = (
    "A rates/credit desk that prices and risks fixed-coupon bonds from a "
    "terminal feed. Feed rows and issuers are fictional."
)

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
        task_fields=(
            TaskFields(
                name="price_from_yield",
                fields=("clean_price", "accrued_interest", "dirty_price"),
            ),
            TaskFields(
                name="ytm_from_price",
                fields=("ytm_pct", "accrued_interest"),
            ),
            TaskFields(
                name="duration_convexity",
                fields=("macaulay_duration", "modified_duration", "convexity", "dv01"),
            ),
            TaskFields(
                name="accrued_interest",
                fields=("days_accrued", "accrued_interest", "day_count_convention"),
            ),
        ),
        forbidden=("i cannot", "unable to", "not possible to"),
        max_words=250,
        hedging_note="Does not refuse or hedge on a fully specified calculation.",
        concise_note="Prose outside the JSON stays under 250 words.",
    )
    mirror = FormatMirror(
        role="quant_researcher",
        workflow="fixed_income",
        world="rates_desk",
        abbrev="fi",
        id_prefix="fi-",
        world_name="Rates and credit desk",
        world_brief=_RATES_BRIEF,
    )
    system_prompt = SYSTEM

    def read_samples(self) -> list[Sample]:
        feed = json.loads((self.root / "fixtures" / "feed.json").read_text())
        samples: list[Sample] = []
        for row in feed["rows"]:
            feed_row = {k: v for k, v in row.items() if k.isupper()}
            given = "YLD_YTM_MID" if "YLD_YTM_MID" in row else "PX_CLEAN"
            samples.append(
                Sample(
                    id=f"fi-{row['task']}-{row['ID_ISIN'][-6:]}-{row['SETTLE_DT']}",
                    task=row["task"],
                    inputs={"feed": feed_row, "given_field": given},
                    expected=_ground_truth(row),
                    tags=list(row.get("tags", [])) + [row["task"]],
                    difficulty=row.get("difficulty", "medium"),
                )
            )
        return samples
