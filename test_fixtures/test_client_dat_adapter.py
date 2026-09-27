#!/usr/bin/env python3
"""Regression coverage for the minimal P0 client DAT adapter/model."""
from pathlib import Path
from types import SimpleNamespace
import sqlite3
import tempfile

from workbench.adapters.servers import LSBAdapter, TopazAdapter
from workbench.client.dat_adapter import (
    ItemDatAdapter,
    bindings_for,
    compare_server_record_to_client,
    persist_client_dat_record_capability,
)
from workbench.core import graph


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); (root/"sql").mkdir()

        raw=SimpleNamespace(
            id=16385,type=4,category="Weapons",format="legacy",
            dat="ROM/118/108.DAT",record_index=1,
        )
        fields={
            "id":16385,"type":4,"flags":0,"stack":1,"jobs":1,
            "level":1,"slots":1,"skill":1,"delay":528,"dmg":1,
            "targets":0,
        }
        adapter=ItemDatAdapter(
            "client:30191204_1",
            reader=lambda item_id: raw if item_id==16385 else None,
            serializer=lambda _raw:dict(fields),
        )
        record=adapter.read(16385)
        assert record is not None,record
        assert record.item_id==16385
        assert record.layout=="weapon"
        assert record.category=="Weapons"
        assert adapter.read(999) is None

        topaz=TopazAdapter(root)
        weapon=topaz.normalize_row("item_weapon",{
            "itemId":16385,"name":"cesti","skill":1,"subskill":0,
            "ilvl_skill":0,"ilvl_parry":0,"ilvl_macc":0,"dmgType":4,
            "hit":1,"delay":528,"dmg":1,"unlock_points":0,
        })
        weapon_cmp=compare_server_record_to_client(weapon,record)
        assert {row.server_field:row.status for row in weapon_cmp}=={
            "skill":"VERIFIED","delay":"VERIFIED","damage":"VERIFIED"
        },weapon_cmp

        lsb=LSBAdapter(root)
        basic=lsb.normalize_row("item_basic",{
            "itemid":16385,"subid":0,"name":"cesti","sortname":"cesti",
            "name_jp":"cesti","type":4,"stackSize":1,"flags":0,"aH":1,"BaseSell":10,
        })
        basic_cmp=compare_server_record_to_client(basic,record)
        by_field={row.server_field:row for row in basic_cmp}
        assert by_field["item_id"].status=="VERIFIED",basic_cmp
        assert by_field["flags"].status=="VERIFIED",basic_cmp
        assert by_field["stack_size"].status=="VERIFIED",basic_cmp
        assert by_field["item_type"].status=="VERIFIED",basic_cmp

        assert bindings_for("item_equipment")
        assert bindings_for("spells")==()

        db=root/"workbench.db"
        con=graph.init_db(db)
        counts=persist_client_dat_record_capability(con,record)
        con.close()
        assert counts=={"capabilities":1,"observations":1,"evidence":1},counts

        con=sqlite3.connect(db)
        obs=con.execute(
            "SELECT status,value_json,evidence_id FROM capability_observations "
            "WHERE capability_id='capability:client-dat-record:16385'"
        ).fetchone()
        assert obs is not None and obs[0]=="VERIFIED",obs
        assert obs[2]=="evidence:client-dat:client:30191204_1:16385",obs
        con.close()

    print("client DAT adapter P0 self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
