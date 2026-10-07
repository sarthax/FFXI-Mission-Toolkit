from __future__ import annotations

import importlib
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    canonical = importlib.import_module("workbench.client.models.schedule_dump")
    assert not (REPO_ROOT / "model_schedule_dump.py").exists()

    assert canonical.model_id_to_file_id(0) == 1300
    assert canonical.model_id_to_file_id(1499) == 2799
    assert canonical.model_id_to_file_id(1500) == 51795
    assert canonical.model_id_to_file_id(3000) == 99907
    assert canonical.model_id_to_file_id(3500) == 101739
    assert canonical.match_anim_ref("at0?", ["at00", "at01", "idle"]) == ["at00", "at01"]
    assert canonical.DAT_EXTRACTOR_DLL == REPO_ROOT / "vendor/dat-extractor/bin/Debug/net9.0/dat-extractor.dll"

    code = (
        "from workbench.client.models import schedule_dump as m; "
        "assert m.model_id_to_file_id(211) == 1511; "
        "assert m.DAT_EXTRACTOR_DLL.name == 'dat-extractor.dll'; "
        "assert m.match_anim_ref('at0?', ['at00','at01','idle']) == ['at00','at01']; "
        "print('outside-repo model schedule import: PASS')"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)
    print("model schedule dump package migration: PASS")


if __name__ == "__main__":
    main()
