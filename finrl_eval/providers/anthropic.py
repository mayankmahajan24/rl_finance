from __future__ import annotations

import time
from typing import Any

import httpx

from finrl_eval.providers.base import ModelProvider, require_env
from finrl_eval.schema import ModelRequest, ModelResponse

API_URL = "https://api.anthropic.com/v1/messages"


class AnthropicProvider(ModelProvider):
    """Anthropic Messages API via httpx. Reads ANTHROPIC_API_KEY from the environment."""

    name = "anthropic"

    @classmethod
    def default_model(cls) -> str:
        return "claude-sonnet-4-5"

    def __init__(self, model: str | None = None, timeout: float = 120.0) -> None:
        super().__init__(model)
        self._api_key = require_env("ANTHROPIC_API_KEY")
        self._client = httpx.Client(timeout=timeout)

    def complete(self, request: ModelRequest) -> ModelResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "system": request.system,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        t0 = time.perf_counter()
        try:
            r = self._client.post(API_URL, json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as exc:
            return ModelResponse(
                text="", model=self.model, provider=self.name, error=f"{type(exc).__name__}: {exc}"
            )
        latency = (time.perf_counter() - t0) * 1000
        text = "".join(block.get("text", "") for block in data.get("content", []))
        usage = data.get("usage", {})
        return ModelResponse(
            text=text,
            model=data.get("model", self.model),
            provider=self.name,
            latency_ms=latency,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )
