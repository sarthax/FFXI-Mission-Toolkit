#!/usr/bin/env python3
"""Phase C package smoke for raw packet ingestion."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workbench.captures import raw_packet_ingest as canonical
from workbench.captures import integrity
from workbench.captures import chat
from workbench.core.services import raw_packet_ingest as legacy


def main() -> int:
    assert legacy is canonical
    assert canonical.capture_integrity is integrity
    assert canonical.capture_chat is chat
    assert canonical.normalize_raw_hex("0e 08 34 12") == "0E083412"
    assert canonical.decode_packet_header("0E083412AABBCCDD")["opcode"] == 0x00E

    code = """
from workbench.captures import raw_packet_ingest as rp
from workbench.captures import integrity, chat
assert rp.capture_integrity is integrity
assert rp.capture_chat is chat
assert rp.normalize_raw_hex('0e 08 34 12') == '0E083412'
print('raw packet ingestion package migration: OK')
"""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-c", code], cwd=tmp, env=env, check=True)
    print("raw packet ingestion compatibility: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
