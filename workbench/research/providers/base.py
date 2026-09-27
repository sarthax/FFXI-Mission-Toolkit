"""Provider-neutral contracts for evidence-aware research."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderCapabilities:
    chat: bool = True
    vision: bool = False
    thinking: bool = False
    tools: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    usage: dict[str, Any] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    provider_id: str

    def list_models(self) -> list[dict[str, Any]]: ...
    def capabilities(self, model: str) -> ProviderCapabilities: ...
    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        temperature: float = 0.2,
        timeout: float = 60.0,
    ) -> ProviderResponse: ...
