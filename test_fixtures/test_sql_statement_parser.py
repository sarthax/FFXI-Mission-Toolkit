#!/usr/bin/env python3
"""Regression coverage for SQL statement parsing used by DSP/Topaz/LSB indexers."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))  # repo root, so no PYTHONPATH needed

import build_sql_index as sqlidx


def main():
    cols=["id","name","x"]

    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/"fixture.sql"
        p.write_text(
            "-- leading comment must not prefix the next statement\n"
            "INSERT INTO `demo` VALUES (1,'alpha',1.5); INSERT INTO `demo` VALUES (2,'beta',2.5);\n"
            "INSERT INTO `other` VALUES (99,'ignore',0);\n"
            "INSERT INTO `demo` VALUES (\n"
            "  3,\n"
            "  'semi;colon -- still text',\n"
            "  3.5\n"
            "); -- trailing comment\n"
            "INSERT INTO `demo` VALUES (4,'quote\\'s ok',4.5);\n",
            encoding="utf-8",
        )

        rows=list(sqlidx.parse_table_file(p,"demo",cols))
        assert len(rows)==4,rows
        assert rows[0]=={"id":"1","name":"'alpha'","x":"1.5"},rows[0]
        assert rows[1]["id"]=="2",rows[1]
        assert rows[2]["id"]=="3",rows[2]
        assert sqlidx.unquote(rows[2]["name"])=="semi;colon -- still text",rows[2]
        assert rows[3]["id"]=="4",rows[3]

        # Exact legacy-DSP failure shape: several complete INSERTs on one physical line.
        q=Path(td)/"npc_list.sql"
        values=lambda ident: ",".join([
            str(ident),f"'npc_{ident}'","'npc'", "0","1.0","2.0","3.0","0",
            "0","0","0","0","0","0","0","'0x00'","0","NULL","0"
        ])
        q.write_text(
            " ".join(
                f"INSERT INTO `npc_list` VALUES ({values(17020+i)});"
                for i in range(4)
            ),
            encoding="utf-8",
        )
        npc_cols=[
            "npcid","name","polutils_name","pos_rot","pos_x","pos_y","pos_z","flag",
            "speed","speedsub","animation","animationsub","namevis","status",
            "entityFlags","look","name_prefix","content_tag","widescan",
        ]
        npc_rows=list(sqlidx.parse_table_file(q,"npc_list",npc_cols))
        assert len(npc_rows)==4,npc_rows
        assert [row["npcid"] for row in npc_rows]==["17020","17021","17022","17023"],npc_rows
        assert all(");" not in row["pos_x"] for row in npc_rows),npc_rows

        # Real DSP mob_spawn_points.sql failure shape: a single INSERT statement with several
        # comma-separated VALUES tuples, not several complete statements. Before
        # split_insert_tuples(), this glued one row's last real column to the next row's leading
        # digits (e.g. pos_x becoming "17021);179") and crashed float() during a DSP cache rebuild.
        r=Path(td)/"mob_spawn_points.sql"
        spawn_cols=["mobid","mobname","polutils_name","groupid","pos_x","pos_y","pos_z","pos_rot"]
        r.write_text(
            "INSERT INTO `mob_spawn_points` VALUES "
            "(1,'Foo','foo',10,100.5,0,0,17021),(2,'Bar','bar',11,179.0,0,0,90);\n",
            encoding="utf-8",
        )
        spawn_rows=list(sqlidx.parse_table_file(r,"mob_spawn_points",spawn_cols))
        assert len(spawn_rows)==2,spawn_rows
        assert float(sqlidx.unquote(spawn_rows[0]["pos_rot"]))==17021.0,spawn_rows[0]
        assert float(sqlidx.unquote(spawn_rows[1]["pos_x"]))==179.0,spawn_rows[1]
        assert all(");" not in row["pos_x"] and "(" not in row["pos_x"] for row in spawn_rows),spawn_rows

        # Real live corruption found in old-dsp-reference's mob_spawn_points.sql (Byakko's row):
        # a genuinely malformed statement (extra stray value, premature "');", missing the
        # trailing ";") leaves its real pos_x/y/z/rot dangling with no semicolon. Before search()
        # replaced an anchored match(), that dangling text got glued onto the *next* statement
        # (Seiryu's, here) and silently dropped it -- invisible data loss for a row that was
        # otherwise perfectly well-formed. The corrupted row itself must still be reported as
        # schema drift (it genuinely has the wrong shape); the point is the *following* row must
        # not silently vanish too.
        s=Path(td)/"mob_spawn_points_corrupt.sql"
        s.write_text(
            "INSERT INTO `mob_spawn_points` VALUES (17961561,'Byakko','Byakko',14430,14471);"
            "105.699,-40.5,-442.299,55\n"
            "INSERT INTO `mob_spawn_points` VALUES (17961567,'Seiryu','Seiryu',14472,95.754,-40.5,-440.72,155);\n",
            encoding="utf-8",
        )
        corrupt_rows=list(sqlidx.parse_table_file(s,"mob_spawn_points",spawn_cols))
        # The corrupted row itself is now repaired too (stray 14471 dropped, groupid 14430 kept
        # -- 14430 exists in mob_groups, 14471 does not), so both rows survive.
        assert [r["mobid"] for r in corrupt_rows]==["17961561","17961567"],corrupt_rows
        assert corrupt_rows[0]["groupid"]=="14430" and corrupt_rows[0]["pos_x"]=="105.699",corrupt_rows[0]
        assert sqlidx.unquote(corrupt_rows[1]["mobname"])=="Seiryu",corrupt_rows[1]

    print("SQL statement parser self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
