#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.captures import packet_correlation, packet_identity
from workbench.captures.correlation import graph_connect as canonical


def main() -> None:
    root_path = Path(__file__).resolve().parents[1] / "capture_graph_connect.py"
    assert not root_path.exists()
    assert canonical.packet_node_id is packet_identity.packet_node_id
    assert canonical.packet_correlation is packet_correlation

    code = (
        "from workbench.captures import packet_correlation, packet_identity; "
        "from workbench.captures.correlation import graph_connect; "
        "assert graph_connect.packet_node_id is packet_identity.packet_node_id; "
        "assert graph_connect.packet_correlation is packet_correlation; "
        "assert callable(graph_connect.connect)"
    )
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-c", code], cwd=tmp, check=True)


if __name__ == "__main__":
    main()
