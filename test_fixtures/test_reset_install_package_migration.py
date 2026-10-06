from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "scripts" / "bootstrap" / "reset_install.py"


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
    assert not (ROOT / "reset_install.py").exists()

    launcher = (ROOT / "reset_install.bat").read_text(encoding="utf-8")
    assert "scripts\\bootstrap\\reset_install.py" in launcher
    assert "python reset_install.py" not in launcher


if __name__ == "__main__":
    main()
