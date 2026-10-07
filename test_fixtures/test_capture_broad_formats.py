#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.captures.ingestion import build_index as build_capture_index


def sqlite_blob(path: Path, columns: str, values: tuple) -> bytes:
    con=sqlite3.connect(path)
    con.execute(f"CREATE TABLE entries ({columns})")
    placeholders=",".join("?" for _ in values)
    con.execute(f"INSERT INTO entries VALUES ({placeholders})",values)
    con.commit()
    con.close()
    return path.read_bytes()


def main():
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        db=root/"capture.db"
        con=sqlite3.connect(db)
        build_capture_index.init_db(con)
        cid=build_capture_index.create_manual_capture(con,"broad formats","Research",None)

        # Current Captain ShopStock buy DB.
        buy=sqlite_blob(
            root/"BuyList.db",
            "id TEXT PRIMARY KEY, version INTEGER, created_at INTEGER, updated_at INTEGER, "
            "NpcUniqueNo INTEGER, NpcName TEXT, NpcZone TEXT, GuildInfo INTEGER, ItemNo INTEGER, "
            "ItemName TEXT, ItemPrice INTEGER, ShopIndex INTEGER, Skill INTEGER",
            ("Curio Vendor Moogle-123",1,100,100,17777777,"Curio Vendor Moogle","Port Jeuno",
             0,123,"Potion",250,1,0),
        )
        r=build_capture_index.ingest_single_file(con,cid,"BuyList.db",buy)
        assert r["format"]=="shopstock_buy_db" and r["rows"]==1,r

        # Historical Captain GuildStock generation: no NPC identity and no Hidden column.
        legacy_guild=sqlite_blob(
            root/"GuildBuy.db",
            "id TEXT PRIMARY KEY, version INTEGER, created_at INTEGER, updated_at INTEGER, "
            "ItemNo INTEGER, ItemName TEXT, Count INTEGER, Max INTEGER, Price INTEGER",
            ("456",1,101,101,456,"Copper Ore",12,80,24),
        )
        r=build_capture_index.ingest_single_file(con,cid,"GuildBuy.db",legacy_guild)
        assert r["format"]=="guildstock_db" and r["rows"]==1,r

        # Current Captain SpawnTrack CSV.
        spawn=(
            "MobName,UniqueNo,DefeatedAt,DespawnedAt,SpawnedAt,DefeatToSpawnDiff,"
            "DespawnToSpawnDiff,XDefeated,YDefeated,ZDefeated,XSpawn,YSpawn,ZSpawn\n"
            "Test Mob,17000001,2026-09-28 10:00:00,2026-09-28 10:00:02,"
            "2026-09-28 10:05:00,300,298,1.0,2.0,3.0,4.0,5.0,6.0\n"
        ).encode()
        r=build_capture_index.ingest_single_file(con,cid,"spawn.csv",spawn)
        assert r["format"]=="spawntrack_csv" and r["rows"]==1,r

        # Historical CheckParam generation before syncId was added.
        checkparam=(
            "recvTime,acc,atk,offacc,offatk,rangeacc,rangeatk,eva,def\n"
            "12345.5,950,1200,900,1100,875,1000,800,700\n"
        ).encode()
        r=build_capture_index.ingest_single_file(con,cid,"checkparam.csv",checkparam)
        assert r["format"]=="checkparam_csv" and r["rows"]==1,r

        # Current Captain MissionTrack text.
        mission=(
            "[2026-09-28 10:06:00] Main Mission\n"
            "{\n"
            "  { \"Zone\", \"Aht Urhgan Whitegate\" },\n"
            "  { \"Mission\", \"Assault\" },\n"
            "  { \"Progress\", \"1 -> 2\" }\n"
            "}\n\n"
        ).encode()
        r=build_capture_index.ingest_single_file(con,cid,"Tester_missions.log",mission)
        assert r["format"]=="missiontrack" and r["rows"]==1,r

        # Historical Wiggo PriceLog simple observation.
        price=(
            "Incoming: 0x03D (Price Response), Item: 123 (Potion) Price: 31 "
            "Character: Tester Zone: Port Jeuno NPC: Curio Vendor Moogle\n\n"
        ).encode()
        r=build_capture_index.ingest_single_file(con,cid,"simple.log",price)
        assert r["format"]=="pricelog_simple" and r["rows"]==1,r

        rows=con.execute(
            """SELECT family,record_type,zone,entity_id,entity_name,item_id,item_name,price,payload_json
               FROM capture_structured_records WHERE capture_id=? ORDER BY family""",(cid,)
        ).fetchall()
        assert len(rows)==6,rows
        by_family={r[0]:r for r in rows}
        assert by_family["shopstock_buy_db"][3]==17777777
        assert by_family["shopstock_buy_db"][5]==123
        assert by_family["shopstock_buy_db"][7]==250
        assert by_family["spawntrack_csv"][3]==17000001
        assert by_family["guildstock_db"][5]==456
        assert by_family["guildstock_db"][3] is None
        assert by_family["checkparam_csv"][2] is None
        assert by_family["missiontrack"][2]=="Aht Urhgan Whitegate"
        assert by_family["pricelog_simple"][5]==123
        assert by_family["pricelog_simple"][7]==31

        locators=con.execute(
            """SELECT filename,locator_basis,COUNT(*) FROM capture_row_locators
               WHERE capture_id=? AND target_table='capture_structured_records'
               GROUP BY filename,locator_basis ORDER BY filename""",(cid,)
        ).fetchall()
        assert len(locators)==6,locators
        assert {x[1] for x in locators}=={"sqlite-row","csv-row","block"},locators

        # Re-adding the same sources must replace their deterministic keys, not duplicate rows.
        build_capture_index.ingest_single_file(con,cid,"spawn.csv",spawn)
        build_capture_index.ingest_single_file(con,cid,"simple.log",price)
        count=con.execute(
            "SELECT COUNT(*) FROM capture_structured_records WHERE capture_id=?",(cid,)
        ).fetchone()[0]
        assert count==6,count

        # Schema sniffers are content based, independent of filenames.
        assert build_capture_index.sniff_sqlite_format(buy)=="shopstock_buy_db"
        assert build_capture_index.sniff_csv_format(spawn.decode())=="spawntrack_csv"
        assert build_capture_index.sniff_sqlite_format(legacy_guild)=="guildstock_db"
        assert build_capture_index.sniff_csv_format(checkparam.decode())=="checkparam_csv"
        assert build_capture_index.sniff_text_format(mission.decode())=="missiontrack"
        assert build_capture_index.sniff_text_format(price.decode())=="pricelog_simple"

        con.close()

    print("Broad capture format ingestion regression: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
