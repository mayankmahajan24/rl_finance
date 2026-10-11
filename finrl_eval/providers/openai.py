from __future__ import annotations

import os
import time
from typing import Any

import httpx

from finrl_eval.providers.base import ModelProvider, require_env
from finrl_eval.schema import ModelRequest, ModelResponse


class OpenAIProvider(ModelProvider):
    """OpenAI Chat Completions API via httpx. Reads OPENAI_API_KEY (and optionally
    OPENAI_BASE_URL for compatible gateways) from the environment."""

    name = "openai"

    @classmethod
    def default_model(cls) -> str:
        return "gpt-4o"

    def __init__(self, model: str | None = None, timeout: float = 120.0) -> None:
        super().__init__(model)
        self._api_key = require_env("OPENAI_API_KEY")
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self._url = f"{base}/chat/completions"
        self._client = httpx.Client(timeout=timeout)

    def complete(self, request: ModelRequest) -> ModelResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
        }
        headers = {"authorization": f"Bearer {self._api_key}", "content-type": "application/json"}
        t0 = time.perf_counter()
        try:
            r = self._client.post(self._url, json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as exc:
            return ModelResponse(
                text="", model=self.model, provider=self.name, error=f"{type(exc).__name__}: {exc}"
            )
        latency = (time.perf_counter() - t0) * 1000
        text = data["choices"][0]["message"].get("content") or ""
        usage = data.get("usage", {})
        return ModelResponse(
            text=text,
            model=data.get("model", self.model),
            provider=self.name,
            latency_ms=latency,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )
