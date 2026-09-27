"""Open WebUI provider adapter backed by the existing llm_client compatibility layer."""
from __future__ import annotations

from typing import Any

import llm_client

from .base import ProviderCapabilities, ProviderResponse


class OpenWebUIProvider:
    provider_id="openwebui"

    def __init__(self, *, base_url: str | None = None):
        self.base_url=base_url

    def list_models(self) -> list[dict[str, Any]]:
        return list(llm_client.list_models(base_url=self.base_url))

    def capabilities(self, model: str) -> ProviderCapabilities:
        match=next((row for row in self.list_models() if row.get("id")==model),None)
        if match is None:
            return ProviderCapabilities()
        caps=set(match.get("ollama",{}).get("capabilities",[]) or [])
        return ProviderCapabilities(
            chat=True,
            vision="vision" in caps,
            thinking="thinking" in caps,
            tools="tools" in caps or "tool" in caps,
            metadata={
                "reported_capabilities":sorted(caps),
                "details":dict(match.get("ollama",{}).get("details",{}) or {}),
            },
        )

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        temperature: float = 0.2,
        timeout: float = 60.0,
    ) -> ProviderResponse:
        result=llm_client.chat_messages(
            messages,
            model=model,
            temperature=temperature,
            timeout=timeout,
            base_url=self.base_url,
        )
        return ProviderResponse(
            content=str(result.get("content","")),
            usage=dict(result.get("usage",{}) or {}),
            provider_metadata={"provider_id":self.provider_id,"model":model},
        )
