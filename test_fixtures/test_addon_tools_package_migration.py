from __future__ import annotations

import os
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
    # The child runs outside the repo, so hand it the same import root this process resolved workbench from.
    src_root = str(Path(canonical.__file__).resolve().parents[2])
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [src_root, os.environ.get("PYTHONPATH")]))}
    subprocess.run([sys.executable, "-c", code], cwd=td, check=True, env=env)

print("addon tools package migration: PASS")
