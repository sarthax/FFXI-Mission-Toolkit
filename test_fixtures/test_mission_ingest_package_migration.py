#!/usr/bin/env python3
"""Focused package-migration regression for normalized mission truth ingestion."""
from __future__ import annotations

import subprocess
import sys
import tempfile

from workbench.devtools.missions import mission_ingest as canonical
from workbench.plugins.domain import mission_ingest as legacy


def payload() -> dict:
    return {
        "kind": "WORKBENCH_MISSION_TRUTH_SET",
        "fixture_id": "migration-smoke",
        "subject": {
            "mission": "TEST_MISSION",
            "next_mission": "NEXT_MISSION",
            "source_revision": "test",
        },
        "verified_server_state_machine": {
            "mission25": {
                "zone": "TEST_ZONE",
                "event_id": 123,
                "npc": "Test_NPC",
                "script": "missions/test.lua",
                "event_args": [1, 2],
            },
            "mission26_gate": {
                "logic": "OR",
                "accepted_quest_completions": ["QUEST_A", "QUEST_B"],
                "known_gap": True,
                "script": "missions/next.lua",
                "function": "check",
            },
        },
    }


def main() -> None:
    assert legacy is canonical
    machine = canonical.ingest_branching_truth(payload())
    assert machine.feature_id == "mission:TEST_MISSION"
    assert machine.entry_state_ids == ("mission:start",)
    assert len(machine.transitions) == 2

    complete = next(row for row in machine.transitions if row.transition_id == "mission:complete")
    assert complete.event.key == "TEST_ZONE:Test_NPC:123"
    assert complete.effects[0].effect == "COMPLETE"

    gate = next(row for row in machine.transitions if row.transition_id == "mission:branch-gate")
    assert gate.gate.logic == "ANY"
    assert tuple(row.subject for row in gate.gate.conditions) == ("quest:QUEST_A", "quest:QUEST_B")
    assert gate.implementation_status == "EXPECTED_GAP"

    code = "from workbench.devtools.missions.mission_ingest import ingest_branching_truth; print(callable(ingest_branching_truth))"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tempfile.gettempdir(),
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "True"


if __name__ == "__main__":
    main()
