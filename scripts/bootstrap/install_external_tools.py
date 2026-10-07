#!/usr/bin/env python3
"""Bootstrap CLI wrapper for the canonical external-tools installer."""
from workbench.runtime.external_tools import *  # noqa: F401,F403
from workbench.runtime.external_tools import main


if __name__ == "__main__":
    main()
