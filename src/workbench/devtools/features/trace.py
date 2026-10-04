"""Canonical Development entry point for Feature Trace.

The mature implementation is staged in ``_trace_impl`` during Phase C. Historical import names
are rebound only while that implementation loads so it consumes final Development services and
Core contracts without keeping Development -> product-implementation dependencies.

Scenario-driven additions live here as a compatibility-safe facade: existing callers keep the
unfiltered trace contract, while callers that pass ``mode=`` get focused traversal/presentation.
The existing GUI can also opt into a mode without route changes by prefixing a query with
``@implementation``, ``@mission``, ``@triggers``, ``@effects``, ``@dependencies``, ``@runtime``,
``@identity``, ``@diagnose``, or ``@all``.
"""
from __future__ import annotations

from contextvars import ContextVar
import re
import sys

import workbench.core.services as _legacy_services
from workbench.core.contracts import capture_row_locators as _capture_row_locators
from workbench.devtools.features import trace_catalog as _trace_catalog
from workbench.devtools.features.canonical_closure import provider_canonical_relationships
from workbench.devtools.features.trace_expansion import provider_candidates
from workbench.devtools.features.trace_generators import generators_for
from workbench.devtools.features.trace_modes import MODE_BY_ID, edge_allowed, mode_options, normalize_mode
from workbench.devtools.features.trace_resolver import resolve_candidates

_ALIASES = {
    "workbench.core.services.feature_trace_catalog": _trace_catalog,
    "workbench.core.services.capture_integrity": _capture_row_locators,
}
_PREVIOUS_MODULES = {name: sys.modules.get(name) for name in _ALIASES}
_PREVIOUS_ATTRS = {
    "feature_trace_catalog": getattr(_legacy_services, "feature_trace_catalog", None),
    "capture_integrity": getattr(_legacy_services, "capture_integrity", None),
}

for _name, _module in _ALIASES.items():
    sys.modules[_name] = _module
setattr(_legacy_services, "feature_trace_catalog", _trace_catalog)
setattr(_legacy_services, "capture_integrity", _capture_row_locators)

try:
    from workbench.devtools.features import _trace_impl as _impl
finally:
    for _name, _previous in _PREVIOUS_MODULES.items():
        if _previous is None:
            sys.modules.pop(_name, None)
        else:
            sys.modules[_name] = _previous
    for _attr, _previous in _PREVIOUS_ATTRS.items():
        if _previous is None:
            try:
                delattr(_legacy_services, _attr)
            except AttributeError:
                pass
        else:
            setattr(_legacy_services, _attr, _previous)

for _export in dir(_impl):
    if not _export.startswith("__"):
        globals()[_export] = getattr(_impl, _export)

_base_trace = _impl.trace
_base_search_nodes = _impl.search_nodes
_base_node_info = _impl.node_info
_base_entity_query_diagnostics = _impl.entity_query_diagnostics
_base_entity_implementation_path = _impl.entity_implementation_path
_QUERY_MODE: ContextVar[str | None] = ContextVar("feature_trace_query_mode", default=None)
_MODE_PREFIX = re.compile(r"^\s*@([a-z][a-z0-9_-]*)\s+(.*?)\s*$", re.IGNORECASE | re.DOTALL)


def split_mode_query(query: str) -> tuple[str | None, str]:
    """Parse an optional ``@mode query`` prefix without changing ordinary searches."""
    text = str(query or "").strip()
    match = _MODE_PREFIX.match(text)
    if not match:
        return None, text
    mode = match.group(1).strip().lower().replace("-", "_")
    if mode not in MODE_BY_ID:
        return None, text
    return mode, match.group(2).strip()


def _query_text(query: str) -> str:
    mode, clean = split_mode_query(query)
    if mode:
        _QUERY_MODE.set(mode)
    return clean


def search_nodes(con, term: str, catalog_con=None):
    return _base_search_nodes(con, _query_text(term), catalog_con)


def node_info(con, node_id: str, catalog_con=None):
    return _base_node_info(con, _query_text(node_id), catalog_con)


def entity_query_diagnostics(graph_con, catalog_con, query: str) -> dict:
    return _base_entity_query_diagnostics(graph_con, catalog_con, _query_text(query))


