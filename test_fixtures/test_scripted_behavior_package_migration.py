#!/usr/bin/env python3
from __future__ import annotations

import importlib
import subprocess
import sys
import tempfile

from workbench.devtools.behavior import scripted_behavior as canonical_model
from workbench.devtools.behavior import scripted_behavior_lsb_extract as canonical_extract


def main() -> None:
    legacy_model = importlib.import_module("workbench.plugins.domain.scripted_behavior")
    legacy_extract = importlib.import_module("workbench.plugins.domain.scripted_behavior_lsb_extract")
    assert legacy_model is canonical_model
    assert legacy_extract is canonical_extract

    behavior = canonical_model.behavior_map_from_probe({
        "kind": "SCRIPTED_NM_BEHAVIOR_PROBE",
        "subject": "Test Mob",
        "zone": "Test Zone",
        "hooks": ["onMobSpawn"],
        "dependencies": [{
            "kind": "hp_threshold",
            "subject": "Test Mob",
            "threshold_hpp": 50,
            "effect": "phase_two",
        }],
    })
    assert behavior.subject == "Test Mob"
    assert behavior.hooks == ("onMobSpawn",)
    assert behavior.rules[0].trigger == "COMBAT_TICK"
    assert behavior.rules[0].conditions[0].value == 50

    lua = """
local entity = {}
entity.onMobSpawn = function(mob)
    mob:setLocalVar('phase', 1)
end
return entity
"""
    blocks = canonical_extract.extract_hook_blocks(lua)
    assert len(blocks) == 1
    assert blocks[0].owner == "entity"
    assert blocks[0].hook == "onMobSpawn"

    with tempfile.TemporaryDirectory() as tmp:
        code = (
            "from workbench.devtools.behavior import scripted_behavior as m; "
            "from workbench.devtools.behavior import scripted_behavior_lsb_extract as e; "
            "assert m.ScriptedBehaviorMap; assert e.extract_hook_blocks; "
            "print('outside-repo scripted behavior import: PASS')"
        )
        subprocess.run([sys.executable, "-c", code], cwd=tmp, check=True)

    print("scripted behavior package migration: PASS")


if __name__ == "__main__":
    main()
