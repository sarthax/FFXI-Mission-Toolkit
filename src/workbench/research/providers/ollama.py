"""Direct Ollama provider adapter using the local HTTP API."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .base import ProviderCapabilities, ProviderResponse


class OllamaProviderError(RuntimeError):
    pass


class OllamaDirectProvider:
    provider_id="ollama"

    def __init__(self, *, base_url: str = "http://127.0.0.1:11434"):
        self.base_url=str(base_url).rstrip("/")

    def _request(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        url=f"{self.base_url}{path}"
        data=None
        headers={}
        method="GET"
        if payload is not None:
            data=json.dumps(payload).encode("utf-8")
            headers["Content-Type"]="application/json"
            method="POST"
        req=urllib.request.Request(url,data=data,headers=headers,method=method)
        try:
            with urllib.request.urlopen(req,timeout=timeout) as resp:
                value=json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as ex:
            body=ex.read().decode("utf-8",errors="replace")
            raise OllamaProviderError(f"HTTP {ex.code} from {url}: {body}") from ex
        except urllib.error.URLError as ex:
            raise OllamaProviderError(
                f"Could not reach Ollama at {url} ({ex.reason}). Is Ollama running?"
            ) from ex
        except (UnicodeDecodeError,json.JSONDecodeError) as ex:
            raise OllamaProviderError(f"Malformed JSON response from {url}") from ex
        if not isinstance(value,dict):
            raise OllamaProviderError(f"Unexpected response shape from {url}")
        return value

    def list_models(self) -> list[dict[str, Any]]:
        payload=self._request("/api/tags")
        rows=[]
        for model in payload.get("models",[]) or []:
            if not isinstance(model,dict):
                continue
            item=dict(model)
            item["id"]=str(item.get("model") or item.get("name") or "")
            rows.append(item)
        return rows

    def capabilities(self, model: str) -> ProviderCapabilities:
        try:
            info=self._request("/api/show",{"model":model})
        except OllamaProviderError:
            return ProviderCapabilities(metadata={"capability_probe":"unavailable"})
        caps={str(x).lower() for x in (info.get("capabilities") or [])}
        return ProviderCapabilities(
            chat=True,
            vision="vision" in caps,
            thinking="thinking" in caps,
            tools="tools" in caps or "tool" in caps,
            metadata={
                "reported_capabilities":sorted(caps),
                "details":dict(info.get("details") or {}),
                "model_info":dict(info.get("model_info") or {}),
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
        result=self._request(
            "/api/chat",
            {
                "model":model,
                "messages":messages,
                "stream":False,
                "options":{"temperature":temperature},
            },
            timeout=timeout,
        )
        message=result.get("message") or {}
        if not isinstance(message,dict) or "content" not in message:
            raise OllamaProviderError(f"Unexpected chat response shape: {result}")
        usage={
            key:result[key]
            for key in (
                "total_duration",
                "load_duration",
                "prompt_eval_count",
                "prompt_eval_cached_count",
                "prompt_eval_duration",
                "eval_count",
                "eval_duration",
            )
            if key in result
        }
        return ProviderResponse(
            content=str(message.get("content") or ""),
            usage=usage,
            provider_metadata={
                "provider_id":self.provider_id,
                "model":str(result.get("model") or model),
                "created_at":result.get("created_at"),
                "done":result.get("done"),
                "done_reason":result.get("done_reason"),
                "thinking":message.get("thinking"),
            },
        )
