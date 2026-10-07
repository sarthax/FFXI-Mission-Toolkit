from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.modules.setdefault(
    "xi_tinkerer",
    SimpleNamespace(
        parse_zone_collision_obj=lambda _path: "v 0 0 0\nv 10 0 0\nv 0 0 10\nf 1 2 3\n",
        parse_zone_visual_obj=lambda _path: "v 0 0 0\nv 10 0 0\nv 0 0 10\nf 1 2 3\n",
    ),
)

from workbench.devtools.spatial import build_topdown as canonical
from workbench.devtools.spatial import build_visual_cache
from workbench.runtime.paths import DATABASE_PATH, GUI_ROOT

REPO_ROOT = Path(__file__).resolve().parents[1]



def main() -> None:
    assert not (REPO_ROOT / "build_zone_topdown.py").exists()
    assert canonical.DB_PATH == DATABASE_PATH
    assert canonical.CACHE_DIR == GUI_ROOT / "static" / "zone_topdown"
    assert canonical.build_visual_cache is build_visual_cache

    verts, faces = canonical.parse_obj_topdown(
        "v 1.5 2.0 -3.5\nv 4.0 5.0 6.0\nv 7.0 8.0 9.0\nf 1 2 3\n"
    )
    assert verts == [(1.5, -3.5), (4.0, 6.0), (7.0, 9.0)]
    assert faces == [(1, 2, 3)]

    print("Zone top-down package migration: PASS")


if __name__ == "__main__":
    main()
