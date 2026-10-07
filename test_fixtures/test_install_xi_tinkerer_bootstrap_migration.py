from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT / "scripts" / "bootstrap" / "install_xi_tinkerer.py"


def load_impl():
    spec = importlib.util.spec_from_file_location("test_bootstrap_install_xi_tinkerer", IMPL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    assert IMPL.is_file()
    assert not (ROOT / "install_xi_tinkerer.py").exists()
    module = load_impl()

    exact = f"xi_tinkerer-1.0-cp{sys.version_info.major}{sys.version_info.minor}-cp{sys.version_info.major}{sys.version_info.minor}-win_amd64.whl"
    abi3 = "xi_tinkerer-1.0-cp39-abi3-win_amd64.whl"
    other = "xi_tinkerer-1.0-py3-none-any.whl"
    assets = [
        {"name": abi3, "browser_download_url": "https://example.invalid/abi3"},
        {"name": exact, "browser_download_url": "https://example.invalid/exact"},
        {"name": other, "browser_download_url": "https://example.invalid/other"},
    ]
    assert module.pick_asset(assets)["name"] == exact
    assert module.pick_asset([assets[0]])["name"] == abi3
    assert module.pick_asset([assets[2]]) is None

    setup = (ROOT / "setup.bat").read_text(encoding="utf-8")
    assert "scripts\\bootstrap\\install_xi_tinkerer.py" in setup
    assert "%PY% install_xi_tinkerer.py" not in setup


if __name__ == "__main__":
    main()
