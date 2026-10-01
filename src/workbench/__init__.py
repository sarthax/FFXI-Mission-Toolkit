"""Canonical src-layout Workbench package during the staged migration.

Most Workbench modules now live under ``src/workbench``. A small set of path-sensitive
components remains under the repository-root compatibility package until their repository-path
assumptions are normalized. This fallback is transitional and is removed in the root-cleanup
phase.
"""
from pathlib import Path

_ROOT_COMPAT = Path(__file__).resolve().parents[2] / "workbench"
if _ROOT_COMPAT.is_dir():
    __path__.append(str(_ROOT_COMPAT))
