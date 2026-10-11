"""Rubrics compose scorers into weighted, dimension-tagged criteria."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from finrl_eval.schema import CriterionResult, Dimension
from finrl_eval.scorers import ScoreContext, Scorer


@dataclass
class Criterion:
    name: str
    dimension: Dimension
    scorer: Scorer
    weight: float = 1.0
    pass_at: float = 1.0
    hard: bool = False
    tasks: set[str] | None = field(default=None)
    description: str = ""

    def applies(self, task: str) -> bool:
        return self.tasks is None or task in self.tasks


@dataclass
class RubricOutcome:
    score: float
    dimension_scores: dict[str, float]
    criteria: list[CriterionResult]
    failed: list[str]
    hard_violation: bool


@dataclass
class Rubric:
    criteria: list[Criterion]

    def for_task(self, task: str) -> list[Criterion]:
        return [c for c in self.criteria if c.applies(task)]

    def evaluate(self, ctx: ScoreContext) -> RubricOutcome:
        results: list[CriterionResult] = []
        failed: list[str] = []
        hard_violation = False
        per_dim: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for crit in self.for_task(ctx.sample.task):
            if crit.scorer.requires_judge and ctx.judge is None:
                continue
            out = crit.scorer.score(ctx)
            passed = out.score >= crit.pass_at
            if not passed:
                failed.append(crit.name)
                if crit.hard:
                    hard_violation = True
            results.append(
                CriterionResult(
                    name=crit.name,
                    dimension=crit.dimension,
                    score=out.score,
                    weight=crit.weight,
                    passed=passed,
                    expected=out.expected,
                    actual=out.actual,
                    detail=out.detail,
                )
            )
            per_dim[crit.dimension.value].append((out.score, crit.weight))

        total_w = sum(r.weight for r in results)
        score = sum(r.score * r.weight for r in results) / total_w if total_w else 0.0
        if hard_violation:
            # A hard constraint violation caps the aggregate: unparseable or rule-breaking
            # output is not a usable answer regardless of partial numeric accuracy.
            score = min(score, 0.25)
        dims = {
            d: sum(s * w for s, w in pairs) / sum(w for _, w in pairs)
            for d, pairs in per_dim.items()
        }
        return RubricOutcome(
            round(score, 4),
            {k: round(v, 4) for k, v in dims.items()},
            results,
            failed,
            hard_violation,
        )

    def describe(self) -> list[dict[str, object]]:
        return [
            {
                "name": c.name,
                "dimension": c.dimension.value,
                "scorer": type(c.scorer).__name__,
                "weight": c.weight,
                "hard": c.hard,
                "tasks": sorted(c.tasks) if c.tasks else "all",
                "description": c.description,
            }
            for c in self.criteria
        ]
