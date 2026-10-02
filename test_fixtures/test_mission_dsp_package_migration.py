#!/usr/bin/env python3
"""Focused package-migration regression for mission proposal generation."""
from __future__ import annotations

import subprocess
import sys
import tempfile

from workbench.devtools.missions import mission_dsp as canonical
from workbench.devtools.missions.mission_representation import (
    MissionRepresentation,
    MissionRequirement,
    plan_mission_representation,
)
from workbench.plugins.domain import mission_dsp as legacy
from workbench.plugins.domain.base import PluginFinding


def main() -> None:
    assert legacy is canonical

    plan = plan_mission_representation(
        (
            MissionRequirement("present", "present"),
            MissionRequirement("missing:event", "missing"),
        ),
        (MissionRepresentation("present", "VERIFIED"),),
    )
    outputs = canonical.generated_mission_patch_proposals(
        plan,
        (
            canonical.MissionPatchProposal("present", "a.lua", "-- skip", "already present"),
            canonical.MissionPatchProposal("missing:event", "b.lua", "-- proposed", "missing behavior"),
        ),
    )
    assert len(outputs) == 1, outputs
    assert outputs[0].relative_path == "proposals/mission/missing_event.lua.patch"
    assert outputs[0].metadata["proposal_only"] is True
    assert outputs[0].metadata["requirement_id"] == "missing:event"

    finding = canonical.mission_proposal_finding("mission:test", plan, len(outputs))
    assert isinstance(finding, PluginFinding)
    assert finding.status == "MANUAL_REQUIRED"
    assert finding.metadata["proposal_count"] == 1

    code = (
        "from workbench.devtools.missions.mission_dsp import MissionPatchProposal; "
        "print(MissionPatchProposal.__name__)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tempfile.gettempdir(),
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "MissionPatchProposal"


if __name__ == "__main__":
    main()
