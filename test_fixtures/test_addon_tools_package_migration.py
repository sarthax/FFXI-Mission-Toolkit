from __future__ import annotations

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

assert not (REPO_ROOT / "addon_tools.py").exists()

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
