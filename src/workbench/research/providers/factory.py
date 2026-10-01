"""Factory for configured research-provider adapters."""
from __future__ import annotations

from .ollama import OllamaDirectProvider
from .openwebui import OpenWebUIProvider


def create_provider(
    provider_id: str,
    *,
    base_url: str | None = None,
):
    key=str(provider_id or "").strip().lower().replace("_","-")
    if key in {"openwebui","open-webui"}:
        return OpenWebUIProvider(base_url=base_url)
    if key in {"ollama","ollama-direct","direct-ollama"}:
        return OllamaDirectProvider(base_url=base_url or "http://127.0.0.1:11434")
    raise ValueError(f"Unsupported research provider: {provider_id}")
