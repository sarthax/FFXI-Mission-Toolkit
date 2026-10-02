#!/usr/bin/env python3
"""Compatibility CLI/import wrapper for packaged wiki compiler tooling."""
from __future__ import annotations

import io
import sys

from workbench.devtools.reference import wiki_compile as _canonical

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _canonical.main()
else:
    sys.modules[__name__] = _canonical
