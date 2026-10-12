"""Composable scorers. Each scorer maps a sample and a response to a score from 0 to 1.

Scorers are small, pure objects so a rubric reads like a spec:

    Rubric([
        Criterion("revenue", Dimension.EXTRACTION, NumericTolerance("revenue_musd", rel_tol=0.001)),
        Criterion("yoy", Dimension.MATH, NumericTolerance("revenue_yoy_pct", abs_tol=0.1)),
        Criterion("json", Dimension.CONSTRAINT, ValidJson(), hard=True),
    ])
"""

from __future__ import annotations

import abc
import json
import math
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any

from finrl_eval.schema import JsonValue, Sample

if TYPE_CHECKING:
    from finrl_eval.providers.base import ModelProvider


@dataclass
class ScoreContext:
    sample: Sample
    response: str
    parsed: dict[str, Any] | None
    judge: ModelProvider | None = None


@dataclass
class ScoreOutcome:
    score: float
    expected: JsonValue = None
    actual: JsonValue = None
    detail: str = ""


class Scorer(abc.ABC):
    @abc.abstractmethod
    def score(self, ctx: ScoreContext) -> ScoreOutcome: ...

    @property
    def requires_judge(self) -> bool:
        return False


# -- helpers --------------------------------------------------------------------------

_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def coerce_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, str):
        s = value.strip().replace("$", "").replace("%", "")
        neg = s.startswith("(") and s.endswith(")")
        m = _NUM.search(s)
        if not m:
            return None
        try:
            n = float(m.group(0).replace(",", ""))
        except ValueError:
            return None
        return -n if neg else n
    return None


def _lookup(ctx: ScoreContext, field_name: str) -> Any:
    if ctx.parsed is None:
        return None
    return ctx.parsed.get(field_name)


def _norm_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().lower()


# -- numeric --------------------------------------------------------------------------


@dataclass
class NumericTolerance(Scorer):
    """1.0 if |actual - expected| within tolerance; linear partial credit out to
    `partial_factor` x tolerance; 0 beyond. Missing or non-numeric answers score 0."""

    field: str
    rel_tol: float = 0.0
    abs_tol: float = 0.0
    partial_factor: float = 5.0

    def score(self, ctx: ScoreContext) -> ScoreOutcome:
        expected = coerce_number(ctx.sample.expected.get(self.field))
        raw = _lookup(ctx, self.field)
        actual = coerce_number(raw)
        if expected is None:
            return ScoreOutcome(1.0, None, raw, "no expected value; skipped")
        if actual is None:
            return ScoreOutcome(0.0, expected, raw, "missing or non-numeric")
        tol = max(self.abs_tol, self.rel_tol * abs(expected))
        err = abs(actual - expected)
        if err <= tol:
            return ScoreOutcome(1.0, expected, actual, f"err={err:.6g} <= tol={tol:.6g}")
        if tol > 0 and err < tol * self.partial_factor:
            partial = 1.0 - (err - tol) / (tol * (self.partial_factor - 1))
            return ScoreOutcome(round(partial, 4), expected, actual, f"err={err:.6g} partial")
        return ScoreOutcome(0.0, expected, actual, f"err={err:.6g} > tol={tol:.6g}")


# -- extraction -----------------------------------------------------------------------


@dataclass
class ExactMatch(Scorer):
    """Case/whitespace-insensitive equality on a field (strings, bools, lists)."""

    field: str

    def score(self, ctx: ScoreContext) -> ScoreOutcome:
        expected = ctx.sample.expected.get(self.field)
        actual = _lookup(ctx, self.field)
        if actual is None:
            return ScoreOutcome(0.0, expected, None, "missing")
        if isinstance(expected, list):
            e = sorted(_norm_text(x) for x in expected)
            a = sorted(_norm_text(x) for x in actual) if isinstance(actual, list) else []
            return ScoreOutcome(1.0 if e == a else 0.0, expected, actual)
        if isinstance(expected, bool):
            a_bool = actual if isinstance(actual, bool) else _norm_text(actual) in {"true", "yes"}
            return ScoreOutcome(1.0 if a_bool == expected else 0.0, expected, actual)
        ok = _norm_text(expected) == _norm_text(actual)
        return ScoreOutcome(1.0 if ok else 0.0, expected, actual)


