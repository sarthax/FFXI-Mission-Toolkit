"""Read-only GM guidance must never infer spawn state or send commands."""
import pytest

from workbench.devtools.research.entity_gm_diagnostics import gm_entity_diagnostic_plan


def test_verified_mob_action_command():
    p = gm_entity_diagnostic_plan(server_entity_id=17215539)
    assert p["commands"][0]["command"] == "!getmobaction 17215539"
    assert p["runtime_status"] == "unknown"
    assert p["commands"][0]["mutates_server"] is False
    assert p["requires_server_modification"] is False


def test_npc_and_unknown_family_do_not_invent_commands():
    assert gm_entity_diagnostic_plan(server_entity_id=17215539, mob=False)["commands"] == []
    assert gm_entity_diagnostic_plan(server_entity_id=17215539, source="lsb")["commands"] == []


@pytest.mark.parametrize("bad", [-1, 4294967296, True, "17215539"])
def test_invalid_id_rejected(bad):
    with pytest.raises(ValueError):
        gm_entity_diagnostic_plan(server_entity_id=bad)
