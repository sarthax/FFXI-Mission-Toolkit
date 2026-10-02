#!/usr/bin/env python3
"""Focused package-migration regression for multi-zone progression tooling."""
from __future__ import annotations

import subprocess
import sys
import tempfile

from workbench.devtools.missions import multizone_progression as canonical
from workbench.plugins.domain import multizone_progression as legacy


def main() -> None:
    assert legacy is canonical

    model = canonical.MultiZoneProgression(
        progression_id="migration-smoke",
        feature_id="mission:MIGRATION_SMOKE",
        objectives=(
            canonical.ProgressionObjective(
                "objective:a",
                "First objective",
                "NPC_INTERACT",
                zones=("ZONE_A",),
                subject="npc:alpha",
            ),
            canonical.ProgressionObjective(
                "objective:b",
                "Second objective",
                "MOB_DEATH",
                zones=("ZONE_B",),
                subject="mob:beta",
            ),
        ),
        stages=(
            canonical.ProgressionStage("stage:a", "Stage A", ("objective:a",)),
            canonical.ProgressionStage(
                "stage:b",
                "Stage B",
                ("objective:b",),
                prerequisite_gate=canonical.ProgressionGate(
                    "gate:b",
                    "ALL",
                    ("stage:a",),
                ),
            ),
        ),
        entry_stage_ids=("stage:a",),
    )

    analysis = canonical.analyze_progression(model)
    assert analysis.status == "STRUCTURALLY_READY"
    assert analysis.reachable_stage_ids == ("stage:a", "stage:b")
    assert analysis.zone_ids == ("ZONE_A", "ZONE_B")
    assert len(analysis.cross_zone_dependencies) == 1
    cross = analysis.cross_zone_dependencies[0]
    assert (cross.source_stage_id, cross.target_stage_id) == ("stage:a", "stage:b")

    projection = canonical.project_progression_graph(model, source_snapshot_id="snapshot:test")
    assert projection.feature.feature_id == "mission:MIGRATION_SMOKE"
    assert projection.feature.feature_type == "MULTIZONE_PROGRESSION"
    relationships = {edge.relationship for edge in projection.edges}
    assert {"HAS_STAGE", "HAS_OBJECTIVE", "REQUIRES", "REFERENCES", "LOCATED_IN"} <= relationships
    entity_ids = {entity.entity_id for entity in projection.entities}
    assert "progression-stage:mission:MIGRATION_SMOKE:stage:a" in entity_ids
    assert "zone:ZONE_B" in entity_ids

    code = (
        "from workbench.devtools.missions.multizone_progression import "
        "MultiZoneProgression, analyze_progression; "
        "print(callable(analyze_progression), MultiZoneProgression.__name__)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tempfile.gettempdir(),
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "True MultiZoneProgression"

    print("multi-zone progression package migration: PASS")


if __name__ == "__main__":
    main()
