"""Ingest normalized mission truth/evidence payloads into the generic state-machine model.

This is intentionally an evidence adapter, not an LSB-specific Lua parser.  It lets
truth sets and later source extractors target the same behavioral contract.
"""
from __future__ import annotations

from typing import Any, Mapping

from .mission_state_machine import (
    DependencyGate, EventIdentity, MissionState, MissionStateMachine, MissionTransition,
    StateCondition, TransitionEffect,
)


def _effects_from_lifecycle(symbol: str, text: str) -> tuple[TransitionEffect,...]:
    lower=text.lower()
    effects=[]
    for needle,effect in (
        ("given","GRANT"),("grant","GRANT"),("required","REQUIRE"),
        ("consumed","CONSUME"),("removed","REMOVE"),("reissued","REISSUE"),
    ):
        if needle in lower and effect not in {x.effect for x in effects}:
            effects.append(TransitionEffect(effect,f"key_item:{symbol}"))
    return tuple(effects)


def ingest_branching_truth(payload: Mapping[str,Any]) -> MissionStateMachine:
    """Convert a WORKBENCH_MISSION_TRUTH_SET into a behavioral proof machine."""
    if payload.get("kind")!="WORKBENCH_MISSION_TRUTH_SET":
        raise ValueError("Unsupported mission evidence payload")

    subject=payload["subject"]
    server=payload["verified_server_state_machine"]
    states=[
        MissionState("mission:start",subject["mission"]),
        MissionState("mission:next",subject["next_mission"],terminal=True),
    ]
    transitions=[]

    mission=server["mission25"]
    transitions.append(MissionTransition(
        "mission:complete","mission:start","mission:next","EVENT_FINISH",
        event=EventIdentity(mission["zone"],int(mission["event_id"]),mission.get("npc")),
        effects=(TransitionEffect("COMPLETE",f"mission:{subject['mission']}"),),
        confidence="VERIFIED",
        metadata={"script":mission.get("script"),"event_args":mission.get("event_args",[])},
    ))

    gate=server.get("mission26_gate")
    if gate:
        logic="ANY" if gate.get("logic")=="OR" else "ALL"
        transitions.append(MissionTransition(
            "mission:branch-gate","mission:next","mission:next","DEPENDENCY_GATE",
            gate=DependencyGate(
                "mission:branch-alternatives",logic,
                tuple(StateCondition(f"quest:{q}","COMPLETE",True) for q in gate.get("accepted_quest_completions",[])),
            ),
            confidence="VERIFIED",
            implementation_status="EXPECTED_GAP" if gate.get("known_gap") else "PRESENT",
            metadata={"known_gap":gate.get("known_gap"),"script":gate.get("script"),"function":gate.get("function")},
        ))

    for branch_name,branch in server.items():
        if not branch_name.endswith("_branch") or not isinstance(branch,dict):
            continue
        if branch.get("scripts_found") is False:
            gap_state=f"branch:{branch_name}:missing"
            states.append(MissionState(gap_state,branch_name))
            transitions.append(MissionTransition(
                f"{branch_name}:missing","mission:next",gap_state,"EXPECTED_BRANCH",
                confidence="EXPECTED",implementation_status="MISSING",
                metadata={"status":branch.get("status")},
            ))
            continue
        for qkey in ("quest9","quest10"):
            quest=branch.get(qkey)
            if not isinstance(quest,dict):
                continue
            values=quest.get("vars",{}).get("Prog",[])
            qprefix=f"branch:{branch_name}:{qkey}"
            qstates=[]
            for v in values:
                sid=f"{qprefix}:prog:{v}"
                states.append(MissionState(sid,f"{quest.get('name',qkey)} Prog {v}",terminal=(v==values[-1] if values else False)))
                qstates.append(sid)
            if not qstates:
                continue
            # Preserve all observed zone/actor/CSID identities as evidence-bearing
            # self transitions until the Lua extractor can assign each CSID to an
            # exact Prog edge.
            for actor in quest.get("actors",[]):
                for event_id in actor.get("events",[]):
                    transitions.append(MissionTransition(
                        f"{qprefix}:event:{actor['zone']}:{actor['entity']}:{event_id}",
                        qstates[0],qstates[0],"OBSERVED_EVENT",
                        event=EventIdentity(actor["zone"],int(event_id),actor["entity"]),
                        confidence="VERIFIED",
                        metadata={"script":quest.get("script"),"unassigned_progress_edge":True},
                    ))
            for a,b in zip(qstates,qstates[1:]):
                transitions.append(MissionTransition(
                    f"{qprefix}:progress:{a.rsplit(':',1)[-1]}-{b.rsplit(':',1)[-1]}",
                    a,b,"PROGRESS_CHANGE",confidence="INFERRED",
                    metadata={"script":quest.get("script"),"variable":"Prog"},
                ))
            lifecycle=[]
            for ki in quest.get("key_items",[]):
                lifecycle.extend(_effects_from_lifecycle(ki["symbol"],ki.get("lifecycle","")))
            if lifecycle:
                transitions.append(MissionTransition(
                    f"{qprefix}:lifecycle",qstates[0],qstates[0],"LIFECYCLE_EVIDENCE",
                    effects=tuple(lifecycle),confidence="VERIFIED",
                ))
            if quest.get("implementation_gap"):
                transitions.append(MissionTransition(
                    f"{qprefix}:implementation-gap",qstates[-1],qstates[-1],"PLACEHOLDER",
                    confidence="VERIFIED",implementation_status="IMPLEMENTATION_GAP",
                    metadata={"gap":quest["implementation_gap"]},
                ))

    # The top-level mission is the only canonical entry here; quest branch
    # submachines remain reachable evidence until exact prerequisite edges are
    # assigned by source extraction.
    return MissionStateMachine(
        machine_id=f"machine:{payload['fixture_id']}",
        feature_id=f"mission:{subject['mission']}",
        states=tuple(states),
        transitions=tuple(transitions),
        entry_state_ids=("mission:start",),
        metadata={"source_revision":subject.get("source_revision"),"ingestion":"normalized_truth"},
    )
