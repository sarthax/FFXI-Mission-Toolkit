#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.packets import decode as canonical
from workbench.runtime.paths import REPO_ROOT, VENDOR_ROOT


def main() -> None:
    assert not (REPO_ROOT / "packet_decode.py").exists()
    packetlyzer = VENDOR_ROOT / "Packetlyzer"
    assert canonical.TOOLS_ROOT == REPO_ROOT
    assert canonical.PACKETLYZER_ROOT == packetlyzer
    assert canonical.DB_XML == packetlyzer / "packetlyzer_db.xml"
    assert canonical.EXT_JSON == packetlyzer / "packetlyzer_ext.json"
    assert canonical.LOOKUP_DIR == packetlyzer / "lookup"
    assert callable(canonical.parse_hex)
    assert callable(canonical.decode)
    assert callable(canonical.list_opcodes)
    assert callable(canonical.main)
    assert canonical.parse_hex("0x2A 10\n4E") == bytes.fromhex("2A104E")

    rows = canonical.list_opcodes("0x02A")
    assert any(row["opcode"] == 0x02A for row in rows), rows

    code = (
        "from workbench.packets import decode; "
        "from workbench.runtime.paths import REPO_ROOT, VENDOR_ROOT; "
        "p=VENDOR_ROOT/'Packetlyzer'; "
        "assert decode.TOOLS_ROOT == REPO_ROOT; "
        "assert decode.PACKETLYZER_ROOT == p; "
        "assert decode.DB_XML == p/'packetlyzer_db.xml'; "
        "assert decode.parse_hex('2A 10') == bytes.fromhex('2A10'); "
        "assert any(r['opcode']==0x02A for r in decode.list_opcodes('0x02A'))"
    )
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-c", code], cwd=Path(tmp), check=True)
        subprocess.run(
            [sys.executable, "-m", "workbench.packets.decode", "--help"],
            cwd=Path(tmp),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    print("packet decoder package migration: OK")


if __name__ == "__main__":
    main()
