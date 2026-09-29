"""Generic scripted-entity behavior representation and canonical graph projection.

This model is intentionally not mission-specific. It represents event hooks and behavioral rules
for scripted entities such as notorious monsters, escorts, interactive props, or other runtime
actors whose behavior depends on timers, thresholds, other entities, player actions, combat state,
or cleanup/override logic.

Source-family extractors may populate this model later; the model itself does not infer behavior.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha1
from typing import Any, Mapping

from workbench.core import graph
from workbench.core.schema import DependencyEdge, Entity, Evidence, Feature


@dataclass(frozen=True)
class BehaviorCondition:
    subject: str
    operator: str
    value: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BehaviorEffect:
    effect: str
    target: str | None = None
    value: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BehaviorRule:
    rule_id: str
    kind: str
    subject: str
    trigger: str | None = None
    target: str | None = None
    conditions: tuple[BehaviorCondition, ...] = ()
    effects: tuple[BehaviorEffect, ...] = ()
    confidence: str = "UNKNOWN"
    implementation_status: str = "UNKNOWN"
    evidence_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScriptedBehaviorMap:
    map_id: str
    feature_id: str
    subject: str
    zone: str | None
    hooks: tuple[str, ...]
    rules: tuple[BehaviorRule, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScriptedBehaviorProjection:
    feature: Feature
    evidence: tuple[Evidence, ...]
    entities: tuple[Entity, ...]
    edges: tuple[DependencyEdge, ...]


def _token(*parts: object) -> str:
    raw="|".join("" if p is None else str(p) for p in parts)
    return sha1(raw.encode("utf-8")).hexdigest()[:16]


def _subject_node(map_id: str, subject: str) -> str:
    return f"behavior-subject:{_token(map_id,subject)}"


def _rule_node(map_id: str, rule_id: str) -> str:
    return f"behavior-rule:{_token(map_id,rule_id)}"


def _hook_node(map_id: str, hook: str) -> str:
    return f"behavior-hook:{_token(map_id,hook)}"


def behavior_map_from_probe(
    payload: Mapping[str, Any],
    *,
    feature_id: str | None = None,
) -> ScriptedBehaviorMap:
    """Adapt a machine-readable scripted behavior proof into the generic model.

    The adapter preserves free-form source observations in rule metadata instead of pretending a
    prose condition has been structurally decoded when the proof did not provide that structure.
    """
    if payload.get("kind") != "SCRIPTED_NM_BEHAVIOR_PROBE":
        raise ValueError("Unsupported scripted behavior proof payload")
    subject=str(payload.get("subject") or "unknown")
    fid=feature_id or f"scripted-behavior:{subject}"
    map_id=f"behavior-map:{_token(fid,subject,payload.get('zone'))}"
    rules=[]

    for index,row in enumerate(payload.get("dependencies",()),1):
        kind=str(row.get("kind") or "behavior")
        rule_subject=str(row.get("subject") or row.get("from") or subject)
        target=(str(row["to"]) if row.get("to") is not None else None)
        trigger=None
        conditions=[]
        effects=[]

        if kind=="spawn_from_death":
            trigger="ENTITY_DEATH"
            if row.get("condition") is not None:
                conditions.append(BehaviorCondition(
                    rule_subject,"SOURCE_CONDITION",row.get("condition")
                ))
            effects.append(BehaviorEffect(
                "SPAWN_ENTITY",target,row.get("delay_seconds"),
                {"delay_seconds":row.get("delay_seconds")},
            ))
        elif kind=="inherit_runtime_target":
            trigger="SPAWN"
            effects.append(BehaviorEffect(
                "TRANSFER_RUNTIME_STATE",target,row.get("state"),
                {"state_kind":"target_or_claim"},
            ))
        elif kind=="cross_entity_state":
            trigger="STATE_TRANSFER"
            effects.append(BehaviorEffect(
                "TRANSFER_RUNTIME_STATE",target,row.get("state"),
                {"state_kind":"cross_entity_state"},
            ))
        elif kind=="hp_threshold":
            trigger="COMBAT_TICK"
            conditions.append(BehaviorCondition(
                rule_subject,"HPP_AT_OR_BELOW",row.get("threshold_hpp")
            ))
            effects.append(BehaviorEffect("APPLY_BEHAVIOR_PHASE",rule_subject,row.get("effect")))
        elif kind=="timed_random_action":
            trigger="TIMER"
            conditions.append(BehaviorCondition(
                rule_subject,"RANDOM_INTERVAL_SECONDS",row.get("range_seconds")
            ))
            effects.append(BehaviorEffect("SELECT_ACTION",rule_subject,row.get("effect")))
        elif kind=="player_action_response":
            trigger="PLAYER_ACTION"
            conditions.append(BehaviorCondition("player","ACTION",row.get("input")))
            effects.append(BehaviorEffect("RESPOND_TO_ACTION",rule_subject,row.get("effect")))
        elif kind=="magic_response":
            trigger="MAGIC_HIT"
            conditions.append(BehaviorCondition("player","MAGIC_INPUT",row.get("input")))
            effects.append(BehaviorEffect("ADJUST_COMBAT_STATE",rule_subject,row.get("effect")))
        elif kind=="spell_override":
            trigger="SPELL_PRECAST"
            effects.append(BehaviorEffect("OVERRIDE_SPELL",rule_subject,row.get("effect")))
        elif kind=="cleanup":
            trigger="CLEANUP"
            conditions.append(BehaviorCondition(
                rule_subject,"TRIGGER_IN",row.get("trigger")
            ))
            effects.append(BehaviorEffect("CLEANUP_RELATED_ENTITIES",rule_subject,row.get("effect")))
        elif kind=="loot_override":
            trigger="DEATH_REWARD"
            conditions.append(BehaviorCondition(
                rule_subject,"SOURCE_CONDITION",row.get("condition")
            ))
            effects.append(BehaviorEffect("OVERRIDE_LOOT",rule_subject,row.get("effect")))
        else:
            trigger=str(row.get("trigger") or "UNKNOWN")
            effects.append(BehaviorEffect("SOURCE_OBSERVED_EFFECT",target,row.get("effect")))

        rules.append(BehaviorRule(
            rule_id=f"{kind}:{index}",
            kind=kind,
            subject=rule_subject,
            trigger=trigger,
            target=target,
            conditions=tuple(conditions),
            effects=tuple(effects),
            confidence="EXPECTED",
            implementation_status="UNVERIFIED",
            metadata={"source_observation":dict(row)},
        ))

    return ScriptedBehaviorMap(
        map_id=map_id,
        feature_id=fid,
        subject=subject,
        zone=(str(payload["zone"]) if payload.get("zone") is not None else None),
        hooks=tuple(str(x) for x in payload.get("hooks",())),
        rules=tuple(rules),
        metadata={
            "proof_kind":payload.get("kind"),
            "sources":list(payload.get("sources",())),
            "generic_map_required":list(payload.get("generic_map_required",())),
        },
    )


def project_scripted_behavior(
    behavior: ScriptedBehaviorMap,
    *,
    source_snapshot_id: str | None = None,
    evidence_source: str = "SCRIPTED_BEHAVIOR_PROOF",
    evidence_location: str | None = None,
) -> ScriptedBehaviorProjection:
    """Project a scripted behavior map into generic Workbench graph records."""
    feature=Feature(
        behavior.feature_id,
        behavior.subject,
        "SCRIPTED_ENTITY_BEHAVIOR",
        "combat",
        source_snapshot_id,
        status="DISCOVERED",
        metadata={
            "behavior_map_id":behavior.map_id,
            "zone":behavior.zone,
            "hook_count":len(behavior.hooks),
            "rule_count":len(behavior.rules),
            **dict(behavior.metadata),
        },
    )
    evidence_id=f"evidence:scripted-behavior:{_token(behavior.map_id,evidence_source,evidence_location,source_snapshot_id)}"
    base_evidence=Evidence(
        evidence_id,
        "REFERENCE_PROOF" if evidence_source=="SCRIPTED_BEHAVIOR_PROOF" else "SERVER_SOURCE",
        evidence_source,
        evidence_location,
        source_snapshot_id,
        "Scripted behavior projection; static/proof evidence does not claim runtime validation.",
    )

    evidence={base_evidence.evidence_id:base_evidence}
    entities={}
    edges=[]
    map_node=f"scripted-behavior-map:{_token(behavior.map_id)}"
    entities[map_node]=Entity(
        map_node,
        "SCRIPTED_BEHAVIOR_MAP",
        behavior.subject,
        {
            "map_id":behavior.map_id,
            "feature_id":behavior.feature_id,
            "zone":behavior.zone,
            **dict(behavior.metadata),
        },
    )
    edges.append(DependencyEdge(
        f"behavior-map:{_token(behavior.feature_id,map_node)}",
        behavior.feature_id,map_node,"HAS_BEHAVIOR_MAP",
        evidence_id,"EXPECTED","DISCOVERED",
        discovered_by="scripted_behavior_projection",
        source_location=evidence_location,
        source_snapshot_id=source_snapshot_id,
    ))

    root_subject=_subject_node(behavior.map_id,behavior.subject)
    entities[root_subject]=Entity(
        root_subject,"SCRIPTED_ENTITY",behavior.subject,
        {"zone":behavior.zone,"behavior_map_id":behavior.map_id,"root_subject":True},
    )
    edges.append(DependencyEdge(
        f"behavior-root-subject:{_token(map_node,root_subject)}",
        map_node,root_subject,"BEHAVIOR_SUBJECT",
        evidence_id,"EXPECTED","DISCOVERED",
        discovered_by="scripted_behavior_projection",
        source_location=evidence_location,
        source_snapshot_id=source_snapshot_id,
    ))

    for hook in behavior.hooks:
        hook_node=_hook_node(behavior.map_id,hook)
        entities[hook_node]=Entity(
            hook_node,"ENTITY_HOOK",hook,
            {"behavior_map_id":behavior.map_id,"hook":hook},
        )
        edges.append(DependencyEdge(
            f"behavior-hook:{_token(map_node,hook_node)}",
            map_node,hook_node,"HAS_HOOK",
            evidence_id,"EXPECTED","DISCOVERED",
            discovered_by="scripted_behavior_projection",
            source_location=evidence_location,
            source_snapshot_id=source_snapshot_id,
        ))

    for rule in behavior.rules:
        rule_node=_rule_node(behavior.map_id,rule.rule_id)
        rule_evidence_id=evidence_id
        rule_location=evidence_location
        if isinstance(rule.metadata,Mapping):
            source_path=rule.metadata.get("source_path")
            source_lines=rule.metadata.get("source_lines")
            if source_path:
                start=end=None
                if isinstance(source_lines,(tuple,list)) and len(source_lines)==2:
                    start,end=source_lines
                rule_location=str(source_path)
                if start is not None:
                    rule_location+=f":L{start}" + (f"-L{end}" if end is not None and end!=start else "")
                rule_evidence_id=f"evidence:scripted-rule:{_token(behavior.map_id,rule.rule_id,rule_location,source_snapshot_id)}"
                evidence[rule_evidence_id]=Evidence(
                    rule_evidence_id,
                    "SERVER_SOURCE",
                    evidence_source if evidence_source!="SCRIPTED_BEHAVIOR_PROOF" else "LSB_LUA",
                    rule_location,
                    source_snapshot_id,
                    "Static Lua source span supporting this scripted behavior rule; runtime behavior remains separately validated.",
                )
        entities[rule_node]=Entity(
            rule_node,"BEHAVIOR_RULE",rule.kind,
            {
                "behavior_map_id":behavior.map_id,
                "rule_id":rule.rule_id,
                "kind":rule.kind,
                "trigger":rule.trigger,
                "subject":rule.subject,
                "target":rule.target,
                "conditions":[
                    {
                        "subject":condition.subject,
                        "operator":condition.operator,
                        "value":condition.value,
                        "metadata":dict(condition.metadata),
                    }
                    for condition in rule.conditions
                ],
                "effects":[
                    {
                        "effect":effect.effect,
                        "target":effect.target,
                        "value":effect.value,
                        "metadata":dict(effect.metadata),
                    }
                    for effect in rule.effects
                ],
                "implementation_status":rule.implementation_status,
                "metadata":dict(rule.metadata),
            },
        )
        edges.append(DependencyEdge(
            f"behavior-rule:{_token(map_node,rule_node)}",
            map_node,rule_node,"HAS_BEHAVIOR_RULE",
            rule_evidence_id,rule.confidence,"DISCOVERED",
            discovered_by="scripted_behavior_projection",
            source_location=rule_location,
            source_snapshot_id=source_snapshot_id,
        ))

        named_subjects={rule.subject}
        if rule.target:
            named_subjects.add(rule.target)
        source_observation=rule.metadata.get("source_observation") if isinstance(rule.metadata,Mapping) else None
        if isinstance(source_observation,Mapping):
            for key in ("from","to","subject"):
                value=source_observation.get(key)
                if isinstance(value,str) and value:
                    named_subjects.add(value)

        for named in sorted(named_subjects):
            subject_node=_subject_node(behavior.map_id,named)
            entities.setdefault(subject_node,Entity(
                subject_node,
                "SCRIPTED_ENTITY" if named not in {"player"} else "RUNTIME_ACTOR",
                named,
                {"behavior_map_id":behavior.map_id,"root_subject":named==behavior.subject},
            ))
            relation="BEHAVIOR_SUBJECT" if named==rule.subject else "REFERENCES_ACTOR"
            edges.append(DependencyEdge(
                f"behavior-rule-subject:{_token(rule_node,subject_node,relation)}",
                rule_node,subject_node,relation,
                rule_evidence_id,rule.confidence,"DISCOVERED",
                discovered_by="scripted_behavior_projection",
                source_location=rule_location,
                source_snapshot_id=source_snapshot_id,
            ))
            # A non-root named actor referenced by a behavior rule is part of dependency review.
            if named not in {behavior.subject,"player"}:
                edges.append(DependencyEdge(
                    f"behavior-rule-requires:{_token(rule_node,subject_node)}",
                    rule_node,subject_node,"REQUIRES",
                    rule_evidence_id,rule.confidence,"DISCOVERED",
                    discovered_by="scripted_behavior_projection",
                    source_location=rule_location,
                    notes="Cross-entity scripted behavior requires this referenced runtime actor to be reviewed.",
                    source_snapshot_id=source_snapshot_id,
                ))

    return ScriptedBehaviorProjection(
        feature,
        tuple(evidence.values()),
        tuple(entities.values()),
        tuple(edges),
    )


def persist_scripted_behavior(con, projection: ScriptedBehaviorProjection, *, commit: bool=True) -> None:
    for evidence in projection.evidence:
        graph.insert_record(con,evidence)
    graph.insert_record(con,projection.feature)
    for entity in projection.entities:
        graph.insert_record(con,entity)
    for edge in projection.edges:
        graph.insert_record(con,edge)
    if commit:
        con.commit()
