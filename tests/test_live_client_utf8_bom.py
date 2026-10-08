"""Windows PowerShell 5.1 UTF-8 BOM compatibility in replay import."""
import json
from pathlib import Path

from workbench.runtime.live_client.inspection import inspect_recording
from workbench.runtime.live_client.recording import load_recorded_frames


def test_windows_bom_recording_import(tmp_path: Path):
    frames = []
    for timestamp in (1, 2):
        frames.append({"schema_version": 1, "client_id": "test-client-01",
            "client_version": "offline-test", "character": "TestCharacter",
            "adapter": "fixture", "observed_at": timestamp,
            "position": {"zone_id": 100, "x": float(timestamp), "y": 0.0,
                         "z": 200.0, "heading": 64.0}, "entities": []})
    path = tmp_path / "test_walk.jsonl"
    text = "".join(json.dumps(frame) + "\n" for frame in frames)
    path.write_bytes(text.encode("utf-8-sig"))
    summary = inspect_recording(str(path))
    assert summary["client_id"] == "test-client-01"
    assert summary["frames"] == 2
    replay = load_recorded_frames(path, client_id="test-client-01")
    assert replay.remaining == 2
    assert replay.advance().snapshot.position.x == 1.0
