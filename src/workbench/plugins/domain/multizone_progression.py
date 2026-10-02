"""Compatibility import for Development-owned multi-zone progression tooling."""
import sys

from workbench.devtools.missions import multizone_progression as _canonical

sys.modules[__name__] = _canonical
