#!/usr/bin/env python3
"""Package migration smoke for mission graph projection and root/plugin compatibility."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent



def main():
    from workbench.devtools.missions import graph_ingest as canonical
    from workbench.plugins.domain import mission_graph_emit as legacy

    assert legacy is canonical
    assert not (REPO_ROOT / "mission_graph_ingest.py").exists()

    canonical_source = (REPO_ROOT / "src" / "workbench" / "devtools" / "missions" / "graph_ingest.py").read_text(encoding="utf-8")
    cli_source = (REPO_ROOT / "src" / "workbench" / "devtools" / "missions" / "graph_ingest_cli.py").read_text(encoding="utf-8")
    assert "graph_ingest_cli import main" in canonical_source
    assert "ArgumentParser" in cli_source
    assert '"--write"' in cli_source
    assert "graph_store.init_db" in cli_source
    assert "graph_ingest.persist_mission_graph" in cli_source

    code = r'''
from workbench.devtools.missions import graph_ingest

lua = """
return Mission:new(xi.mission.log_id.COP, xi.mission.id.cop.TEST, {
    [xi.zone.MISAREAUX_COAST] = {
        ['_0p2'] = {
            onTrigger = function(player, npc)
                return mission:progressEvent(6)
            end,
        },
    },
})
"""
projection = graph_ingest.extract_and_project_lsb_mission(
    lua,
    feature_id="mission:test:package-migration",
    source_path="scripts/missions/test.lua",
    source_snapshot_id="snapshot:test",
)
assert projection.feature.feature_id == "mission:test:package-migration"
assert projection.artifact.path == "scripts/missions/test.lua"
assert projection.entities
assert projection.edges
assert any(e.entity_type == "MISSION_EVENT" for e in projection.entities)
print("mission graph package migration subprocess: PASS")
'''
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=tempfile.gettempdir(),
        check=True,
    )
    print("mission graph package migration self-test: PASS")


if __name__ == "__main__":
    main()
