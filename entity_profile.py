#!/usr/bin/env python3
"""Compatibility launcher for :mod:`workbench.devtools.entities.profile`.

The Entity Profile implementation moved into the Development component during Phase C. Existing
root imports and ``py -3 entity_profile.py ...`` workflows remain supported temporarily while
callers migrate to the canonical package path.
"""
import io
import sys

from workbench.devtools.entities import profile as _profile

# Preserve the historical module surface for callers that still import ``entity_profile``.
for _name in dir(_profile):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_profile, _name)


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _profile.main()
