from __future__ import annotations

import importlib
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    assault = importlib.import_module("workbench.packages.migration.drivers.assault_batch")
    gm = importlib.import_module("workbench.packages.migration.drivers.gm_debug")
    nyzul = importlib.import_module("workbench.packages.migration.drivers.nyzul")
    lua_convert = importlib.import_module("workbench.packages.migration.lua_convert")

    assert not (REPO_ROOT / "backport_convert_7_packages.py").exists()
    assert not (REPO_ROOT / "backport_convert_gm_debug_tools.py").exists()
    assert not (REPO_ROOT / "backport_convert_nyzul_package.py").exists()

    periqia = assault.zone_settings_for("scripts/zones/Periqia/npcs/test.lua")
    assert periqia == {"zone_table": "PERIQIA", "id_shape": "zones_table", "id_file_hint": None}

    required = 'local ID = require("scripts/zones/Nyzul_Isle/IDs")\nreturn tpz.job.COR\n'
    nyzul_settings = nyzul.zone_settings_for("scripts/commands/nyzuldebug.lua", required)
    assert nyzul_settings == {"zone_table": "NyzulIsle", "id_shape": "nested", "id_file_hint": "IDs"}

    ns_map = lua_convert.load_map()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        package_base = root / "mission-packages"

        assault_pkg = package_base / "synthetic_assault"
        _write(assault_pkg / "lua/scripts/globals/custom.lua", "local job = tpz.job.COR\n")
        _write(assault_pkg / "lua/scripts/globals/missions.lua", "return tpz.job.COR\n")
        report = assault.convert_package("synthetic_assault", ns_map, package_base)
        assert report["converted"] == ["scripts/globals/custom.lua"]
        assert report["skipped"] == ["scripts/globals/missions.lua"]
        converted = (assault_pkg / "lua-dsp/scripts/globals/custom.lua").read_text(encoding="utf-8")
        assert "JOBS.COR" in converted
        assert not (assault_pkg / "lua-dsp/scripts/globals/missions.lua").exists()

        nyzul_pkg = package_base / "nyzul_isle_investigation"
        _write(nyzul_pkg / "lua/scripts/globals/custom.lua", "local job = tpz.job.COR\n")
        _write(nyzul_pkg / "lua/scripts/globals/missions.lua", "return tpz.job.COR\n")
        nyzul_report = nyzul.main(nyzul_pkg)
        assert nyzul_report["converted"] == ["scripts/globals/custom.lua"]
        assert nyzul_report["skipped"] == ["scripts/globals/missions.lua"]
        assert "JOBS.COR" in (nyzul_pkg / "lua-dsp/scripts/globals/custom.lua").read_text(encoding="utf-8")

        gm_pkg = package_base / "assault_gm_debug_tools"
        _write(gm_pkg / "lua/scripts/commands/test.lua", "local job = tpz.job.COR\n")
        original_verify = gm.blc.verify_target_or_raise
        try:
            gm.blc.verify_target_or_raise = lambda *_args, **_kwargs: None
            gm_report = gm.main(gm_pkg, root / "synthetic-dsp")
        finally:
            gm.blc.verify_target_or_raise = original_verify
        assert gm_report["converted"] == ["scripts/commands/test.lua"]
        assert "JOBS.COR" in (gm_pkg / "lua-dsp/scripts/commands/test.lua").read_text(encoding="utf-8")

    code = (
        "from workbench.packages.migration.drivers import assault_batch, gm_debug, nyzul; "
        "print(assault_batch.zone_settings_for, gm_debug.main, nyzul.zone_settings_for)"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)


if __name__ == "__main__":
    main()
