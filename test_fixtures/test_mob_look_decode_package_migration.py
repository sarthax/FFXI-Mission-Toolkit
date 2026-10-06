#!/usr/bin/env python3
"""Regression coverage for retiring the root mob_look_decode compatibility launcher."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from workbench.client.models import look_decode

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    assert not (ROOT / "mob_look_decode.py").exists()
    assert callable(look_decode.decode_look_data)

    flat = bytes.fromhex("0000640100000000000000000000000000000000")
    decoded = look_decode.decode_look_data(flat)
    assert decoded["kind"] == "flat", decoded
    assert decoded["modelid"] == 356, decoded
    assert decoded["file_id"] == 1656, decoded

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from workbench.client.models import look_decode; "
                "assert callable(look_decode.decode_look_data); "
                "print(look_decode.__file__)"
            ),
        ],
        cwd=Path.home(),
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "workbench/client/models/look_decode.py" in proc.stdout.replace("\\", "/"), proc.stdout

    print("mob look decode package migration: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