def entity_implementation_path(graph_con, catalog_con, query: str, *, max_provider_depth: int = 4):
    return _base_entity_implementation_path(
        graph_con, catalog_con, _query_text(query), max_provider_depth=max_provider_depth
    )


def resolve_query(con, query: str, catalog_con=None) -> dict:
    """Rank and group Feature Trace search matches without manufacturing graph identity."""
    mode, clean = split_mode_query(query)
    if mode:
        _QUERY_MODE.set(mode)
    rows = _base_search_nodes(con, clean, catalog_con)
    result = resolve_candidates(clean, rows).as_dict()
    result["requested_mode"] = mode
    result["original_query"] = query
    return result


def _generated_display_edge(row: dict) -> dict:
    """Adapt one read-only generated candidate to the historical edge presentation shape."""
    metadata = dict(row.get("metadata") or {})
    metadata.update({
        "generated": True,
        "generator": row.get("generator"),
        "provider_evidence": True,
    })
    evidence = list(row.get("evidence") or ())
    return {
        "relationship_id": None,
        "source_node": row.get("source_node"),
        "target_node": row.get("target_node"),
        "relationship": row.get("relationship"),
        "evidence_id": None,
        "confidence": row.get("confidence") or "STRONG",
        "status": "GENERATED_EVIDENCE",
        "metadata": metadata,
        "metadata_json": None,
        "source_snapshot_id": None,
        "generated": True,
        "generator": row.get("generator"),
        "evidence": evidence,
    }


def _attach_provider_canonical_links(result: dict, graph_con, root: str, catalog_con=None) -> dict:
    """Attach exact cross-store provider links without adding canonical graph edges."""
    links = list(result.get("provider_relationships") or ())
    candidates = list(provider_canonical_relationships(graph_con, graph_con, root))
    if catalog_con is not None and catalog_con is not graph_con:
        candidates.extend(provider_canonical_relationships(graph_con, catalog_con, root))
    seen = {(row.get("relationship"), row.get("target_node")) for row in links}
    for row in candidates:
        key = (row.get("relationship"), row.get("target_node"))
        if key in seen:
            continue
        seen.add(key)
        links.append(row)
    result["provider_relationships"] = links
    return result


