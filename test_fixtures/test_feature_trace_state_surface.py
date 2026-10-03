from pathlib import Path

from workbench.devtools.features.state_surface import build_state_surface


def test_state_surface_extracts_mission_owned_state_and_provenance(tmp_path: Path):
    root = tmp_path / "server"
    mission_dir = root / "scripts" / "missions" / "cop"
    npc_dir = root / "scripts" / "zones" / "Sea" / "npcs"
    mission_dir.mkdir(parents=True)
    npc_dir.mkdir(parents=True)

    mission_dir.joinpath("7_1_Test_Mission.lua").write_text(
        """
local mission = Mission:new({ missionId = xi.mission.id.cop.TEST_MISSION })
mission.sections = {
  {
    check = function(player)
      return player:getCharVar('PromathiaStatus') == 3 and player:hasKeyItem(xi.keyItem.TEST_KEY)
    end,
    [xi.zone.SEA] = {
      ['Test_NPC'] = {
        onTrigger = function(player, npc)
          return mission:progressEvent(149)
        end,
        onEventFinish = {
          [149] = function(player, csid, option, npc)
            player:setCharVar('PromathiaStatus', 4)
            npcUtil.giveItem(player, xi.item.TEST_REWARD)
            npcUtil.giveKeyItem(player, xi.keyItem.TEST_KEY_2)
            player:completeMission(xi.mission.log_id.COP, xi.mission.id.cop.TEST_MISSION)
          end,
        },
      },
    },
  },
}
return mission
""",
        encoding="utf-8",
    )
    npc_dir.joinpath("Other.lua").write_text(
        """
local entity = {}
entity.onTrigger = function(player, npc)
  if player:getCurrentMission(xi.mission.log_id.COP) == xi.mission.id.cop.TEST_MISSION then
    player:startEvent(200)
  end
end
return entity
""",
        encoding="utf-8",
    )
    npc_dir.joinpath("Unrelated.lua").write_text("player:setCharVar('Noise', 99)\n", encoding="utf-8")

    surface = build_state_surface(
        root,
        kind="mission",
        area_id=6,
        entry_id=7,
        symbol="TEST_MISSION",
        label="Test Mission",
    )

    assert surface["target"]["symbol"] == "TEST_MISSION"
    assert surface["summary"]["scripts_matched"] == 2
    assert surface["summary"]["reference_count"] > 0
    refs = surface["references"]
    assert any(r["state_type"] == "charvar" and r["key"] == "PromathiaStatus" for r in refs)
    assert any(r["state_type"] == "charvar" and r["expectation_value"] == "3" for r in refs)
    assert any(r["state_type"] == "key_item" and r["key"] == "TEST_KEY" and r["operation"] == "require" for r in refs)
    assert any(r["state_type"] == "key_item" and r["key"] == "TEST_KEY_2" and r["operation"] == "grant" for r in refs)
    assert any(r["state_type"] == "item" and "TEST_REWARD" in r["key"] for r in refs)
    assert any(r["state_type"] == "mission" and r["operation"] == "complete" for r in refs)
    assert any(r["state_type"] == "event" and r["operation"] == "start" for r in refs)
    assert all(r["source_path"] and r["source_line"] >= 1 for r in refs)
    assert not any("Noise" in r["key"] for r in refs)


def test_state_surface_rejects_unknown_kind(tmp_path: Path):
    try:
        build_state_surface(tmp_path, kind="battle", area_id=0, entry_id=0)
    except ValueError as exc:
        assert "mission or quest" in str(exc)
    else:
        raise AssertionError("expected ValueError")
