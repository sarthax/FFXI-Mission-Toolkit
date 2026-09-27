#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

from workbench.plugins.domain.mission_ingest import ingest_branching_truth
from workbench.plugins.domain.mission_state_machine import analyze_state_machine
from workbench.plugins.domain.mission_representation import requirements_from_state_machine

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/"test_fixtures"/"fixtures"/"wotg25_branching_mission_truth.json"


def main():
    payload=json.loads(FIXTURE.read_text(encoding="utf-8"))
    machine=ingest_branching_truth(payload)
    errors=machine.validate()
    assert not errors,errors
    analysis=analyze_state_machine(machine)

    assert machine.feature_id=="mission:The Will of the World",machine
    gate=next(t for t in machine.transitions if t.transition_id=="mission:branch-gate")
    assert gate.gate and gate.gate.logic=="ANY",gate
    assert len(gate.gate.conditions)==3,gate
    assert "event:Southern San d'Oria (S):Raustigne:149" in analysis.event_keys,analysis
    assert "event:Everbloom Hollow:INSTANCE_EVENT:10000" in analysis.event_keys,analysis
    assert analysis.lifecycle_subjects["key_item:WAX_SEAL"]==("GRANT","REMOVE","REQUIRE"),analysis
    assert analysis.lifecycle_subjects["key_item:COMMANDERS_ENDORSEMENT"]==("GRANT","REISSUE","REQUIRE"),analysis
    assert any("implementation-gap" in x for x in analysis.gap_transition_ids),analysis
    assert "windurst_branch:missing" in analysis.gap_transition_ids,analysis

    reqs=requirements_from_state_machine(machine)
    assert any(r.requirement_id=="transition:mission:complete" for r in reqs),reqs
    assert any(r.requirement_id=="lifecycle:key_item:WAX_SEAL" for r in reqs),reqs

    # This ingestion deliberately refuses to pretend truth-set CSIDs map to exact
    # Prog transitions. That assignment requires source parsing/evidence.
    observed=[t for t in machine.transitions if t.trigger=="OBSERVED_EVENT"]
    assert observed and all(t.metadata.get("unassigned_progress_edge") for t in observed),observed

    print("branching mission ingestion self-test: PASS")
    print(f"states={len(machine.states)} transitions={len(machine.transitions)} events={len(analysis.event_keys)} gaps={len(analysis.gap_transition_ids)}")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
