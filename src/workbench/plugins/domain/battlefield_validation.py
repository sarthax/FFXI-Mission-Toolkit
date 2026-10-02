"""Compatibility import for DSP battlefield proposal validation."""
import sys as _sys

from workbench.validation import battlefields as _canonical

_sys.modules[__name__] = _canonical
