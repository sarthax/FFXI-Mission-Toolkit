from pathlib import Path

from workbench.devtools.features.state_surface_scoped import build_state_surface
from workbench.devtools.missions.legacy_progression_extract import extract_legacy_progression
from workbench.editors.character.progression_assessment import assess_progression
from workbench.editors.character.progression_inspector import build_progression_inspector
from workbench.editors.character.transition_bundles import annotate_transition_bundles


def _catalog(kind: str, area: int, entry: int, symbol: str, label: str) -> dict:
    return {"areas": {str(area): {str(entry): {"id": entry, "symbol": symbol, "label": label}}}}


def _catalog_rows(*rows: tuple[int, int, str, str]) -> dict:
    areas = {}
    for area, entry, symbol, label in rows:
        areas.setdefault(str(area), {})[str(entry)] = {"id": entry, "symbol": symbol, "label": label}
    return {"areas": areas}


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
    assert any(condition.subject == "mission_current:LEGACY_TEST" for condition in transition.gate.conditions)
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

    assessed = assess_progression(annotate_transition_bundles(inspector))
    assert assessed["assessment"]["state"] == "READY"
    bundle = assessed["primary_bundle"]
    assert bundle["event"]["event_id"] == 100
    assert any(row["subject"] == "charvar:LegacyStatus" and row["after"] == 3 for row in bundle["projected_changes"])
    assert any(row["subject"] == "key_item:TEST_KEY" and row["kind"] == "removal" for row in bundle["projected_changes"])
    assert bundle["projection_is_read_only"] is True


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


def test_topaz_quest_status_and_trade_are_admin_readable(tmp_path: Path):
    root = tmp_path / "server"
    path = _write_legacy(root, "MHAURA", "Ekokoko", r'''
function onTrade(player, npc, trade)
    if player:getQuestStatus(JEUNO, tpz.quest.id.jeuno.LEGACY_QUEST) == QUEST_ACCEPTED and
       trade:hasItemQty(1127, 1) then
        player:startEvent(300)
    end
end

function onEventFinish(player, csid, option)
    if csid == 300 then
        player:tradeComplete()
        player:completeQuest(JEUNO, tpz.quest.id.jeuno.LEGACY_QUEST)
    end
end
''')
    machine = extract_legacy_progression((path,), feature_id="quest:3:77")
    transition = next(row for row in machine.transitions if row.event and row.event.event_id == 300)
    assert any(row.subject == "quest_active:LEGACY_QUEST" for row in transition.gate.conditions)
    assert any(row.subject == "trade:item:1127" and row.operator == "TRADE_MATCHES" for row in transition.gate.conditions)
    assert any(row.effect == "COMPLETE_TRADE" for row in transition.effects)
    assert any(row.effect == "COMPLETE" for row in transition.effects)

    surface = build_state_surface(root, kind="quest", area_id=3, entry_id=77, symbol="LEGACY_QUEST", label="Legacy Quest")
    inspector = build_progression_inspector(
        surface, root,
        variables={},
        packed={"mission": {}, "quest": {3: {"current": {77}, "completed": set()}}, "key_items": {}},
        mission_catalog={"areas": {}},
        quest_catalog=_catalog("quest", 3, 77, "LEGACY_QUEST", "Legacy Quest"),
    )
    assert inspector["primary_action"]["event"]["event_id"] == 300
    assert any(row["subject"] == "trade:item:1127" and row["runtime_only"] for row in inspector["primary_action"]["runtime_requirements"])
    active = next(row for row in inspector["primary_action"]["conditions"] if row["subject"] == "quest_active:LEGACY_QUEST")
    assert active["resolved"] is True and active["matches"] is True

    assessed = assess_progression(annotate_transition_bundles(inspector))
    assert assessed["assessment"]["state"] == "WAITING_RUNTIME"
    assert assessed["assessment"]["persisted_blockers"] == 0
    assert assessed["assessment"]["runtime_requirements"] >= 1
    assert any(row["kind"] == "runtime_requirement" and row["subject"] == "trade:item:1127" for row in assessed["primary_bundle"]["why_blocked"])


def test_dsp_completed_prerequisites_and_aliases_resolve(tmp_path: Path):
    root = tmp_path / "server"
    path = _write_legacy(root, "SOUTHERN_SAN_DORIA", "Legacy_Gate", r'''
function onTrigger(player, npc)
    local current = player:getCurrentMission(SANDORIA)
    local qstatus = player:getQuestStatus(SANDORIA, dsp.quest.id.sandoria.LEGACY_SIDEQUEST)
    if current == dsp.mission.id.sandoria.LEGACY_MISSION and
       player:hasCompletedMission(SANDORIA, dsp.mission.id.sandoria.PREREQ_MISSION) and
       player:hasCompletedQuest(SANDORIA, dsp.quest.id.sandoria.PREREQ_QUEST) and
       qstatus == QUEST_COMPLETED then
        player:startEvent(400)
    end
end
''')
    machine = extract_legacy_progression((path,), feature_id="mission:0:20")
    transition = next(row for row in machine.transitions if row.event and row.event.event_id == 400)
    subjects = {row.subject for row in transition.gate.conditions}
    assert "mission_current:LEGACY_MISSION" in subjects
    assert "mission_completed:PREREQ_MISSION" in subjects
    assert "quest_completed:PREREQ_QUEST" in subjects
    assert "quest_completed:LEGACY_SIDEQUEST" in subjects

    surface = build_state_surface(root, kind="mission", area_id=0, entry_id=20, symbol="LEGACY_MISSION", label="Legacy Mission")
    inspector = build_progression_inspector(
        surface, root,
        variables={},
        packed={
            "mission": {0: {"current": 20, "completed": {10}}},
            "quest": {0: {"current": set(), "completed": {30, 31}}},
            "key_items": {},
        },
        mission_catalog=_catalog_rows(
            (0, 10, "PREREQ_MISSION", "Prerequisite Mission"),
            (0, 20, "LEGACY_MISSION", "Legacy Mission"),
        ),
        quest_catalog=_catalog_rows(
            (0, 30, "PREREQ_QUEST", "Prerequisite Quest"),
            (0, 31, "LEGACY_SIDEQUEST", "Legacy Sidequest"),
        ),
    )
    assert inspector["primary_action"]["event"]["event_id"] == 400
    assert all(row["matches"] is True for row in inspector["primary_action"]["conditions"] if row["resolved"])

    assessed = assess_progression(annotate_transition_bundles(inspector))
    assert assessed["assessment"]["state"] == "READY"
    assert assessed["assessment"]["persisted_blockers"] == 0
