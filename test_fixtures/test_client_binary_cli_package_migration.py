from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_root(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return sys.modules[name]


def main() -> None:
    analyze = importlib.import_module("workbench.client.cli.binary_analyze")
    index_cli = importlib.import_module("workbench.client.cli.binary_index")
    diff_cli = importlib.import_module("workbench.client.cli.binary_diff")

    assert load_root("client_binary_analyze", "client_binary_analyze.py") is analyze
    assert load_root("client_binary_index", "client_binary_index.py") is index_cli
    assert load_root("client_binary_diff", "client_binary_diff.py") is diff_cli

    assert analyze._int("0x20") == 32
    assert callable(index_cli.index_binary)
    assert callable(diff_cli.diff_binary_indexes)

    code = (
        "from workbench.client.cli import binary_analyze, binary_index, binary_diff; "
        "assert binary_analyze._int('0x10') == 16; "
        "assert callable(binary_index.main) and callable(binary_diff.main); "
        "print('outside-repo client binary CLI import: PASS')"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)
    print("client binary CLI package migration: PASS")


if __name__ == "__main__":
    main()
