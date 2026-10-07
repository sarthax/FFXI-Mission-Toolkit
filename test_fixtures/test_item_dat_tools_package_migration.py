from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.editors.items import dat_tools


def main() -> None:
    assert not (ROOT / "item_dat_tools.py").exists()
    assert Path(dat_tools.__file__) == ROOT / "item_dat_tools.py"
    assert dat_tools._dat_backup_root() == ROOT / "data" / "item_dat_backups"
    assert Path(dat_tools.settings_mod.DB_PATH) == ROOT / "ffxi_zone_database.db"
    assert dat_tools.STRIDE_LEGACY == 0xC00
    assert dat_tools.STRIDE_RETAIL == 0x1400
    assert dat_tools.TYPE_LAYOUT[3] == "armor"



if __name__ == "__main__":
    main()
