from __future__ import annotations

from collections.abc import Callable

from finrl_eval.providers.base import ModelProvider, ProviderError

PROVIDERS: dict[str, Callable[..., ModelProvider]] = {}


def _register() -> None:
    from finrl_eval.providers.anthropic import AnthropicProvider
    from finrl_eval.providers.mock import MockProvider
    from finrl_eval.providers.openai import OpenAIProvider

    PROVIDERS.update(
        {
            MockProvider.name: MockProvider,
            AnthropicProvider.name: AnthropicProvider,
            OpenAIProvider.name: OpenAIProvider,
        }
    )


_register()


def get_provider(name: str, model: str | None = None, seed: int = 0) -> ModelProvider:
    try:
        factory = PROVIDERS[name]
    except KeyError as exc:
        raise ProviderError(f"Unknown provider {name!r}. Available: {sorted(PROVIDERS)}") from exc
    if name == "mock":
        return factory(model=model, seed=seed)
    return factory(model=model)


__all__ = ["PROVIDERS", "ModelProvider", "ProviderError", "get_provider"]
