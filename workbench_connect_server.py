#!/usr/bin/env python3
"""Compatibility entry point for the canonical server Workbench connector."""
from __future__ import annotations

import sys

from workbench.runtime import connect_server as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())
else:
    sys.modules[__name__] = _canonical
