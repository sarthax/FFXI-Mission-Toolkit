#!/usr/bin/env python3
"""Migration smoke for Captures-owned packet identity helpers."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from workbench.captures import packet_identity as canonical
from workbench.core.services import packet_identity as legacy


def main() -> None:
    assert legacy.parse_opcode is canonical.parse_opcode
    assert legacy.canonical_opcode is canonical.canonical_opcode
    assert legacy.packet_node_id is canonical.packet_node_id
    assert legacy.opcode_aliases is canonical.opcode_aliases
    assert canonical.canonical_opcode("0x02A") == "0x02a"
    assert canonical.canonical_opcode("42") == "0x02a"

    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from workbench.captures.packet_identity import canonical_opcode, packet_node_id; "
                    "assert canonical_opcode('42') == '0x02a'; "
                    "assert packet_node_id('0x02A') == 'packet:0x02a'; "
                    "print('ok')"
                ),
            ],
            cwd=tmp,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    print("packet identity package migration: OK")


if __name__ == "__main__":
    main()
