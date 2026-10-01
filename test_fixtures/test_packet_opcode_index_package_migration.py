#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.packets import opcode_index as canonical
from workbench.runtime.paths import REPO_ROOT


def _load_legacy_launcher():
    path = REPO_ROOT / "packet_opcode_index.py"
    spec = importlib.util.spec_from_file_location("packet_opcode_index", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["packet_opcode_index"] = module
    spec.loader.exec_module(module)
    return sys.modules["packet_opcode_index"]


def main() -> None:
    legacy = _load_legacy_launcher()
    assert legacy is canonical
    assert callable(canonical.index_packet_db)
    assert callable(canonical.index_server)
    assert callable(canonical.self_test)
    assert callable(canonical.main)

    canonical.self_test()

    code = (
        "from workbench.packets import opcode_index; "
        "assert callable(opcode_index.index_packet_db); "
        "assert callable(opcode_index.index_server); "
        "opcode_index.self_test()"
    )
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-c", code], cwd=Path(tmp), check=True)

    print("packet opcode index package migration: OK")


if __name__ == "__main__":
    main()
