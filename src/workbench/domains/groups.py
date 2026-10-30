"""Sub-domain grouping for the /domains overview.

Presentation only: it sorts the existing domain definitions and the hand-built tools into
named groups. A domain key that is not listed here still appears, under "Other domains",
so a newly added definition can never disappear from the page.
"""
from __future__ import annotations

# Hand-built pages that are not entries in definitions.json.
STATIC_ENTRIES = {
    "assault": {"label": "Assault", "href": "/domains/assault", "archetype": "system.assault",
                "note": "Built: Assault workspace"},
    "nyzul": {"label": "Nyzul Isle", "href": "/nyzul", "archetype": "system.nyzul",
              "note": "Built: live layout editor"},
    "ws-calc": {"label": "Weapon Skill Calculator", "href": "/tools/ws-calc", "archetype": "tool.ws_calc",
                "note": "Built: what-if damage calculator"},
    "magic-calc": {"label": "Magic Nuke Calculator (elemental + ninjutsu)", "href": "/tools/magic-calc",
                   "archetype": "tool.magic_calc", "note": "Built: what-if damage calculator"},
    "heal-calc": {"label": "Healing and Defense Overview (WHM/PLD)", "href": "/tools/heal-calc",
                  "archetype": "tool.heal_calc", "note": "Built: what-if healing, damage reduction and resists"},
    "pet-calc": {"label": "Pet Gear Calculator (SMN/BST/PUP/DRG)", "href": "/tools/pet-calc",
                 "archetype": "tool.pet_calc", "note": "Built: what-if pet gear and augment effects"},
    "melee-calc": {"label": "Melee Calculator", "href": "/tools/melee-calc", "archetype": "tool.melee_calc",
                   "note": "Built: what-if melee damage, haste, TP and procs"},
}

GROUPS = (
    ("instanced", "Instanced content", "Assault, Nyzul, battlefields and the other instanced fights.",
     ("assault", "nyzul", "battlefields", "combat", "salvage", "voidwatch", "voidwalker", "znm")),
    ("zones", "Zone systems", "Content that lives in a zone or a zone family.",
     ("abyssea", "escha", "dynamis", "waypoint")),
    ("conflict", "Conflict and campaign", "Nation and beastman warfare systems.",
     ("conflict", "campaign")),
    ("progression", "Progression", "Missions, quests and the long-running progression frameworks.",
     ("missions", "quests", "roe", "unity", "trust", "survival_guides", "run_geo")),
    ("activities", "Activities and events", "Gathering, hobbies, events and similar side systems.",
     ("helm", "hobbies", "events", "chocobo_raising", "synergy", "super_kupopower")),
    ("calculators", "Calculators", "What-if damage and healing tools.",
     ("ws-calc", "magic-calc", "heal-calc", "pet-calc", "melee-calc")),
)
FALLBACK = ("other", "Other domains", "Everything not placed in a group above.")


def group_rows(rows):
    """Return [{id,label,blurb,entries:[...]}] in display order.

    ``rows`` are the dicts built by ``domains_index_page``; each item keeps every field of its
    row, plus ``href``. Static entries get ``static=True`` so the template shows the note.
    """
    by_key = {r["key"]: {**r, "href": f"/domains/{r['key']}", "static": False} for r in rows}
    for key, e in STATIC_ENTRIES.items():
        by_key.setdefault(key, {"key": key, "label": e["label"], "href": e["href"],
                                "archetype": e["archetype"], "note": e["note"], "static": True})
    placed, out = set(), []
    for gid, label, blurb, keys in GROUPS:
        items = [by_key[k] for k in keys if k in by_key]
        placed.update(k for k in keys if k in by_key)
        if items:
            out.append({"id": gid, "label": label, "blurb": blurb, "entries": items})
    rest = sorted((v for k, v in by_key.items() if k not in placed), key=lambda v: v["label"].lower())
    if rest:
        out.append({"id": FALLBACK[0], "label": FALLBACK[1], "blurb": FALLBACK[2], "entries": rest})
    return out
