#!/usr/bin/env python3
"""Regression checks for conservative Lua receiver typing."""
from __future__ import annotations

from workbench.analyzers.server import lua_events


def main():
    api = {
        "functions": [
            {
                "function_id": "f:getZone",
                "signature": {"return_type": "CLuaZone*"},
                "source_snapshot_id": "snap-a",
            },
            {
                "function_id": "f:getZone2",
                "signature": {"return_type": "const CLuaZone &"},
                "source_snapshot_id": "snap-a",
            },
            {
                "function_id": "f:getThingA",
                "signature": {"return_type": "CLuaZone*"},
                "source_snapshot_id": "snap-a",
            },
            {
                "function_id": "f:getThingB",
                "signature": {"return_type": "CLuaBaseEntity*"},
                "source_snapshot_id": "snap-a",
            },
        ],
        "bindings": [
            {
                "binding_id": "b:getZone",
                "lua_name": "getZone",
                "class_name": "CLuaBaseEntity",
                "function_id": "f:getZone",
                "source_snapshot_id": "snap-a",
            },
            {
                "binding_id": "b:getZone2",
                "lua_name": "getZone",
                "class_name": "CLuaBaseEntity",
                "function_id": "f:getZone2",
                "source_snapshot_id": "snap-a",
            },
            {
                "binding_id": "b:getThingA",
                "lua_name": "getThing",
                "class_name": "CLuaBaseEntity",
                "function_id": "f:getThingA",
                "source_snapshot_id": "snap-a",
            },
            {
                "binding_id": "b:getThingB",
                "lua_name": "getThing",
                "class_name": "CLuaBaseEntity",
                "function_id": "f:getThingB",
                "source_snapshot_id": "snap-a",
            },
            {
                "binding_id": "b:zoneGetID",
                "lua_name": "getID",
                "class_name": "CLuaZone",
                "function_id": None,
                "source_snapshot_id": "snap-a",
            },
        ],
    }

    hints = lua_events.return_type_hints_from_api(api)
    zone_hint = hints[("CLuaBaseEntity", "getZone")]
    assert zone_hint["class_name"] == "CLuaZone", zone_hint
    assert zone_hint["binding_ids"] == ["b:getZone", "b:getZone2"], zone_hint
    assert ("CLuaBaseEntity", "getThing") not in hints, hints

    text = """function onEventFinish(player, csid, option)
    if csid == 42 then
        local alias = player
        local zone = alias:getZone()
        zone:getID()
        local zone_alias = zone
        zone_alias:getID()
        alias = unknown
        alias:getName()
    end
end
"""
    fn = lua_events.FUNC_RE.search(text)
    calls = lua_events.typed_calls(text, 0, len(text), fn, hints)
    by_method = {}
    for row in calls:
        by_method.setdefault(row["method"], []).append(row)

    get_zone = by_method["getZone"][0]
    assert get_zone["class_hint"] == "CLuaBaseEntity", get_zone
    assert get_zone["class_hint_source"] == "LOCAL_ALIAS", get_zone

    zone_get_id = by_method["getID"][0]
    assert zone_get_id["class_hint"] == "CLuaZone", zone_get_id
    assert zone_get_id["class_hint_source"] == "API_RETURN_TYPE", zone_get_id
    assert "f:getZone" in zone_get_id["class_hint_evidence"]["function_ids"], zone_get_id

    zone_alias_get_id = by_method["getID"][1]
    assert zone_alias_get_id["class_hint"] == "CLuaZone", zone_alias_get_id
    assert zone_alias_get_id["class_hint_source"] == "LOCAL_ALIAS", zone_alias_get_id

    after_unknown = by_method["getName"][0]
    assert after_unknown["class_hint"] is None, after_unknown

    print("Lua event typing self-test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
