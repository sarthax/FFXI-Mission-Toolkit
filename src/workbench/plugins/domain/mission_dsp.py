"""Compatibility alias for Development-owned mission proposal generation."""
import sys

from workbench.devtools.missions import mission_dsp as _canonical

sys.modules[__name__] = _canonical
