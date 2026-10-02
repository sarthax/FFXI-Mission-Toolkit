#!/usr/bin/env python3
"""Focused package-migration regression for the reusable minigame framework."""
from __future__ import annotations

import subprocess
import sys
import tempfile

from workbench.devtools.missions import minigame as canonical
from workbench.plugins.domain import minigame as legacy


def main() -> None:
    assert legacy is canonical

    model = canonical.MinigameModel(
        "migration-smoke",
        "feature:migration-minigame",
        interactions=(
            canonical.MinigameInteraction(
                "start", "Start", "NPC_INTERACT", starts_timers=("round",)
            ),
        ),
        outcomes=(
            canonical.MinigameOutcome("win", "Win", "WIN"),
            canonical.MinigameOutcome("timeout", "Timeout", "TIMEOUT"),
        ),
        timers=(
            canonical.MinigameTimer("round", duration_seconds=30, expiry_outcome_ids=("timeout",)),
        ),
        resets=(
            canonical.MinigameReset("reset", "Reset", "NPC_INTERACT", cancels_timers=("round",)),
        ),
    )

    analysis = canonical.analyze_minigame(model)
    assert analysis.status == "STRUCTURALLY_READY", analysis
    assert analysis.has_win and analysis.has_loss
    assert analysis.timer_lifecycles[0].structurally_closed

    projection = canonical.project_minigame_graph(model)
    assert projection.feature.feature_type == "MINIGAME"
    relationships = {edge.relationship for edge in projection.edges}
    assert {"HAS_TIMER", "HAS_OUTCOME", "HAS_INTERACTION", "HAS_RESET", "STARTS_TIMER", "EXPIRES_TO"} <= relationships

    code = "from workbench.devtools.missions.minigame import MinigameModel, analyze_minigame; print(callable(analyze_minigame), MinigameModel.__name__)"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tempfile.gettempdir(),
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "True MinigameModel"


if __name__ == "__main__":
    main()
