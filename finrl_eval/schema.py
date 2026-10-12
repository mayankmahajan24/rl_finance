"""Pydantic models for a task suite and its samples."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


TaskFields.model_rebuild()
FormatMirror.model_rebuild()
SuiteSpec.model_rebuild()
