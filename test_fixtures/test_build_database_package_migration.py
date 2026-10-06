import importlib
import sys
from pathlib import Path
from types import ModuleType

from workbench.client.dat import extractor_bin
from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT, VENDOR_ROOT


def _import_database_indexer(monkeypatch):
    # xi_tinkerer is an optional compiled wheel installed by setup.bat, not pyproject.toml.
    # The implementation only dereferences it when client parsing is requested, so a module stub
    # is sufficient for package-migration import/path tests in CI.
    monkeypatch.setitem(sys.modules, "xi_tinkerer", ModuleType("xi_tinkerer"))
    sys.modules.pop("workbench.devtools.indexing.build_database", None)
    return importlib.import_module("workbench.devtools.indexing.build_database")


def test_root_build_database_shim_is_retired(monkeypatch):
    _import_database_indexer(monkeypatch)
    assert not (REPO_ROOT / "build_database.py").exists()


def test_canonical_build_database_preserves_repository_paths(monkeypatch):
    canonical = _import_database_indexer(monkeypatch)
    assert canonical.TOOLS_ROOT == REPO_ROOT
    assert canonical.DB_PATH == DATABASE_PATH
    assert canonical.LSB_ROOT == REPO_ROOT / "LandSandBoat"
    assert canonical.XI_TINKERER_EXE == VENDOR_ROOT / "xi-tinkerer/target/release/xi-tinkerer-cli.exe"
    assert canonical.DAT_EXTRACTOR_EXE == extractor_bin.EXE
    assert canonical.ALTANA_ZONES_CSV == VENDOR_ROOT / "ffxi/reference/AltanaViewer_zones.csv"
    assert canonical.FFXI_RESOURCES_DIST == REPO_ROOT / "FFXI-Resources-dist"
    assert canonical.DB_BACKUPS_DIR == REPO_ROOT / "db_backups"


def test_database_indexer_import_time_opcode_table_still_loads(monkeypatch):
    canonical = _import_database_indexer(monkeypatch)
    assert canonical.OPCODE_TABLE
    assert canonical.SIZES
    assert canonical.NAMES


def test_database_indexer_keeps_core_normalization_behavior(monkeypatch):
    canonical = _import_database_indexer(monkeypatch)
    assert canonical.normalize("Foo Bar!") == "foobar"


def test_implementation_remains_packaged_under_src():
    impl_source = Path("src/workbench/devtools/indexing/_build_database_impl.py").read_text(encoding="utf-8")
    assert "import xi_tinkerer" in impl_source
    assert "import settings" in impl_source
