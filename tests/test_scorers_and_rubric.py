from typing import Any

from finrl_eval.prompts import parse_json_answer
from finrl_eval.rubric import Criterion, Rubric
from finrl_eval.schema import Dimension, Sample
from finrl_eval.scorers import (
    ExactMatch,
    ForbiddenTerms,
    FuzzyMatch,
    LLMJudge,
    MaxWords,
    NumericTolerance,
    RequiredFields,
    ScoreContext,
    ValidJson,
    ValueInRange,
    coerce_number,
)

SAMPLE = Sample(
    id="s1",
    task="t",
    expected={
        "revenue": 100.0,
        "label": "GAAP",
        "items": ["restructuring", "gain on sale"],
        "flag": False,
    },
)


def ctx(parsed: dict[str, Any] | None, response: str = "") -> ScoreContext:
    return ScoreContext(sample=SAMPLE, response=response, parsed=parsed)


def test_coerce_number_handles_formatting() -> None:
    assert coerce_number("$1,234.5") == 1234.5
    assert coerce_number("(12.5)") == -12.5
    assert coerce_number("12.5%") == 12.5
    assert coerce_number(True) is None
    assert coerce_number("n/a") is None


def test_numeric_tolerance_full_partial_zero() -> None:
    s = NumericTolerance("revenue", rel_tol=0.01)
    assert s.score(ctx({"revenue": 100.5})).score == 1.0
    partial = s.score(ctx({"revenue": 102.0})).score
    assert 0.0 < partial < 1.0
    assert s.score(ctx({"revenue": 200.0})).score == 0.0
    assert s.score(ctx({"revenue": "one hundred"})).score == 0.0
    assert s.score(ctx(None)).score == 0.0


def test_exact_match_variants() -> None:
    assert ExactMatch("label").score(ctx({"label": " gaap "})).score == 1.0
    assert ExactMatch("label").score(ctx({"label": "non-GAAP"})).score == 0.0
    assert ExactMatch("flag").score(ctx({"flag": "yes"})).score == 0.0
    assert ExactMatch("flag").score(ctx({"flag": "no"})).score == 1.0
    assert ExactMatch("flag").score(ctx({"flag": False})).score == 1.0
    assert ExactMatch("items").score(ctx({"items": ["Gain on sale", "restructuring"]})).score == 1.0


def test_fuzzy_match_list_and_string() -> None:
    s = FuzzyMatch("items", threshold=0.6)
    assert s.score(ctx({"items": ["restructuring charges", "gain on sale of assets"]})).score == 1.0
    assert s.score(ctx({"items": ["restructuring"]})).score == 0.5
    # Over-reporting is penalised.
    assert s.score(ctx({"items": ["restructuring", "gain on sale", "sbc", "tax"]})).score == 0.5
    assert FuzzyMatch("label").score(ctx({"label": "GAAP basis"})).score < 1.0


def test_constraint_scorers() -> None:
    assert ValidJson().score(ctx({"a": 1})).score == 1.0
    assert ValidJson().score(ctx(None)).score == 0.0
    assert RequiredFields(["a", "b"]).score(ctx({"a": 1, "b": None})).score == 0.5
    assert MaxWords(3).score(ctx({}, "one two three ```json\n{}\n```")).score == 1.0
    assert MaxWords(3).score(ctx({}, "one two three four")).score == 0.0
    assert ForbiddenTerms(["I cannot"]).score(ctx({}, "Sorry, i cannot do that")).score == 0.0
    assert ValueInRange("revenue", 0, 150).score(ctx({"revenue": 100})).score == 1.0
    assert ValueInRange("revenue", 0, 50).score(ctx({"revenue": 100})).score == 0.0


def test_llm_judge_skips_without_judge() -> None:
    out = LLMJudge("is it good?").score(ctx({}, "answer"))
    assert out.score == 1.0 and "skipped" in out.detail


def test_parse_json_answer() -> None:
    text = 'Recap text.\n```json\n{"revenue": 1.5, "label": "GAAP"}\n```'
    assert parse_json_answer(text) == {"revenue": 1.5, "label": "GAAP"}
    assert parse_json_answer('bare {"a": 1} tail') == {"a": 1}
    assert parse_json_answer("no json here") is None
    assert parse_json_answer("```json\n[1,2]\n```") is None


def test_rubric_weights_task_filter_and_hard_cap() -> None:
    rubric = Rubric(
        [
            Criterion("json", Dimension.CONSTRAINT, ValidJson(), weight=1, hard=True),
            Criterion(
                "rev", Dimension.EXTRACTION, NumericTolerance("revenue", rel_tol=0.01), weight=3
            ),
            Criterion("other", Dimension.MATH, ExactMatch("label"), tasks={"other_task"}),
            Criterion("judge", Dimension.JUDGMENT, LLMJudge("q")),
        ]
    )
    assert [c.name for c in rubric.for_task("t")] == ["json", "rev", "judge"]
    good = rubric.evaluate(ctx({"revenue": 100}))
    assert good.score == 1.0 and good.failed == [] and not good.hard_violation
    # Judge criterion is excluded entirely when no judge is configured.
    assert {c.name for c in good.criteria} == {"json", "rev"}
    bad = rubric.evaluate(ctx(None, "prose only revenue 100"))
    assert bad.hard_violation and bad.score <= 0.25 and "json" in bad.failed
    assert bad.dimension_scores == {"constraint": 0.0, "extraction": 0.0}
