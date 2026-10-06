from __future__ import annotations

import importlib
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    coverage = importlib.import_module("workbench.validation.packages.coverage")
    confidence = importlib.import_module("workbench.validation.packages.map_confidence")
    assert not (REPO_ROOT / "backport_coverage_check.py").exists()
    assert not (REPO_ROOT / "backport_map_confidence_check.py").exists()

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        topaz = root / "topaz"
        zone = topaz / "scripts" / "zones" / "Test_Zone"
        zone.mkdir(parents=True)
        (zone / "npc.lua").write_text("local job = tpz.job.COR\n", encoding="utf-8")
        cov = coverage.run(topaz, ["Test_Zone"])
        assert cov["files_processed"] == 1
        assert cov["files_with_unflagged"] == 0

        scripts = topaz / "scripts" / "globals"
        scripts.mkdir(parents=True)
        (scripts / "mods.lua").write_text("local a = tpz.testfam.A\nlocal b = tpz.testfam.B\n", encoding="utf-8")
        dsp = root / "dsp"
        (dsp / "src").mkdir(parents=True)
        (dsp / "src" / "ids.cpp").write_text("int DSP_A = 1;\n", encoding="utf-8")
        confidence.dsp_has_identifier.__defaults__[0].clear()
        result = confidence.check_simple_family(topaz, dsp, "testfam", {"dsp_prefix": "DSP_"})
        assert ("A", "DSP_A") in result["confirmed"]
        assert ("B", "DSP_B") in result["missing"]

    code = (
        "from workbench.validation.packages.coverage import run; "
        "from workbench.validation.packages.map_confidence import check_simple_family; "
        "print(run, check_simple_family)"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)


if __name__ == "__main__":
    main()
