"""Suite contract. A suite bundles samples, a prompt engine and a rubric."""

from __future__ import annotations

import abc
from pathlib import Path

from finrl_eval.prompts import DEFAULT_SYSTEM, PromptEngine
from finrl_eval.rubric import Rubric
from finrl_eval.schema import Sample, SuiteSpec


class TaskSuite(abc.ABC):
    spec: SuiteSpec
    system_prompt: str = DEFAULT_SYSTEM

    @property
    def root(self) -> Path:
        import inspect

        return Path(inspect.getfile(type(self))).parent

    @property
    def template_dir(self) -> Path:
        return self.root / "templates"

    @abc.abstractmethod
    def load_samples(self) -> list[Sample]: ...

    @abc.abstractmethod
    def rubric(self) -> Rubric: ...

    def prompt_engine(self) -> PromptEngine:
        return PromptEngine(self.template_dir, system=self.system_prompt)
