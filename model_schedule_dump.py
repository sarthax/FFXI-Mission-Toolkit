#!/usr/bin/env python3
"""Compatibility launcher for the packaged Client model schedule inspector."""
from __future__ import annotations
import sys
from workbench.client.models import schedule_dump as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
