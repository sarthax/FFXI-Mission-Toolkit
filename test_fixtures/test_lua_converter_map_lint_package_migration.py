#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_root(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return sys.modules[name]


def main() -> None:
    from workbench.packages.migration import lua_convert
    from workbench.runtime.paths import DATA_ROOT
    from workbench.validation.packages import map_lint

    root_converter = load_root("backport_lua_convert", REPO_ROOT / "backport_lua_convert.py")
    assert root_converter is lua_convert
    assert not (REPO_ROOT / "backport_map_lint.py").exists()

    assert lua_convert.MAP_PATH == DATA_ROOT / "dsp_namespace_map.json"
    ns_map = lua_convert.load_map()
    assert "simple_families" in ns_map

    result = lua_convert.convert("if player:getMainJob() == tpz.job.COR then\nend\n", ns_map=ns_map)
    assert "JOBS.COR" in result.converted
    assert "tpz.job.COR" not in result.converted

    assert map_lint.lint() == 0

    with tempfile.TemporaryDirectory() as tmp:
        code = (
            "from workbench.packages.migration import lua_convert; "
            "from workbench.validation.packages import map_lint; "
            "m=lua_convert.load_map(); "
            "assert 'simple_families' in m; "
            "assert map_lint.lint() == 0"
        )
        subprocess.run([sys.executable, "-c", code], cwd=tmp, check=True)
        subprocess.run(
            [sys.executable, "-m", "workbench.validation.packages.map_lint"],
            cwd=tmp,
            check=True,
        )


if __name__ == "__main__":
    main()
