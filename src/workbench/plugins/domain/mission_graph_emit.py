"""Compatibility shim for Development mission graph projection."""
from __future__ import annotations

import sys

from workbench.devtools.missions import graph_ingest as _canonical

sys.modules[__name__] = _canonical
