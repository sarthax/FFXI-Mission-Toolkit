#!/usr/bin/env python3
"""Compatibility launcher for the Development entity lookup tool.

Canonical implementation: ``workbench.devtools.entities.lookup``.
"""

from workbench.devtools.entities.lookup import *  # noqa: F401,F403
from workbench.devtools.entities.lookup import main


if __name__ == "__main__":
    main()
