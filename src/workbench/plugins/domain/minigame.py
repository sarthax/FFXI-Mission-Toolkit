"""Compatibility import for the Development-owned minigame framework."""
import sys
from workbench.devtools.missions import minigame as _canonical

sys.modules[__name__] = _canonical
