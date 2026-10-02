from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "scripts" / "bootstrap" / "reset_install.py"
ROOT_SHIM = ROOT / "reset_install.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    canonical = _load(CANONICAL, "reset_install_canonical_test")
    assert canonical.TOOLS_ROOT == ROOT
    assert canonical.human_size(1024) == "1KB"
    assert (".venv", "this toolkit's dedicated Python environment (recreated by setup.bat)") in canonical.TARGET_DIRS

    root_module = _load(ROOT_SHIM, "reset_install")
    assert root_module.TOOLS_ROOT == ROOT
    assert root_module.plan is not None
    assert sys.modules["reset_install"] is root_module

    source = ROOT_SHIM.read_text(encoding="utf-8")
    assert "shutil.rmtree" not in source
    assert "scripts\" / \"bootstrap\" / \"reset_install.py" in source


if __name__ == "__main__":
    main()
