"""Suite contract. A suite bundles samples, a prompt engine and a rubric."""

from __future__ import annotations

import abc
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from finrl_eval.prompts import DEFAULT_SYSTEM, PromptEngine
from finrl_eval.rubric import Criterion, Rubric
from finrl_eval.schema import Dimension, FormatMirror, Sample, SuiteSpec, TaskFields
from finrl_eval.scorers import ForbiddenTerms, MaxWords, RequiredFields, ValidJson


def _answer_constraints(
    task_fields: Sequence[TaskFields],
    *,
    forbidden: Sequence[str],
    max_words: int,
    hedging_note: str,
    concise_note: str,
) -> list[Criterion]:
    """Shared prefix. Only TaskSuite.rubric calls this.

    Names, weights, the hard flag, and the valid_json / fields descriptions
    are fixed. A suite cannot ship a second copy.
    """
    return [
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
                f"fields_{item.name}",
                Dimension.CONSTRAINT,
                RequiredFields(list(item.fields)),
                weight=0.5,
                tasks={item.name},
                description=f"All requested fields present for {item.name}.",
            )
            for item in task_fields
        ],
        Criterion(
            "no_hedging",
            Dimension.CONSTRAINT,
            ForbiddenTerms(list(forbidden)),
            weight=0.25,
            description=hedging_note,
        ),
        Criterion(
            "concise",
            Dimension.CONSTRAINT,
            MaxWords(max_words),
            weight=0.25,
            description=concise_note,
        ),
    ]


class TaskSuiteMeta(abc.ABCMeta):
    """Reject a second rubric or a load_samples that skips answer_fields."""

    def __new__(
        mcls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: object,
    ) -> type:
        if any(isinstance(base, TaskSuiteMeta) for base in bases):
            if "rubric" in namespace:
                raise TypeError(
                    f"{name} must not define rubric(); "
                    "return domain criteria from domain_criteria()"
                )
            if "load_samples" in namespace:
                raise TypeError(
                    f"{name} must not define load_samples(); return samples from read_samples()"
                )
        return super().__new__(mcls, name, bases, namespace, **kwargs)


class TaskSuite(abc.ABC, metaclass=TaskSuiteMeta):
    """Suite contract. Callers use load_samples, rubric, and prompt_engine.

    Authors set spec, mirror, and system_prompt, and implement read_samples
    and domain_criteria.
    """

    spec: SuiteSpec
    mirror: FormatMirror
    system_prompt: str = DEFAULT_SYSTEM

    @property
    def root(self) -> Path:
        import inspect

        return Path(inspect.getfile(type(self))).parent

    @property
    def template_dir(self) -> Path:
        return self.root / "templates"

    def prompt_engine(self) -> PromptEngine:
        return PromptEngine(self.template_dir, system=self.system_prompt)

    def answer_fields(self, task: str) -> list[str]:
        for item in self.spec.task_fields:
            if item.name == task:
                return list(item.fields)
        raise KeyError(f"{self.spec.name}: unknown task {task}")

    def load_samples(self) -> list[Sample]:
        """Stamp answer_fields from spec.task_fields. One stamp path."""
        samples = self.read_samples()
        seen: set[str] = set()
        allowed = set(self.spec.tasks)
        for sample in samples:
            if sample.task not in allowed:
                raise ValueError(f"{self.spec.name}: unknown task {sample.task}")
            if sample.id in seen:
                raise ValueError(f"{self.spec.name}: duplicate id {sample.id}")
            seen.add(sample.id)
            sample.inputs["answer_fields"] = self.answer_fields(sample.task)
        return samples

    def rubric(self) -> Rubric:
        spec = self.spec
        return Rubric(
            [
                *_answer_constraints(
                    spec.task_fields,
                    forbidden=spec.forbidden,
                    max_words=spec.max_words,
                    hedging_note=spec.hedging_note,
                    concise_note=spec.concise_note,
                ),
                *self.domain_criteria(),
            ]
        )

    @abc.abstractmethod
    def read_samples(self) -> list[Sample]:
        """Return samples without answer_fields. Gold stays in the suite."""

    @abc.abstractmethod
    def domain_criteria(self) -> list[Criterion]:
        """Domain criteria only. Constraint names are reserved."""
