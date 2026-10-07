#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.packets import opcode_index as canonical
from workbench.runtime.paths import REPO_ROOT



def main() -> None:
    assert not (REPO_ROOT / "packet_opcode_index.py").exists()
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
