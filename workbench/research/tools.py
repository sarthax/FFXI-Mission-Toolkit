"""Typed, permission-aware tool registry for evidence-aware research sessions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .session import ResearchSessionStore


ACCESS_READ="READ"
ACCESS_PROPOSE="PROPOSE"
ACCESS_VALIDATE="VALIDATE"

PROFILE_ACCESS={
    "READ_ONLY_RESEARCH":{ACCESS_READ},
    "PROPOSE_CHANGES":{ACCESS_READ,ACCESS_PROPOSE},
    "VALIDATION_ORCHESTRATOR":{ACCESS_READ,ACCESS_VALIDATE},
}


@dataclass(frozen=True)
class ResearchTool:
    name: str
    description: str
    handler: Callable[..., Any]
    access: str = ACCESS_READ
    provenance_fields: tuple[str, ...] = (
        "evidence_id",
        "evidence_ids",
        "supporting_evidence_ids",
        "contradicting_evidence_ids",
    )


def _collect_evidence_ids(value: Any, fields: set[str]) -> tuple[str, ...]:
    found=set()

    def walk(node: Any) -> None:
        if isinstance(node,dict):
            for key,item in node.items():
                if key in fields:
                    if isinstance(item,str) and item:
                        found.add(item)
                    elif isinstance(item,(list,tuple,set)):
                        for entry in item:
                            if isinstance(entry,str) and entry:
                                found.add(entry)
                walk(item)
        elif isinstance(node,(list,tuple,set)):
            for item in node:
                walk(item)

    walk(value)
    return tuple(sorted(found))


class ResearchToolRegistry:
    def __init__(self):
        self._tools: dict[str,ResearchTool]={}

    def register(self, tool: ResearchTool) -> None:
        if tool.access not in {ACCESS_READ,ACCESS_PROPOSE,ACCESS_VALIDATE}:
            raise ValueError(f"Unsupported tool access level: {tool.access}")
        if tool.name in self._tools:
            raise ValueError(f"Duplicate research tool: {tool.name}")
        self._tools[tool.name]=tool

    def get(self, name: str) -> ResearchTool | None:
        return self._tools.get(name)

    def specs(self) -> tuple[dict[str,Any], ...]:
        return tuple(
            {
                "name":tool.name,
                "description":tool.description,
                "access":tool.access,
            }
            for tool in sorted(self._tools.values(),key=lambda item:item.name)
        )

    def call(
        self,
        name: str,
        args: dict[str,Any],
        *,
        permission_profile: str,
        session_store: ResearchSessionStore | None = None,
        research_session_id: str | None = None,
    ) -> dict[str,Any]:
        tool=self.get(name)
        if tool is None:
            result={"status":"ERROR","error":f"Unknown research tool: {name}"}
            if session_store and research_session_id:
                session_store.append_tool_call(
                    research_session_id,
                    tool_name=name,
                    args=args,
                    result=result,
                    status="ERROR",
                )
            return result

        allowed=PROFILE_ACCESS.get(permission_profile)
        if allowed is None:
            raise ValueError(f"Unknown permission profile: {permission_profile}")
        if tool.access not in allowed:
            result={
                "status":"DENIED",
                "error":f"Permission profile {permission_profile} cannot call {tool.access} tool {name}.",
            }
            if session_store and research_session_id:
                session_store.append_tool_call(
                    research_session_id,
                    tool_name=name,
                    args=args,
                    result=result,
                    status="DENIED",
                )
            return result

        try:
            raw=tool.handler(**args)
            result=raw if isinstance(raw,dict) else {"value":raw}
            status="ERROR" if result.get("error") else str(result.get("status") or "OK")
        except Exception as exc:
            result={"status":"ERROR","error":f"{type(exc).__name__}: {exc}"}
            status="ERROR"

        evidence_ids=_collect_evidence_ids(result,set(tool.provenance_fields))
        if session_store and research_session_id:
            session_store.append_tool_call(
                research_session_id,
                tool_name=name,
                args=args,
                result=result,
                status=status,
                evidence_ids=evidence_ids,
            )
        return result


def register_legacy_db_tools(registry: ResearchToolRegistry) -> None:
    """Expose current llm_db_tools only as explicit read-only compatibility tools."""
    import llm_db_tools

    for name,(handler,description) in llm_db_tools.TOOLS.items():
        registry.register(ResearchTool(
            name=f"db.{name}",
            description=description,
            handler=handler,
            access=ACCESS_READ,
        ))
