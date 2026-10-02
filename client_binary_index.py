#!/usr/bin/env python3
"""Compatibility launcher for the packaged Client binary index CLI."""
from __future__ import annotations
import sys
from workbench.client.cli import binary_index as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
