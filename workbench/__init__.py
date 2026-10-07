"""Repo-root compatibility bootstrap for the canonical src-layout Workbench package.

All Workbench implementation code lives under ``src/workbench``. This one-file bridge remains for
repo-root development and regression workflows that exercise imports with ``PYTHONPATH=.`` before
an editable install is guaranteed. It extends the package search path to the canonical src package.

Do not add implementation modules below this root ``workbench/`` directory. The bridge can be
removed only after launch/setup and CI universally install the project or put ``src`` on the
Python import path.
"""
from pathlib import Path

_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "workbench"
if _SRC_PACKAGE.is_dir():
    __path__.append(str(_SRC_PACKAGE))
else:
    raise ImportError(f"canonical workbench package not found: {_SRC_PACKAGE}")
