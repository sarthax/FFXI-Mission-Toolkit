#!/usr/bin/env python3
"""Bootstrap launcher for the canonical Runtime external-tools service."""
from workbench.runtime.external_tools import *  # noqa: F401,F403
from workbench.runtime.external_tools import main


if __name__ == "__main__":
    main()
