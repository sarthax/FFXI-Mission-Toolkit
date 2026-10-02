"""Compatibility import for the packaged Client DAT extractor helper."""
from __future__ import annotations

import sys

from workbench.client.dat import extractor_bin as _canonical

sys.modules[__name__] = _canonical
