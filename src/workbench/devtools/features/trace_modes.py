"""Scenario-focused traversal modes for Feature Trace.

Modes do not invent relationships. They rank/filter already recorded or provider-generated
relationships so the trace answers one question at a time instead of returning one giant graph.
Confidence ranks evidence within a relevant scenario; it never bypasses the selected mode.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TraceMode:
    mode_id: str
    label: str
    question: str
    preferred_relationship_terms: tuple[str, ...]
    preferred_node_types: tuple[str, ...] = ()
    include_runtime: bool = False
    direction: str = "both"


MODES = (
    TraceMode("implementation", "How is this implemented?", "Show source/server/client implementation wiring.",
              ("implement", "script", "bind", "source", "spawn", "group", "pool", "instance", "wiring", "uses", "defines"),
              ("FUNCTION", "BINDING", "ARTIFACT", "NPC", "MOB", "MOB_GROUP", "MOB_POOL", "INSTANCE")),
    TraceMode("triggers", "What triggers this?", "Show prerequisites, callers, interactions, events and inbound activation paths.",
              ("trigger", "require", "prereq", "depends", "call", "event", "interact", "trade", "zone", "spawn"), direction="in"),
    TraceMode("effects", "What does this change?", "Show downstream state changes, rewards, spawns and consequences.",
              ("effect", "set", "grant", "remove", "complete", "reward", "drop", "spawn", "start", "next", "changes"), direction="out"),
    TraceMode("dependencies", "What depends on this?", "Show downstream consumers and dependency closure.",
              ("depend", "require", "uses", "references", "consumes", "maps", "contains"), direction="out"),
    TraceMode("mission", "Mission progression", "Show mission/quest prerequisites, state, events, rewards and next steps.",
              ("mission", "quest", "event", "state", "var", "key_item", "prereq", "complete", "reward", "next", "interact", "trade")),
    TraceMode("runtime", "Runtime evidence", "Show capture/runtime observations and their implementation anchors.",
              ("runtime", "capture", "packet", "observation", "event", "entity"), include_runtime=True),
    TraceMode("identity", "Client ↔ server identity", "Show explicit identity mappings and source representations.",
              ("identity", "snapshot", "maps", "representation", "client", "server", "entity")),
    TraceMode("diagnose", "Why is this broken?", "Prioritize blockers, missing mappings, validation failures and contradictory evidence.",
              ("missing", "conflict", "invalid", "unresolved", "fail", "blocked", "mismatch", "validation", "drift", "evidence")),
    TraceMode("all", "Everything recorded", "Unfiltered evidence navigation.", tuple(), include_runtime=True),
)

MODE_BY_ID = {mode.mode_id: mode for mode in MODES}
DEFAULT_MODE = "implementation"


def normalize_mode(mode: str | None) -> TraceMode:
    return MODE_BY_ID.get(str(mode or "").strip().lower(), MODE_BY_ID[DEFAULT_MODE])


def relationship_relevance(relationship: str | None, mode: str | TraceMode | None) -> int:
    selected = mode if isinstance(mode, TraceMode) else normalize_mode(mode)
    if selected.mode_id == "all":
        return 100
    text = str(relationship or "").replace("_", " ").replace("-", " ").casefold()
    return sum(20 for term in selected.preferred_relationship_terms if term.casefold() in text)


def edge_allowed(edge: dict, mode: str | TraceMode | None) -> bool:
    selected = mode if isinstance(mode, TraceMode) else normalize_mode(mode)
    if selected.mode_id == "all":
        return True
    if edge.get("runtime_only") and not selected.include_runtime:
        return False
    status = str(edge.get("status") or "").upper()
    if status in {"REJECTED", "INVALID"}:
        return selected.mode_id == "diagnose"
    return relationship_relevance(edge.get("relationship"), selected) > 0


def mode_options() -> list[dict]:
    return [
        {"id": mode.mode_id, "label": mode.label, "question": mode.question,
         "direction": mode.direction, "include_runtime": mode.include_runtime}
        for mode in MODES
    ]
