from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "scripts" / "bootstrap" / "install_external_tools.py"
ROOT_SHIM = ROOT / "install_external_tools.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    canonical = _load(CANONICAL, "external_tools_canonical_test")
    assert canonical.TOOLS_ROOT == ROOT
    assert set(canonical.INSTALLERS) == {
        "xi-tinkerer-cli",
        "ffxi-dats",
        "landsandboat-full",
        "ffxi-resources-dist",
        "yt-dlp",
        "ffmpeg",
        "tesseract",
    }
    assert canonical.pending_installer("not-a-tool") is None

    root_module = _load(ROOT_SHIM, "install_external_tools")
    assert root_module.TOOLS_ROOT == ROOT
    assert root_module.INSTALLERS is not None
    assert sys.modules["install_external_tools"] is root_module

    source = ROOT_SHIM.read_text(encoding="utf-8")
    assert "urllib.request.urlopen" not in source
    assert "scripts\" / \"bootstrap\" / \"install_external_tools.py" in source


if __name__ == "__main__":
    main()
