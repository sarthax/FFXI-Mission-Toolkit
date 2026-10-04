"""Character-aware bridge for Feature Trace mission/quest state surfaces."""
from __future__ import annotations

from typing import Any

from workbench.devtools.features.state_surface_scoped import build_state_surface

from .category_data import build_category_payload
from .progression_assessment import assess_progression
from .progression_catalog import mission_catalog
from .progression_inspector import build_progression_inspector
from .quest_catalog import quest_catalog
from .transition_bundles import annotate_transition_bundles


def _catalog_row(service, kind: str, area_id: int, entry_id: int) -> dict[str, Any]:
    root = getattr(service, "server_root", None)
    catalog = mission_catalog(root) if kind == "mission" else quest_catalog(root)
    areas = catalog.get("areas") or {}
    area = areas.get(str(int(area_id)), areas.get(int(area_id), {}))
    row = area.get(str(int(entry_id))) if isinstance(area, dict) else None
    if row is None and isinstance(area, dict):
        row = area.get(int(entry_id))
    return dict(row or {"id": int(entry_id), "label": f"{kind.title()} {entry_id}", "symbol": None})


def _variable_values(service, char_id: int) -> dict[str, Any]:
    values: dict[str, Any] = {}
    table_names = list((service.schema.capabilities or {}).get("variables", ()))
    if service.schema.table("char_vars") is not None and "char_vars" not in table_names:
        table_names.append("char_vars")
    for table_name in table_names:
        try:
            rows = service.load_table(char_id, table_name)
        except (KeyError, RuntimeError):
            continue
        for row in rows:
            key = row.get("varname", row.get("name", row.get("var")))
            if key is None:
                continue
            value = row.get("value", row.get("val", row.get("varvalue")))
            values[str(key)] = value
    return values


def _packed_current(service, char_id: int) -> dict[str, Any]:
    current: dict[str, Any] = {"key_items": {}, "titles": set(), "mission": {}, "quest": {}}
    try:
        key_payload = build_category_payload(service, char_id, "key-items")
        entry = (key_payload.get("packed") or {}).get("key_items") or {}
        decoded = entry.get("decoded") or {}
        catalog = entry.get("catalog") or {}
        owned = set(int(v) for v in decoded.get("owned_ids", ()))
        for raw_id, row in (catalog.get("items") or {}).items():
            try:
                item_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            symbol = str(row.get("symbol") or "")
            if symbol:
                current["key_items"][symbol] = item_id in owned
        current["key_item_owned_ids"] = owned
    except Exception:
        pass

    try:
        progression = build_category_payload(service, char_id, "missions-quests")
        packed = progression.get("packed") or {}
        missions = (packed.get("missions") or {}).get("decoded") or {}
        for area in missions.get("areas", ()):
            area_id = int(area.get("area_id", -1))
            current["mission"][area_id] = {
                "current": int(area.get("current", 0)),
                "completed": set(int(v) for v in area.get("completed_ids", ())),
            }
        quests = (packed.get("quests") or {}).get("decoded") or {}
        for area in quests.get("areas", ()):
            area_id = int(area.get("area_id", -1))
            current["quest"][area_id] = {
                "current": set(int(v) for v in area.get("current_ids", ())),
                "completed": set(int(v) for v in area.get("completed_ids", ())),
            }
    except Exception:
        pass

    try:
        unlocks = build_category_payload(service, char_id, "unlocks-travel")
        titles = ((unlocks.get("packed") or {}).get("titles") or {}).get("decoded") or {}
        current["titles"] = set(int(v) for v in titles.get("set_ids", ()))
    except Exception:
        pass
    return current


def _normalize_expected(value: str | None) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    try:
        return int(text, 0)
    except (TypeError, ValueError):
        return text.strip("'\"")


