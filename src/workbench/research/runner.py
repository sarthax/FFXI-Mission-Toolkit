"""Bounded provider/tool orchestration for evidence-aware research sessions."""
from __future__ import annotations

import json
from typing import Any

from .session import ResearchSessionStore
from .tools import ResearchToolRegistry


DEFAULT_SYSTEM_PROMPT = """You are a research client of the FFXI Workbench.
Use only the typed tools supplied to you for project evidence.
Preserve UNKNOWN/INFERRED/CONTRADICTED states and cite evidence ids when available.
Do not claim absence from a missing graph edge.
Do not treat wiki/reference evidence as server truth.
Do not apply changes. Any change proposal remains a proposal requiring deterministic or human review.

To call a tool, respond with exactly one JSON object:
{"tool":"tool.name","args":{...}}

When you have enough evidence, respond with a plain-text draft research report.
"""


def _tool_prompt(registry: ResearchToolRegistry) -> str:
    lines=["Available typed tools:"]
    for spec in registry.specs():
        lines.append(f"- {spec['name']} [{spec['access']}]: {spec['description']}")
    return "\n".join(lines)


def _parse_tool_call(content: str) -> tuple[str,dict[str,Any]] | None:
    text=content.strip()
    if not (text.startswith("{") and text.endswith("}")):
        return None
    try:
        payload=json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload,dict) or not isinstance(payload.get("tool"),str):
        return None
    args=payload.get("args",{})
    if not isinstance(args,dict):
        return None
    return payload["tool"],args


class ResearchRunner:
    def __init__(
        self,
        *,
        provider,
        registry: ResearchToolRegistry,
        session_store: ResearchSessionStore,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ):
        self.provider=provider
        self.registry=registry
        self.session_store=session_store
        self.system_prompt=system_prompt

    def run(
        self,
        research_session_id: str,
        *,
        max_tool_calls: int | None = None,
        max_provider_calls: int = 12,
        temperature: float = 0.1,
        timeout: float = 120.0,
    ) -> dict[str,Any]:
        session=self.session_store.get(research_session_id)
        if session is None:
            raise KeyError(research_session_id)

        budget=max_tool_calls
        if budget is None:
            budget=int(session.get("budgets",{}).get("max_tool_calls",8))
        if budget < 0:
            raise ValueError("max_tool_calls cannot be negative")
        if max_provider_calls <= 0:
            raise ValueError("max_provider_calls must be positive")

        messages=[
            {
                "role":"system",
                "content":self.system_prompt+"\n\n"+_tool_prompt(self.registry),
            },
            {
                "role":"user",
                "content":session["question"],
            },
        ]
        tool_calls=0
        provider_calls=0
        usage_records=[]
        final_report=None
        verification_state="DRAFT"

        while provider_calls < max_provider_calls:
            response=self.provider.chat(
                messages,
                model=session["model"],
                temperature=temperature,
                timeout=timeout,
            )
            provider_calls+=1
            usage_records.append(dict(response.usage or {}))
            content=response.content
            tool_call=_parse_tool_call(content)

            if tool_call is None:
                final_report=content
                break

            tool_name,args=tool_call
            if tool_calls >= budget:
                final_report=(
                    "Research stopped before completion because the typed tool-call budget "
                    f"({budget}) was exhausted. Last requested tool: {tool_name}."
                )
                verification_state="INCOMPLETE"
                break

            result=self.registry.call(
                tool_name,
                args,
                permission_profile=session["permission_profile"],
                session_store=self.session_store,
                research_session_id=research_session_id,
            )
            tool_calls+=1
            messages.append({"role":"assistant","content":content})
            messages.append({
                "role":"user",
                "content":"TOOL_RESULT\n"+json.dumps(result,sort_keys=True,default=str),
            })

        if final_report is None:
            final_report=(
                "Research stopped before completion because the provider-call budget "
                f"({max_provider_calls}) was exhausted."
            )
            verification_state="INCOMPLETE"

        self.session_store.finalize(
            research_session_id,
            final_report=final_report,
            verification_state=verification_state,
            usage={
                "provider_calls":provider_calls,
                "tool_calls":tool_calls,
                "provider_usage":usage_records,
            },
        )
        return {
            "status":"OK" if verification_state=="DRAFT" else verification_state,
            "research_session_id":research_session_id,
            "verification_state":verification_state,
            "provider_calls":provider_calls,
            "tool_calls":tool_calls,
            "final_report":final_report,
        }
