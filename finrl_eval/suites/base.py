"""Suite contract. A suite bundles samples and a prompt engine.

The rubric is added later. This module only loads samples and renders prompts.
"""

from __future__ import annotations

import abc
from pathlib import Path

from finrl_eval.prompts import DEFAULT_SYSTEM, PromptEngine
from finrl_eval.schema import FormatMirror, Sample, SuiteSpec


class TaskSuite(abc.ABC):
    """Suite contract. Callers use load_samples and prompt_engine.

    Authors set spec, mirror, and system_prompt, and implement read_samples.
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

    @abc.abstractmethod
    def read_samples(self) -> list[Sample]:
        """Return samples without answer_fields. Gold stays in the suite."""