def _condition_result(actual: Any, operator: str | None, expected: Any) -> bool | None:
    if operator is None:
        return None
    try:
        if operator == "==": return actual == expected
        if operator == "~=": return actual != expected
        if operator == ">=": return actual >= expected
        if operator == "<=": return actual <= expected
        if operator == ">": return actual > expected
        if operator == "<": return actual < expected
    except TypeError:
        return None
    return None


def _feature_var_storage(kind: str, area_id: int, entry_id: int, key: str) -> str:
    prefix = "Quest" if kind == "quest" else "Mission"
    return f"{prefix}[{int(area_id)}][{int(entry_id)}]{key}"


def build_character_state_surface(service, char_id: int, *, kind: str, area_id: int, entry_id: int) -> dict[str, Any]:
    if not service.character_exists(char_id):
        raise KeyError(f"Character {char_id} was not found")
    row = _catalog_row(service, kind, area_id, entry_id)
    root = getattr(service, "server_root", None)
    if root is None:
        raise RuntimeError("The active server environment has no server root")

    surface = build_state_surface(
        root,
        kind=kind,
        area_id=area_id,
        entry_id=entry_id,
        symbol=row.get("symbol"),
        label=row.get("label"),
    )
    variables = _variable_values(service, char_id)
    packed = _packed_current(service, char_id)

    checked = 0
    matched = 0
    mismatched = 0
    unresolved = 0
    for ref in surface.get("references", []):
        actual = None
        resolved = False
        state_type = ref.get("state_type")
        key = str(ref.get("key") or "")
        if state_type == "charvar":
            # Missing charvars have server semantics equivalent to zero on the supported lineages.
            actual = variables.get(key, 0)
            resolved = True
        elif state_type in {"quest_var", "mission_var"} and "." not in key:
            storage = _feature_var_storage(kind, area_id, entry_id, key)
            actual = variables.get(storage, 0)
            resolved = True
            ref["storage_key"] = storage
        elif state_type == "key_item" and key in packed.get("key_items", {}):
            actual = bool(packed["key_items"][key])
            resolved = True
        ref["current_value"] = actual if resolved else None
        ref["current_resolved"] = resolved

        expected = _normalize_expected(ref.get("expectation_value"))
        result = _condition_result(actual, ref.get("expectation_operator"), expected) if resolved else None
        ref["condition_matches"] = result
        if ref.get("expectation_operator"):
            checked += 1
            if result is True:
                matched += 1
            elif result is False:
                mismatched += 1
            else:
                unresolved += 1

    # The extractor groups are snapshots of the pre-enrichment references. Rebuild them so the
    # Character Editor renders the exact live-state-enriched rows rather than stale copies.
    groups: dict[str, list[dict[str, Any]]] = {}
    for ref in surface.get("references", []):
        groups.setdefault(str(ref.get("state_type") or "other"), []).append(ref)
    surface["groups"] = groups

    target_state: dict[str, Any] = {"resolved": False}
    if kind == "mission":
        area = packed.get("mission", {}).get(int(area_id), {})
        if area:
            target_state = {
                "resolved": True,
                "current": int(area.get("current", 0)) == int(entry_id),
                "current_id": int(area.get("current", 0)),
                "completed": int(entry_id) in area.get("completed", set()),
            }
    else:
        area = packed.get("quest", {}).get(int(area_id), {})
        if area:
            target_state = {
                "resolved": True,
                "active": int(entry_id) in area.get("current", set()),
                "completed": int(entry_id) in area.get("completed", set()),
            }

    surface["character"] = {"char_id": int(char_id), "target_state": target_state}
    surface["consistency"] = {
        "conditions_checked": checked,
        "matching": matched,
        "mismatching": mismatched,
        "unresolved": unresolved,
        "status": "MISMATCH" if mismatched else ("CONSISTENT" if checked and not unresolved else "PARTIAL"),
    }
    progression = annotate_transition_bundles(build_progression_inspector(
        surface,
        root,
        variables=variables,
        packed=packed,
        mission_catalog=mission_catalog(root),
        quest_catalog=quest_catalog(root),
    ))
    surface["progression"] = assess_progression(progression)
    return surface