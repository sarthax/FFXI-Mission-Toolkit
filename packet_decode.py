#!/usr/bin/env python3
"""Compatibility entry point for the canonical packet decoder service."""
from workbench.packets.decode import *  # noqa: F401,F403

if __name__ == "__main__":
    import io
    import sys

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
