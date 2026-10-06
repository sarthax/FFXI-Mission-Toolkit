from __future__ import annotations

import importlib
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    tables = importlib.import_module("workbench.client.models.mob_model_tables")
    assert not (REPO_ROOT / "mob_model_tables.py").exists()

    assert tables.resolve_family_file_id(169, 740) == 2017
    assert tables.resolve_family_file_id(169, 755) == 2032
    assert tables.resolve_family_dat_path(169, 740) == r"ROM\7\64.DAT"
    assert tables.resolve_family_file_id(133, 497) == 1797
    assert tables.resolve_family_file_id(133, 680) == 1980
    assert tables.resolve_family_file_id(133, 1086) is None
    assert tables.resolve_family_file_id(447, 2605) == 52900
    assert tables.resolve_family_file_id(9999, 1) is None

    code = (
        "from pathlib import Path; "
        "from workbench.client.models import mob_model_tables as t; "
        "assert t.resolve_family_file_id(169, 740) == 2017; "
        "assert t.resolve_family_file_id(133, 1086) is None; "
        "assert t.resolve_family_dat_path(169, 755) == r'ROM\\7\\79.DAT'; "
        "assert 'src' in Path(t.__file__).resolve().parts; "
        "print('outside-repo mob model tables import: PASS')"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)
    print("mob model tables package migration: PASS")


if __name__ == "__main__":
    main()
