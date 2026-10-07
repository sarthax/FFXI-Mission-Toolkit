#!/usr/bin/env python3
"""Regression contract for standalone operator scripts relocated out of repository root."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MOVED = {
    "build_item_repair_package.py": "scripts/maintenance/build_item_repair_package.py",
    "seed_auction_house.py": "scripts/maintenance/seed_auction_house.py",
    "discord_inventory.py": "scripts/import/discord_inventory.py",
    "discord_holiday_load.py": "scripts/import/discord_holiday_load.py",
    "tools_gen_dsp_enums.py": "scripts/maintenance/generate_dsp_item_enums.py",
}


def main() -> None:
    for old, new in MOVED.items():
        assert not (ROOT / old).exists(), old
        assert (ROOT / new).is_file(), new

    repair = (ROOT / MOVED["build_item_repair_package.py"]).read_text(encoding="utf-8")
    assert "from workbench.runtime.paths import REPO_ROOT" in repair
    assert "ROOT = REPO_ROOT" in repair
    assert "\nROOT = Path(__file__).parent\n" not in repair

    enums = (ROOT / MOVED["tools_gen_dsp_enums.py"]).read_text(encoding="utf-8")
    assert "from workbench.runtime.paths import REPO_ROOT" in enums
    assert "from workbench.runtime.legacy_settings import get_dsp_root" in enums
    assert "REPO_ROOT / 'src/workbench/editors/items/_enums_dsp.py'" in enums

    seed = (ROOT / MOVED["seed_auction_house.py"]).read_text(encoding="utf-8")
    assert "scripts/maintenance/seed_auction_house.py" in seed

    inventory = (ROOT / MOVED["discord_inventory.py"]).read_text(encoding="utf-8")
    holiday = (ROOT / MOVED["discord_holiday_load.py"]).read_text(encoding="utf-8")
    assert "scripts/import/discord_inventory.py" in inventory
    assert "scripts/import/discord_holiday_load.py" in holiday

    print("standalone operator script relocation: PASS")


if __name__ == "__main__":
    main()
