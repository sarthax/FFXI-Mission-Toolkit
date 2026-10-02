#!/usr/bin/env python3
"""Compatibility CLI/import wrapper for the packaged BG Wiki scraper."""
from __future__ import annotations

import sys

from workbench.devtools.reference import scrape_bg_wiki as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
