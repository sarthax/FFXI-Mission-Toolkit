#!/usr/bin/env python3
"""Compatibility CLI/import wrapper for Development wiki evidence tooling."""
import sys

from workbench.devtools.reference import wiki_evidence as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

# Legacy imports resolve to the canonical implementation module itself so monkeypatches and
# module-global state remain shared during the migration.
sys.modules[__name__] = _canonical
