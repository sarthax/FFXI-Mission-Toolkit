"""Live Client persisted Settings and recording inspection regressions."""
import json
import sqlite3
import tempfile
from pathlib import Path

from workbench.runtime import settings_store
from workbench.runtime.live_client.configuration import effective_replay_configuration
from workbench.runtime.live_client.inspection import inspect_recording


def test_settings_roundtrip():
    con = sqlite3.connect(":memory:")
    settings_store.set_many(con, {
        "live_client_source": "replay", "live_client_replay_file": "recording.jsonl",
        "live_client_replay_client": "hero", "live_client_auto_connect": "1"})
    settings = settings_store.get_all(con)
    effective = effective_replay_configuration(settings, {})
    assert effective["FFXI_LIVE_REPLAY_CLIENT"] == "hero"
    assert effective["FFXI_LIVE_REPLAY_FILE"] == "recording.jsonl"
    assert effective_replay_configuration({**settings, "live_client_auto_connect": "0"}, {}) == {}
    assert effective_replay_configuration(settings, {"FFXI_LIVE_REPLAY_CLIENT": "override",
                                                    "FFXI_LIVE_REPLAY_FILE": "other.jsonl"
                                                    })["FFXI_LIVE_REPLAY_CLIENT"] == "override"
    con.close()


def test_recording_inspection():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "trace.jsonl"
        frame = {"schema_version": 1, "client_id": "hero", "client_version": "fixture",
                 "character": "Hero", "adapter": "fixture", "observed_at": 1,
                 "position": {"zone_id": 100, "x": 0, "y": 0, "z": 0, "heading": 0},
                 "entities": []}
        path.write_text(json.dumps(frame) + "\n", encoding="utf-8")
        assert inspect_recording(str(path))["client_id"] == "hero"
        assert inspect_recording(str(path))["frames"] == 1


def test_host_and_settings_controls():
    root = Path(__file__).resolve().parents[1]
    page = (root / "gui/templates/settings.html").read_text(encoding="utf-8")
    host = (root / "src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    assert 'name="live_client_source"' in page
    assert 'name="live_client_replay_file"' in page
    assert 'name="live_client_replay_client"' in page
    assert 'name="live_client_auto_connect"' in page
    assert "effective_replay_configuration" in host
