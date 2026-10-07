from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_test(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> None:
    canonical = importlib.import_module("workbench.validation.packages.lua_sanity")
    assert not (REPO_ROOT / "backport_lua_sanity_check.py").exists()

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        good = root / "good"
        good.mkdir()
        (good / "IDs.lua").write_text("Periqia = {}\n", encoding="utf-8")
        (good / "npc.lua").write_text("local ID = Periqia\n", encoding="utf-8")
        result = canonical.check_package(good)
        assert result["file_count"] == 2
        assert result["undeclared_globals"] == []

        bad = root / "bad"
        bad.mkdir()
        (bad / "npc.lua").write_text("local ID = Periqia\n", encoding="utf-8")
        result = canonical.check_package(bad)
        assert len(result["undeclared_globals"]) == 1
        assert result["undeclared_globals"][0][1] == "Periqia"

    code = (
        "from workbench.validation.packages.lua_sanity import check_package; "
        "print(check_package)"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)

    converter_migration = _load_test(
        "_lua_converter_map_lint_package_migration",
        REPO_ROOT / "test_fixtures" / "test_lua_converter_map_lint_package_migration.py",
    )
    converter_migration.main()


if __name__ == "__main__":
    main()
