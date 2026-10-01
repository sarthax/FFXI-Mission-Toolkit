#!/usr/bin/env python3
"""Regression checks for Development server-catalog identity migration."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from workbench.core.services import server_catalog_identity as legacy
from workbench.devtools.server import catalog_identity as canonical


def main() -> None:
    assert legacy.SOURCE_MARKER == canonical.SOURCE_MARKER
    assert legacy.ENTITY_TABLES == canonical.ENTITY_TABLES
    assert legacy.sync_server_catalog_entities is canonical.sync_server_catalog_entities

    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        code = (
            "from pathlib import Path; "
            "from workbench.devtools.server import catalog_identity; "
            "assert 'src' in Path(catalog_identity.__file__).resolve().parts; "
            "assert callable(catalog_identity.sync_server_catalog_entities); "
            "assert catalog_identity.SOURCE_MARKER == 'server-catalog'; "
            "print('Development server catalog identity:', catalog_identity.__file__)"
        )
        subprocess.run([sys.executable, "-c", code], cwd=td, env=env, check=True)

    print("Development server catalog identity migration: PASS")


if __name__ == "__main__":
    main()
