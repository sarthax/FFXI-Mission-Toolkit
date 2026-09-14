"""NPC/Entity ID Lookup Module for the Packetlyzer Analyzer.

Parses npc_list.sql from the FFXI server source to build a mapping of
NPC ID → name. Uses the FFXI NPC ID structure:
  0x01[ZoneID:12bits][Index:12bits]

Also supports mob_list.sql for mob spawns, and provides contextual
resolution for item IDs, zone IDs, and model IDs using the existing
lookup tables.
"""

import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Regex to extract NPC ID and name from npc_list.sql INSERT statements
# Format: INSERT INTO `npc_list` VALUES (id,'polutils_name','display_name',...)
_NPC_INSERT_PATTERN = re.compile(
    r"VALUES\s*\(\s*(\d+)\s*,\s*'([^']*?)'\s*,\s*'([^']*?)'"
)

# Regex for mob_list.sql: INSERT INTO `mob_list` VALUES (id,'group_name','zone_name',...)
_MOB_INSERT_PATTERN = re.compile(
    r"VALUES\s*\(\s*(\d+)\s*,\s*'([^']*?)'\s*,\s*'([^']*?)'"
)

# Field name patterns that indicate specific data types for DB lookup
# These are checked case-insensitively
_ENTITY_ID_NAMES = {
    "player_id", "npc_id", "actor_id", "target_id", "uniqueno",
    "uniquenotar", "uniquenocas", "btargetid", "lootuniqueno",
    "entryuniqueno", "gmuniqueno", "uniqueno2", "uniqueno3",
    "casuniqueono", "taruniqueno", "m_ppcastratel", "m_pptargetatel",
}

_ZONE_ID_NAMES = {
    "zone_id", "zoneno", "zone", "zonesubno", "mapnumber", "submapnumber",
}

_ITEM_ID_NAMES = {
    "item_id", "itemno", "crystal_item_id", "ingredient_1", "ingredient_2",
    "ingredient_3", "ingredient_4", "myroomitemno", "myroomadditemno",
    "myroomplantitemno", "shopitemoffsetindex", "trophyitemno",
    "crystalno", "crystal",
}

_MODEL_ID_NAMES = {
    "model_id_head", "model_id_body", "model_id_hands", "model_id_legs",
    "model_id_feet", "model_id_main", "model_id_sub", "model_id_range",
    "feet_model", "body_model", "head_model", "hands_model", "legs_model",
    "main_weapon_model", "sub_weapon_model", "ranged_weapon_model",
    "costumeId", "costume_id", "mon_no",
}

_SPELL_ID_NAMES = {
    "spellid", "spell_id",
}

_JOB_ABILITY_NAMES = {
    "skillid", "skill_id",
}


def decode_npc_id(npc_id: int) -> dict:
    """Decode an FFXI NPC/entity ID into its components.

    FFXI entity IDs follow the structure:
      Bits 24-31: Type (0x01 = NPC/mob)
      Bits 12-23: Zone ID
      Bits  0-11: Index within zone

    Args:
        npc_id: The raw 32-bit entity ID.

    Returns:
        Dict with keys: type, zone_id, index
    """
    type_field = (npc_id >> 24) & 0xFF
    zone_id = (npc_id >> 12) & 0xFFF
    index = npc_id & 0xFFF
    return {
        "type": type_field,
        "zone_id": zone_id,
        "index": index,
    }


