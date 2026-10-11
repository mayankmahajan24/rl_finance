"""Generate the synthetic earnings-release fixtures for the `earnings` suite.

Companies, numbers and events are fictional. Each spec is a small set of underlying
financials; the press-release prose and the ground truth are both derived from it so they
can never disagree. Re-run after editing SPECS:

    uv run python scripts/generate_earnings_fixtures.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parents[1] / "finrl_eval/suites/earnings/fixtures/earnings.json"
ORDINALS = {"Q1": "first", "Q2": "second", "Q3": "third", "Q4": "fourth"}


@dataclass
class Spec:
    company: str
    ticker: str
    quarter: str
    fiscal_year: int
    revenue: float  # $M, current quarter
    revenue_prior: float  # $M, same quarter prior year
    cogs: float  # $M
    opex: float  # $M (ex one-time items)
    op_income_prior: float  # $M prior-year operating income
    revenue_prior_for_margin: float  # $M prior-year revenue (same as revenue_prior)
    tax_rate: float
    diluted_shares: float  # millions
    one_time: list[tuple[str, float]] = field(default_factory=list)  # (label, $M; + = charge)
    sbc: float = 0.0  # $M, excluded from non-GAAP but NOT a one-time item
    guidance_low: float = 0.0  # $M FY revenue
    guidance_high: float = 0.0
    guidance_basis: str = "non-GAAP"
    guidance_margin_pct: float = 0.0
    state_yoy: bool = True
    units: str = "millions"  # "millions" | "thousands" | "billions"
    non_gaap_first: bool = False
    difficulty: str = "medium"
    tags: list[str] = field(default_factory=list)
    tasks: list[str] = field(default_factory=lambda: ["headline_extraction"])
    other_income: float = 0.0  # $M, below operating line


SPECS: list[Spec] = [
    Spec(
        "Halcyon Networks",
        "HLCN",
        "Q3",
        2026,
        1842.3,
        1610.5,
        702.1,
        780.4,
        262.0,
        1610.5,
        0.21,
        412.5,
        one_time=[("restructuring charges", 48.0)],
        sbc=96.0,
        guidance_low=7400,
        guidance_high=7550,
        guidance_margin_pct=19.5,
        state_yoy=False,
        difficulty="medium",
        tags=["restructuring", "guidance-range"],
        tasks=["headline_extraction", "margin_analysis", "gaap_reconciliation"],
    ),
    Spec(
        "Meridian Freight Systems",
        "MFRT",
        "Q2",
        2026,
        963.8,
        1021.4,
        711.0,
        198.2,
        118.0,
        1021.4,
        0.24,
        88.2,
        one_time=[("gain on sale of terminal assets", -62.5)],
        sbc=12.0,
        guidance_low=3850,
        guidance_high=3950,
        guidance_basis="GAAP",
        guidance_margin_pct=0,
        state_yoy=True,
        difficulty="hard",
        tags=["one-time-gain", "revenue-decline"],
        tasks=["headline_extraction", "gaap_reconciliation"],
    ),
    Spec(
        "Cobalt Harbor Semiconductor",
        "CBHS",
        "Q4",
        2025,
        4218.0,
        3140.0,
        1897.0,
        1310.0,
        540.0,
        3140.0,
        0.15,
        1205.0,
        one_time=[("inventory write-down", 215.0), ("litigation settlement", 90.0)],
        sbc=410.0,
        guidance_low=18900,
        guidance_high=19500,
        guidance_margin_pct=33.0,
        units="thousands",
        difficulty="hard",
        tags=["units-thousands", "multi-one-time"],
        tasks=["headline_extraction", "margin_analysis", "gaap_reconciliation"],
    ),
    Spec(
        "Brightwater Utilities",
        "BWTR",
        "Q1",
        2026,
        712.4,
        688.9,
        391.3,
        201.7,
        92.0,
        688.9,
        0.22,
        156.0,
        sbc=4.5,
        guidance_low=2900,
        guidance_high=2960,
        guidance_basis="GAAP",
        state_yoy=True,
        difficulty="easy",
        tags=["no-one-time", "low-growth"],
        tasks=["headline_extraction", "margin_analysis"],
    ),
    Spec(
        "Ardent Biologics",
        "ARDB",
        "Q2",
        2026,
        318.6,
        204.1,
        41.2,
        402.9,
        -148.0,
        204.1,
        0.0,
        64.3,
        one_time=[("acquired in-process R&D", 85.0)],
        sbc=38.0,
        guidance_low=1250,
        guidance_high=1350,
        guidance_margin_pct=-30.0,
        state_yoy=False,
        difficulty="hard",
        tags=["loss-making", "ipr&d", "negative-eps"],
        tasks=["headline_extraction", "gaap_reconciliation"],
    ),
    Spec(
        "Northgate Consumer Brands",
        "NGCB",
        "Q3",
        2026,
        2765.0,
        2698.0,
        1587.0,
        879.0,
        236.0,
        2698.0,
        0.25,
        301.0,
        one_time=[("brand impairment", 120.0), ("gain on divestiture", -45.0)],
        sbc=31.0,
        guidance_low=11100,
        guidance_high=11300,
        guidance_margin_pct=9.0,
        non_gaap_first=True,
        difficulty="hard",
        tags=["non-gaap-first", "offsetting-items"],
        tasks=["headline_extraction", "margin_analysis", "gaap_reconciliation"],
    ),
    Spec(
        "Silverline Payments",
        "SLVP",
        "Q4",
        2025,
        1398.2,
        1152.6,
        412.0,
        701.5,
        190.0,
        1152.6,
        0.19,
        276.4,
        one_time=[("acquisition-related costs", 27.3)],
        sbc=142.0,
        guidance_low=6200,
        guidance_high=6400,
        guidance_margin_pct=24.0,
        units="billions",
        difficulty="medium",
        tags=["units-billions", "high-sbc"],
        tasks=["headline_extraction", "gaap_reconciliation"],
    ),
    Spec(
        "Keystone Steel & Alloys",
        "KSTA",
        "Q1",
        2026,
        2130.0,
        2455.0,
        1861.0,
        142.0,
        310.0,
        2455.0,
        0.23,
        97.0,
        one_time=[("plant closure costs", 66.0)],
        sbc=6.0,
        guidance_low=8200,
        guidance_high=8600,
        guidance_basis="GAAP",
        state_yoy=True,
        difficulty="medium",
        tags=["cyclical", "margin-compression", "revenue-decline"],
        tasks=["headline_extraction", "margin_analysis"],
    ),
    Spec(
        "Lumen Analytics Cloud",
        "LMAC",
        "Q2",
        2026,
        486.9,
        352.2,
        121.7,
        371.0,
        -41.0,
        352.2,
        0.0,
        142.8,
        sbc=88.0,
        guidance_low=2010,
        guidance_high=2030,
        guidance_margin_pct=4.0,
        non_gaap_first=True,
        state_yoy=False,
        difficulty="medium",
        tags=["gaap-loss-non-gaap-profit", "sbc-heavy"],
        tasks=["headline_extraction", "gaap_reconciliation"],
    ),
    Spec(
        "Pinecrest Hospitality",
        "PNCH",
        "Q3",
        2026,
        1576.0,
        1498.0,
        1012.0,
        379.0,
        160.0,
        1498.0,
        0.26,
        208.0,
        one_time=[("hurricane-related losses", 54.0), ("insurance recoveries", -31.0)],
        sbc=9.0,
        guidance_low=6050,
        guidance_high=6150,
        guidance_margin_pct=12.0,
        difficulty="hard",
        tags=["offsetting-items", "insurance"],
        tasks=["headline_extraction", "margin_analysis", "gaap_reconciliation"],
    ),
    Spec(
        "Orbital Defense Systems",
        "ORBD",
        "Q4",
        2025,
        3312.0,
        3077.0,
        2651.0,
        356.0,
        288.0,
        3077.0,
        0.18,
        540.0,
        sbc=22.0,
        guidance_low=13800,
        guidance_high=14100,
        guidance_basis="GAAP",
        units="thousands",
        state_yoy=True,
        difficulty="medium",
        tags=["units-thousands", "no-one-time"],
        tasks=["headline_extraction", "margin_analysis"],
    ),
    Spec(
        "Verdant Agri Holdings",
        "VRDA",
        "Q1",
        2026,
        845.5,
        790.2,
        611.4,
        171.3,
        56.0,
        790.2,
        0.2,
        118.5,
        one_time=[("legal reserve release", -18.0)],
        sbc=7.5,
        guidance_low=3500,
        guidance_high=3650,
        guidance_margin_pct=8.5,
        other_income=-12.0,
        difficulty="medium",
        tags=["reserve-release", "below-the-line"],
        tasks=["headline_extraction", "gaap_reconciliation"],
    ),
]


def fmt_money(musd: float, units: str) -> str:
    if units == "thousands":
        return f"${musd * 1000:,.0f} thousand"
    if units == "billions":
        return f"${musd / 1000:,.3f} billion"
    return f"${musd:,.1f} million"


def build(spec: Spec) -> dict[str, Any]:
    one_time_total = sum(v for _, v in spec.one_time)
    gross_profit = spec.revenue - spec.cogs
    op_income_gaap = gross_profit - spec.opex - one_time_total
    op_income_non_gaap = gross_profit - spec.opex + spec.sbc
    pretax_gaap = op_income_gaap + spec.other_income
    tax_gaap = max(pretax_gaap, 0.0) * spec.tax_rate
    net_income_gaap = pretax_gaap - tax_gaap
    pretax_non_gaap = op_income_non_gaap + spec.other_income
    tax_non_gaap = max(pretax_non_gaap, 0.0) * spec.tax_rate
    net_income_non_gaap = pretax_non_gaap - tax_non_gaap
    eps_gaap = net_income_gaap / spec.diluted_shares
    eps_non_gaap = net_income_non_gaap / spec.diluted_shares
    yoy = (spec.revenue / spec.revenue_prior - 1) * 100
    gross_margin = gross_profit / spec.revenue * 100
    op_margin = op_income_gaap / spec.revenue * 100
    op_margin_prior = spec.op_income_prior / spec.revenue_prior_for_margin * 100
    u = spec.units

    headline_gaap = (
        f"GAAP net {'income' if net_income_gaap >= 0 else 'loss'} was "
        f"{fmt_money(abs(net_income_gaap), u)}, or ${abs(eps_gaap):.2f} per diluted share"
        f"{' (loss)' if eps_gaap < 0 else ''}."
    )
    headline_non_gaap = (
        f"Non-GAAP net {'income' if net_income_non_gaap >= 0 else 'loss'} was "
        f"{fmt_money(abs(net_income_non_gaap), u)}, or ${abs(eps_non_gaap):.2f} per diluted share"
        f"{' (loss)' if eps_non_gaap < 0 else ''}."
    )
    order = (
        [headline_non_gaap, headline_gaap]
        if spec.non_gaap_first
        else [headline_gaap, headline_non_gaap]
    )

    yoy_clause = (
        f", {'up' if yoy >= 0 else 'down'} {abs(yoy):.1f}% year over year"
        if spec.state_yoy
        else f", compared with {fmt_money(spec.revenue_prior, u)} in the prior-year quarter"
    )
    items_sentence = ""
    if spec.one_time:
        parts = []
        for label, v in spec.one_time:
            kind = "charge" if v > 0 else "gain"
            parts.append(f"a {fmt_money(abs(v), u)} {label} ({kind})")
        items_sentence = (
            " Results include "
            + ", ".join(parts)
            + ", which "
            + ("is" if len(parts) == 1 else "are")
            + " excluded from non-GAAP measures along with stock-based compensation of "
            + fmt_money(spec.sbc, u)
            + "."
        )
    else:
        items_sentence = (
            " Non-GAAP measures exclude stock-based compensation of "
            + fmt_money(spec.sbc, u)
            + "; there were no other adjusting items in the quarter."
        )
    if spec.guidance_basis == "GAAP":
        guidance = (
            f" For fiscal {spec.fiscal_year}, the company {'now ' if spec.quarter != 'Q1' else ''}"
            f"expects revenue of {fmt_money(spec.guidance_low, u)} to "
            f"{fmt_money(spec.guidance_high, u)} on a GAAP basis."
        )
    else:
        guidance = (
            f" For fiscal {spec.fiscal_year}, the company {'now ' if spec.quarter != 'Q1' else ''}"
            f"expects revenue of {fmt_money(spec.guidance_low, u)} to "
            f"{fmt_money(spec.guidance_high, u)} and a non-GAAP operating margin of approximately "
            f"{spec.guidance_margin_pct:.1f}%."
        )
    table = (
        f"\n\nCondensed income statement ({'in ' + u}, unaudited)\n"
        f"  Revenue                       {fmt_money(spec.revenue, u)}\n"
        f"  Cost of revenue               {fmt_money(spec.cogs, u)}\n"
        f"  Gross profit                  {fmt_money(gross_profit, u)}\n"
        f"  Operating expenses            {fmt_money(spec.opex + one_time_total, u)}"
        + (f" (incl. {fmt_money(one_time_total, u)} of items noted above)" if spec.one_time else "")
        + f"\n  Operating income (loss)       {fmt_money(op_income_gaap, u)}\n"
        + (
            f"  Other income (expense), net   {fmt_money(spec.other_income, u)}\n"
            if spec.other_income
            else ""
        )
        + f"  Income tax expense            {fmt_money(tax_gaap, u)}\n"
        f"  Net income (loss)             {fmt_money(net_income_gaap, u)}\n"
        f"  Diluted shares (millions)     {spec.diluted_shares:,.1f}\n\n"
        f"Prior-year quarter: revenue {fmt_money(spec.revenue_prior, u)}; operating income "
        f"{fmt_money(spec.op_income_prior, u)}."
    )
    text = (
        f"{spec.company.upper()} REPORTS {spec.quarter} FISCAL {spec.fiscal_year} RESULTS\n\n"
        f"{spec.company} (NASDAQ: {spec.ticker}) today announced financial results for the "
        f"{ORDINALS[spec.quarter]} quarter of fiscal {spec.fiscal_year}. "
        f"Revenue was {fmt_money(spec.revenue, u)}{yoy_clause}. "
        + " ".join(order)
        + items_sentence
        + guidance
        + table
    )

    expected_common = {
        "revenue_musd": round(spec.revenue, 1),
        "eps_gaap": round(eps_gaap, 2),
        "eps_non_gaap": round(eps_non_gaap, 2),
        "revenue_yoy_pct": round(yoy, 1),
        "fy_revenue_guidance_low_musd": round(spec.guidance_low, 1),
        "fy_revenue_guidance_high_musd": round(spec.guidance_high, 1),
    }
    expected_by_task = {
        "headline_extraction": expected_common,
        "margin_analysis": {
            "gross_margin_pct": round(gross_margin, 1),
            "operating_margin_pct": round(op_margin, 1),
            "operating_margin_change_bps": round((op_margin - op_margin_prior) * 100),
        },
        "gaap_reconciliation": {
            "one_time_items": [label for label, _ in spec.one_time],
            "one_time_items_net_musd": round(one_time_total, 1),
            "sbc_is_one_time_item": False,
            "net_income_gaap_musd": round(net_income_gaap, 1),
            "net_income_non_gaap_musd": round(net_income_non_gaap, 1),
            "eps_gaap": round(eps_gaap, 2),
            "eps_non_gaap": round(eps_non_gaap, 2),
            "guidance_basis": spec.guidance_basis,
        },
    }
    samples = []
    for task in spec.tasks:
        samples.append(
            {
                "id": f"earn-{task}-{spec.ticker.lower()}-{spec.quarter.lower()}{spec.fiscal_year}",
                "task": task,
                "inputs": {
                    "company": spec.company,
                    "ticker": spec.ticker,
                    "quarter": spec.quarter,
                    "fiscal_year": spec.fiscal_year,
                    "press_release": text,
                },
                "expected": expected_by_task[task],
                "tags": spec.tags + [task, f"units-{u}"]
                if f"units-{u}" not in spec.tags
                else spec.tags + [task],
                "difficulty": spec.difficulty,
            }
        )
    return {"ticker": spec.ticker, "samples": samples}


def render() -> str:
    samples = [s for spec in SPECS for s in build(spec)["samples"]]
    return (
        json.dumps(
            {
                "_comment": "Generated by scripts/generate_earnings_fixtures.py; "
                "all companies and figures are fictional.",
                "samples": samples,
            },
            indent=2,
        )
        + "\n"
    )


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = render()
    OUT.write_text(text)
    n_samples = len(json.loads(text)["samples"])
    print(f"wrote {n_samples} samples to {OUT}")


if __name__ == "__main__":
    main()
