"""Deterministic offline provider.

The mock simulates a model with known failure modes so scoring, aggregation,
failure-mode reporting, and reward export can run with no credentials.
Behaviour is a pure function of seed, sample id, and mode, so runs are reproducible.

Modes
-----
- ``oracle``: always returns the ground truth. A rubric sanity check expects 1.0
  for a perfect answer.
- ``noisy``, the default: mostly correct, with numeric slips, GAAP and non-GAAP
  confusion, unit errors, dropped fields, and format violations.
- ``broken``: always returns an unparseable prose answer. Tests use it to check the rubric floor.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from finrl_eval.providers.base import ModelProvider
from finrl_eval.schema import ModelRequest, ModelResponse

FAILURE_BUCKETS: list[tuple[int, str]] = [
    # (upper bound of bucket in [0,100), failure kind)
    (58, "correct"),
    (70, "numeric_slip"),
    (78, "gaap_confusion"),
    (86, "unit_error"),
    (93, "missing_field"),
    (100, "format_violation"),
]


def _bucket(seed: int, sample_id: str) -> int:
    digest = hashlib.sha256(f"{seed}:{sample_id}".encode()).hexdigest()
    return int(digest[:8], 16) % 100


def failure_kind(seed: int, sample_id: str, mode: str) -> str:
    if mode == "oracle":
        return "correct"
    if mode == "broken":
        return "format_violation"
    b = _bucket(seed, sample_id)
    for upper, kind in FAILURE_BUCKETS:
        if b < upper:
            return kind
    return "correct"


class MockProvider(ModelProvider):
    name = "mock"
    needs_oracle = True

    @classmethod
    def default_model(cls) -> str:
        return "mock-noisy"

    def __init__(self, model: str | None = None, seed: int = 0) -> None:
        super().__init__(model)
        self.mode = self.model.removeprefix("mock-") if self.model.startswith("mock-") else "noisy"
        if self.mode not in {"oracle", "noisy", "broken"}:
            raise ValueError(
                f"Unknown mock mode {self.mode!r}; use mock-oracle|mock-noisy|mock-broken"
            )
        self.seed = seed

    def complete(self, request: ModelRequest) -> ModelResponse:
        if request.oracle is None:
            return ModelResponse(
                text="", model=self.model, provider=self.name, error="mock provider needs oracle"
            )
        expected: dict[str, Any] = dict(request.oracle.get("expected", {}))
        kind = failure_kind(self.seed, request.sample_id, self.mode)
        answer = self._apply_failure(expected, kind, request.sample_id)
        if kind == "format_violation":
            text = self._prose(answer)
        else:
            text = (
                "Here is the structured answer based on the provided data.\n\n"
                "```json\n" + json.dumps(answer, indent=2) + "\n```"
            )
        return ModelResponse(text=text, model=self.model, provider=self.name, latency_ms=1.0)

    # -- failure simulation -----------------------------------------------------------

    def _apply_failure(self, answer: dict[str, Any], kind: str, sample_id: str) -> dict[str, Any]:
        numeric_keys = [
            k for k, v in answer.items() if isinstance(v, int | float) and not isinstance(v, bool)
        ]
        if not numeric_keys or kind == "correct":
            return answer
        pick = numeric_keys[_bucket(self.seed + 1, sample_id) % len(numeric_keys)]
        if kind == "numeric_slip":
            # Off by a few percent, the kind of error produced by sloppy arithmetic.
            answer[pick] = round(float(answer[pick]) * 1.035 + 0.01, 6)
        elif kind == "gaap_confusion":
            swapped = False
            for a, b in (("eps_gaap", "eps_non_gaap"), ("net_income_gaap", "net_income_non_gaap")):
                if a in answer and b in answer:
                    answer[a], answer[b] = answer[b], answer[a]
                    swapped = True
            if not swapped:
                # Non-earnings suites: flip the sign of a value instead.
                answer[pick] = -float(answer[pick])
        elif kind == "unit_error":
            pct_like = [k for k in numeric_keys if "pct" in k or "yield" in k or "margin" in k]
            target = pct_like[0] if pct_like else pick
            answer[target] = round(float(answer[target]) / 100, 8)
        elif kind == "missing_field":
            del answer[pick]
        return answer

    @staticmethod
    def _prose(answer: dict[str, Any]) -> str:
        parts = [f"the {k.replace('_', ' ')} is {v}" for k, v in answer.items()]
        return (
            "Based on my reading of the materials, " + "; ".join(parts) + ". "
            "I cannot provide this in JSON form, but I hope this summary is helpful. "
            "Note that these figures should be double-checked against the filing."
        )

    # -- judge ------------------------------------------------------------------------

    def judge(self, system: str, prompt: str) -> str:
        """Heuristic judge: share of reference numbers that also appear in the response."""
        ref = _section(prompt, "REFERENCE")
        resp = _section(prompt, "RESPONSE")
        ref_nums = set(re.findall(r"-?\d+(?:\.\d+)?", ref))
        if not ref_nums:
            score = 1.0 if resp.strip() else 0.0
        else:
            hits = sum(1 for n in ref_nums if n in resp)
            score = hits / len(ref_nums)
        return json.dumps({"score": round(score, 3), "rationale": "mock heuristic numeric overlap"})


def _section(prompt: str, header: str) -> str:
    m = re.search(rf"{header}:\n(.*?)(?:\n[A-Z]+:\n|\Z)", prompt, flags=re.S)
    return m.group(1) if m else ""
