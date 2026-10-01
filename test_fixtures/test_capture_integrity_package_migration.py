#!/usr/bin/env python3
"""Migration smoke for Captures-owned integrity/provenance services."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from workbench.captures import chat
from workbench.captures import integrity as canonical
from workbench.core.services import capture_integrity as legacy


def main() -> None:
    assert legacy.init_db is canonical.init_db
    assert legacy.record_row_locator is canonical.record_row_locator
    assert legacy.content_identity is canonical.content_identity
    assert legacy.PARSER_VERSION == canonical.PARSER_VERSION
    assert chat.capture_integrity is canonical

    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from workbench.captures import integrity; "
                    "from workbench.captures import chat; "
                    "assert chat.capture_integrity is integrity; "
                    "print(integrity.PARSER_VERSION); "
                    "print(integrity.record_row_locator.__module__)"
                ),
            ],
            cwd=tmp,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    print("capture integrity package migration: OK")


if __name__ == "__main__":
    main()
