import importlib
import sys
from pathlib import Path
from types import ModuleType

from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT


def _import_lsb_indexer(monkeypatch):
    monkeypatch.setitem(sys.modules, "xi_tinkerer", ModuleType("xi_tinkerer"))
    for name in (
        "workbench.devtools.indexing.build_lsb_index",
        "workbench.devtools.indexing.build_database",
    ):
        sys.modules.pop(name, None)
    return importlib.import_module("workbench.devtools.indexing.build_lsb_index")


def test_root_build_lsb_index_shim_is_retired(monkeypatch):
    _import_lsb_indexer(monkeypatch)
    assert not (REPO_ROOT / "build_lsb_index.py").exists()


def test_canonical_build_lsb_index_uses_packaged_foundations(monkeypatch):
    canonical = _import_lsb_indexer(monkeypatch)
    build_database = importlib.import_module("workbench.devtools.indexing.build_database")
    build_sql_index = importlib.import_module("workbench.devtools.indexing.build_sql_index")
    assert canonical.build_database is build_database
    assert canonical.sqlidx is build_sql_index
    assert canonical.normalize is build_database.normalize
    assert canonical.parse_table_file is build_sql_index.parse_table_file
    assert canonical.unquote is build_sql_index.unquote


def test_canonical_build_lsb_index_preserves_repository_paths(monkeypatch):
    canonical = _import_lsb_indexer(monkeypatch)
    assert canonical.TOOLS_ROOT == REPO_ROOT
    assert canonical.DB_PATH == DATABASE_PATH
    assert canonical.WORKBENCH_DB == REPO_ROOT / "workbench.db"
    assert canonical.LSB_ROOT == REPO_ROOT / "LandSandBoat"
    assert canonical.LSB_SQL_DIR == REPO_ROOT / "LandSandBoat" / "sql"
    assert canonical.LSB_SCRIPTS_DIR == REPO_ROOT / "LandSandBoat" / "scripts" / "zones"


def test_lsb_effect_name_normalization_is_preserved(monkeypatch):
    canonical = _import_lsb_indexer(monkeypatch)
    assert canonical._lsb_effect_norm_name("sleep_i") == "sleep"
    assert canonical._lsb_effect_norm_name("sleep_ii") == "sleepii"


def test_implementation_remains_packaged_under_src():
    impl_source = Path("src/workbench/devtools/indexing/_build_lsb_index_impl.py").read_text(encoding="utf-8")
    assert "import build_database" in impl_source
    assert "import build_sql_index as sqlidx" in impl_source
