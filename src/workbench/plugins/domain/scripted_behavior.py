"""Compatibility shim for Development scripted behavior modeling."""
from __future__ import annotations
import sys
from workbench.devtools.behavior import scripted_behavior as _canonical
sys.modules[__name__] = _canonical
