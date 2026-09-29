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

    print("instance lifecycle stage/progress regression: PASS")


if __name__=="__main__":
    main()
