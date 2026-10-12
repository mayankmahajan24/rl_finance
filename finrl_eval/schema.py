"""Pydantic data model shared by suites, providers, scorers, the runner and reports."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

JsonValue = str | int | float | bool | None | list[Any] | dict[str, Any]


class Dimension(StrEnum):
    """Top-level rubric categories. Every rubric criterion belongs to one of these."""

    EXTRACTION = "extraction"
    MATH = "math"
    CONTEXT = "context"
    CONSTRAINT = "constraint"
    JUDGMENT = "judgment"


class Sample(BaseModel):
    """One evaluation item: inputs the model sees plus the ground truth it is scored against."""

    model_config = ConfigDict(extra="forbid")

    id: str
    task: str = Field(description="Task type within the suite, e.g. 'price_from_yield'.")
    inputs: dict[str, Any] = Field(
        default_factory=dict, description="Variables fed to the prompt template."
    )
    expected: dict[str, Any] = Field(
        default_factory=dict, description="Ground-truth answer fields."
    )
    tags: list[str] = Field(default_factory=list)
    difficulty: str = "medium"
    notes: str = ""


class TaskFields(BaseModel):
    """Ordered answer fields for one task. This tuple is the only field list."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    fields: tuple[str, ...]

    @model_validator(mode="after")
    def _fields_ok(self) -> TaskFields:
        if not self.fields or any(not field for field in self.fields):
            raise ValueError(f"{self.name}: answer fields must be non-empty")
        if len(set(self.fields)) != len(self.fields):
            raise ValueError(f"{self.name}: duplicate answer field")
        return self


class FormatMirror(BaseModel):
    """Where a live suite is written under rl/roles and rl/worlds.

    task.yaml wire fields (mode, status, provenance, grader module) are not
    on this type. The FORMAT builder owns those.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str = Field(min_length=1)
    workflow: str = Field(min_length=1)
    world: str = Field(min_length=1)
    abbrev: str = Field(min_length=1)
    id_prefix: str = Field(min_length=1)
    world_name: str = Field(min_length=1)
    world_brief: str = Field(min_length=1)


class SuiteSpec(BaseModel):
    """Static description of a live suite.

    `tasks` is derived from `task_fields`. Constraint weights are not fields.
    FORMAT placement is `TaskSuite.mirror`, so dumping a spec cannot leak it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    title: str
    description: str
    task_fields: tuple[TaskFields, ...]
    forbidden: tuple[str, ...]
    max_words: int
    hedging_note: str
    concise_note: str = ""
    version: str = "0.1"
    tasks: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _derive_tasks(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "tasks" in data:
                raise ValueError("tasks is derived from task_fields")
            names: list[str] = []
            for item in data.get("task_fields", ()):
                names.append(item["name"] if isinstance(item, dict) else item.name)
            data["tasks"] = names
        return data

    @model_validator(mode="after")
    def _spec_ok(self) -> SuiteSpec:
        if not self.task_fields:
            raise ValueError(f"{self.name}: task_fields is empty")
        if len(self.tasks) != len(set(self.tasks)):
            raise ValueError(f"{self.name}: duplicate task name")
        if self.max_words < 1:
            raise ValueError(f"{self.name}: max_words must be positive")
        if not self.forbidden:
            raise ValueError(f"{self.name}: forbidden phrases are empty")
        return self


class ModelRequest(BaseModel):
    """What a provider receives. `oracle` is only populated for providers that declare
    `needs_oracle` (the mock), so real providers never see ground truth."""

    sample_id: str
    system: str
    prompt: str
    max_tokens: int = 1024
    temperature: float = 0.0
    oracle: dict[str, Any] | None = None


class ModelResponse(BaseModel):
    text: str
    model: str
    provider: str
    latency_ms: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None


class CriterionResult(BaseModel):
    """Score for one rubric criterion on one sample."""

    name: str
    dimension: Dimension
    score: float = Field(ge=0.0, le=1.0)
    weight: float
    passed: bool
    expected: JsonValue = None
    actual: JsonValue = None
    detail: str = ""


class SampleResult(BaseModel):
    sample_id: str
    task: str
    tags: list[str]
    difficulty: str
    prompt: str
    response: str
    parsed: dict[str, Any] | None
    score: float = Field(ge=0.0, le=1.0)
    dimension_scores: dict[str, float]
    criteria: list[CriterionResult]
    failed_criteria: list[str]
    latency_ms: float
    error: str | None = None


class DimensionAggregate(BaseModel):
    mean: float
    n: int


class RunSummary(BaseModel):
    run_id: str
    suite: str
    suite_version: str
    provider: str
    model: str
    started_at: datetime
    finished_at: datetime
    n_samples: int
    n_errors: int
    mean_score: float
    pass_rate: float = Field(description="Share of samples with score >= pass_threshold.")
    pass_threshold: float
    by_dimension: dict[str, DimensionAggregate]
    by_task: dict[str, DimensionAggregate]
    by_criterion: dict[str, DimensionAggregate]


class RunConfig(BaseModel):
    suite: str
    provider: str
    model: str | None = None
    limit: int | None = None
    pass_threshold: float = 0.8
    judge_provider: str | None = Field(
        default=None, description="Provider used for LLM-as-judge criteria; None disables them."
    )
    seed: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RewardRecord(BaseModel):
    """One line of rewards.jsonl."""

    sample_id: str
    suite: str
    task: str
    prompt: str
    system: str
    response: str
    reward: float
    dimension_rewards: dict[str, float]
    failed_criteria: list[str]
    hard_constraint_violation: bool


TaskFields.model_rebuild()
FormatMirror.model_rebuild()
SuiteSpec.model_rebuild()
