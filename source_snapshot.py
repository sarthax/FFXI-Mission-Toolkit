"""Compatibility shim for canonical source provenance utilities.

New code should import from ``workbench.core.provenance``.
"""
from workbench.core.provenance import *  # noqa: F401,F403

if __name__ == "__main__":
    from workbench.core.provenance import main
    raise SystemExit(main())
