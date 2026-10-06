#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.client.snapshots import overview as canonical
from workbench.runtime.paths import REPO_ROOT


def main() -> None:
    assert not (REPO_ROOT / "client_overview.py").exists()

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "ffxi"
        root.mkdir()
        anchor_bytes = b"not-a-real-pe-but-still-fingerprintable"
        (root / "FFXiMain.dll").write_bytes(anchor_bytes)
        (root / "pol.exe").write_bytes(b"not-a-pe-either")
        (root / "FTABLE.DAT").write_bytes(b"1234")
        (root / "VTABLE.DAT").write_bytes(b"56789")
        (root / "ROM").mkdir()
        (root / "ROM2").mkdir()

        build_id = hashlib.sha256(anchor_bytes).hexdigest()[:12]
        snapshot_id = f"snapshot:client-{build_id}"

        graph = Path(td) / "workbench.db"
        con = sqlite3.connect(graph)
        con.execute(
            "CREATE TABLE capability_observations (capability_id TEXT, status TEXT, source_snapshot_id TEXT)"
        )
        con.executemany(
            "INSERT INTO capability_observations VALUES (?, ?, ?)",
            [
                ("capability:client-binary-probe:event-table", "OBSERVED", snapshot_id),
                ("capability:client-binary-probe:model-table", "UNKNOWN", snapshot_id),
                ("capability:client-binary-probe:other-build", "OBSERVED", "snapshot:client-deadbeef0000"),
            ],
        )
        con.commit()
        con.close()

        result = canonical.overview(str(root), graph)
        assert result["build_id"] == build_id
        assert result["snapshot_id"] == snapshot_id
        assert [row["name"] for row in result["tables"]] == ["FTABLE.DAT", "VTABLE.DAT"]
        assert result["rom_dirs"] == ["ROM", "ROM2"]
        assert {row["name"] for row in result["binaries"]} == {"FFXiMain.dll", "pol.exe"}
        assert result["observations"]["graph_built"] is True
        assert result["observations"]["counts"] == {"OBSERVED": 1, "UNKNOWN": 1}
        assert {row["capability"] for row in result["observations"]["rows"]} == {"event-table", "model-table"}

        empty = canonical.saved_observations(None, snapshot_id)
        assert empty == {"graph_built": False, "counts": {}, "rows": []}

        code = (
            "from pathlib import Path; "
            "from workbench.client.snapshots import overview as o; "
            "assert o.BUILD_ANCHOR == 'FFXiMain.dll'; "
            "assert o.saved_observations(None, None)['graph_built'] is False; "
            "assert 'src' in Path(o.__file__).resolve().parts; "
            "print('outside-repo client overview import: PASS')"
        )
        subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)

    print("client overview package migration: PASS")


if __name__ == "__main__":
    main()
