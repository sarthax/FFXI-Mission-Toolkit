from pathlib import Path
import importlib

from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT


def test_root_build_sql_index_shim_is_retired():
    importlib.import_module("workbench.devtools.indexing.build_sql_index")
    assert not (REPO_ROOT / "build_sql_index.py").exists()


def test_canonical_build_sql_index_preserves_repository_paths():
    canonical = importlib.import_module("workbench.devtools.indexing.build_sql_index")
    assert canonical.TOOLS_ROOT == REPO_ROOT
    assert canonical.DB_PATH == DATABASE_PATH
    assert canonical.WORKBENCH_DB == REPO_ROOT / "workbench.db"
    assert canonical.LSB_ROOT == REPO_ROOT / "LandSandBoat"
    assert canonical.SQL_DIR == REPO_ROOT / "LandSandBoat" / "sql"
    assert canonical._CLEAN_CACHE_DIR == REPO_ROOT / "mission_reports" / "_sql_clean"


def test_canonical_build_sql_index_keeps_parser_behavior():
    canonical = importlib.import_module("workbench.devtools.indexing.build_sql_index")
    assert canonical.split_sql_values("'alpha,beta', 42, NULL") == ["'alpha,beta'", "42", "NULL"]


def test_implementation_remains_packaged_under_src():
    impl_source = Path("src/workbench/devtools/indexing/_build_sql_index_impl.py").read_text(encoding="utf-8")
    assert "import settings" in impl_source
