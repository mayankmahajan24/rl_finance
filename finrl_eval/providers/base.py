from __future__ import annotations

import abc
import os

from finrl_eval.schema import ModelRequest, ModelResponse


class ProviderError(RuntimeError):
    pass


class ModelProvider(abc.ABC):
    """Minimal chat-completion abstraction. Implementations must be deterministic for a
    given request when `temperature == 0` as far as the backing API allows."""

    name: str = "base"
    needs_oracle: bool = False

    def __init__(self, model: str | None = None) -> None:
        self.model = model or self.default_model()

    @classmethod
    @abc.abstractmethod
    def default_model(cls) -> str: ...

    @abc.abstractmethod
    def complete(self, request: ModelRequest) -> ModelResponse: ...

    def judge(self, system: str, prompt: str) -> str:
        """Used by LLM-as-judge criteria. Defaults to a plain completion."""
        resp = self.complete(ModelRequest(sample_id="judge", system=system, prompt=prompt))
        if resp.error:
            raise ProviderError(resp.error)
        return resp.text


def require_env(var: str) -> str:
    value = os.environ.get(var)
    if not value:
        raise ProviderError(f"{var} is not set. Export it or use `--provider mock` to run offline.")
    return value
