#!/usr/bin/env python3
"""Compatibility entry point for the canonical packet decoder service."""
from __future__ import annotations

import io
import sys

from workbench.packets import decode as _canonical

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _canonical.main()
else:
    sys.modules[__name__] = _canonical
