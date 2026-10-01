#!/usr/bin/env python3
"""Compatibility launcher for Client Shared look decoding.

Canonical implementation: ``workbench.client.models.look_decode``.
"""

from workbench.client.models.look_decode import *  # noqa: F401,F403
from workbench.client.models.look_decode import main


if __name__ == "__main__":
    main()
