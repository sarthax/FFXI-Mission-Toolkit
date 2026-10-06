#!/usr/bin/env python3
"""Compatibility launcher/import alias for the canonical packaged GUI host."""
from __future__ import annotations

import sys

from workbench.app import host as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

# Preserve historical ``import gui_server`` monkeypatch/module-global behavior.
sys.modules[__name__] = _canonical
