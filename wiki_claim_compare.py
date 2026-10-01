#!/usr/bin/env python3
"""Compatibility CLI/import wrapper for Development wiki claim comparison."""
from workbench.devtools.reference import wiki_claim_compare as _canonical

for _name in dir(_canonical):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_canonical, _name)


if __name__ == "__main__":
    raise SystemExit(_canonical.main())
