#!/usr/bin/env python3
"""Compatibility CLI/import for the canonical Development SQL indexer."""
from __future__ import annotations

import io
import sys

from workbench.devtools.indexing import build_sql_index as _canonical

if __name__ == "__main__":
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        sys.stdout = io.TextIOWrapper(stream, encoding="utf-8", errors="replace")
    _canonical.main()
else:
    sys.modules[__name__] = _canonical
