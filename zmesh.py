"""Compatibility CLI/import launcher for Development zone-mesh tooling."""
from __future__ import annotations

import sys

from workbench.devtools.spatial import zmesh as _canonical

if __name__ == "__main__":
    _canonical.main()
else:
    sys.modules[__name__] = _canonical
