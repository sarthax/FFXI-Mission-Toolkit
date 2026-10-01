from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.runtime import addon_tools as canonical
from workbench.runtime.paths import ADDONS_ROOT, REPO_ROOT

assert canonical.TOOLS_ROOT == REPO_ROOT
assert canonical.ADDONS_DIR == ADDONS_ROOT
assert canonical.human_size(1024) == "1KB"
assert callable(canonical.install_addon)
assert callable(canonical.main)

spec = importlib.util.spec_from_file_location("addon_tools", REPO_ROOT / "addon_tools.py")
assert spec and spec.loader
legacy = importlib.util.module_from_spec(spec)
sys.modules["addon_tools"] = legacy
spec.loader.exec_module(legacy)
legacy = sys.modules["addon_tools"]
assert legacy is canonical

original = canonical.ADDONS_DIR
try:
    sentinel = REPO_ROOT / "__addon_tools_migration_sentinel__"
    canonical.ADDONS_DIR = sentinel
    assert legacy.ADDONS_DIR == sentinel
finally:
    canonical.ADDONS_DIR = original

with tempfile.TemporaryDirectory() as td:
    code = (
        "from workbench.runtime import addon_tools as m; "
        "from workbench.runtime.paths import REPO_ROOT, ADDONS_ROOT; "
        "assert m.TOOLS_ROOT == REPO_ROOT; "
        "assert m.ADDONS_DIR == ADDONS_ROOT; "
        "assert m.human_size(1024) == '1KB'"
    )
    subprocess.run([sys.executable, "-c", code], cwd=td, check=True)

print("addon tools package migration: PASS")
