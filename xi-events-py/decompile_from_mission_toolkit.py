#!/usr/bin/env python3
"""
Bridges this repo's real decompiler (xi_events) onto mission_toolkit.py's own export format
(events.yml/dialog.yml, produced via xi-tinkerer -- see FFXI-Tools/mission_toolkit.py), so any
event from any zone we've already pulled a report for can be decompiled to real, structured Lua
pseudocode in one command -- no manual Fixture-building glue code needed each time.

xi-events-py's own normal input is a released FFXI-Resources ndjson dataset -- this script is an
alternative front door using our own already-established mission_toolkit.py pipeline instead, since
we already have that data on disk for every zone we've investigated this session.

Usage:
    python decompile_from_mission_toolkit.py <events.yml> <entity_id> <event_id> [dialog.yml] [zone_id]
"""
import sys
from pathlib import Path

import yaml

from xi_events import Fixture, decompile


def _bytecode_hex(raw) -> str:
    """2026-08-31: mission_toolkit.py originally shelled out to a separate xi-tinkerer-cli.exe and
    round-tripped through YAML text, where byte_code came out unquoted for real content --
    PyYAML auto-parsed that as a Python int, not a string, a real quirk found integrating this
    bridge. mission_toolkit.py has since been switched to native xi-tinkerer-py, which always
    returns byte_code as a real string -- the int branch below is now just legacy-compat for any
    old-format events.yml still lying around, not something the current export can produce."""
    if isinstance(raw, str):
        return raw[2:] if raw.startswith("0x") else raw
    hexstr = format(raw, "x")
    return "0" + hexstr if len(hexstr) % 2 else hexstr


def load_fixture(events_yml: str, entity_id: int, event_id: int, dialog_yml: str = None, zone_id: int = 0) -> Fixture:
    with open(events_yml, encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    block = next((b for b in doc["blocks"] if b.get("entity_id") == entity_id), None)
    if block is None:
        raise SystemExit(f"entity_id {entity_id} not found in {events_yml}")

    ev = next((e for e in block["events"] if e["id"] == event_id), None)
    if ev is None:
        raise SystemExit(f"event id {event_id} not found under entity_id {entity_id}")

    hexstr = _bytecode_hex(ev["byte_code"])
    if hexstr in ("00", "0"):
        raise SystemExit(
            f"event {event_id} on entity {entity_id} is a bare '0x00' stub in this export -- "
            "no real bytecode to decompile. NOTE: this does not necessarily mean the real client "
            "has no content here -- see topaz_startevent_padding_required memory for a real case "
            "this session where confirmed-working events (5000/5002/5020/5022) showed this same "
            "false-empty signature. Check other entities in this zone that might own the same csid, "
            "or verify via a real GM !cs test in-game before concluding the event is truly empty."
        )

    bytecode = bytes.fromhex(hexstr)
    imed_data = block.get("data") or []

    strings = {}
    if dialog_yml:
        with open(dialog_yml, encoding="utf-8") as f:
            dd = yaml.safe_load(f)
        strings = dd.get("entries", dd)

    return Fixture(
        zone_id=zone_id,
        actor_id=entity_id,
        block=0,
        idx=1,
        event_id=event_id,
        bytecode=bytecode,
        entrypoint=0,
        imed_data=imed_data,
        strings=strings,
        entities={},
    )


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    events_yml = sys.argv[1]
    entity_id = int(sys.argv[2])
    event_id = int(sys.argv[3])
    dialog_yml = sys.argv[4] if len(sys.argv) > 4 else None
    zone_id = int(sys.argv[5]) if len(sys.argv) > 5 else 0

    fixture = load_fixture(events_yml, entity_id, event_id, dialog_yml, zone_id)
    print(decompile(fixture))
