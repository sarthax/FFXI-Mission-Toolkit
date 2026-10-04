"""Representative Feature Trace benchmark scenarios.

These are coverage contracts, not golden full graphs. A scenario describes the question being
asked and the minimum evidence concepts that must survive resolver/mode/provider expansion.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TraceScenario:
    scenario_id: str
    label: str
    root_kind: str
    mode: str
    required_terms: tuple[str, ...]
    forbidden_terms: tuple[str, ...] = ()
    required_generators: tuple[str, ...] = ()
    min_relationships: int = 1


SCENARIOS = (
    TraceScenario("wotg-fires", "WotG: Fires of Discontent", "mission", "mission", ("quest", "event", "state", "complete"), required_generators=("mission-state",)),
    TraceScenario("wotg-light", "WotG: Light in the Darkness", "mission", "mission", ("quest", "event", "key", "state"), required_generators=("mission-state",)),
    TraceScenario("wotg-cait-sith", "WotG: Cait Sith", "mission", "mission", ("mission", "event", "complete", "reward"), required_generators=("mission-state",)),
    TraceScenario("cop-mission", "CoP mission", "mission", "mission", ("mission", "event", "state")),
    TraceScenario("nation-mission", "Nation mission", "mission", "mission", ("mission", "event", "complete")),
    TraceScenario("dsp-quest", "DSP legacy quest", "mission", "mission", ("quest", "var", "event"), required_generators=("mission-state",)),
    TraceScenario("topaz-quest", "Topaz legacy quest", "mission", "mission", ("quest", "var", "event"), required_generators=("mission-state",)),
    TraceScenario("absolute-virtue", "Absolute Virtue", "entity", "implementation", ("spawn", "group", "pool", "script")),
    TraceScenario("overworld-mob", "Normal overworld mob", "entity", "implementation", ("spawn", "group", "pool"), required_generators=("lua-sql",)),
    TraceScenario("nm", "Notorious monster", "entity", "implementation", ("spawn", "group", "pool", "drop", "item"), required_generators=("lua-sql",), min_relationships=4),
    TraceScenario("npc", "NPC by name", "entity", "implementation", ("script", "event")),
    TraceScenario("npc-id", "NPC by numeric ID", "entity", "identity", ("identity", "server")),
    TraceScenario("door", "Door / prop", "entity", "triggers", ("trigger", "state")),
    TraceScenario("vendor", "Vendor NPC", "entity", "effects", ("item", "shop")),
    TraceScenario("battlefield", "Battlefield", "instance", "implementation", ("instance", "spawn", "complete")),
    TraceScenario("instance", "Instanced content", "instance", "implementation", ("instance", "entity", "script")),
    TraceScenario("item", "Item", "item", "dependencies", ("drop", "vendor", "recipe", "quest")),
    TraceScenario("key-item", "Key item", "item", "dependencies", ("quest", "mission", "grant")),
    TraceScenario("spell", "Spell", "ability", "implementation", ("bind", "script")),
    TraceScenario("ability", "Job ability", "ability", "implementation", ("bind", "script")),
    TraceScenario("mob-skill", "Mob skill", "ability", "implementation", ("mob", "bind")),
    TraceScenario("event", "Event / CSID", "feature", "triggers", ("event", "npc", "state")),
    TraceScenario("capture-entity", "Capture entity", "runtime", "identity", ("capture", "identity", "server")),
    TraceScenario("packet", "Packet observation", "runtime", "runtime", ("packet", "capture")),
    TraceScenario("client-model", "Client model identity", "runtime", "identity", ("client", "identity", "server")),
    TraceScenario("recipe", "Crafting recipe", "item", "dependencies", ("recipe", "item")),
    TraceScenario("drop", "Treasure/drop", "item", "dependencies", ("drop", "item"), required_generators=("lua-sql",)),
    TraceScenario("teleport", "Teleport progression", "feature", "effects", ("teleport", "state")),
    TraceScenario("timer", "Timer-driven script", "feature", "triggers", ("timer", "trigger", "effect")),
    TraceScenario("multi-npc-mission", "Multi-NPC mission", "mission", "mission", ("npc", "event", "state")),
    TraceScenario("shared-helper", "Shared Lua helper", "implementation", "implementation", ("call", "source", "bind")),
    TraceScenario("binding", "Lua to C++ binding", "implementation", "implementation", ("bind", "function", "source"), required_generators=("binding",)),
    TraceScenario("runtime-diagnose", "Runtime mismatch diagnosis", "runtime", "diagnose", ("mismatch", "identity", "evidence")),
    TraceScenario("wiki-conflict", "Wiki/reference conflict", "feature", "diagnose", ("conflict", "evidence")),
)

SCENARIO_BY_ID = {row.scenario_id: row for row in SCENARIOS}


def evaluate_terms(relationships: list[str], scenario: TraceScenario) -> dict:
    text = " ".join(str(value or "").replace("_", " ").casefold() for value in relationships)
    required = {term: term.casefold() in text for term in scenario.required_terms}
    forbidden = {term: term.casefold() in text for term in scenario.forbidden_terms}
    return {
        "scenario_id": scenario.scenario_id,
        "passed": all(required.values()) and not any(forbidden.values()),
        "required": required,
        "forbidden": forbidden,
    }


def evaluate_trace(result: dict, scenario: TraceScenario) -> dict:
    """Evaluate one focused trace result against a scenario's minimum useful contract."""
    edges=list(result.get("edges") or ())
    relationships=[str(edge.get("relationship") or "") for edge in edges]
    term_result=evaluate_terms(relationships,scenario)
    active_generators={
        str(row.get("id")) for row in (result.get("generator_plan") or ())
        if row.get("active")
    }
    generated_generators={
        str(row.get("generator") or row.get("generator_id") or "")
        for row in (result.get("generated_relationships") or ())
    }
    available_generators=active_generators|generated_generators
    generators={name:name in available_generators for name in scenario.required_generators}
    actual_mode=str((result.get("trace_mode") or {}).get("id") or "")
    actual_kind=str(result.get("root_kind") or "")
    checks={
        "mode": actual_mode==scenario.mode,
        "root_kind": actual_kind==scenario.root_kind,
        "relationship_count": len(edges)>=scenario.min_relationships,
        "required_terms": term_result["passed"],
        "required_generators": all(generators.values()),
    }
    return {
        "scenario_id":scenario.scenario_id,
        "label":scenario.label,
        "passed":all(checks.values()),
        "checks":checks,
        "required":term_result["required"],
        "forbidden":term_result["forbidden"],
        "generators":generators,
        "relationship_count":len(edges),
        "actual_mode":actual_mode,
        "actual_root_kind":actual_kind,
    }
