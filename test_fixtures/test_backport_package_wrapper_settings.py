from pathlib import Path
import importlib


def test_root_wrapper_aliases_canonical_module():
    root = importlib.import_module("backport_package")
    canonical = importlib.import_module("workbench.packages.migration.orchestrator")
    assert root is canonical


def test_root_wrapper_uses_package_safe_cli_defaults():
    source = Path("backport_package.py").read_text(encoding="utf-8")
    assert "import settings" not in source
    assert "from workbench.runtime.legacy_settings import get_dsp_root" in source
    assert "from workbench.runtime.paths import DATABASE_PATH" in source
    assert "default_dsp_root=get_dsp_root()" in source
    assert "default_db_path=DATABASE_PATH" in source
