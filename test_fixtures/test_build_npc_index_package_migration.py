from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

from workbench.devtools.indexing import build_npc_index as canonical
from workbench.runtime.paths import DATABASE_PATH, VENDOR_ROOT

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_root():
    spec = importlib.util.spec_from_file_location("build_npc_index", REPO_ROOT / "build_npc_index.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_npc_index"] = module
    spec.loader.exec_module(module)
    return sys.modules["build_npc_index"]


def main() -> None:
    assert load_root() is canonical
    assert canonical.DB_PATH == DATABASE_PATH
    assert canonical.DAT_EXTRACTOR_EXE == VENDOR_ROOT / "dat-extractor" / "bin" / "Debug" / "net9.0" / "dat-extractor.exe"
    assert canonical.npclist_id_for_zone(77) == 6797

    con = sqlite3.connect(":memory:")
    canonical.init_db(con)
    cols = {row[1] for row in con.execute("PRAGMA table_info(npc_names)")}
    assert {"zoneid", "npcid", "name", "content_tag", "norm_name"} <= cols
    con.execute("CREATE TABLE zones (zoneid INTEGER, name TEXT)")
    con.execute("INSERT INTO zones VALUES (77, 'NYZUL_ISLE')")
    assert canonical.resolve_zoneid(con, "Nyzul_Isle") == 77
    assert canonical.resolve_zoneid(con, "Missing_Zone") is None
    con.close()

    print("NPC index package migration: PASS")


if __name__ == "__main__":
    main()
