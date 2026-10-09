"""Raw capture downloads preserve observations and never advance a source."""
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.runtime.live_client.file_bridge import FileTelemetryBridge
from workbench.runtime.live_client.recording import load_recorded_frames
from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.registry_api import create_registry_router
from workbench.runtime.live_client.waypoints import parse_path, parse_waypoints


CAPTURE = Path(__file__).parent / 'fixtures/live_client/ashita_v4_runtime_anonymized.jsonl'
CLIENT = 'ashita-runtime-sample'


def setup():
    registry = ReplayRegistry()
    replay = load_recorded_frames(CAPTURE, client_id=CLIENT)
    registry.add(CLIENT, replay)
    app = FastAPI()
    app.include_router(create_registry_router(registry))
    return TestClient(app), registry, replay


def test_player_target_and_full_path_exports_from_runtime_capture():
    client, registry, replay = setup()
    replay.seek(121)
    response = client.get('/live-client/replay/path', params={'client_id': CLIENT})
    assert response.status_code == 200
    assert response.headers['content-disposition'] == 'attachment; filename="observed-path.json"'
    assert response.headers['cache-control'] == 'no-store'
    document = response.json()
    samples = parse_path(document)
    assert len(samples) == 121
    assert samples[-1].position == registry.frame(CLIENT).snapshot.position
    assert {sample.client_id for sample in samples} == {CLIENT}
    assert document['provenance']['version_verified'] is False
    assert document['provenance']['coordinates'] == 'raw'
    assert replay.position == 121

    replay.seek(10)
    assert len(client.get('/live-client/replay/path', params={'client_id': CLIENT}).json()['samples']) == 10
    response = client.get('/live-client/replay/waypoint', params={'client_id': CLIENT, 'name': 'Stairs'})
    waypoint, = parse_waypoints(response.json())
    assert waypoint.name == 'Stairs'
    assert waypoint.position == registry.frame(CLIENT).snapshot.position
    assert waypoint.source == 'ashita-v4-api-experimental'
    assert replay.position == 10

    frames = [json.loads(line) for line in CAPTURE.read_text().splitlines()]
    index = next(i for i, frame in enumerate(frames, 1) if frame['entities'])
    frame = replay.seek(index)
    target = frame.entities[0]
    response = client.get('/live-client/replay/waypoint', params={
        'client_id': CLIENT, 'name': 'Observed target', 'entity_index': target.client_index})
    assert response.status_code == 200
    waypoint, = parse_waypoints(response.json())
    assert waypoint.position == target.position
    assert response.json()['observation']['server_entity_id'] is None
    assert response.json()['provenance']['client_id'] == CLIENT
    assert replay.position == index


def test_exports_reject_unobserved_missing_entities_invalid_names_and_file_feed_path():
    client, registry, replay = setup()
    for kind in ('waypoint', 'path'):
        assert client.get('/live-client/replay/'+kind, params={'client_id': CLIENT, 'name': 'Here'}).status_code == 409
        assert client.get('/live-client/replay/'+kind, params={'client_id': 'missing', 'name': 'Here'}).status_code == 404
        assert client.post('/live-client/replay/'+kind).status_code == 405
    replay.advance()
    for name in ('', ' ', 'a'*201):
        assert client.get('/live-client/replay/waypoint', params={'client_id': CLIENT, 'name': name}).status_code == 422
    assert client.get('/live-client/replay/waypoint', params={
        'client_id': CLIENT, 'name': 'Unknown', 'entity_index': 65535}).status_code == 404
    bridge = FileTelemetryBridge(CAPTURE, CLIENT)
    registry.remove(CLIENT)
    registry.add_feed(CLIENT, bridge)
    bridge.poll()
    assert client.get('/live-client/replay/path', params={'client_id': CLIENT}).status_code == 404
    assert client.get('/live-client/replay/waypoint', params={'client_id': CLIENT, 'name': 'Feed'}).status_code == 200
    assert replay.position == 1


def test_path_export_preserves_zone_and_instance_boundaries():
    client, registry, replay = setup()
    frames = [json.loads(line) for line in CAPTURE.read_text().splitlines()[:3]]
    frames[1]['position']['zone_id'] = 51
    frames[1]['instance_hint'] = 'visit-b'
    from workbench.runtime.live_client.replay import RecordedTelemetryReplay
    replay = RecordedTelemetryReplay(CLIENT, frames)
    registry.remove(CLIENT); registry.add(CLIENT, replay)
    replay.seek(3)
    document = client.get('/live-client/replay/path', params={'client_id': CLIENT}).json()
    assert [sample['position']['zone_id'] for sample in document['samples']] == [50, 51, 50]
    assert [sample['instance_hint'] for sample in document['samples']] == [None, 'visit-b', None]
