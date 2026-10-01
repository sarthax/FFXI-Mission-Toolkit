#!/usr/bin/env python3
import sqlite3

import lookup_entity as legacy
from workbench.devtools.entities import lookup
from workbench.runtime.paths import DATABASE_PATH


def main():
    assert lookup.DB_PATH == DATABASE_PATH
    assert legacy.resolve_query_to_ids is lookup.resolve_query_to_ids

    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE npc_names(npcid INTEGER, name TEXT, zoneid INTEGER, norm_name TEXT)")
    con.executemany(
        "INSERT INTO npc_names VALUES(?,?,?,?)",
        [
            (100, "Lamia No.13", 55, "lamiano13"),
            (101, "Qiqirn_Treasure_Hunter", 56, "qiqirntreasurehunter"),
        ],
    )
    assert lookup.resolve_query_to_ids(con, "Lamia No 13") == [(100, "Lamia No.13", 55)]
    assert lookup.count_name_matches(con, "Qiqirn Treasure Hunter") == 1
    con.close()

    print("Development entity lookup migration self-test: PASS")


if __name__ == "__main__":
    main()
