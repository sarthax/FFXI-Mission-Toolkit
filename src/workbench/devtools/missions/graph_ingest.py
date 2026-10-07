"""Project mission/quest state-machine evidence into the canonical Workbench graph.

The mission plugin owns interpretation of states, events, actors, gates, and effects. This
module emits only generic Workbench records so the core graph remains domain-neutral.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1

from workbench.core import graph as graph_store
from workbench.core.schema import Artifact, DependencyEdge, Entity, Evidence, Feature, Implementation

from .mission_lsb_extract import chain_event_transitions, correlate_lsb_handlers, mission_extraction_metrics
from .mission_state_machine import MissionStateMachine


@dataclass(frozen=True)
class MissionGraphProjection:
    feature: Feature
    artifact: Artifact
    implementation: Implementation
    evidence: tuple[Evidence, ...]
    entities: tuple[Entity, ...]
    edges: tuple[DependencyEdge, ...]


def _token(*parts: object) -> str:
    raw="|".join("" if p is None else str(p) for p in parts)
    return sha1(raw.encode("utf-8")).hexdigest()[:16]


def _state_node(feature_id: str, state_id: str) -> str:
    return f"mission-state:{feature_id}:{state_id}"


def _transition_node(feature_id: str, transition_id: str) -> str:
    return f"mission-transition:{feature_id}:{transition_id}"


def _event_node(source_family: str, zone: str, actor: str | None, event_id: int) -> str:
    return f"server-event:{source_family.casefold()}:{zone}:{actor or '*'}:{event_id}"


def _actor_node(source_family: str, zone: str, actor: str) -> str:
    return f"server-actor:{source_family.casefold()}:{zone}:{actor}"


def _subject_node(feature_id: str, subject: str) -> str:
    prefix=subject.split(":",1)[0].casefold()
    if prefix in {"mission_status","mission_var","local_var","timer","trade"} or subject in {"player:x","player_to_actor","interaction","message","player"}:
        return f"mission-subject:{feature_id}:{subject}"
    return subject


def _subject_type(subject: str) -> str:
    prefix=subject.split(":",1)[0].casefold()
    return {
        "key_item":"KEY_ITEM_SYMBOL",
        "battlefield":"BATTLEFIELD_SYMBOL",
        "entity":"SERVER_ENTITY_SYMBOL",
        "title":"TITLE_SYMBOL",
        "mission_status":"MISSION_STATE_CHANNEL",
        "mission_var":"MISSION_STATE_CHANNEL",
        "local_var":"MISSION_STATE_CHANNEL",
        "timer":"TIMER_SYMBOL",
        "trade":"TRADE_REQUIREMENT",
    }.get(prefix,"MISSION_SUBJECT")


def _source_evidence(
    feature_id: str,
    transition_id: str,
    source_family: str,
    source_path: str,
    source_snapshot_id: str | None,
    source_lines,
) -> Evidence:
    start=end=None
    if isinstance(source_lines,(tuple,list)) and len(source_lines)==2:
        start,end=source_lines
    location=source_path
    if start is not None:
        location=f"{source_path}:L{start}" + (f"-L{end}" if end is not None and end!=start else "")
    evidence_id=f"evidence:mission-source:{_token(feature_id,transition_id,source_path,start,end,source_snapshot_id)}"
    return Evidence(
        evidence_id,
        "SOURCE_CODE",
        source_family,
        location=location,
        snapshot=source_snapshot_id,
        notes="Static mission/quest source correlation; behavior is not runtime-validated by this evidence alone.",
    )


def _edge(
    edge_id: str,
    source: str,
    target: str,
    relationship: str,
    evidence_id: str | None,
    confidence: str,
    status: str,
    source_path: str,
    source_snapshot_id: str | None,
    notes: str | None=None,
) -> DependencyEdge:
    return DependencyEdge(
        edge_id,source,target,relationship,evidence_id,confidence,status,
        discovered_by="mission_source_graph_emit",
        source_location=source_path,
        notes=notes,
        source_snapshot_id=source_snapshot_id,
    )


def project_mission_graph(
    machine: MissionStateMachine,
    *,
    source_path: str,
    source_snapshot_id: str | None=None,
    source_family: str="LSB",
    feature_name: str | None=None,
) -> MissionGraphProjection:
    errors=machine.validate()
    if errors:
        raise ValueError("; ".join(errors))

    feature=Feature(
        machine.feature_id,
        feature_name or machine.feature_id,
        "MISSION",
        "mission",
        source_snapshot_id,
        status="DISCOVERED",
        metadata={"machine_id":machine.machine_id,"extractor":machine.metadata.get("extractor"),
                  "transition_count":len(machine.transitions),"source_family":source_family,
                  "extraction_metrics":mission_extraction_metrics(machine),
                  "completion_gate":(
                      {
                          "logic":machine.completion_gate.logic,
                          "conditions":[
                              {"subject":condition.subject,"operator":condition.operator,"value":condition.value}
                              for condition in machine.completion_gate.conditions
                          ],
                      }
                      if machine.completion_gate else None
                  )},
    )
    artifact_id=f"artifact:mission-source:{_token(machine.feature_id,source_path,source_snapshot_id)}"
    artifact=Artifact(
        artifact_id,"LUA",source_path,source_snapshot_id,None,machine.feature_id,
        {"machine_id":machine.machine_id,"source_family":source_family},
    )
    file_evidence=Evidence(
        f"evidence:mission-file:{_token(machine.feature_id,source_path,source_snapshot_id)}",
        "SOURCE_FILE",source_family,source_path,source_snapshot_id,
        "Mission/quest source artifact used for static extraction.",
    )
    implementation=Implementation(
        f"implementation:mission-source:{_token(machine.feature_id,source_path,source_snapshot_id)}",
        machine.feature_id,source_snapshot_id,None,artifact_id,"LUA","DISCOVERED",
        language="Lua",path=source_path,scope="MISSION_SOURCE",
        evidence_id=file_evidence.evidence_id,
        notes=["Static source presence; does not claim runtime correctness."],
    )

    entities={}
    edges=[]
    evidence={file_evidence.evidence_id:file_evidence}

    if machine.completion_gate:
        for index,condition in enumerate(machine.completion_gate.conditions):
            raw_subject=condition.subject
            subject=_subject_node(machine.feature_id,raw_subject)
            scoped=subject!=raw_subject
            entities.setdefault(subject,Entity(subject,_subject_type(raw_subject),raw_subject,{
                "scope":"feature" if scoped else "shared",
                **({"feature_id":machine.feature_id} if scoped else {}),
                "raw_subject":raw_subject,
            }))
            notes=f"mission completion gate: {condition.operator} {condition.value!r}"
            if condition.evidence_ids:
                notes+=f"; original_evidence_ids={list(condition.evidence_ids)!r}"
            edges.append(_edge(
                f"mission-completion-requires:{_token(machine.feature_id,index,subject,condition.operator,condition.value)}",
                machine.feature_id,subject,"REQUIRES",file_evidence.evidence_id,"INFERRED","DISCOVERED",
                source_path,source_snapshot_id,
                notes=notes,
            ))

    for state in machine.states:
        node=_state_node(machine.feature_id,state.state_id)
        entities[node]=Entity(node,"MISSION_STATE",state.label,{
            "feature_id":machine.feature_id,"state_id":state.state_id,"terminal":state.terminal,
            "entry":state.state_id in machine.entry_state_ids,"metadata":dict(state.metadata),
        })
        edges.append(_edge(
            f"mission-has-state:{_token(machine.feature_id,state.state_id)}",
            machine.feature_id,node,"HAS_STATE",file_evidence.evidence_id,"INFERRED","DISCOVERED",
            source_path,source_snapshot_id,
        ))

    for transition in machine.transitions:
        transition_node=_transition_node(machine.feature_id,transition.transition_id)
        source_lines=transition.metadata.get("source_lines") or transition.metadata.get("trigger_source_lines")
        source_ev=_source_evidence(
            machine.feature_id,transition.transition_id,source_family,source_path,source_snapshot_id,source_lines
        )
        evidence[source_ev.evidence_id]=source_ev
        edge_evidence=source_ev.evidence_id
        confidence=transition.confidence
        status=transition.implementation_status or "UNKNOWN"
        entities[transition_node]=Entity(
            transition_node,"MISSION_TRANSITION",transition.transition_id,{
                "feature_id":machine.feature_id,"trigger":transition.trigger,
                "confidence":confidence,"implementation_status":status,
                "source_lines":source_lines,"metadata":dict(transition.metadata),
                "original_evidence_ids":list(transition.evidence_ids),
                "post_effect_gate":(
                    {
                        "logic":transition.post_effect_gate.logic,
                        "conditions":[
                            {"subject":condition.subject,"operator":condition.operator,"value":condition.value}
                            for condition in transition.post_effect_gate.conditions
                        ],
                    }
                    if transition.post_effect_gate else None
                ),
            },
        )
        edges.append(_edge(
            f"mission-has-transition:{_token(machine.feature_id,transition.transition_id)}",
            machine.feature_id,transition_node,"HAS_TRANSITION",edge_evidence,confidence,status,
            source_path,source_snapshot_id,
        ))
        for helper_name in transition.metadata.get("helper_calls",()):
            helper_node=f"mission-helper:{machine.feature_id}:{helper_name}"
            entities.setdefault(helper_node,Entity(
                helper_node,"MISSION_HELPER",helper_name,{
                    "feature_id":machine.feature_id,
                    "helper":helper_name,
                    "source_family":source_family,
                },
            ))
            edges.append(_edge(
                f"mission-calls-helper:{_token(machine.feature_id,transition.transition_id,helper_name)}",
                transition_node,helper_node,"CALLS_HELPER",edge_evidence,confidence,status,
                source_path,source_snapshot_id,
                notes="Exact helper(player) call in this extracted handler path.",
            ))
        from_node=_state_node(machine.feature_id,transition.from_state)
        to_node=_state_node(machine.feature_id,transition.to_state)
        edges.append(_edge(
            f"mission-from-state:{_token(machine.feature_id,transition.transition_id,transition.from_state)}",
            transition_node,from_node,"FROM_STATE",edge_evidence,confidence,status,
            source_path,source_snapshot_id,
        ))
        edges.append(_edge(
            f"mission-to-state:{_token(machine.feature_id,transition.transition_id,transition.to_state)}",
            transition_node,to_node,"TO_STATE",edge_evidence,confidence,status,
            source_path,source_snapshot_id,
        ))

        if transition.event:
            event=transition.event
            event_node=_event_node(source_family,event.zone,event.actor,event.event_id)
            entities[event_node]=Entity(event_node,"MISSION_EVENT",event.key,{
                "source_family":source_family,"zone":event.zone,"actor":event.actor,"event_id":event.event_id,
            })
            edges.append(_edge(
                f"mission-triggered-by:{_token(machine.feature_id,transition.transition_id,event.key)}",
                transition_node,event_node,"TRIGGERED_BY_EVENT",edge_evidence,confidence,status,
                source_path,source_snapshot_id,
            ))
            if event.actor:
                actor_node=_actor_node(source_family,event.zone,event.actor)
                entities[actor_node]=Entity(actor_node,"SERVER_ACTOR",event.actor,{
                    "source_family":source_family,"zone":event.zone,"actor":event.actor,
                })
                edges.append(_edge(
                    f"mission-event-actor:{_token(event_node,actor_node)}",
                    event_node,actor_node,"EVENT_ACTOR",edge_evidence,confidence,status,
                    source_path,source_snapshot_id,
                ))

        conditions=transition.gate.conditions if transition.gate else ()
        for index,condition in enumerate(conditions):
            raw_subject=condition.subject
            subject=_subject_node(machine.feature_id,raw_subject)
            scoped=subject!=raw_subject
            entities.setdefault(subject,Entity(subject,_subject_type(raw_subject),raw_subject,{
                "scope":"feature" if scoped else "shared",
                **({"feature_id":machine.feature_id} if scoped else {}),
                "raw_subject":raw_subject,
            }))
            condition_notes=f"{condition.operator} {condition.value!r}"
            if condition.evidence_ids:
                condition_notes+=f"; original_evidence_ids={list(condition.evidence_ids)!r}"
            edges.append(_edge(
                f"mission-requires:{_token(machine.feature_id,transition.transition_id,index,subject,condition.operator,condition.value)}",
                transition_node,subject,"REQUIRES",edge_evidence,confidence,status,
                source_path,source_snapshot_id,
                notes=condition_notes,
            ))

        section_conditions=transition.metadata.get("section_eligibility_conditions",())
        for index,condition in enumerate(section_conditions):
            raw_subject=condition.get("subject")
            operator=condition.get("operator")
            value=condition.get("value")
            if not raw_subject or not operator:
                continue
            subject=_subject_node(machine.feature_id,raw_subject)
            scoped=subject!=raw_subject
            entities.setdefault(subject,Entity(subject,_subject_type(raw_subject),raw_subject,{
                "scope":"feature" if scoped else "shared",
                **({"feature_id":machine.feature_id} if scoped else {}),
                "raw_subject":raw_subject,
            }))
            edges.append(_edge(
                f"mission-section-requires:{_token(machine.feature_id,transition.transition_id,index,subject,operator,value)}",
                transition_node,subject,"REQUIRES",edge_evidence,"INFERRED","DISCOVERED",
                source_path,source_snapshot_id,
                notes=f"section eligibility: {operator} {value!r}",
            ))

        post_conditions=transition.post_effect_gate.conditions if transition.post_effect_gate else ()
        for index,condition in enumerate(post_conditions):
            raw_subject=condition.subject
            subject=_subject_node(machine.feature_id,raw_subject)
            scoped=subject!=raw_subject
            entities.setdefault(subject,Entity(subject,_subject_type(raw_subject),raw_subject,{
                "scope":"feature" if scoped else "shared",
                **({"feature_id":machine.feature_id} if scoped else {}),
                "raw_subject":raw_subject,
            }))
            condition_notes=f"post-effect {condition.operator} {condition.value!r}"
            if condition.evidence_ids:
                condition_notes+=f"; original_evidence_ids={list(condition.evidence_ids)!r}"
            edges.append(_edge(
                f"mission-post-requires:{_token(machine.feature_id,transition.transition_id,index,subject,condition.operator,condition.value)}",
                transition_node,subject,"REQUIRES",edge_evidence,confidence,status,
                source_path,source_snapshot_id,
                notes=condition_notes,
            ))

        for index,effect in enumerate(transition.effects):
            raw_subject=effect.subject
            subject=_subject_node(machine.feature_id,raw_subject)
            scoped=subject!=raw_subject
            entities.setdefault(subject,Entity(subject,_subject_type(raw_subject),raw_subject,{
                "scope":"feature" if scoped else "shared",
                **({"feature_id":machine.feature_id} if scoped else {}),
                "raw_subject":raw_subject,
            }))
            effect_notes=f"{effect.effect} {effect.value!r}"
            if effect.evidence_ids:
                effect_notes+=f"; original_evidence_ids={list(effect.evidence_ids)!r}"
            edges.append(_edge(
                f"mission-affects:{_token(machine.feature_id,transition.transition_id,index,effect.effect,subject,effect.value)}",
                transition_node,subject,"AFFECTS",edge_evidence,confidence,status,
                source_path,source_snapshot_id,
                notes=effect_notes,
            ))

    return MissionGraphProjection(
        feature,artifact,implementation,tuple(evidence.values()),tuple(entities.values()),tuple(edges)
    )


def persist_mission_graph(con, projection: MissionGraphProjection, *, commit: bool=True) -> None:
    for record in projection.evidence:
        graph_store.insert_record(con,record)
    graph_store.insert_record(con,projection.feature)
    graph_store.insert_record(con,projection.artifact)
    for record in projection.entities:
        graph_store.insert_record(con,record)
    graph_store.insert_record(con,projection.implementation)
    for record in projection.edges:
        graph_store.insert_record(con,record)
    if commit:
        con.commit()


def extract_and_project_lsb_mission(
    lua: str,
    *,
    feature_id: str,
    source_path: str,
    source_snapshot_id: str | None=None,
    feature_name: str | None=None,
) -> MissionGraphProjection:
    machine=chain_event_transitions(correlate_lsb_handlers(lua,feature_id=feature_id))
    return project_mission_graph(
        machine,source_path=source_path,source_snapshot_id=source_snapshot_id,
        source_family="LSB",feature_name=feature_name,
    )


if __name__ == "__main__":
    from workbench.devtools.missions.graph_ingest_cli import main

    main()
