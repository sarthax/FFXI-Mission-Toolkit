from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_root(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return sys.modules[name]


def main() -> None:
    canonical = importlib.import_module("workbench.validation.packages.item_audit")
    legacy = _load_root("backport_item_audit", REPO_ROOT / "backport_item_audit.py")
    assert legacy.audit_package is canonical.audit_package

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pkg = root / "pkg"
        dsp = root / "dsp"
        (pkg / "scripts" / "globals").mkdir(parents=True)
        (dsp / "sql").mkdir(parents=True)
        (dsp / "scripts" / "globals" / "items").mkdir(parents=True)
        (dsp / "scripts" / "globals").mkdir(parents=True, exist_ok=True)

        (dsp / "sql" / "item_basic.sql").write_text(
            "INSERT INTO `item_basic` VALUES (100,0,'good_item');\n"
            "INSERT INTO `item_basic` VALUES (101,0,'no_script');\n",
            encoding="utf-8",
        )
        (dsp / "scripts" / "globals" / "items" / "good_item.lua").write_text("return {}\n", encoding="utf-8")
        (dsp / "scripts" / "globals" / "keyitems.lua").write_text("GOOD_KEY = 1\n", encoding="utf-8")
        (dsp / "scripts" / "globals" / "shared.lua").write_text("return {}\n", encoding="utf-8")

        (pkg / "test.lua").write_text(
            "local GOOD_ITEM = 100\n"
            "local WARN_ITEM = 101\n"
            "local BAD_ITEM = 999\n"
            "player:hasKeyItem(GOOD_KEY)\n"
            "player:addKeyItem(MISSING_KEY)\n"
            "require(\"scripts/globals/shared\")\n"
            "require(\"scripts/globals/missing\")\n"
            "GetNPCByID(foo, instance)\n",
            encoding="utf-8",
        )

        result = canonical.audit_package(pkg, dsp)
        assert [row[0] for row in result["missing_item_rows"]] == [999]
        assert [(row[0], row[1]) for row in result["missing_item_scripts"]] == [(101, "no_script")]
        assert [row[0] for row in result["missing_keyitems"]] == ["MISSING_KEY"]
        assert [row[0] for row in result["dangling_requires"]] == ["scripts/globals/missing"]
        assert len(result["bad_call_shapes"]) == 1

    code = "from workbench.validation.packages.item_audit import audit_package; print(audit_package)"
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)


if __name__ == "__main__":
    main()
