"""Canonical Development entry point for Feature Trace.

The mature implementation is staged in ``_trace_impl`` during Phase C. Historical import names
are rebound only while that implementation loads so it consumes final Development services and
Core contracts without keeping Development -> product-implementation dependencies.

Scenario-driven additions live here as a compatibility-safe facade: existing callers keep the
unfiltered trace contract, while callers that pass ``mode=`` get focused traversal/presentation.
"""
from __future__ import annotations

import sys

import workbench.core.services as _legacy_services
from workbench.core.contracts import capture_row_locators as _capture_row_locators
from workbench.devtools.features import trace_catalog as _trace_catalog
from workbench.devtools.features.trace_generators import generators_for
from workbench.devtools.features.trace_modes import edge_allowed, mode_options, normalize_mode
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


def resolve_query(con, query: str, catalog_con=None) -> dict:
    """Rank and group Feature Trace search matches without manufacturing graph identity."""
    rows = _base_search_nodes(con, query, catalog_con)
    return resolve_candidates(query, rows).as_dict()


def trace(con, root: str, depth: int, direction: str,
          catalog_con=None, relationships=None, include_runtime_edges: bool = False,
          max_nodes: int = 5000, mode: str | None = None) -> dict:
    """Trace one root, optionally narrowing the returned evidence to a scenario mode.

    ``mode=None`` preserves the historical byte-for-byte behavior contract as far as callers are
    concerned.  Focused modes filter presentation after canonical traversal; they never create
    synthetic graph edges.  Provider/generator expansion is reported separately so later phases
    can add proven candidates without conflating them with persisted canonical relationships.
    """
    if mode is None:
        return _base_trace(
            con, root, depth, direction, catalog_con,
            relationships=relationships,
            include_runtime_edges=include_runtime_edges,
            max_nodes=max_nodes,
        )

    selected = normalize_mode(mode)
    effective_direction = direction
    if direction == "both" and selected.direction in {"in", "out"}:
        effective_direction = selected.direction
    result = _base_trace(
        con, root, depth, effective_direction, catalog_con,
        relationships=relationships,
        include_runtime_edges=include_runtime_edges or selected.include_runtime,
        max_nodes=max_nodes,
    )

    kept_edges = [edge for edge in result.get("edges", ()) if edge_allowed(edge, selected)]
    kept_ids = {root}
    for edge in kept_edges:
        kept_ids.add(edge.get("source_node"))
        kept_ids.add(edge.get("target_node"))
    result["edges"] = kept_edges
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
    # Lightweight root-kind mapping aligns the persisted graph with the central resolver/generator registry.
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
    }
    result["mode_options"] = mode_options()
    result["root_kind"] = root_kind
    result["generator_plan"] = [
        {
            "id": spec.generator_id,
            "label": spec.label,
            "phase": spec.phase,
            "evidence_domains": list(spec.evidence_domains),
        }
        for spec in generators_for(root_kind, selected.mode_id)
    ]
    result.setdefault("notes", []).append(
        "Trace mode narrows recorded evidence; generator_plan lists additional evidence adapters eligible for this scenario."
    )
    return result


__all__ = sorted({name for name in dir(_impl) if not name.startswith("_")} | {"resolve_query", "trace"})
