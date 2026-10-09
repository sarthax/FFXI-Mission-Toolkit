"""Regression evidence from an anonymized, authorized Ashita v4 runtime capture."""
from pathlib import Path

import pytest

from workbench.runtime.live_client.file_bridge import FileTelemetryBridge
from workbench.runtime.live_client.recording import load_recorded_frames


CAPTURE = Path(__file__).parent / 'fixtures/live_client/ashita_v4_runtime_anonymized.jsonl'
CLIENT = 'ashita-runtime-sample'


def test_actual_ashita_recording_replay_feed_and_target_observations():
    replay = load_recorded_frames(CAPTURE, client_id=CLIENT)
    assert replay.total == 121
    first = replay.advance()
    assert first.snapshot.observed_at == 1000
    assert replay.next_frame_delay == 1
    assert replay.seek(121).snapshot.observed_at == 1120
    points = replay.path_points()
    assert len(points) == 121
    assert {p['zone_id'] for p in points} == {50}
    assert {p['segment'] for p in points} == {0}
    assert max(p['y'] for p in points) - min(p['y'] for p in points) > 100
    assert max(p['z'] for p in points) - min(p['z'] for p in points) == pytest.approx(6)
    assert replay.previous().snapshot.observed_at == 1119
    assert replay.restart().snapshot.position == first.snapshot.position
    assert len(replay.path_points()) == 1

    bridge = FileTelemetryBridge(CAPTURE, CLIENT)
    assert bridge.poll() == 100
    assert bridge.poll() == 21
    assert bridge.poll() == 0
    assert bridge.feed.snapshot().position == replay.seek(121).snapshot.position
    assert bridge.feed.version_verified is False
    assert bridge.feed.supports_writes is False

    targets = set()
    headings = []
    replay.restart()
    for i in range(1, 122):
        frame = replay.seek(i)
        headings.append(frame.snapshot.position.heading)
        for entity in frame.entities:
            targets.add((entity.client_index, entity.name))
            assert entity.server_entity_id is None
            assert entity.kind.value == 'unknown'
            assert entity.position.zone_id == 50
    assert len(targets) == 8
    # Preserve SDK heading values; do not silently wrap/reinterpret observations.
    assert min(headings) < 0 and max(headings) > 4
