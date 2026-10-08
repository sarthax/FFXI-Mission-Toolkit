"""Displayed-frame guards reject seek, slot reuse and identical replacement."""
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.runtime.live_client.recording import load_recorded_frames
from workbench.runtime.live_client.replay import RecordedTelemetryReplay
from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.registry_api import create_registry_router
from workbench.runtime.live_client.waypoint_library import WaypointLibrary
from workbench.runtime.live_client.waypoint_library_api import create_waypoint_library_router
from workbench.runtime.live_client.observation_guard import observation_token
from workbench.runtime.live_client.telemetry import decode_frame
from workbench.runtime.live_client.file_bridge import FileTelemetryBridge

CAPTURE = Path(__file__).parent / 'fixtures/live_client/ashita_v4_runtime_anonymized.jsonl'
ORIGIN = {'origin': 'http://testserver'}


def setup(tmp_path):
    replay = load_recorded_frames(CAPTURE, client_id='ashita-runtime-sample'); replay.advance()
    registry = ReplayRegistry(); session = registry.add_recording(replay, label='Capture')
    library = WaypointLibrary(tmp_path / 'library.db')
    app = FastAPI(); app.include_router(create_registry_router(registry))
    app.include_router(create_waypoint_library_router(library, registry))
    return TestClient(app), registry, session, replay, library


def projection(client, session):
    response = client.get('/live-client/replay/projection', params={'client_id': session, 'zone_id': 50})
    assert response.status_code == 200
    return response.json()['observation_token']


def capture(client, session, token):
    return client.post('/live-client/waypoints/capture', headers=ORIGIN,
                       params={'client_id': session, 'name': 'Shown position', 'observation_token': token})


def test_seek_rejects_stale_player_download_path_and_library_capture(tmp_path):
    client, registry, session, replay, library = setup(tmp_path)
    token = projection(client, session)
    assert projection(client, session) == token
    replay.seek(2)
    for endpoint in ('waypoint', 'path'):
        response = client.get('/live-client/replay/'+endpoint,
                              params={'client_id': session, 'name': 'Shown', 'observation_token': token})
        assert response.status_code == 409
    assert capture(client, session, token).status_code == 409
    assert library.entries() == []
    assert not library.path.exists()
    fresh = projection(client, session)
    assert fresh != token
    assert capture(client, session, fresh).status_code == 200
    assert library.entries()[0]['provenance']['observed_at'] == 1001


def test_identical_replacement_invalidates_generation_and_cross_session_token(tmp_path):
    client, registry, session, replay, library = setup(tmp_path)
    token = projection(client, session)
    twin = load_recorded_frames(CAPTURE, client_id='ashita-runtime-sample'); twin.advance()
    other = registry.add_recording(twin, label='Same client')
    assert capture(client, other, token).status_code == 409
    replacement = load_recorded_frames(CAPTURE, client_id='ashita-runtime-sample'); replacement.advance()
    registry.add_recording(replacement, label='Replacement', replace_session=session)
    assert capture(client, session, token).status_code == 409
    assert projection(client, session) != token
    assert library.entries() == []


def test_entity_slot_reuse_at_same_timestamp_changes_token(tmp_path):
    client, registry, session, replay, library = setup(tmp_path)
    payload = json.loads(CAPTURE.read_text().splitlines()[0])
    payload['entities'] = [{'client_index': 42, 'server_entity_id': 123, 'name': 'Old',
                            'position': {'zone_id': 50, 'x': 1, 'y': 2, 'z': 3}}]
    candidate = RecordedTelemetryReplay('ashita-runtime-sample', [payload]); candidate.advance()
    registry.add_recording(candidate, label='Entity', replace_session=session)
    token = projection(client, session)
    changed = {**payload, 'entities': [{**payload['entities'][0], 'name': 'New', 'server_entity_id': 456}]}
    candidate.feed._latest = decode_frame(changed)
    response = client.get('/live-client/replay/waypoint', params={'client_id': session, 'name': 'Old target',
                           'entity_index': 42, 'observation_token': token})
    assert response.status_code == 409
    assert library.entries() == []


def test_generation_change_during_token_hash_is_rejected(tmp_path, monkeypatch):
    import pytest
    from workbench.runtime.live_client import observation_guard
    client, registry, session, replay, library = setup(tmp_path)
    original = observation_guard.json.dumps
    def replaced(*args, **kwargs):
        result = original(*args, **kwargs)
        registry.add_recording(replay, label='Changed generation', replace_session=session)
        return result
    monkeypatch.setattr(observation_guard.json, 'dumps', replaced)
    with pytest.raises(ValueError, match='observation changed'):
        observation_token(registry, session, registry.frame(session))


def test_feed_poll_invalidates_displayed_capture_token(tmp_path):
    client, registry, session, replay, library = setup(tmp_path)
    lines = CAPTURE.read_text().splitlines()
    path = tmp_path / 'live.jsonl'; path.write_text(lines[0]+'\n')
    bridge = FileTelemetryBridge(path, 'ashita-runtime-sample')
    registry.add_feed('ashita-runtime-sample', bridge); bridge.poll()
    token = projection(client, 'ashita-runtime-sample')
    path.write_text(lines[0]+'\n'+lines[1]+'\n'); bridge.poll()
    assert capture(client, 'ashita-runtime-sample', token).status_code == 409
    assert library.entries() == []
    fresh = projection(client, 'ashita-runtime-sample')
    assert capture(client, 'ashita-runtime-sample', fresh).status_code == 200
    registry.remove('ashita-runtime-sample')
    assert 'ashita-runtime-sample' not in registry._generations
