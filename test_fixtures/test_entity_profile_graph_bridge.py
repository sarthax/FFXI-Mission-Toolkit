#!/usr/bin/env python3
import sqlite3
import tempfile
from pathlib import Path

from workbench.core.services.entity_profile_graph import import_entity_profile_provenance


def main():
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

    print("entity profile canonical graph bridge self-test: PASS")


if __name__=="__main__":
    main()
