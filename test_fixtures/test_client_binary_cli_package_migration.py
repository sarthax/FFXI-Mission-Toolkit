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
    inspector = importlib.import_module("workbench.client.binary.inspector")

    for retired in ("client_binary_analyze.py", "client_binary_index.py", "client_binary_diff.py"):
        assert not (REPO_ROOT / retired).exists(), retired

    # Binary Inspector is a separate compatibility contract and remains intentionally supported.
    assert load_root("binary_inspector", "binary_inspector.py") is inspector

    assert analyze._int("0x20") == 32
    assert callable(index_cli.index_binary)
    assert callable(diff_cli.diff_binary_indexes)
    assert inspector.PROBE_DIR == REPO_ROOT / "client_probe_sets"
    sets = {row["file"]: row for row in inspector.list_probe_sets()}
    assert "mog_wardrobe.json" in sets

    with tempfile.TemporaryDirectory() as td:
        code = (
            "from workbench.client.cli import binary_analyze, binary_index, binary_diff; "
            "from workbench.client.binary import inspector; "
            "assert binary_analyze._int('0x10') == 16; "
            "assert callable(binary_index.main) and callable(binary_diff.main); "
            "assert inspector.PROBE_DIR.name == 'client_probe_sets'; "
            "assert any(x['file'] == 'mog_wardrobe.json' for x in inspector.list_probe_sets()); "
            "print('outside-repo client binary import: PASS')"
        )
        subprocess.run([sys.executable, "-c", code], cwd=td, check=True)
        for module in (
            "workbench.client.cli.binary_analyze",
            "workbench.client.cli.binary_index",
            "workbench.client.cli.binary_diff",
        ):
            subprocess.run([sys.executable, "-m", module, "--help"], cwd=td, check=True)

    print("client binary package migration: PASS")


if __name__ == "__main__":
    main()
