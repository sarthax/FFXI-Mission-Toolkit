"""Canonical FFXI Auction House category metadata.

The numeric values are the client-facing AH category IDs retained across DSP, Topaz, and
LandSandBoat item_basic data. Labels follow LandSandBoat's item_AH_category enum/menu comments;
the database value remains authoritative and unknown fork-specific values are preserved.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuctionCategory:
    id: int
    group: str
    label: str
    path: str


def _category(category_id: int, path: str) -> AuctionCategory:
    parts = [part.strip() for part in path.split("->")]
    return AuctionCategory(id=category_id, group=parts[0], label=parts[-1], path=" → ".join(parts))


# IDs 1..65 mirror the retail/client AH category values. Category 27 is historically unused.
_PATHS = {
    1: "Weapons->Hand-to-Hand",
    2: "Weapons->Dagger",
    3: "Weapons->Sword",
    4: "Weapons->Great Sword",
    5: "Weapons->Axe",
    6: "Weapons->Great Axe",
    7: "Weapons->Scythe",
    8: "Weapons->Polearm",
    9: "Weapons->Katana",
    10: "Weapons->Great Katana",
    11: "Weapons->Club",
    12: "Weapons->Staff",
    13: "Weapons->Bow",
    14: "Weapons->Instruments",
    15: "Weapons->Ammo & Misc.->Ammunition",
    16: "Armor->Shield",
    17: "Armor->Head",
    18: "Armor->Body",
    19: "Armor->Hands",
    20: "Armor->Legs",
    21: "Armor->Feet",
    22: "Armor->Neck",
    23: "Armor->Waist",
    24: "Armor->Earrings",
    25: "Armor->Rings",
    26: "Armor->Back",
    27: "Unused",
    28: "Scrolls->White Magic",
    29: "Scrolls->Black Magic",
    30: "Scrolls->Summoning",
    31: "Scrolls->Ninjutsu",
    32: "Scrolls->Songs",
    33: "Medicines",
    34: "Furnishings",
    35: "Crystals",
    36: "Others->Cards",
    37: "Others->Cursed Items",
    38: "Materials->Smithing",
    39: "Materials->Goldsmithing",
    40: "Materials->Clothcraft",
    41: "Materials->Leathercraft",
    42: "Materials->Bonecraft",
    43: "Materials->Woodworking",
    44: "Materials->Alchemy",
    45: "Scrolls->Geomancy",
    46: "Others->Misc.",
    47: "Weapons->Ammo & Misc.->Fishing Gear",
    48: "Weapons->Ammo & Misc.->Pet Items",
    49: "Others->Ninja Tools",
    50: "Others->Beast-made",
    51: "Food->Fish",
    52: "Food->Meals->Meat & Eggs",
    53: "Food->Meals->Seafood",
    54: "Food->Meals->Vegetables",
    55: "Food->Meals->Soups",
    56: "Food->Meals->Breads & Rice",
    57: "Food->Meals->Sweets",
    58: "Food->Meals->Drinks",
    59: "Food->Ingredients",
    60: "Scrolls->Dice",
    61: "Others->Automaton",
    62: "Weapons->Ammo & Misc.->Grips",
    63: "Materials->Alchemy 2",
    64: "Others->Misc. 2",
    65: "Others->Misc. 3",
}

CATEGORIES = {category_id: _category(category_id, path) for category_id, path in _PATHS.items()}


def category_metadata(category_id: int) -> AuctionCategory:
    """Return canonical metadata, preserving unknown custom-fork category IDs."""
    category_id = int(category_id)
    return CATEGORIES.get(
        category_id,
        AuctionCategory(category_id, "Custom / Unknown", f"Category {category_id}", f"Category {category_id}"),
    )
