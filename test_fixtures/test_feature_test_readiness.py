"""Tests for safe read-only resolution of planned GM diagnostic utilities."""
import json
from pathlib import Path

from workbench.server_admin.gm_commands.test_readiness import resolve_test_utilities


def test_resolution_never_authorizes_or_invents(tmp_path: Path):
    command_dir = tmp_path / "server" / "scripts" / "commands"
    command_dir.mkdir(parents=True)
    (command_dir / "garden.lua").write_text(
        '-- desc: Gardening diagnostic\n'
        'cmdprops = { permission = 1, parameters = "s" }\n'
        'error(player, "!garden <mode>")\n', encoding="utf-8")
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"features": [
        {"id": "gardening", "existing_gm_candidates": ["garden", "notreal"]}
    ]}), encoding="utf-8")
    result = resolve_test_utilities(command_dir.parents[1], plan)
    commands = result["features"][0]["commands"]
    assert commands[0]["availability"] == "found_unreviewed"
    assert commands[0]["permission"] == 1
    assert commands[1]["availability"] == "not_found"
    assert not result["execution_enabled"]
    assert all(not c["execution_enabled"] for c in commands)


def test_gardening_collision_case_and_blocker_present():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    plan = json.loads((root / "data/testing/feature_test_readiness.json").read_text(encoding="utf-8"))
    garden = next(f for f in plan["features"] if f["id"] == "gardening")
    collision = next(t for t in garden["cases"] if t["id"] == "GARD-09")
    assert collision["kind"] == "negative"
    assert collision["run_mode"].startswith(("blocked_", "focused_only"))
    assert "GARD-GM-01" in collision["blocking_gaps"][0]
    assert plan["gm_source_review"]["garden"]["cpp_review"]["automation_gate"]
