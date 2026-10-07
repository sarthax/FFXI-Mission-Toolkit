from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# xi_tinkerer is an optional compiled dependency installed by setup.bat; this migration smoke
# only verifies package ownership/path rebinding and does not invoke client DAT parsing.
sys.modules.setdefault("xi_tinkerer", ModuleType("xi_tinkerer"))

from workbench.devtools.indexing import build_database, build_dsp_index, build_sql_index
from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT, repo_path


def main() -> None:
    assert not (ROOT / "build_dsp_index.py").exists()
    assert build_dsp_index.TOOLS_ROOT == REPO_ROOT == ROOT
    assert build_dsp_index.DB_PATH == DATABASE_PATH
    assert build_dsp_index.WORKBENCH_DB == repo_path("workbench.db")
    assert build_dsp_index.build_database is build_database
    assert build_dsp_index.sqlidx is build_sql_index
    assert build_dsp_index.normalize is build_database.normalize
    assert build_dsp_index.parse_table_file is build_sql_index.parse_table_file
    assert build_dsp_index.unquote is build_sql_index.unquote

    adapter_source = (SRC / "workbench" / "devtools" / "indexing" / "build_dsp_index.py").read_text(encoding="utf-8")
    assert "from workbench.runtime import legacy_settings" in adapter_source
    assert "_build_dsp_index_impl.py" in adapter_source


if __name__ == "__main__":
    main()
