from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.client.models import look_decode, resolver
from workbench.devtools.spatial import zone_plot
from workbench.editors.zone import editor


def main() -> None:
    assert not (ROOT / "zone_edit.py").exists()
    assert Path(editor.__file__) == ROOT / "zone_edit.py"
    assert editor.DATA == ROOT / "data"
    assert editor.BACKUPS == ROOT / "data" / "zoneplot_backups"
    assert editor.LOG == ROOT / "data" / "zoneplot_edit_log.sql"
    assert editor.zone_plot is zone_plot
    assert editor.client_model_resolver is resolver
    assert editor.mob_look_decode is look_decode
    assert "mob_spawn_points" in editor.TABLES
    assert "instance_entities" in editor.TABLES



if __name__ == "__main__":
    main()
