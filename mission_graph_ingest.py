#!/usr/bin/env python3
"""Compatibility CLI/import alias for packaged mission graph projection."""
from __future__ import annotations

import sys

from workbench.devtools.missions import graph_ingest as _canonical

if __name__ == "__main__":
    from workbench.devtools.missions.graph_ingest_cli import main

    raise SystemExit(main())

sys.modules[__name__] = _canonical
