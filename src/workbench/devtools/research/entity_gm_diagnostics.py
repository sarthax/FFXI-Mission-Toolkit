"""Unmodified-server GM command diagnostics, advisory and read-only.

Commands are intended for a human GM in-game; this module never transmits
commands, elevates permissions, changes server state, or claims runtime proof.
"""
from __future__ import annotations

import re

_ALLOWED = re.compile(r"^[0-9]{1,10}$")


def gm_entity_diagnostic_plan(*, server_entity_id: int | None,
                              mob: bool = True, source: str = "dsp") -> dict:
    """Return verified command suggestions plus explicit evidence limitations."""
    result = {
        "source": source,
        "mode": "manual_gm_read_only",
        "requires_gm_permission": True,
        "requires_server_modification": False,
        "commands": [],
        "runtime_status": "unknown",
        "note": "GM text is observational evidence; command output must not be treated as authoritative instance state.",
    }
    if source != "dsp":
        result["note"] = "Command availability not verified for this server family."
        return result
    if not mob or server_entity_id is None:
        result["note"] = "Verified getmobaction applies to mobs only; no NPC runtime command verified."
        return result
    if type(server_entity_id) is not int or not 0 <= server_entity_id <= 0xFFFFFFFF:
        raise ValueError("Invalid global server entity ID")
    ident = str(server_entity_id)
    if not _ALLOWED.fullmatch(ident):
        raise ValueError("Invalid command argument")
    result["commands"].append({
        "command": "!getmobaction " + ident,
        "purpose": "Print a mob's current action ID using the existing GM command",
        "availability": "verified_topaz_to_valhalla_release",
        "permission": 1,
        "mutates_server": False,
        "limitations": "An action ID is not a spawn/despawn verdict; command may reject missing mob IDs.",
    })
    return result
