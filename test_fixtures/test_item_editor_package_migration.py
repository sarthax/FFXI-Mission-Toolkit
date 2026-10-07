from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.devtools.spatial import zone_plot
from workbench.editors.items import dat_tools, editor


def main() -> None:
    assert not (ROOT / "item_edit.py").exists()
    assert Path(editor.__file__) == ROOT / "item_edit.py"
    assert editor.DATA == ROOT / "data"
    assert editor.BACKUPS == ROOT / "data" / "item_backups"
    assert editor.LOG == ROOT / "data" / "item_edit_log.sql"
    assert editor.dat is dat_tools
    assert editor.zone_plot is zone_plot
    assert "item_basic" in editor.TABLES
    assert "item_equipment" in editor.TABLES



if __name__ == "__main__":
    main()
