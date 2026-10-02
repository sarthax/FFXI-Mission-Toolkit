"""Compatibility import for the packaged Client Binary Inspector service."""
from __future__ import annotations
import sys
from workbench.client.binary import inspector as _canonical

sys.modules[__name__] = _canonical
