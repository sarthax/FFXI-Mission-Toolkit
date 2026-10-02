#!/usr/bin/env python3
"""Compatibility launcher for global client DAT table ingestion.

Canonical implementation: ``workbench.client.dat.global_tables``.
"""
from __future__ import annotations

import io
import sys

from workbench.client.dat import global_tables as _canonical

sys.modules[__name__] = _canonical

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _canonical.main()
