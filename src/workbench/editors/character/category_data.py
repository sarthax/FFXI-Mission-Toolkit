"""Read payloads for Character Editor tabs.

Row tables are returned as rows and packed fields as their physical raw value plus location.
Verified scalar tables expose editable-column metadata. Supported packed state is decoded through
lineage-aware codecs and enriched from the configured server checkout's own catalogs.
"""
from __future__ import annotations

from typing import Any

from .assault_catalog import assault_catalog
from .campaign_catalog import campaign_catalog
from .categories import TAB_DEFINITIONS, get_tab
from .eminence_catalog import eminence_catalog
from .eminence_codec import EminenceCodecError, decode_eminence
from .merit_catalog import merit_catalog
from .packed_codecs import PackedCodecError, decode_packed_field
from .progression_catalog import progression_catalog
from .quest_catalog import quest_catalog

_ALIAS_CAPABILITIES = {
    "experience": "jobs",
    "equipment": "inventory",
    "storage": "inventory",
    "currencies": "points",
    "teleports": "unlocks",
}
_PACKED_EDITABLE = {
    "missions",
    "quests",
    "assaults",
    "campaign",
    "eminence",
    "key_items",
    "blue_spells",
    "abilities",
    "weaponskills",
    "titles",
    "visited_zones",
}


def build_category_payload(service, char_id: int, tab_key: str) -> dict[str, Any]:
    tab = get_tab(tab_key)
    identity = service._identity(char_id)
    if identity is None:
        raise KeyError(f"Character {char_id} was not found")

    tables: dict[str, list[dict[str, Any]]] = {}
    packed: dict[str, dict[str, Any]] = {}
    editors: dict[str, list[dict[str, Any]]] = {}
    catalogs: dict[str, Any] = {}
    capability_map = service.schema.capabilities or {}
    catalog_cache: dict[str, Any] | None = None

    requested_caps = set(tab.capabilities)
    if tab.key == "advanced":
        known = {cap for item in TAB_DEFINITIONS for cap in item.capabilities}
        requested_caps.update(cap for cap in capability_map if cap not in known and cap != "other")

    loaded_tables: set[str] = set()
    for capability in sorted(requested_caps):
        physical_capability = _ALIAS_CAPABILITIES.get(capability, capability)
        for table_name in capability_map.get(physical_capability, ()):
            if table_name in loaded_tables or table_name == "chars":
                continue
            loaded_tables.add(table_name)
            tables[table_name] = service.load_table(char_id, table_name)
            editable = service.editable_fields(table_name)
            if editable:
                editors[table_name] = editable

        location = (service.schema.packed_fields or {}).get(capability)
        if location and "." in location:
            table_name, column = location.split(".", 1)
            value = identity.get(column) if table_name == "chars" else None
            entry: dict[str, Any] = {"location": location, "value": value, "editable": False}
            try:
                if capability == "eminence":
                    decoded = decode_eminence(value, service.adapter_family)
                else:
                    decoded = decode_packed_field(capability, value, service.adapter_family)
                if decoded is not None:
                    entry["decoded"] = decoded
                    entry["codec"] = decoded.get("codec")
                    entry["layout"] = decoded.get("layout")
                    entry["editable"] = capability in _PACKED_EDITABLE
                    if capability == "quests":
                        entry["catalog"] = quest_catalog(getattr(service, "server_root", None))
                    elif capability == "assaults":
                        entry["catalog"] = assault_catalog(getattr(service, "server_root", None))
                    elif capability == "campaign":
                        entry["catalog"] = campaign_catalog(getattr(service, "server_root", None))
                    elif capability == "eminence":
                        entry["catalog"] = eminence_catalog(getattr(service, "server_root", None))
                    else:
                        if catalog_cache is None:
                            catalog_cache = progression_catalog(
                                getattr(service, "server_root", None),
                                service.adapter_family,
                            )
                        entry["catalog"] = catalog_cache.get(capability, {})
            except (PackedCodecError, EminenceCodecError) as exc:
                entry["decode_error"] = str(exc)
            packed[capability] = entry

    if tab.key == "character":
        tables["chars"] = [identity]
        editable = service.editable_fields("chars")
        if editable:
            editors["chars"] = editable

    if tab.key == "merits-jobpoints":
        catalogs["merits"] = merit_catalog(
            getattr(service, "server_root", None),
            service.adapter_family,
        )

    return {
        "tab": tab.as_dict(),
        "char_id": int(char_id),
        "tables": tables,
        "packed": packed,
        "editors": editors,
        "catalogs": catalogs,
    }