class NPCLookup:
    """Manages NPC/mob name resolution and contextual field lookups.

    Loads npc_list.sql and optionally mob_list.sql to build a mapping
    of entity ID → display name. Also uses LookupManager tables for
    item, zone, and model resolution based on field name patterns.
    """

    def __init__(self, sql_dir: Optional[str] = None, lookup_mgr=None):
        """Initialize the NPC lookup.

        Args:
            sql_dir: Path to the directory containing npc_list.sql and
                     mob_list.sql. If None or not found, operates empty.
            lookup_mgr: Optional LookupManager instance for item/zone/model
                        resolution via existing lookup tables.
        """
        self._names: dict[int, str] = {}
        self._sql_dir = sql_dir
        self._lookup_mgr = lookup_mgr

        if sql_dir:
            self._load_npc_list(sql_dir)
            self._load_mob_list(sql_dir)

        if self._names:
            logger.info("NPC Lookup loaded %d entity names", len(self._names))
        else:
            logger.warning("NPC Lookup: no entity names loaded (sql_dir=%s)", sql_dir)

    def _load_npc_list(self, sql_dir: str) -> None:
        """Load npc_list.sql entries."""
        npc_path = os.path.join(sql_dir, "npc_list.sql")
        if not os.path.isfile(npc_path):
            logger.debug("npc_list.sql not found at %s", npc_path)
            return

        count = 0
        try:
            with open(npc_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    for match in _NPC_INSERT_PATTERN.finditer(line):
                        npc_id = int(match.group(1))
                        # Use display name (group 3), fall back to polutils name (group 2)
                        display_name = match.group(3) or match.group(2)
                        self._names[npc_id] = display_name
                        count += 1
        except OSError as e:
            logger.warning("Failed to read npc_list.sql: %s", e)

        logger.debug("Loaded %d NPCs from npc_list.sql", count)

    def _load_mob_list(self, sql_dir: str) -> None:
        """Load mob_list.sql entries (mob spawns with group/zone names)."""
        for filename in ("mob_spawn_list.sql", "mob_list.sql"):
            mob_path = os.path.join(sql_dir, filename)
            if not os.path.isfile(mob_path):
                continue

            count = 0
            try:
                with open(mob_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        for match in _MOB_INSERT_PATTERN.finditer(line):
                            mob_id = int(match.group(1))
                            if mob_id not in self._names:
                                display_name = match.group(3) or match.group(2)
                                self._names[mob_id] = display_name
                                count += 1
            except OSError as e:
                logger.warning("Failed to read %s: %s", filename, e)

            if count > 0:
                logger.debug("Loaded %d mobs from %s", count, filename)
            break

    def resolve(self, entity_id: int) -> Optional[str]:
        """Look up an entity ID and return its name.

        Args:
            entity_id: The raw 32-bit entity ID (NPC or mob).

        Returns:
            The entity's display name if found, or None if not in the database.
        """
        return self._names.get(entity_id)

    def resolve_with_info(self, entity_id: int) -> str:
        """Look up an entity ID and return a formatted info string.

        Returns:
            Formatted lookup string or empty string.
        """
        name = self._names.get(entity_id)
        if name is None:
            return ""

        info = decode_npc_id(entity_id)
        return f"{name} (Zone:{info['zone_id']}, Idx:{info['index']})"

    def resolve_field(self, field_name: str, field_type: str, value, raw_value=None) -> str:
        """Contextual resolution based on field name and type.

        Examines the field name to determine what kind of data it holds,
        then resolves using the appropriate lookup source.

        Args:
            field_name: The field name from the packet definition.
            field_type: The field type (uint16, uint32, etc.)
            value: The decoded display value (usually int).
            raw_value: The raw value (int, float, str, bytes).

        Returns:
            Resolved display string, or empty string if no resolution applies.
        """
        # Normalize field name for matching
        name_lower = field_name.lower().replace("_", "").replace(" ", "")

        # Get the numeric value
        num_value = None
        if isinstance(raw_value, int):
            num_value = raw_value
        elif isinstance(value, int):
            num_value = value
        elif isinstance(value, str):
            try:
                num_value = int(value)
            except (ValueError, TypeError):
                pass

        if num_value is None or num_value == 0:
            return ""

        # --- Entity ID resolution (uint32 fields) ---
        if field_type in ("uint32", "int32"):
            # Check by field name first
            name_check = field_name.lower().replace(" ", "_")
            if name_check in _ENTITY_ID_NAMES or any(n in name_lower for n in ("uniqueno", "targetid", "actorid", "playerid", "npcid")):
                if self.is_entity_id(num_value):
                    return self.resolve_with_info(num_value)
            # Also try structural matching for any uint32
            elif self.is_entity_id(num_value):
                result = self.resolve_with_info(num_value)
                if result:
                    return result

        # --- Zone ID resolution (uint16 fields typically) ---
        if field_type in ("uint16", "uint32", "byte"):
            name_check = field_name.lower().replace(" ", "_")
            if name_check in _ZONE_ID_NAMES or any(n in name_lower for n in ("zone", "zoneno", "mapnumber")):
                if self._lookup_mgr and 0 < num_value < 300:
                    resolved = self._lookup_mgr.resolve("zones", num_value)
                    if "unknown" not in resolved and "missing" not in resolved:
                        # Strip the leading "N → " from LookupManager format
                        return resolved.split("\u2192")[-1].strip().strip('"') if "\u2192" in resolved else ""
                    return ""

        # --- Item ID resolution (uint16 fields) ---
        if field_type in ("uint16", "uint32"):
            name_check = field_name.lower().replace(" ", "_")
            if name_check in _ITEM_ID_NAMES or any(n in name_lower for n in ("itemno", "itemid", "crystal")):
                if self._lookup_mgr and num_value > 0:
                    resolved = self._lookup_mgr.resolve("items", num_value)
                    if "unknown" not in resolved and "missing" not in resolved:
                        return resolved.split("\u2192")[-1].strip().strip('"') if "\u2192" in resolved else ""
                    return ""

        # --- Model ID resolution (uint16 fields) ---
        if field_type == "uint16":
            name_check = field_name.lower().replace(" ", "_")
            if name_check in _MODEL_ID_NAMES or any(n in name_lower for n in ("model", "grapid")):
                if self._lookup_mgr and num_value > 0:
                    resolved = self._lookup_mgr.resolve("itemmodels", num_value)
                    if "unknown" not in resolved and "missing" not in resolved:
                        # itemmodels format: 'N → "Name;slot info"' — extract just the name
                        raw_name = resolved.split("\u2192")[-1].strip().strip('"') if "\u2192" in resolved else ""
                        # Strip slot info after semicolon (e.g., "Leather Vest;body 1" → "Leather Vest")
                        if ";" in raw_name:
                            raw_name = raw_name.split(";")[0]
                        return raw_name
                    # Also try items.txt as fallback
                    resolved = self._lookup_mgr.resolve("items", num_value)
                    if "unknown" not in resolved and "missing" not in resolved:
                        return resolved.split("\u2192")[-1].strip().strip('"') if "\u2192" in resolved else ""
                    return ""

        # --- Spell ID resolution ---
        if field_type in ("uint16", "uint32"):
            name_check = field_name.lower().replace(" ", "_")
            if name_check in _SPELL_ID_NAMES or "spell" in name_lower:
                if self._lookup_mgr and num_value > 0:
                    resolved = self._lookup_mgr.resolve("spells", num_value)
                    if "unknown" not in resolved and "missing" not in resolved:
                        return resolved.split("\u2192")[-1].strip().strip('"') if "\u2192" in resolved else ""

        # --- Weather resolution ---
        if "weather" in name_lower and field_type in ("uint16", "byte"):
            if self._lookup_mgr and num_value >= 0:
                resolved = self._lookup_mgr.resolve("weather", num_value)
                if "unknown" not in resolved and "missing" not in resolved:
                    raw_name = resolved.split("\u2192")[-1].strip().strip('"') if "\u2192" in resolved else ""
                    # Weather format: "Hot Spell;WEATHER_HOT_SPELL" - take first part
                    if ";" in raw_name:
                        raw_name = raw_name.split(";")[0]
                    return raw_name

        # --- Job resolution ---
        if field_type == "byte" and any(n in name_lower for n in ("job", "mjob", "sjob")):
            if self._lookup_mgr and 0 < num_value < 30:
                resolved = self._lookup_mgr.resolve("jobs", num_value)
                if "unknown" not in resolved and "missing" not in resolved:
                    raw_name = resolved.split("\u2192")[-1].strip().strip('"') if "\u2192" in resolved else ""
                    # Jobs format: "WAR;Warrior" - take second part (full name)
                    if ";" in raw_name:
                        raw_name = raw_name.split(";")[1]
                    return raw_name

        return ""

    @property
    def entry_count(self) -> int:
        """Return the number of loaded entity names."""
        return len(self._names)

    def is_entity_id(self, value: int) -> bool:
        """Check if a uint32 value looks like a valid FFXI entity ID.

        Valid entity IDs have:
        - Type byte = 0x01 (bits 24-31)
        - Zone ID 1-299 (bits 12-23)
        - Index 0-4095 (bits 0-11)
        """
        if value == 0:
            return False
        type_field = (value >> 24) & 0xFF
        zone_id = (value >> 12) & 0xFFF
        if type_field != 0x01:
            return False
        if zone_id < 1 or zone_id > 299:
            return False
        return True
