"""Temporary compatibility bridge for the src-layout migration.

The canonical package now lives in ``src/workbench``. This root package remains for one
transition cycle so existing repo-root execution continues to resolve ``workbench.*`` imports
before editable installation is universal. New code must target the installed src-layout
package; this bridge is removed in the root-cleanup phase.
"""
from pathlib import Path

_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "workbench"
if _SRC_PACKAGE.is_dir():
    __path__.append(str(_SRC_PACKAGE))
else:
    raise ImportError(f"canonical workbench package not found: {_SRC_PACKAGE}")
