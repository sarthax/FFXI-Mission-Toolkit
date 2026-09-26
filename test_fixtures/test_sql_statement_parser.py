#!/usr/bin/env python3
"""Regression coverage for SQL statement parsing used by DSP/Topaz/LSB indexers."""
from pathlib import Path
import tempfile

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

    print("SQL statement parser self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
