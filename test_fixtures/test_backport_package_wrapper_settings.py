from pathlib import Path
import importlib


def test_orchestrator_resolves_package_safe_cli_defaults():
    canonical = importlib.import_module("workbench.packages.migration.orchestrator")
    legacy = importlib.import_module("workbench.runtime.legacy_settings")
    runtime_paths = importlib.import_module("workbench.runtime.paths")

    assert canonical._default_dsp_root() == legacy.get_dsp_root()
    assert canonical._default_db_path() == runtime_paths.DATABASE_PATH


def test_backport_package_root_wrapper_is_retired():
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "backport_package.py").exists()
