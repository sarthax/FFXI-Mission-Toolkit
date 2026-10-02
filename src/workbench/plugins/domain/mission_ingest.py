"""Compatibility bridge to Development mission truth ingestion."""
from __future__ import annotations

import sys

from workbench.devtools.missions import mission_ingest as _canonical

sys.modules[__name__] = _canonical
