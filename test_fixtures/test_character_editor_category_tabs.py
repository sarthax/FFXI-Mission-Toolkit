#!/usr/bin/env python3
"""Focused regressions for Character Editor category organization and full storage display."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.editors.character.categories import build_tab_manifest
from workbench.editors.character.inventory_slots import CONTAINERS


class _Schema:
    capabilities = {
        "identity": ["chars"],
        "profile": ["char_profile"],
        "jobs": ["char_jobs", "char_exp"],
        "skills": ["char_skills"],
        "inventory": ["char_inventory", "char_storage", "char_equip"],
        "points": ["char_points"],
        "variables": ["char_vars"],
        "character_other": ["char_custom_fork_state"],
    }


def main() -> None:
    manifest = build_tab_manifest(
        _Schema(),
        {
            "supported": [
                "identity", "profile", "jobs", "experience", "skills", "inventory",
                "storage", "equipment", "points", "currencies", "variables", "missions",
                "key_items", "character_other",
            ]
        },
    )
    by_key = {row["key"]: row for row in manifest}
    required = {
        "character": "Character",
        "inventory": "Inventory",
        "profile": "Profile",
        "jobs-skills": "Jobs & Skills",
        "currencies": "Currencies",
        "missions-quests": "Mission Flags",
        "key-items": "Key Items",
        "spells-abilities": "Spells & Abilities",
        "merits-jobpoints": "Merits & Job Points",
        "unlocks-travel": "Unlocks & Travel",
        "variables": "Variables",
        "pets-effects": "Pets & Effects",
        "advanced": "Advanced",
    }
    assert {key: by_key[key]["label"] for key in required} == required
    assert by_key["jobs-skills"]["available"] is True
    assert {"jobs", "experience", "skills"}.issubset(set(by_key["jobs-skills"]["supported_capabilities"]))
    assert by_key["missions-quests"]["available"] is True
    assert by_key["key-items"]["available"] is True
    assert "character_other" in by_key["advanced"]["supported_capabilities"]

    # FFXI storage locations used by DSP/Topaz/LSB. Storage/temp are viewable even though their
    # capacity/write semantics are not equivalent to directly-sized bags.
    expected_containers = {
        0: "inventory",
        1: "safe",
        2: "storage",
        3: "temporary",
        4: "locker",
        5: "satchel",
        6: "sack",
        7: "case",
        8: "wardrobe",
        9: "safe2",
        10: "wardrobe2",
        11: "wardrobe3",
        12: "wardrobe4",
        13: "wardrobe5",
        14: "wardrobe6",
        15: "wardrobe7",
        16: "wardrobe8",
    }
    for location, name in expected_containers.items():
        assert CONTAINERS[location] == name

    template = (ROOT / "gui" / "templates" / "character_editor.html").read_text(encoding="utf-8")
    gui = (SRC / "workbench" / "editors" / "character" / "gui.py").read_text(encoding="utf-8")
    service = (SRC / "workbench" / "editors" / "character" / "service.py").read_text(encoding="utf-8")
    category_data = (SRC / "workbench" / "editors" / "character" / "category_data.py").read_text(encoding="utf-8")

    assert 'id="categoryTabs"' in template
    assert 'id="inventoryContainers"' in template
    assert "async function loadCategory" in template
    assert "async function loadInventory" in template
    assert "/categories/${encodeURIComponent(key)}.json" in template
    assert '@router.get("/characters/{char_id}/categories/{tab_key}.json")' in gui
    assert '"containers": _safe(containers)' in gui
    assert "def inventory_containers" in service
    assert 'packed[capability] = {"location": location, "value": value}' in category_data


if __name__ == "__main__":
    main()
