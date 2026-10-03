from __future__ import annotations

from datetime import date, datetime, time, timezone

from workbench.editors.character.gui import _safe


def test_character_editor_json_safety_for_temporal_fields():
    payload = {
        "character": {
            "lastonline": datetime(2026, 10, 2, 23, 45, 12),
            "created": date(2026, 10, 2),
            "reset_time": time(6, 30, 15),
            "utc_seen": datetime(2026, 10, 3, 6, 45, tzinfo=timezone.utc),
        },
        "binary": b"\x00\x01",
    }

    safe = _safe(payload)

    assert safe["character"]["lastonline"] == "2026-10-02T23:45:12"
    assert safe["character"]["created"] == "2026-10-02"
    assert safe["character"]["reset_time"] == "06:30:15"
    assert safe["character"]["utc_seen"] == "2026-10-03T06:45:00+00:00"
    assert safe["binary"] == {"hex": "0001", "bytes": 2}
