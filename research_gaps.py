"""Compatibility import wrapper for Development research gap detection."""
import sys

from workbench.devtools.research import gaps as _canonical

sys.modules[__name__] = _canonical
