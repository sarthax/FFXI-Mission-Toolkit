from pathlib import Path

from workbench.devtools.features.state_surface_scoped import build_state_surface
from workbench.devtools.missions.legacy_progression_extract import extract_legacy_progression
from workbench.editors.character.progression_inspector import build_progression_inspector


def _catalog(kind: str, area: int, entry: int, symbol: str, label: str) -> dict:
    return {"areas": {str(area): {str(entry): {"id": entry, "symbol": symbol, "label": label}}}}


def _write_legacy(root: Path, zone: str, actor: str, text: str) -> Path:
    path = root / "scripts" / "zones" / zone / "npcs" / f"{actor}.lua"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_topaz_legacy_mission_normalizes_current_step_and_event_finish(tmp_path: Path):
    root = tmp_path / "server"
    path = _write_legacy(root, "BASTOK_MARKETS_S", "Engelhart", r'''
function onTrigger(player, npc)
    if player:getCurrentMission(tpz.mission.log_id.WOTG) == tpz.mission.id.wotg.LEGACY_TEST and
       player:getCharVar("LegacyStatus") == 2 and
       player:hasKeyItem(tpz.ki.TEST_KEY) then
        player:startEvent(100)
    elseif player:getCharVar("LegacyStatus") == 3 then
        player:startEvent(101)
    end
end

function onEventFinish(player, csid, option)
    if csid == 100 then
        player:setCharVar("LegacyStatus", 3)
        player:delKeyItem(tpz.ki.TEST_KEY)
    end
end
''')
    machine = extract_legacy_progression((path,), feature_id="mission:5:42")
    assert machine is not None
    assert machine.metadata["adapter"] == "legacy_dsp_topaz"
    transition = next(row for row in machine.transitions if row.event and row.event.event_id == 100)
    assert transition.event.zone == "BASTOK_MARKETS_S"
    assert transition.event.actor == "Engelhart"
    assert transition.metadata.get("logical_event_chain") is True
    assert any(effect.subject == "charvar:LegacyStatus" and effect.value == 3 for effect in transition.effects)
    assert any(effect.effect == "REMOVE" and effect.subject == "key_item:TEST_KEY" for effect in transition.effects)

    surface = build_state_surface(
        root, kind="mission", area_id=5, entry_id=42,
        symbol="LEGACY_TEST", label="Legacy Test",
    )
    assert surface["summary"]["selection_mode"] == "legacy_reference_scan"
    inspector = build_progression_inspector(
        surface, root,
        variables={"LegacyStatus": 2},
        packed={
            "mission": {5: {"current": 42, "completed": set()}},
            "quest": {},
            "key_items": {"TEST_KEY": True},
        },
        mission_catalog=_catalog("mission", 5, 42, "LEGACY_TEST", "Legacy Test"),
        quest_catalog={"areas": {}},
    )
    assert inspector["available"] is True
    assert inspector["source_adapter"] == "DSP/Topaz legacy handlers"
    assert inspector["diagnosis"] == "CURRENT"
    assert inspector["primary_action"]["event"]["event_id"] == 100
    assert inspector["primary_action"]["progression_score"] >= 4
    assert any(row["storage_key"] == "LegacyStatus" and row["value"] == 2 for row in inspector["feature_vars"])


def test_dsp_namespace_key_items_and_getvar_setvar_are_normalized(tmp_path: Path):
    root = tmp_path / "server"
    path = _write_legacy(root, "PORT_BASTOK", "Legacy_NPC", r'''
function onTrigger(player, npc)
    if player:getVar("DSPQuestStep") == 1 and player:hasKeyItem(dsp.ki.DSP_TEST_KEY) then
        player:startEvent(200)
    end
end

function onEventFinish(player, csid, option)
    if csid == 200 then
        player:setVar("DSPQuestStep", 2)
        player:delKeyItem(dsp.ki.DSP_TEST_KEY)
        player:addTitle(dsp.title.DSP_TEST_TITLE)
    end
end
''')
    machine = extract_legacy_progression((path,), feature_id="quest:7:99")
    assert machine is not None
    transition = next(row for row in machine.transitions if row.event and row.event.event_id == 200)
    assert any(condition.subject == "charvar:DSPQuestStep" and condition.value == 1 for condition in transition.gate.conditions)
    assert any(effect.subject == "charvar:DSPQuestStep" and effect.value == 2 for effect in transition.effects)
    assert any(effect.subject == "key_item:DSP_TEST_KEY" and effect.effect == "REMOVE" for effect in transition.effects)
    assert any(effect.subject == "title:DSP_TEST_TITLE" and effect.effect == "GRANT_TITLE" for effect in transition.effects)
