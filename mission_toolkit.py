#!/usr/bin/env python3
"""Compatibility launcher/import alias for the packaged Mission Toolkit developer CLI."""
from __future__ import annotations

import sys

from workbench.devtools.app import mission_toolkit as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
