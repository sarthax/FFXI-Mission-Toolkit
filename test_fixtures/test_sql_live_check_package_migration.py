from __future__ import annotations

import importlib
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]



class FakeCursor:
    def __init__(self):
        self.rows = []
        self.queries: list[tuple[str, object]] = []

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split())
        self.queries.append((normalized, params))
        if "SELECT DISTINCT npcid, name FROM `npc_list`" in normalized:
            self.rows = [(100, "Same"), (200, "Other")]
        elif "SELECT groupid, dropid FROM `mob_groups` WHERE" in normalized:
            self.rows = [(99, 41)]
        elif "SELECT COUNT(*) FROM `mob_spawn_points` WHERE `groupid` = %s" in normalized:
            gid = params[0]
            self.rows = [(3 if gid == 99 else 0,)]
        elif "GROUP_CONCAT(groupid)" in normalized:
            self.rows = [(20, 30, "99,100")]
        elif "SELECT dropid FROM `mob_groups` WHERE `groupid` = %s" in normalized:
            gid = params[0]
            self.rows = [(41 if gid == 99 else 42,)]
        else:
            raise AssertionError(f"unexpected query: {normalized!r} params={params!r}")

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.rows[0]


def main() -> None:
    live = importlib.import_module("workbench.validation.live_db.sql_check")
    converter = importlib.import_module("workbench.packages.migration.sql_convert")
    assert not (REPO_ROOT / "backport_sql_live_check.py").exists()
    assert live.bsc is converter
    assert sys.modules["backport_sql_convert"] is converter
    assert live.parse_id_range("1,3-5,9") == [1, 3, 4, 5, 9]

    schema = {
        "npc_list": {"id_column": "npcid", "name_column": "name"},
        "mob_groups": {
            "id_column": "groupid",
            "topaz_columns": ["groupid", "poolid", "zoneid", "dropid"],
        },
    }

    cursor = FakeCursor()
    checked = live.check_live(
        cursor,
        "npc_list",
        [100, 200, 300],
        schema,
        id_to_name={100: "Same", 200: "Expected", 300: "Missing"},
    )
    assert checked["same_entity"] == [{"id": 100, "name": "Same"}]
    assert checked["name_mismatch"] == [
        {"id": 200, "live_name": "Other", "our_name": "Expected"}
    ]
    assert checked["unclassified"] == []

    rows = [["10", "20", "30", "40"]]
    duplication = live.check_live_content_duplication(cursor, "mob_groups", rows, schema)
    assert duplication["checked_count"] == 1
    assert duplication["duplicates"][0]["content_key"] == {"poolid": 20, "zoneid": 30}
    assert duplication["duplicates"][0]["existing"] == [
        {"groupid": 99, "dropid": 41, "spawn_count": 3, "classification": "live_conflict"}
    ]

    health = live.scan_live_duplicates(cursor, "mob_groups")
    assert len(health["live_conflict"]) == 1
    assert health["live_conflict"][0]["groups"] == [
        {"groupid": 99, "dropid": 41, "spawn_count": 3},
        {"groupid": 100, "dropid": 42, "spawn_count": 0},
    ]
    assert health["ambiguous"] == []

    # Canonical import must work from outside the checkout and must not require
    # mysql-connector-python until the operator actually invokes main().
    code = (
        "from workbench.validation.live_db import sql_check; "
        "print(sql_check.parse_id_range('7-8'))"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)


if __name__ == "__main__":
    main()
