#!/usr/bin/env python3
"""Domain definitions and Salvage reconstruction semantics are well-formed."""
import re, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from workbench.domains import service
from workbench.domains.salvage_reconstruction import build_dossier
from workbench.gui_shell import WORKSPACES

ROOT = Path(__file__).resolve().parent.parent


def test_salvage_dossier():
    con = sqlite3.connect(":memory:")
    con.executescript("""
    CREATE TABLE captures(capture_id INTEGER PRIMARY KEY,capture_label TEXT,content_type TEXT,zones TEXT,mission_name TEXT,client_build TEXT,start_time INTEGER,ingested_at TEXT);
    INSERT INTO captures VALUES(7,'Zhayolm test','Salvage','ZHAYOLM_REMNANTS',NULL,'retail-x',1,'now');
    CREATE TABLE capture_npc_entries(capture_id INTEGER,zone_db TEXT,entity_id INTEGER,name TEXT,model_id INTEGER,x REAL,y REAL,z REAL,dir INTEGER,hpp INTEGER,door_id INTEGER,act_index INTEGER,sub_kind INTEGER);
    INSERT INTO capture_npc_entries VALUES(7,'ZHAYOLM_REMNANTS',100,'_door',55,1,2,3,64,100,12,4,2);
    INSERT INTO capture_npc_entries VALUES(7,'ZHAYOLM_REMNANTS',101,'Archaic_Gear',99,4,5,6,32,100,0,0,0);
    CREATE TABLE capture_npc_history(capture_id INTEGER,zone_db TEXT,entity_id INTEGER,seq INTEGER,ts INTEGER,delta_json TEXT);
    INSERT INTO capture_npc_history VALUES(7,'ZHAYOLM_REMNANTS',100,1,10,'{"animation":8}');
    INSERT INTO capture_npc_history VALUES(7,'ZHAYOLM_REMNANTS',100,2,20,'{"animation":9}');
    CREATE TABLE capture_events(capture_id INTEGER,zone_db TEXT,seq INTEGER,direction TEXT,opcode TEXT,opcode_name TEXT,entity_id INTEGER,entity_name TEXT,event_hex TEXT,option INTEGER,message_id INTEGER,params_raw TEXT);
    INSERT INTO capture_events VALUES(7,'ZHAYOLM_REMNANTS',1,'S2C','0x034','EVENT',100,'_door','00AF',2,NULL,'[]');
    CREATE TABLE capture_npc_path(capture_id INTEGER,zone_db TEXT,entity_id INTEGER,leg INTEGER,step INTEGER,x REAL,y REAL,z REAL,dir INTEGER,delta INTEGER);
    INSERT INTO capture_npc_path VALUES(7,'ZHAYOLM_REMNANTS',101,1,1,4,5,6,32,0);
    CREATE TABLE capture_pc_path(capture_id INTEGER,zone_db TEXT,leg INTEGER,step INTEGER,x REAL,y REAL,z REAL,dir INTEGER,delta INTEGER);
    INSERT INTO capture_pc_path VALUES(7,'ZHAYOLM_REMNANTS',1,1,0,0,0,0,0);
    INSERT INTO capture_pc_path VALUES(7,'ZHAYOLM_REMNANTS',1,2,40,0,40,0,0);
    CREATE TABLE capture_actions(capture_id INTEGER,action_key TEXT,actor INTEGER,actor_name TEXT,action_type TEXT,animation INTEGER,category INTEGER,message INTEGER,name TEXT,ts INTEGER);
    INSERT INTO capture_actions VALUES(7,'a',101,'Archaic_Gear','ABILITY',44,1,10,'Gear Ability',1);
    INSERT INTO capture_actions VALUES(7,'b',999,'Other_Zone_Mob','ABILITY',55,1,11,'Wrong Zone',2);
    """)
    d = build_dossier(con, 7, "ZHAYOLM_REMNANTS")
    assert len(d["entities"]) == 2
    assert d["doors"][0]["entity_id"] == 100
    assert d["doors"][0]["basis"] == "capture_npc_entries.door_id"
    assert d["entity_state_changes"][0]["observations"] == 2
    assert d["event_observations"][0]["event_hex"] == "00AF"
    assert d["player_path"][0]["samples"] == 2
    assert len(d["spatial_regions"]) == 1
    region = d["spatial_regions"][0]
    assert region["region_id"] == "pc_leg_1"
    assert region["floor_room_claim"] == "UNRESOLVED"
    assert region["entity_overlap_candidates"] == [100, 101]
    assert region["door_overlap_candidates"] == [100]
    assert all(r["status"] == "SINGLE_REGION_CANDIDATE" for r in d["entity_region_candidates"])
    assert len(d["actions"]) == 1 and d["actions"][0]["actor"] == 101
    assert d["proposal_readiness"]["npc_or_mob_rows"] == "READY_FOR_REVIEW"
    assert d["proposal_readiness"]["floor_room_segmentation"] == "PARTIAL"
    assert d["proposal_readiness"]["door_state_rows"] == "READY_FOR_REVIEW"
    assert d["proposal_readiness"]["telepad_csid_mapping"] == "PARTIAL"
    assert d["proposal_readiness"]["telepad_destination"] == "PARTIAL"
    assert any("evidence only" in g for g in d["gaps"])
    assert any("not proven Salvage floors or rooms" in g for g in d["gaps"])
    con.close()


