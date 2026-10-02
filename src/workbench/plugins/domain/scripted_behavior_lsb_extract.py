"""Compatibility shim for Development LSB scripted behavior extraction."""
from __future__ import annotations
import sys
from workbench.devtools.behavior import scripted_behavior_lsb_extract as _canonical
sys.modules[__name__] = _canonical
