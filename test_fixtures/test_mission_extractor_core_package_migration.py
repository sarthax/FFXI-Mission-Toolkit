#!/usr/bin/env python3
"""Regression for Development-owned mission extractor/state-machine modules."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.devtools.missions import mission_lsb_extract as canonical_extract
from workbench.devtools.missions import mission_state_machine as canonical_state
from workbench.plugins.domain import mission_lsb_extract as legacy_extract
from workbench.plugins.domain import mission_state_machine as legacy_state


def main() -> None:
    assert legacy_extract is canonical_extract
    assert legacy_state is canonical_state

    lua = """[xi.zone.TEST_ZONE] = {\n['Test_NPC'] = mission:progressEvent(7),\n}\n"""
    findings = canonical_extract.extract_lsb_mission_findings(lua)
    event = next(item for item in findings if item.kind == "event")
    assert (event.zone, event.actor, event.event_id) == ("TEST_ZONE", "Test_NPC", 7)

    machine = canonical_state.MissionStateMachine(
        "machine:test",
        "mission:test",
        (
            canonical_state.MissionState("start", "Start"),
            canonical_state.MissionState("done", "Done", terminal=True),
        ),
        (
            canonical_state.MissionTransition(
                "finish",
                "start",
                "done",
                "OBSERVED_EVENT",
                event=canonical_state.EventIdentity("TEST_ZONE", 7, "Test_NPC"),
                implementation_status="PRESENT",
            ),
        ),
        ("start",),
    )
    analysis = canonical_state.analyze_state_machine(machine)
    assert analysis.status == "COMPLETE"
    assert analysis.event_keys == ("event:TEST_ZONE:Test_NPC:7",)

    code = """
import workbench.devtools.missions.mission_lsb_extract as ce
import workbench.devtools.missions.mission_state_machine as cs
import workbench.plugins.domain.mission_lsb_extract as le
import workbench.plugins.domain.mission_state_machine as ls
assert ce is le
assert cs is ls
assert ce.extract_lsb_mission_findings("[xi.zone.TEST] = {\\n['NPC'] = mission:progressEvent(3),\\n}")[0].event_id == 3
print('outside-repo mission extractor core import: PASS')
"""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-c", code], cwd=Path(tmp), check=True)

    print("mission extractor core package migration self-test: PASS")


if __name__ == "__main__":
    main()
