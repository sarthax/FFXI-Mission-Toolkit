"""Compatibility shim for the canonical Workbench graph.

New code should import from ``workbench.core.graph``.
"""
from workbench.core.graph import *  # noqa: F401,F403

if __name__ == "__main__":
    from workbench.core.graph import main
    raise SystemExit(main())
