#!/usr/bin/env python3
"""Migration smoke for Captures-owned chat and spatial services."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from workbench.captures import chat as canonical_chat
from workbench.captures import spatial as canonical_spatial
from workbench.core.services import capture_chat as legacy_chat
from workbench.core.services import capture_spatial as legacy_spatial


def main() -> None:
    assert legacy_chat.insert_chat_observation is canonical_chat.insert_chat_observation
    assert legacy_spatial.capture_spatial_entities is canonical_spatial.capture_spatial_entities

    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from workbench.captures.chat import insert_chat_observation; "
                    "from workbench.captures.spatial import capture_spatial_entities; "
                    "print(insert_chat_observation.__module__); "
                    "print(capture_spatial_entities.__module__)"
                ),
            ],
            cwd=tmp,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    print("capture chat/spatial package migration: OK")


if __name__ == "__main__":
    main()