def trace(con, root: str, depth: int, direction: str,
          catalog_con=None, relationships=None, include_runtime_edges: bool = False,
          max_nodes: int = 5000, mode: str | None = None) -> dict:
    """Trace one root, optionally narrowing the returned evidence to a scenario mode.

    ``mode=None`` preserves historical behavior unless the current request explicitly used an
    ``@mode`` query prefix. Focused trace ``edges`` are presentation edges: persisted canonical
    edges plus clearly marked read-only generated provider evidence. ``canonical_edges`` retains
    the persisted-only subset, and nothing generated here is written to the graph database.
    """
    prefixed_mode, clean_root = split_mode_query(root)
    if prefixed_mode:
        _QUERY_MODE.set(prefixed_mode)
    root = clean_root
    requested_mode = mode or prefixed_mode or _QUERY_MODE.get()
    if requested_mode is None:
        result = _base_trace(
            con, root, depth, direction, catalog_con,
            relationships=relationships,
            include_runtime_edges=include_runtime_edges,
            max_nodes=max_nodes,
        )
        return _attach_provider_canonical_links(result, con, root, catalog_con)

    _QUERY_MODE.set(None)
    selected = normalize_mode(requested_mode)
    effective_direction = direction
    if direction == "both" and selected.direction in {"in", "out"}:
        effective_direction = selected.direction
    result = _base_trace(
        con, root, depth, effective_direction, catalog_con,
        relationships=relationships,
        include_runtime_edges=include_runtime_edges or selected.include_runtime,
        max_nodes=max_nodes,
    )
    result = _attach_provider_canonical_links(result, con, root, catalog_con)

    kept_edges = [edge for edge in result.get("edges", ()) if edge_allowed(edge, selected)]
    kept_ids = {root}
    for edge in kept_edges:
        kept_ids.add(edge.get("source_node"))
        kept_ids.add(edge.get("target_node"))
    result["canonical_edges"] = list(kept_edges)
    result["nodes"] = [node for node in result.get("nodes", ()) if node.get("node_id") in kept_ids]
    result["paths"] = [
        path for path in result.get("paths", ())
        if all(node in kept_ids for node in path.get("nodes", ()))
    ]
    result["provider_relationships"] = [
        link for link in result.get("provider_relationships", ())
        if edge_allowed({
            "relationship": link.get("relationship"),
            "confidence": link.get("confidence") or "EXACT",
            "status": link.get("status") or "DISCOVERED",
        }, selected)
    ]
    if not selected.include_runtime:
        result.pop("_runtime_edges", None)
        result["runtime_hierarchy"] = {"groups": [], "observation_count": 0, "group_count": 0, "capture_count": 0}
        result["runtime_observation_count"] = 0
        result["runtime_group_count"] = 0
        result["runtime_capture_count"] = 0

    root_info = next((node for node in result.get("nodes", ()) if node.get("node_id") == root), None) or _impl.node_info(con, root, catalog_con)
    reps = root_info.get("representations") or []
    root_type = str((reps[0] if reps else {}).get("node_type") or "FEATURE").upper()
    if root_type in {"NPC", "MOB", "INSTANCE_ENTITY", "CLIENT_IDENTITY", "ENTITY"}:
        root_kind = "entity"
    elif "MISSION" in root_type or "QUEST" in root_type:
        root_kind = "mission"
    elif "ITEM" in root_type:
        root_kind = "item"
    elif root_type in {"INSTANCE", "BATTLEFIELD"}:
        root_kind = "instance"
    elif root_type in {"SPELL", "ABILITY", "WEAPON_SKILL", "MOB_SKILL", "TRAIT"}:
        root_kind = "ability"
    elif root_type in {"CAPTURE", "CLIENT_SNAPSHOT"}:
        root_kind = "runtime"
    elif root_type in {"FUNCTION", "BINDING", "ARTIFACT", "BUILD_TARGET"}:
        root_kind = "implementation"
    else:
        root_kind = "feature"

    result["trace_mode"] = {
        "id": selected.mode_id,
        "label": selected.label,
        "question": selected.question,
        "effective_direction": effective_direction,
        "query_prefix": f"@{selected.mode_id}",
    }
    result["mode_options"] = mode_options()
    result["root_kind"] = root_kind

    generator_specs = generators_for(root_kind, selected.mode_id)
    source_con = catalog_con or con
    generated = provider_candidates(
        source_con,
        root,
        mode=selected.mode_id,
        max_depth=max(1, min(int(depth), 4)),
        max_nodes=min(max_nodes, 500),
    )
    generated_rows = [row.as_dict() for row in generated]
    generated_edges = [_generated_display_edge(row) for row in generated_rows]
    active_generators = {row.get("generator") for row in generated_rows}
    result["generated_relationships"] = generated_rows
    result["generated_relationship_count"] = len(generated_rows)
    result["edges"] = [*kept_edges, *generated_edges]

    existing_nodes = {node.get("node_id") for node in result.get("nodes", ())}
    for node_id in sorted({
        str(value) for edge in generated_edges
        for value in (edge.get("source_node"), edge.get("target_node")) if value
    }):
        if node_id in existing_nodes:
            continue
        info = _impl.node_info(con, node_id, catalog_con)
        if info.get("known"):
            result.setdefault("nodes", []).append(info)
            existing_nodes.add(node_id)

    result["generator_plan"] = [
        {
            "id": spec.generator_id,
            "label": spec.label,
            "phase": spec.phase,
            "evidence_domains": list(spec.evidence_domains),
            "active": spec.generator_id in active_generators,
            "generated_count": sum(1 for row in generated_rows if row.get("generator") == spec.generator_id),
        }
        for spec in generator_specs
    ]
    result.setdefault("notes", []).extend((
        "Trace mode narrows recorded evidence to the selected question.",
        "Focused display edges may include read-only generated provider evidence; canonical_edges contains only persisted graph relationships.",
        "Generated provider evidence is never silently written into the canonical graph.",
    ))
    return result


__all__ = sorted({name for name in dir(_impl) if not name.startswith("_")} | {
    "resolve_query", "split_mode_query", "search_nodes", "node_info",
    "entity_query_diagnostics", "entity_implementation_path", "trace",
})
