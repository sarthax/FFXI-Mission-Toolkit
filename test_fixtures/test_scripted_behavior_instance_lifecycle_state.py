#!/usr/bin/env python3
"""Regression for first-class instance lifecycle stage/progress state."""
from __future__ import annotations

from workbench.plugins.domain.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior


SCRIPT=r'''
local entity = {}

entity.onInstanceCreated = function(instance)
    local stage = instance:getStage()
    local progress = instance:getProgress()

    if stage == 0 then
        instance:setStage(1)
        instance:setProgress(9)
    end

    if stage == dynamicStage then
        instance:setStage(2)
    end

    if progress < 3 then
        instance:setProgress(progress + 1)
    end

    instance:setLocalVar("wave", 2)
end

return entity
'''


def main():
    behavior=extract_lsb_scripted_behavior(
        SCRIPT,
        feature_id="feature:instance-lifecycle-state",
        subject="Instance Controller",
        zone="TEST",
        source_path="scripts/zones/Test/instances/Test.lua",
    )

    states=[]
    for rule in behavior.rules:
        if rule.kind!="state_flow":
            continue
        for condition in rule.conditions:
            states.append(("READ",condition.subject,condition.metadata))
        for effect in rule.effects:
            states.append(("WRITE",effect.target,effect.metadata))

    lifecycle=[
        row for row in states
        if row[2].get("scope")=="INSTANCE_LIFECYCLE"
    ]
    generic=[
        row for row in states
        if row[2].get("scope")=="INSTANCE_LOCAL"
    ]

    lifecycle_ids={row[1] for row in lifecycle}
    assert "state:INSTANCE_LIFECYCLE:instance:stage" in lifecycle_ids,lifecycle
    assert "state:INSTANCE_LIFECYCLE:instance:progress" in lifecycle_ids,lifecycle

    stage_reads=[row for row in lifecycle if row[0]=="READ" and row[2].get("name")=="stage"]
    stage_writes=[row for row in lifecycle if row[0]=="WRITE" and row[2].get("name")=="stage"]
    progress_reads=[row for row in lifecycle if row[0]=="READ" and row[2].get("name")=="progress"]
    progress_writes=[row for row in lifecycle if row[0]=="WRITE" and row[2].get("name")=="progress"]

    assert stage_reads and stage_writes,lifecycle
    assert progress_reads and progress_writes,lifecycle
    assert any(row[2].get("method")=="setStage" for row in stage_writes),stage_writes
    assert any(row[2].get("method")=="setProgress" for row in progress_writes),progress_writes

    assert any(row[2].get("name")=="wave" for row in generic),generic

    transitions=[
        rule for rule in behavior.rules
        if rule.kind=="state_transition"
        and rule.metadata.get("transition_form")=="INSTANCE_LIFECYCLE_LITERAL_IF"
    ]
    assert len(transitions)==1,transitions
    transition=transitions[0]
    assert transition.metadata["state_id"]=="state:INSTANCE_LIFECYCLE:instance:stage",transition
    assert transition.metadata["selector_alias"]=="stage",transition.metadata
    assert transition.metadata["if_literal"]=="0",transition.metadata
    assert transition.conditions[0].subject=="state:INSTANCE_LIFECYCLE:instance:stage",transition.conditions
    assert transition.conditions[0].value=="0",transition.conditions
    assert transition.effects[0].target=="state:INSTANCE_LIFECYCLE:instance:stage",transition.effects
    assert transition.effects[0].value=="1",transition.effects

    # Cross-lifecycle writes, computed equality predicates, and non-equality guards stay generic.
    assert not any(rule.metadata.get("if_literal")=="dynamicStage" for rule in transitions),transitions
    assert not any(rule.metadata.get("state_name")=="progress" for rule in transitions),transitions

    print("instance lifecycle stage/progress regression: PASS")


if __name__=="__main__":
    main()
