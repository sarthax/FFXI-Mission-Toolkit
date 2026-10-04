"""Read-only scenario expansion for Feature Trace.

This module turns existing provider-native evidence into ranked relationship candidates without
writing canonical graph edges.  It is intentionally safe to run on arbitrary catalog roots.
"""
from __future__ import annotations

from collections import deque

from workbench.devtools.features.trace_catalog import catalog_node, provider_relationships
from workbench.devtools.features.trace_generators import RelationshipCandidate, dedupe_candidates
from workbench.devtools.features.trace_modes import edge_allowed, normalize_mode


def _generator_for_relationship(relationship: str) -> str:
    text = relationship.casefold()
    if any(term in text for term in ("identity", "snapshot", "representation", "client")):
        return "identity"
    if any(term in text for term in ("event", "csid")):
        return "event-csid"
    if any(term in text for term in ("bind", "function", "engine", "cpp")):
        return "binding"
    if any(term in text for term in ("capture", "packet", "runtime", "observation")):
        return "runtime"
    if any(term in text for term in ("mission", "quest", "state", "var", "reward", "complete")):
        return "mission-state"
    return "lua-sql"


def provider_candidates(catalog_con, root: str, *, mode: str = "implementation", max_depth: int = 3, max_nodes: int = 500) -> list[RelationshipCandidate]:
    """Recursively expand deterministic provider-native relationships from one catalog root."""
    selected = normalize_mode(mode)
    queue = deque([(root, 0)])
    visited = {root}
    rows: list[RelationshipCandidate] = []
    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for link in provider_relationships(catalog_con, current):
            target = str(link.get("target_node") or "")
            relationship = str(link.get("relationship") or "")
            if not target or not relationship:
                continue
            edge = {
                "relationship": relationship,
                "confidence": "EXACT",
                "status": "DISCOVERED",
            }
            if edge_allowed(edge, selected):
                rows.append(RelationshipCandidate(
                    source_node=current,
                    target_node=target,
                    relationship=relationship,
                    confidence="VERIFIED",
                    generator=_generator_for_relationship(relationship),
                    evidence=({
                        "kind": "PROVIDER_NATIVE",
                        "basis": link.get("basis") or "deterministic indexed provider relationship",
                        "provider_native": True,
                    },),
                    metadata={"depth": depth + 1},
                ))
            if target not in visited and len(visited) < max_nodes:
                visited.add(target)
                queue.append((target, depth + 1))
    return dedupe_candidates(rows)


def mission_state_candidates(machine, root_node: str) -> list[RelationshipCandidate]:
    """Project a normalized MissionStateMachine into relationship candidates.

    The machine may come from LSB or the DSP/Topaz compatibility adapter; Feature Trace therefore
    does not need framework-specific mission semantics once a machine has been normalized.
    """
    rows: list[RelationshipCandidate] = []
    for transition in getattr(machine, "transitions", ()):
        transition_node = f"{root_node}:transition:{transition.transition_id}"
        rows.append(RelationshipCandidate(root_node, transition_node, "HAS_MISSION_TRANSITION", "VERIFIED", "mission-state"))
        if transition.event is not None:
            event = transition.event
            event_node = f"event:{event.zone}:{event.event_id}"
            rows.append(RelationshipCandidate(transition_node, event_node, "TRIGGERS_EVENT", "VERIFIED", "mission-state"))
        gate = getattr(transition, "gate", None)
        for index, condition in enumerate(getattr(gate, "conditions", ()) if gate is not None else (), 1):
            subject = str(condition.subject)
            condition_node = f"{root_node}:condition:{transition.transition_id}:{index}"
            rows.append(RelationshipCandidate(transition_node, condition_node, "REQUIRES_STATE", "VERIFIED", "mission-state",
                                              metadata={"subject": subject, "operator": condition.operator, "expected": condition.value}))
        for index, effect in enumerate(getattr(transition, "effects", ()), 1):
            target = str(effect.subject)
            effect_node = f"{root_node}:effect:{transition.transition_id}:{index}:{target}"
            relationship = {
                "COMPLETE": "COMPLETES_MISSION_STATE",
                "GRANT": "GRANTS_REWARD",
                "GRANT_TITLE": "GRANTS_REWARD",
                "REMOVE": "REMOVES_STATE",
                "CONSUME": "REMOVES_STATE",
                "SET_VAR": "SETS_MISSION_STATE",
                "SET_STATE": "SETS_MISSION_STATE",
                "SET_CHANNEL": "SETS_MISSION_STATE",
                "START": "STARTS_NEXT_FEATURE",
            }.get(str(effect.effect).upper(), "APPLIES_MISSION_EFFECT")
            rows.append(RelationshipCandidate(transition_node, effect_node, relationship, "VERIFIED", "mission-state",
                                              metadata={"effect": effect.effect, "subject": target, "value": effect.value}))
    return dedupe_candidates(rows)


def binding_engine_candidates(engine: dict, root_node: str) -> list[RelationshipCandidate]:
    """Convert existing Behavior Inspector binding drill-down evidence into trace candidates."""
    rows: list[RelationshipCandidate] = []
    for call in engine.get("direct_calls") or ():
        qualified = str(call.get("qualified_name") or "").strip()
        if not qualified:
            continue
        lua_node = f"lua-api:{qualified}"
        rows.append(RelationshipCandidate(root_node, lua_node, "CALLS_LUA_API", "VERIFIED", "binding",
                                          evidence=({"kind": "LUA_SYNTAX", "line": call.get("line"), "source_line": call.get("source_line")},)))
        binding = call.get("binding") or {}
        status = str(binding.get("status") or "")
        for loc in binding.get("locations") or ():
            target = f"cpp:{loc.get('class')}:{qualified}:{loc.get('file')}:{loc.get('line')}"
            confidence = "VERIFIED" if status in {"EXACT", "MATCHED"} else "STRONG"
            rows.append(RelationshipCandidate(lua_node, target, "BINDS_CPP_FUNCTION", confidence, "binding",
                                              evidence=({"kind": "BINDING_REGISTRATION", "file": loc.get("file"), "line": loc.get("line")},)))
    return dedupe_candidates(rows)
