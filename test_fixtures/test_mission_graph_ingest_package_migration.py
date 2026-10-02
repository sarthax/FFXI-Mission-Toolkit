#!/usr/bin/env python3
"""Package migration smoke for mission graph projection and root/plugin compatibility."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_root_module():
    name = "mission_graph_ingest_migration_root"
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "mission_graph_ingest.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return sys.modules[name]


def main():
    from workbench.devtools.missions import graph_ingest as canonical
    from workbench.plugins.domain import mission_graph_emit as legacy

    root = load_root_module()
    assert root is canonical
    assert legacy is canonical

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
