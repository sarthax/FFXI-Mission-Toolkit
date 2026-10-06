#!/usr/bin/env python3
import sqlite3
import tempfile
from pathlib import Path

from workbench.client.models import look_decode
from workbench.devtools.entities import lookup, profile as entity_profile
from workbench.devtools.entities.profile_graph import import_entity_profile_provenance
from workbench.runtime.paths import DATABASE_PATH


def main():
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "lookup_entity.py").exists()
    assert not (repo_root / "entity_profile.py").exists()
    assert lookup.DB_PATH == DATABASE_PATH
    assert entity_profile.DB_PATH == DATABASE_PATH

    # The moved implementation must execute against canonical component dependencies rather than
    # depending on repository-root modules being importable from sys.path.
    profile_globals = entity_profile.build_profile.__globals__
    assert profile_globals["DB_PATH"] == DATABASE_PATH
    assert profile_globals["lookup_entity"] is lookup
    assert profile_globals["mob_look_decode"] is look_decode
    decoded = entity_profile.decode_entity_id(0x0103702A)
    assert decoded["hex"] == "0x0103702A"
    assert decoded["local_bits"] == 0x02A

    con=sqlite3.connect(":memory:")
    con.execute("CREATE TABLE npc_names(npcid INTEGER, name TEXT, zoneid INTEGER, norm_name TEXT)")
    con.executemany(
        "INSERT INTO npc_names VALUES(?,?,?,?)",
        [
            (100,"Lamia No.13",55,"lamiano13"),
            (101,"Qiqirn_Treasure_Hunter",56,"qiqirntreasurehunter"),
        ],
    )
    assert lookup.resolve_query_to_ids(con,"Lamia No 13")==[(100,"Lamia No.13",55)]
    assert lookup.count_name_matches(con,"Qiqirn Treasure Hunter")==1
    con.close()

    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        profile=root/"legacy.db"
        graph_db=root/"workbench.db"

        con=sqlite3.connect(profile)
        con.execute(
            "CREATE TABLE field_sources("
            "entity_type TEXT, entity_id INTEGER, field_name TEXT, source TEXT, "
            "value TEXT, confidence TEXT)"
        )
        con.executemany(
            "INSERT INTO field_sources VALUES(?,?,?,?,?,?)",
            [
                ("npc",17000001,"name","client_dat","Test NPC","ground truth"),
                ("npc",17000001,"name","topaz_sql","Test NPC","server implementation"),
                ("npc",17000001,"position","client_dat","1,2,3","ground truth"),
                ("npc",17000001,"position","topaz_sql","4,5,6","server implementation"),
            ],
        )
        con.commit()
        con.close()

        result=import_entity_profile_provenance(profile,graph_db,17000001)
        assert result["status"]=="OK",result
        assert result["conflicts"]==1,result

        con=sqlite3.connect(graph_db)
        node=con.execute(
            "SELECT entity_id FROM entity_identifiers WHERE identifier_type='npcid' AND identifier_value='17000001'"
        ).fetchone()[0]
        assert node==result["entity_node"],(node,result)
        rows=con.execute(
            "SELECT field,status,confidence FROM findings WHERE subject_id=? ORDER BY finding_id",
            (node,),
        ).fetchall()
        assert any(field=="position" and status=="CONTRADICTED" for field,status,_ in rows),rows
        assert sum(1 for field,status,_ in rows if field=="name" and status=="DISCOVERED")==2,rows
        con.close()

    print("entity profile and lookup canonical migration self-test: PASS")


if __name__=="__main__":
    main()
