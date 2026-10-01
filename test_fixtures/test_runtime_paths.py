#!/usr/bin/env python3
"""Repository-owned paths must remain stable through the src-layout migration."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from workbench.runtime import paths


def test_repository_resource_paths_remain_at_checkout_root():
    assert paths.REPO_ROOT == ROOT
    assert paths.SRC_ROOT == ROOT / "src"
    assert paths.GUI_ROOT == ROOT / "gui"
    assert paths.DATA_ROOT == ROOT / "data"
    assert paths.VENDOR_ROOT == ROOT / "vendor"
    assert paths.ADDONS_ROOT == ROOT / "addons"
    assert paths.PLOT_DESCRIPTORS_ROOT == ROOT / "plot_descriptors"
    assert paths.BACKPORT_WORKSPACE_ROOT == ROOT / "backport-workspace"
    assert paths.CLIENT_PROBE_SETS_ROOT == ROOT / "client_probe_sets"
    assert paths.DATABASE_PATH == ROOT / "ffxi_zone_database.db"
    assert paths.CONFIG_PATH == paths.DATABASE_PATH
    assert paths.OPENWEBUI_KEY_PATH == ROOT / ".openwebui_key"


def test_repository_root_resolution_is_independent_of_package_depth():
    current_location = ROOT / "workbench" / "runtime" / "paths.py"
    future_src_location = ROOT / "src" / "workbench" / "runtime" / "paths.py"
    assert paths._resolve_repo_root(current_location) == ROOT
    assert paths._resolve_repo_root(future_src_location) == ROOT


def test_repo_path_helper_is_absolute_and_stable():
    assert paths.repo_path("gui", "static", "zone_visual") == ROOT / "gui" / "static" / "zone_visual"
