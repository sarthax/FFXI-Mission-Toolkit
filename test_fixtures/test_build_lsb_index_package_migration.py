import importlib
import sys
from pathlib import Path
from types import ModuleType

from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT


def _import_lsb_indexer(monkeypatch):
    monkeypatch.setitem(sys.modules, "xi_tinkerer", ModuleType("xi_tinkerer"))
    for name in (
        "build_lsb_index",
        "workbench.devtools.indexing.build_lsb_index",
        "build_database",
        "workbench.devtools.indexing.build_database",
    ):
        sys.modules.pop(name, None)
    canonical = importlib.import_module("workbench.devtools.indexing.build_lsb_index")
    root = importlib.import_module("build_lsb_index")
    return root, canonical


def test_root_build_lsb_index_aliases_canonical_module(monkeypatch):
    root, canonical = _import_lsb_indexer(monkeypatch)
    assert root is canonical


def test_canonical_build_lsb_index_uses_packaged_foundations(monkeypatch):
    _, canonical = _import_lsb_indexer(monkeypatch)
    build_database = importlib.import_module("workbench.devtools.indexing.build_database")
    build_sql_index = importlib.import_module("workbench.devtools.indexing.build_sql_index")
    assert canonical.build_database is build_database
    assert canonical.sqlidx is build_sql_index
    assert canonical.normalize is build_database.normalize
    assert canonical.parse_table_file is build_sql_index.parse_table_file
    assert canonical.unquote is build_sql_index.unquote


def test_canonical_build_lsb_index_preserves_repository_paths(monkeypatch):
    _, canonical = _import_lsb_indexer(monkeypatch)
    assert canonical.TOOLS_ROOT == REPO_ROOT
    assert canonical.DB_PATH == DATABASE_PATH
    assert canonical.WORKBENCH_DB == REPO_ROOT / "workbench.db"
    assert canonical.LSB_ROOT == REPO_ROOT / "LandSandBoat"
    assert canonical.LSB_SQL_DIR == REPO_ROOT / "LandSandBoat" / "sql"
    assert canonical.LSB_SCRIPTS_DIR == REPO_ROOT / "LandSandBoat" / "scripts" / "zones"


def test_lsb_effect_name_normalization_is_preserved(monkeypatch):
    _, canonical = _import_lsb_indexer(monkeypatch)
    assert canonical._lsb_effect_norm_name("sleep_i") == "sleep"
    assert canonical._lsb_effect_norm_name("sleep_ii") == "sleepii"


def test_root_wrapper_is_thin_and_implementation_moved_under_src():
    root_source = Path("build_lsb_index.py").read_text(encoding="utf-8")
    impl_source = Path("src/workbench/devtools/indexing/_build_lsb_index_impl.py").read_text(encoding="utf-8")
    assert "import settings" not in root_source
    assert "from workbench.devtools.indexing import build_lsb_index as _canonical" in root_source
    assert "import build_database" in impl_source
    assert "import build_sql_index as sqlidx" in impl_source
