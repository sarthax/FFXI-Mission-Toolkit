"""Compatibility import for DSP battlefield migration proposals."""
import sys as _sys

from workbench.packages.battlefields import dsp as _canonical

_sys.modules[__name__] = _canonical
