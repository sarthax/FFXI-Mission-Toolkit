"""Canonical filesystem locations for the FFXI Mission Toolkit.

This module is the single source of truth for repository-owned resources and
runtime state that intentionally remain outside the Python package.  It is
written to survive the planned ``workbench/`` -> ``src/workbench/`` move: the
repository root is discovered by markers instead of assuming a fixed number of
``Path(__file__)`` parents.

Code should only use ``Path(__file__)`` directly for assets that truly belong
to the importing Python package.  Repository data, GUI assets, vendor tools,
launch-time state, and the primary SQLite database belong here instead.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

ROOT_ENV_VAR = "FFXI_MISSION_TOOLKIT_ROOT"


def _candidate_roots(start: Path) -> Iterable[Path]:
    start = start.resolve()
    if start.is_file():
        start = start.parent
    yield start
    yield from start.parents


def _looks_like_repo_root(candidate: Path) -> bool:
    """Return True when *candidate* has the stable repository resource shape."""
    package_present = (candidate / "workbench").is_dir() or (candidate / "src" / "workbench").is_dir()
    return (
        package_present
        and (candidate / "README.md").is_file()
        and (candidate / "gui").is_dir()
        and (candidate / "data").is_dir()
        and (candidate / "vendor").is_dir()
    )


def _resolve_repo_root(start: Path | None = None) -> Path:
    """Locate the checkout root without depending on package physical depth.

    ``FFXI_MISSION_TOOLKIT_ROOT`` is an explicit escape hatch for unusual
    launch/install environments.  Otherwise we walk upward from this module
    until the repository resource markers are found.
    """
    override = os.environ.get(ROOT_ENV_VAR)
    if override:
        root = Path(override).expanduser().resolve()
        if not _looks_like_repo_root(root):
            raise RuntimeError(
                f"{ROOT_ENV_VAR}={root!s} does not look like an FFXI Mission Toolkit checkout"
            )
        return root

    probe = start or Path(__file__)
    for candidate in _candidate_roots(probe):
        if _looks_like_repo_root(candidate):
            return candidate
    raise RuntimeError(f"Unable to locate FFXI Mission Toolkit repository root from {probe!s}")


REPO_ROOT = _resolve_repo_root()

# The future src-layout location.  It intentionally need not exist during
# Phase 1; callers should not use it to find current package code.
SRC_ROOT = REPO_ROOT / "src"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]

GUI_ROOT = REPO_ROOT / "gui"
DATA_ROOT = REPO_ROOT / "data"
VENDOR_ROOT = REPO_ROOT / "vendor"
ADDONS_ROOT = REPO_ROOT / "addons"
PLOT_DESCRIPTORS_ROOT = REPO_ROOT / "plot_descriptors"
BACKPORT_WORKSPACE_ROOT = REPO_ROOT / "backport-workspace"
CLIENT_PROBE_SETS_ROOT = REPO_ROOT / "client_probe_sets"

DATABASE_PATH = REPO_ROOT / "ffxi_zone_database.db"
# Settings are currently stored in the primary SQLite database.  Keep an
# explicit CONFIG_PATH alias so callers do not invent a package-relative
# configuration location during the src-layout migration.
CONFIG_PATH = DATABASE_PATH
OPENWEBUI_KEY_PATH = REPO_ROOT / ".openwebui_key"


def repo_path(*parts: str | os.PathLike[str]) -> Path:
    """Return an absolute path below the repository root."""
    return REPO_ROOT.joinpath(*parts)