@dataclass
class FuzzyMatch(Scorer):
    """Similarity ratio on strings; for lists, mean best-match ratio across expected items."""

    field: str
    threshold: float = 0.85

    def _ratio(self, a: Any, b: Any) -> float:
        return SequenceMatcher(None, _norm_text(a), _norm_text(b)).ratio()

    def score(self, ctx: ScoreContext) -> ScoreOutcome:
        expected = ctx.sample.expected.get(self.field)
        actual = _lookup(ctx, self.field)
        if actual is None:
            return ScoreOutcome(0.0, expected, None, "missing")
        if isinstance(expected, list):
            if not expected:
                return ScoreOutcome(1.0 if not actual else 0.0, expected, actual)
            got = actual if isinstance(actual, list) else [actual]
            best = [max((self._ratio(e, g) for g in got), default=0.0) for e in expected]
            hits = sum(1 for r in best if r >= self.threshold)
            precision_penalty = min(1.0, len(expected) / max(len(got), 1))
            return ScoreOutcome(
                round(hits / len(expected) * precision_penalty, 4),
                expected,
                actual,
                f"{hits}/{len(expected)} matched",
            )
        ratio = self._ratio(expected, actual)
        return ScoreOutcome(
            1.0 if ratio >= self.threshold else round(ratio, 4),
            expected,
            actual,
            f"ratio={ratio:.3f}",
        )


# -- constraints ----------------------------------------------------------------------


@dataclass
class ValidJson(Scorer):
    def score(self, ctx: ScoreContext) -> ScoreOutcome:
        ok = ctx.parsed is not None
        return ScoreOutcome(1.0 if ok else 0.0, True, ok, "" if ok else "no JSON object found")


@dataclass
class RequiredFields(Scorer):
    """Fraction of required fields present (and non-null) in the parsed answer."""

    fields: list[str] = field(default_factory=list)

    def score(self, ctx: ScoreContext) -> ScoreOutcome:
        if ctx.parsed is None:
            return ScoreOutcome(0.0, self.fields, None, "no JSON")
        present = [f for f in self.fields if ctx.parsed.get(f) is not None]
        missing = sorted(set(self.fields) - set(present))
        return ScoreOutcome(
            len(present) / len(self.fields) if self.fields else 1.0,
            self.fields,
            present,
            f"missing={missing}" if missing else "",
        )


@dataclass
class MaxWords(Scorer):
    """Response length ceiling (prose outside the JSON block). Penalises verbosity."""

    limit: int

    def score(self, ctx: ScoreContext) -> ScoreOutcome:
        prose = re.sub(r"```.*?```", "", ctx.response, flags=re.S)
        n = len(prose.split())
        return ScoreOutcome(1.0 if n <= self.limit else 0.0, self.limit, n)


@dataclass
class ForbiddenTerms(Scorer):
    """Fails if any forbidden phrase appears (e.g. hedging like 'I cannot')."""

    terms: list[str] = field(default_factory=list)

    def score(self, ctx: ScoreContext) -> ScoreOutcome:
        low = ctx.response.lower()
        found = [t for t in self.terms if t.lower() in low]
        return ScoreOutcome(0.0 if found else 1.0, [], found)


@dataclass
class ValueInRange(Scorer):
    """Domain-constraint sanity check independent of ground truth, e.g. 0 < price < 300."""

    field: str
    low: float | None = None
    high: float | None = None

    def score(self, ctx: ScoreContext) -> ScoreOutcome:
        actual = coerce_number(_lookup(ctx, self.field))
        if actual is None:
            return ScoreOutcome(0.0, [self.low, self.high], None, "missing")
        ok = (self.low is None or actual >= self.low) and (self.high is None or actual <= self.high)
        return ScoreOutcome(1.0 if ok else 0.0, [self.low, self.high], actual)


# -- LLM-as-judge ---------------------------------------------------------------------


JUDGE_SYSTEM = (
    "You are a strict grader of financial analysis. Compare the RESPONSE against the "
    "REFERENCE using the CRITERIA. Reply with only a JSON object: "
    '{"score": <0..1>, "rationale": "<one sentence>"}.'
)


@dataclass
class LLMJudge(Scorer):
    """Optional qualitative criterion. Skipped (scores 1.0, detail 'skipped') when no judge
    provider is configured, so offline runs stay deterministic."""

    criteria: str
    reference_fields: list[str] = field(default_factory=list)

    @property
    def requires_judge(self) -> bool:
        return True

    def score(self, ctx: ScoreContext) -> ScoreOutcome:
        if ctx.judge is None:
            return ScoreOutcome(1.0, None, None, "skipped: no judge provider")
        reference = {
            k: ctx.sample.expected.get(k) for k in self.reference_fields
        } or ctx.sample.expected
        prompt = (
            f"CRITERIA:\n{self.criteria}\n\nREFERENCE:\n{json.dumps(reference, indent=2)}\n\n"
            f"RESPONSE:\n{ctx.response}\n"
        )
        try:
            raw = ctx.judge.judge(JUDGE_SYSTEM, prompt)
            obj = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))  # type: ignore[union-attr]
            score = float(obj.get("score", 0.0))
        except Exception as exc:  # noqa: BLE001 - judge output is untrusted
            return ScoreOutcome(0.0, None, None, f"judge parse error: {exc}")
        return ScoreOutcome(min(1.0, max(0.0, score)), None, None, str(obj.get("rationale", "")))