def test_salvage_workspace_assets():
    template = (ROOT / "gui/templates/domain_detail.html").read_text(encoding="utf-8")
    script = (ROOT / "gui/static/salvage_reconstruction.js").read_text(encoding="utf-8")
    assert 'd.archetype == "system.salvage"' in template
    assert 'id="salvage-reconstruction-workspace"' in template
    assert 'id="sr-map"' in template
    assert 'id="sr-readiness"' in template
    assert 'id="sr-regions"' in template
    assert 'id="sr-doors"' in template
    assert 'id="sr-events"' in template
    assert '/static/salvage_reconstruction.js' in template
    for table in (
        "capture_npc_entries", "capture_npc_history", "capture_events",
        "capture_npc_path", "capture_pc_path",
    ):
        assert f"csvTable('{table}'" in script
    assert '/spatial.json' in script
    assert 'buildSpatialRegions' in script
    assert 'UNRESOLVED floor/room' in script
    assert 'Floor / room segmentation' in script
    assert 'READY_FOR_REVIEW' in script
    assert 'CSID/option observations do not prove activation conditions' in script
    assert 'captured state must not be treated as an open/close rule' in script
    assert 'path leg is not a proven Salvage floor or room' in script
    assert '/zoneplot2?capture_id=' in script
    assert '/features/trace' in script
    assert '/packages/scope' in script


def main():
    defs = service.load()
    for k, d in defs.items():
        for f in ("label", "archetype", "summary", "wiki", "entities", "compare"):
            assert f in d, (k, f)
        assert all({"kind", "fields", "server_globs", "edit"} <= set(e) for e in d["entities"]), k
        for p in d.get("pipeline", []):
            assert {"stage", "status", "summary", "handoffs"} <= set(p), (k, p)
            assert p["status"] in {"ready", "partial", "blocked"}, (k, p["status"])
            assert all({"label", "href"} <= set(h) for h in p["handoffs"]), (k, p)

    salvage = defs["salvage"]
    assert salvage["archetype"] == "system.salvage"
    assert salvage["children"] == [
        "Zhayolm Remnants I", "Zhayolm Remnants II",
        "Arrapago Remnants I", "Arrapago Remnants II",
        "Bhaflau Remnants I", "Bhaflau Remnants II",
        "Silver Sea Remnants I", "Silver Sea Remnants II",
    ]
    stages = {p["stage"]: p["status"] for p in salvage["pipeline"]}
    assert stages["1. Evidence intake"] == "ready"
    assert stages["3. Spawn and instance registration proposal"] == "partial"
    assert stages["5. Telepad / door / CSID mapping"] == "partial"
    assert stages["6. Package and validation"] == "ready"
    test_salvage_dossier()
    test_salvage_workspace_assets()

    ws = next(w for w in WORKSPACES if w["name"] == "Domains")
    def walk(items):
        for s in items:
            yield s
            yield from walk(s.get("children", ()))
    for s in walk(ws["sections"]):
        m = re.match(r"/domains/([a-z]+)(#|$)", s.get("href") or "")
        if m and m.group(1) != "assault":
            assert m.group(1) in defs, s
    print("Domain definitions self-test: PASS")


if __name__ == "__main__":
    main()
