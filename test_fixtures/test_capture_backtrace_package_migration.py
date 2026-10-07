#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.captures import packet_identity
from workbench.captures.correlation import backtrace as canonical


def main() -> None:
    root_path = Path(__file__).resolve().parents[1] / "capture_backtrace.py"
    assert not root_path.exists()
    assert canonical.packet_node_id is packet_identity.packet_node_id

    code = (
        "from workbench.captures import packet_identity; "
        "from workbench.captures.correlation import backtrace; "
        "assert backtrace.packet_node_id is packet_identity.packet_node_id; "
        "assert callable(backtrace.backtrace)"
    )
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-c", code], cwd=tmp, check=True)


if __name__ == "__main__":
    main()
