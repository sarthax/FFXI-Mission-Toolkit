from __future__ import annotations

import sqlite3
from pathlib import Path

from workbench.core import graph
from workbench.devtools.features.trace_identity_provider import (
    canonical_identity_candidates,
    numeric_identity_roots,
    runtime_identity_evidence,
)
from workbench.devtools.features.trace_mission_provider import mission_trace_candidates

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "test_fixtures" / "fixtures"


def test_lsb_mission_provider_projects_real_cait_sith_fixture(tmp_path: Path):
    server = tmp_path / "lsb"
    target = server / "scripts" / "missions" / "wotg" / "03_Cait_Sith.lua"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text((FIX / "lsb_wotg03_cait_sith.lua").read_text(encoding="utf-8"), encoding="utf-8")
    result = mission_trace_candidates(
        server,
        family="lsb",
        kind="mission",
        symbol="CAIT_SITH",
        root_node="mission:wotg:cait-sith",
    )
    assert result["available"] is True
    assert result["source_mode"] == "LSB_EXACT_DEFINITION"
    relationships = {row["relationship"] for row in result["relationships"]}
    assert "HAS_MISSION_TRANSITION" in relationships
    assert "TRIGGERS_EVENT" in relationships
    assert any(rel in relationships for rel in {"COMPLETES_MISSION_STATE", "GRANTS_REWARD", "SETS_MISSION_STATE"})


def test_topaz_mission_provider_uses_same_relationship_contract(tmp_path: Path):
    server = tmp_path / "topaz"
    npc = server / "scripts" / "zones" / "Bastok_Markets_S" / "npcs" / "Engelhart.lua"
    npc.parent.mkdir(parents=True, exist_ok=True)
    npc.write_text(r'''
function onTrigger(player, npc)
    if player:getCurrentMission(tpz.mission.log_id.WOTG) == tpz.mission.id.wotg.LEGACY_TEST and player:getCharVar("LegacyStatus") == 2 then
        player:startEvent(100)
    end
end
function onEventFinish(player, csid, option)
    if csid == 100 then
        player:setCharVar("LegacyStatus", 3)
        player:completeMission(tpz.mission.log_id.WOTG, tpz.mission.id.wotg.LEGACY_TEST)
    end
end
''', encoding="utf-8")
    result = mission_trace_candidates(
        server,
        family="topaz",
        kind="mission",
        symbol="LEGACY_TEST",
        feature_id="mission:5:42",
        legacy_files=(npc,),
        root_node="mission:wotg:legacy-test",
    )
    assert result["available"] is True
    assert result["source_mode"] == "LEGACY_HANDLER_SCOPE"
    relationships = {row["relationship"] for row in result["relationships"]}
    assert "HAS_MISSION_TRANSITION" in relationships
    assert "TRIGGERS_EVENT" in relationships
    assert "REQUIRES_STATE" in relationships
    assert "SETS_MISSION_STATE" in relationships
    assert "COMPLETES_MISSION_STATE" in relationships


def test_identity_provider_preserves_unique_and_ambiguous_mappings():
    con = sqlite3.connect(":memory:")
    con.executescript(graph.SCHEMA)
    con.execute("INSERT INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES('npc:test','NPC','Test NPC','{}')")
    con.execute("INSERT INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES('npc:other','NPC','Other NPC','{}')")
    # entity_identifiers exists in canonical graph schema used by Feature Trace.
    con.execute("INSERT INTO entity_identifiers(entity_id,identifier_type,identifier_value,source_snapshot_id) VALUES(?,?,?,?)", ('npc:test','npcid','16974347','server:topaz'))
    con.execute("INSERT INTO entity_identifiers(entity_id,identifier_type,identifier_value,source_snapshot_id) VALUES(?,?,?,?)", ('npc:test','client_entity_id','16974347','client:retail'))
    con.commit()
    unique = numeric_identity_roots(con, 16974347)
    assert unique["status"] == "RESOLVED"
    assert unique["roots"] == ["npc:test"]
    rows = canonical_identity_candidates(con, "npc:test")
    assert len(rows) == 2
    assert all(row.relationship == "HAS_IDENTITY_REPRESENTATION" for row in rows)

    con.execute("INSERT INTO entity_identifiers(entity_id,identifier_type,identifier_value,source_snapshot_id) VALUES(?,?,?,?)", ('npc:other','npcid','16974347','server:dsp'))
    con.commit()
    ambiguous = numeric_identity_roots(con, 16974347)
    assert ambiguous["status"] == "AMBIGUOUS"
    assert set(ambiguous["roots"]) == {"npc:test", "npc:other"}
    con.close()


def test_runtime_identity_provider_surfaces_recorded_capture_evidence():
    con = sqlite3.connect(":memory:")
    con.executescript(graph.SCHEMA)
    con.execute("INSERT INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES('npc:test','NPC','Test NPC','{}')")
    con.execute("INSERT INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES('capture:5','CAPTURE','Capture 5','{}')")
    con.execute(
        "INSERT INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
        ('rel:runtime','npc:test','capture:5','OBSERVED_IN_CAPTURE','ev:5','VERIFIED','DISCOVERED','{}','capture:5'),
    )
    con.commit()
    rows = runtime_identity_evidence(con, 'npc:test')
    assert len(rows) == 1
    assert rows[0].generator == 'runtime'
    assert rows[0].target_node == 'capture:5'
    assert rows[0].confidence == 'VERIFIED'
    con.close()
