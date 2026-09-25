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


def register_source_tools(registry: ResearchToolRegistry, crawler) -> None:
    """Register bounded source-search/read tools backed by a configured crawler."""
    registry.register(ResearchTool(
        name="source.search",
        description="Search configured source roots within bounded file/byte/type limits.",
        handler=crawler.search,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="source.read",
        description="Read one file from configured source roots within crawler policy limits.",
        handler=crawler.read,
        access=ACCESS_READ,
    ))


def register_graph_tools(registry: ResearchToolRegistry, reader) -> None:
    """Register bounded canonical graph discovery/trace tools."""
    registry.register(ResearchTool(
        name="graph.search",
        description="Search canonical Workbench graph records by id or display label.",
        handler=reader.search,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="graph.trace",
        description="Traverse canonical Workbench relationships with evidence/confidence/status.",
        handler=reader.trace,
        access=ACCESS_READ,
    ))


def register_domain_tools(registry: ResearchToolRegistry, reader) -> None:
    """Register typed read-only Workbench domain tools."""
    registry.register(ResearchTool(
        name="feature.inspect",
        description="Inspect a canonical feature across requirements, implementations, semantic relationships, and validation dimensions.",
        handler=reader.feature_inspect,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="entity.lookup",
        description="Resolve canonical entities by identifier, entity id, or display name and return identifiers/findings/evidence.",
        handler=reader.entity_lookup,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="binding.lookup",
        description="Resolve Lua binding names to canonical binding/C++ function records with evidence and wrapper-class context.",
        handler=reader.binding_lookup,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="packet.lookup",
        description="Inspect canonical packet relationships and resolved handler functions for an opcode.",
        handler=reader.packet_lookup,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="validation.inspect",
        description="Inspect canonical ValidationRun and ValidationResult records by feature, run, or subject.",
        handler=reader.validation_inspect,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="server.symbol",
        description="Inspect canonical C++ function symbols, linked Lua bindings, and implementation relationships.",
        handler=reader.server_symbol_lookup,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="server.enum",
        description="Inspect canonical enum/constant definitions and usage relationships.",
        handler=reader.server_enum_lookup,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="server.build-target",
        description="Inspect canonical build targets and relationships connecting implementation symbols/artifacts.",
        handler=reader.server_build_target_lookup,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="capability.inspect",
        description="Inspect canonical capability definitions, observations, and feature requirements.",
        handler=reader.capability_inspect,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="migration.inspect",
        description="Inspect canonical migration records, actions, and related feature evidence.",
        handler=reader.migration_inspect,
        access=ACCESS_READ,
    ))

    # Architecture-aligned aliases retained alongside the more explicit names.
    registry.register(ResearchTool(
        name="feature.check",
        description="Alias for feature.inspect.",
        handler=reader.feature_inspect,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="cpp.symbol",
        description="Alias for server.symbol.",
        handler=reader.server_symbol_lookup,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="enum.lookup",
        description="Alias for server.enum.",
        handler=reader.server_enum_lookup,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="build.target",
        description="Alias for server.build-target.",
        handler=reader.server_build_target_lookup,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="validation.status",
        description="Alias for validation.inspect.",
        handler=reader.validation_inspect,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="packet.handlers",
        description="Alias for packet.lookup focused on handler relationships.",
        handler=reader.packet_lookup,
        access=ACCESS_READ,
    ))


def register_extended_tools(
    registry: ResearchToolRegistry,
    *,
    capture_reader=None,
    reference_reader=None,
    client_reader=None,
) -> None:
    """Register read-only capture/reference/client-DAT research tool families."""
    if capture_reader is not None:
        registry.register(ResearchTool(
            name="capture.search",
            description="Search indexed runtime capture bundles by label/capturer/zone/mission.",
            handler=capture_reader.search,
            access=ACCESS_READ,
        ))
        registry.register(ResearchTool(
            name="capture.backtrace",
            description="Backtrace one indexed runtime capture into canonical server/client implementation evidence.",
            handler=capture_reader.backtrace,
            access=ACCESS_READ,
        ))
    if reference_reader is not None:
        registry.register(ResearchTool(
            name="reference.search",
            description="Search the bundled reference/wiki corpus. Results remain REFERENCE/INFERRED evidence.",
            handler=reference_reader.search,
            access=ACCESS_READ,
        ))
        registry.register(ResearchTool(
            name="reference.compare",
            description="Compare presence/revision metadata for explicit reference/wiki page titles.",
            handler=reference_reader.compare,
            access=ACCESS_READ,
        ))
    if client_reader is not None:
        registry.register(ResearchTool(
            name="client.capability",
            description="Inspect canonical client capability evidence and observations.",
            handler=client_reader.capability,
            access=ACCESS_READ,
        ))
        registry.register(ResearchTool(
            name="dat.lookup",
            description="Read one client item DAT record through the existing read-only DAT decoder.",
            handler=client_reader.dat_lookup,
            access=ACCESS_READ,
        ))
        registry.register(ResearchTool(
            name="dat.describe",
            description="Inspect client item DAT layout, record stride, category, and capacity without modifying files.",
            handler=client_reader.dat_describe,
            access=ACCESS_READ,
        ))


def register_proposal_tools(registry: ResearchToolRegistry, service) -> None:
    """Register proposal staging/status/verification tools with separated authority."""
    registry.register(ResearchTool(
        name="proposal.create",
        description="Stage a Finding/MigrationAction/ValidationResult proposal in a PROPOSE_CHANGES research session.",
        handler=service.create,
        access=ACCESS_PROPOSE,
    ))
    registry.register(ResearchTool(
        name="proposal.status",
        description="Read the current verification/promotion state of a staged research proposal.",
        handler=service.status,
        access=ACCESS_READ,
    ))
    registry.register(ResearchTool(
        name="proposal.verify",
        description="Run deterministic evidence/type checks on a staged proposal without canonical promotion.",
        handler=service.verify,
        access=ACCESS_VALIDATE,
    ))
    registry.register(ResearchTool(
        name="proposal.promote",
        description="Promote only a deterministically verified proposal into canonical Workbench records.",
        handler=service.promote,
        access=ACCESS_VALIDATE,
    ))
