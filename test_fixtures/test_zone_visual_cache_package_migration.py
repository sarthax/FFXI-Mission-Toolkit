from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.modules.setdefault("xi_tinkerer", SimpleNamespace(parse_zone_visual_obj=lambda _path: "v 0 0 0\nf 1 1 1\n"))

from workbench.devtools.spatial import build_visual_cache as canonical
from workbench.runtime.paths import DATABASE_PATH, GUI_ROOT

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_root():
    spec = importlib.util.spec_from_file_location("build_zone_visual_cache", REPO_ROOT / "build_zone_visual_cache.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_zone_visual_cache"] = module
    spec.loader.exec_module(module)
    return sys.modules["build_zone_visual_cache"]


def main() -> None:
    assert load_root() is canonical
    assert canonical.DB_PATH == DATABASE_PATH
    assert canonical.CACHE_DIR == GUI_ROOT / "static" / "zone_visual"
    assert canonical.visual_mesh_api_available()

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        dat = root / "ROM" / "1" / "1.DAT"
        dat.parent.mkdir(parents=True)
        dat.write_bytes(b"stub")
        cache = root / "cache"

        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE zones (zoneid INTEGER, name TEXT, geometry_rom_path TEXT)")
        con.execute("INSERT INTO zones VALUES (1, 'TEST_ZONE', 'ROM/1/1.DAT')")
        with patch.object(canonical, "CACHE_DIR", cache):
            assert canonical.build_one(con, 1, str(root)) is True
        assert (cache / "1.obj").exists()
        con.close()

    print("Zone visual cache package migration: PASS")


if __name__ == "__main__":
    main()
