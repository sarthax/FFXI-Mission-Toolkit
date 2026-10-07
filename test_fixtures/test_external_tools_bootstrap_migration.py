from __future__ import annotations

import importlib.util
from pathlib import Path

from workbench.runtime import external_tools

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "scripts" / "bootstrap" / "install_external_tools.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    launcher = _load(CANONICAL, "external_tools_launcher_test")
    assert launcher.TOOLS_ROOT == ROOT
    assert launcher.INSTALLERS is external_tools.INSTALLERS
    assert external_tools.TOOLS_ROOT == ROOT
    assert set(external_tools.INSTALLERS) == {
        "xi-tinkerer-cli",
        "ffxi-dats",
        "landsandboat-full",
        "ffxi-resources-dist",
        "yt-dlp",
        "ffmpeg",
        "tesseract",
    }
    assert external_tools.pending_installer("not-a-tool") is None
    assert not (ROOT / "install_external_tools.py").exists()

    setup = (ROOT / "setup.bat").read_text(encoding="utf-8")
    assert "scripts\\bootstrap\\install_external_tools.py xi-tinkerer-cli" in setup
    assert "%PY% install_external_tools.py" not in setup


if __name__ == "__main__":
    main()
