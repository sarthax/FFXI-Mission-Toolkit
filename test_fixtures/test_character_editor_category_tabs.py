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
from workbench.editors.character.inventory_slots import CONTAINERS, CONTAINER_KEYS
from test_character_editor_packed_codecs import main as packed_codec_regression


class _Schema:
    capabilities = {
        "identity": ["chars"],
        "profile": ["char_profile"],
        "jobs": ["char_jobs", "char_exp"],
        "skills": ["char_skills"],
        "inventory": ["char_inventory", "char_storage", "char_equip"],
        "points": ["char_points"],
        "variables": ["char_vars"],
        "history": ["char_history"],
        "runtime_flags": ["char_flags"],
        "recasts": ["char_recast"],
        "character_other": ["char_custom_fork_state"],
    }


def main() -> None:
    manifest = build_tab_manifest(
        _Schema(),
        {
            "supported": [
                "identity", "profile", "jobs", "experience", "skills", "inventory",
                "storage", "equipment", "points", "currencies", "variables", "missions",
                "key_items", "history", "runtime_flags", "recasts", "character_other",
            ]
        },
    )
    by_key = {row["key"]: row for row in manifest}
    required = {
        "character": "Character",
        "inventory": "Inventory",
        "profile": "Profile",
        "currencies": "Currencies",
        "missions-quests": "Mission Flags",
        "key-items": "Key Items",
        "jobs-skills": "Jobs & Skills",
        "spells-abilities": "Spells & Abilities",
        "merits-jobpoints": "Merits & Job Points",
        "unlocks-travel": "Unlocks & Travel",
        "variables": "Variables",
        "pets-effects": "Pets & Effects",
        "advanced": "Advanced",
    }
    assert {key: by_key[key]["label"] for key in required} == required

    primary_keys = ["character", "inventory", "profile", "currencies", "missions-quests", "key-items"]
    assert [row["key"] for row in manifest[:6]] == primary_keys
    assert all(row["primary"] is True for row in manifest[:6])
    assert all(row["primary"] is False for row in manifest[6:])

    assert by_key["jobs-skills"]["available"] is True
    assert {"jobs", "experience", "skills"}.issubset(set(by_key["jobs-skills"]["supported_capabilities"]))
    assert by_key["missions-quests"]["available"] is True
    assert by_key["key-items"]["available"] is True
    assert {"history", "runtime_flags", "recasts", "character_other"}.issubset(
        set(by_key["advanced"]["supported_capabilities"])
    )

    expected_containers = {
        0: "Inventory",
        1: "Mog Safe",
        2: "Storage",
        3: "Temporary Items",
        4: "Mog Locker",
        5: "Mog Satchel",
        6: "Mog Sack",
        7: "Mog Case",
        8: "Mog Wardrobe",
        9: "Mog Safe 2",
        10: "Mog Wardrobe 2",
        11: "Mog Wardrobe 3",
        12: "Mog Wardrobe 4",
        13: "Mog Wardrobe 5",
        14: "Mog Wardrobe 6",
        15: "Mog Wardrobe 7",
        16: "Mog Wardrobe 8",
    }
    for location, name in expected_containers.items():
        assert CONTAINERS[location] == name
    assert CONTAINER_KEYS[0] == "inventory"
    assert CONTAINER_KEYS[9] == "safe2"
    assert CONTAINER_KEYS[16] == "wardrobe8"

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
    assert '"label": CONTAINER_LABELS.get' in service
    assert "decode_packed_field" in category_data
    assert 'entry["decoded"] = decoded' in category_data

    # This focused test is already exercised by Src Layout/Workbench; route the packed codec
    # vectors through it so the new decoder cannot silently escape the established gates.
    packed_codec_regression()


if __name__ == "__main__":
    main()
