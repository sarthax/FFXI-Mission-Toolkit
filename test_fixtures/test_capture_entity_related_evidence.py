#!/usr/bin/env python3
from __future__ import annotations

import sqlite3

from workbench.core.services import capture_integrity
from workbench.core.services.capture_related_evidence import entity_identity_matches


def key(**values):
    return capture_integrity.canonical_row_key(values)


def main():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript("""
        CREATE TABLE capture_npc_entries (
            capture_id INTEGER, zone_db TEXT, entity_id INTEGER, name TEXT
        );
        CREATE TABLE capture_events (
            capture_id INTEGER, zone_db TEXT, seq INTEGER, entity_id INTEGER, entity_name TEXT
        );
        CREATE TABLE capture_eventview (
            capture_id INTEGER, zone_db TEXT, seq INTEGER, entity_id INTEGER
        );
        CREATE TABLE capture_actions (
            capture_id INTEGER, action_key TEXT, actor INTEGER, name TEXT, ts INTEGER
        );
    """)

    # Entity 100 is unique in Zone A; entity 200 deliberately appears in two zones.
    con.executemany(
        "INSERT INTO capture_npc_entries VALUES(?,?,?,?)",
        [
            (1, "Zone_A", 100, "Alpha"),
            (1, "Zone_A", 200, "Beta A"),
            (1, "Zone_B", 200, "Beta B"),
            # Same name as Alpha but a different numeric identity: must never correlate by name.
            (1, "Zone_A", 300, "Alpha"),
        ],
    )
    con.executemany(
        "INSERT INTO capture_events VALUES(?,?,?,?,?)",
        [
            (1, "Zone_A", 1, 100, "Alpha"),
            (1, "Zone_B", 2, 100, "Alpha"),
            (1, "Zone_A", 3, 300, "Alpha"),
        ],
    )
    con.executemany(
        "INSERT INTO capture_eventview VALUES(?,?,?,?)",
        [
            (1, "Zone_A", 10, 100),
            (1, "Zone_B", 11, 100),
        ],
    )
    con.executemany(
        "INSERT INTO capture_actions VALUES(?,?,?,?,?)",
        [
            (1, "a100", 100, "Unique actor action", 1000),
            (1, "a200", 200, "Ambiguous actor action", 1001),
        ],
    )
    con.commit()

    # Same capture + same zone + same numeric entity id links event -> entity snapshot.
    event_matches = entity_identity_matches(
        con, 1, "capture_events", key(zone_db="Zone_A", seq=1)
    )
    assert len(event_matches) == 1, event_matches
    assert event_matches[0]["target_table"] == "capture_npc_entries", event_matches
    assert event_matches[0]["row_key"] == key(zone_db="Zone_A", entity_id=100), event_matches

    # Same numeric id in a different zone is not linked from this event.
    assert not any(
        m["row_key"] == key(zone_db="Zone_B", entity_id=100) for m in event_matches
    ), event_matches

    # EventView obeys the same exact-zone identity rule.
    ev_matches = entity_identity_matches(
        con, 1, "capture_eventview", key(zone_db="Zone_A", seq=10)
    )
    assert len(ev_matches) == 1, ev_matches
    assert ev_matches[0]["row_key"] == key(zone_db="Zone_A", entity_id=100), ev_matches

    # Unique actor id links action -> entity snapshot.
    action_matches = entity_identity_matches(
        con, 1, "capture_actions", key(action_key="a100")
    )
    assert len(action_matches) == 1, action_matches
    assert action_matches[0]["row_key"] == key(zone_db="Zone_A", entity_id=100), action_matches

    # The same actor id appearing in multiple captured zones is intentionally ambiguous.
    ambiguous_action = entity_identity_matches(
        con, 1, "capture_actions", key(action_key="a200")
    )
    assert ambiguous_action == [], ambiguous_action

    # Reverse entity expansion remains zone-bounded and includes the uniquely resolvable action.
    reverse = entity_identity_matches(
        con, 1, "capture_npc_entries", key(zone_db="Zone_A", entity_id=100)
    )
    reverse_ids = {(m["target_table"], m["row_key"]) for m in reverse}
    assert ("capture_events", key(zone_db="Zone_A", seq=1)) in reverse_ids, reverse
    assert ("capture_eventview", key(zone_db="Zone_A", seq=10)) in reverse_ids, reverse
    assert ("capture_actions", key(action_key="a100")) in reverse_ids, reverse
    assert ("capture_events", key(zone_db="Zone_B", seq=2)) not in reverse_ids, reverse
    assert ("capture_eventview", key(zone_db="Zone_B", seq=11)) not in reverse_ids, reverse

    # A duplicate display name with a different numeric id never becomes a relationship.
    assert ("capture_npc_entries", key(zone_db="Zone_A", entity_id=300)) not in reverse_ids, reverse

    # Reverse expansion for an entity id present in multiple zones must not attach action evidence.
    reverse_ambiguous = entity_identity_matches(
        con, 1, "capture_npc_entries", key(zone_db="Zone_A", entity_id=200)
    )
    assert not any(m["target_table"] == "capture_actions" for m in reverse_ambiguous), reverse_ambiguous

    con.close()
    print("Capture entity Related Evidence runtime regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
