"""Read payloads for Character Editor tabs.

Row tables are returned as rows and packed fields as their physical raw value plus location.
Verified scalar tables expose editable-column metadata.  Packed mission/key-item state is decoded
through lineage-aware codecs but remains read-only until guarded packed-state transactions exist.
"""
from __future__ import annotations

from typing import Any

from .categories import TAB_DEFINITIONS, get_tab
from .packed_codecs import PackedCodecError, decode_packed_field

_ALIAS_CAPABILITIES = {
    "experience": "jobs",
    "equipment": "inventory",
    "storage": "inventory",
    "currencies": "points",
    "teleports": "unlocks",
}


def build_category_payload(service, char_id: int, tab_key: str) -> dict[str, Any]:
    tab = get_tab(tab_key)
    identity = service._identity(char_id)
    if identity is None:
        raise KeyError(f"Character {char_id} was not found")

    tables: dict[str, list[dict[str, Any]]] = {}
    packed: dict[str, dict[str, Any]] = {}
    editors: dict[str, list[dict[str, Any]]] = {}
    capability_map = service.schema.capabilities or {}

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
                decoded = decode_packed_field(capability, value, service.adapter_family)
                if decoded is not None:
                    entry["decoded"] = decoded
                    entry["codec"] = decoded.get("codec")
                    entry["layout"] = decoded.get("layout")
            except PackedCodecError as exc:
                entry["decode_error"] = str(exc)
            packed[capability] = entry

    if tab.key == "character":
        tables["chars"] = [identity]
        editable = service.editable_fields("chars")
        if editable:
            editors["chars"] = editable

    return {
        "tab": tab.as_dict(),
        "char_id": int(char_id),
        "tables": tables,
        "packed": packed,
        "editors": editors,
    }
