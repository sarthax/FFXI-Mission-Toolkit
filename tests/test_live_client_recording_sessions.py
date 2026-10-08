"""Recording lifecycles preserve telemetry identity and last-good replay state."""
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.runtime.live_client.file_bridge import FileTelemetryBridge
from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.registry_api import create_registry_router
from workbench.runtime.live_client.setup_api import create_recording_upload_router


def payload(timestamp, x=1):
    return {"schema_version": 1, "client_id": "same-client", "client_version": "fixture",
            "character": "Hero", "adapter": "offline", "observed_at": timestamp,
            "position": {"zone_id": 100, "x": x, "y": 2, "z": 3, "heading": 4},
            "entities": []}


def browser(tmp_path):
    registry = ReplayRegistry()
    app = FastAPI()
    app.include_router(create_registry_router(registry))
    app.include_router(create_recording_upload_router(tmp_path / "recordings", registry))
    return TestClient(app), registry


def upload(client, frames, **params):
    data = ''.join(json.dumps(frame) + '\n' for frame in frames)
    return client.post('/live-client/upload-recording', params={"open_session": True, **params},
                       files={"recording": ("walk.jsonl", data, "application/x-ndjson")},
                       headers={"origin": "http://testserver"})


def test_same_identity_independent_seek_replace_and_unload(tmp_path):
    client, registry = browser(tmp_path)
    a = upload(client, [payload(1), payload(3, 9)]).json()['session_id']
    b = upload(client, [payload(10, 20)]).json()['session_id']
    assert a != b
    rows = client.get('/live-client/replay/clients').json()['clients']
    assert {row['recorded_client_id'] for row in rows} == {'same-client'}
    assert next(row for row in rows if row['client_id'] == a)['next_frame_delay'] == 2
    endpoint = '/live-client/replay/seek'
    args = {'client_id': a, 'position': 2}
    assert client.post(endpoint, params=args).status_code == 403
    assert client.post(endpoint, params=args, headers={'origin': 'http://evil'}).status_code == 403
    assert client.post(endpoint, params=args, headers={'origin': 'http://testserver'}).status_code == 200
    assert registry.frame(a).snapshot.position.x == 9
    assert registry.frame(b).snapshot.position.x == 20
    assert registry._clients[a].next_frame_delay is None
    projection = client.get('/live-client/replay/projection', params={'client_id': a, 'zone_id': 100})
    assert projection.status_code == 200, projection.text
    assert projection.json()['player']['position']['x'] == 9
    assert upload(client, [payload(1, 33)], replace_session=a).json()['session_id'] == a
    assert registry.frame(a).snapshot.position.x == 33
    assert len(registry.client_ids()) == 2
    assert client.post('/live-client/replay/unload', params={'client_id': a}).status_code == 403
    assert client.post('/live-client/replay/unload', params={'client_id': a},
                       headers={'origin': 'http://testserver'}).status_code == 200
    assert registry.client_ids() == (b,)


def test_failed_replacement_and_seek_leave_last_good_session(tmp_path):
    client, registry = browser(tmp_path)
    a = upload(client, [payload(1), payload(3)]).json()['session_id']
    stored = set((tmp_path / 'recordings').iterdir())
    invalid = payload(1); invalid['position']['x'] = 'invalid'
    assert upload(client, [invalid], replace_session=a).status_code == 422
    assert set((tmp_path / 'recordings').iterdir()) == stored
    assert registry.frame(a).snapshot.observed_at == 1
    assert upload(client, [payload(1)], replace_session='missing').status_code == 404
    for position in (0, 3, 'invalid'):
        assert client.post('/live-client/replay/seek', params={'client_id': a, 'position': position},
                           headers={'origin': 'http://testserver'}).status_code == 422
    assert registry._clients[a].position == 1
    feed_path = tmp_path / 'feed.jsonl'; feed_path.write_text('')
    registry.add_feed('feed', FileTelemetryBridge(feed_path, 'feed'))
    assert upload(client, [payload(1)], replace_session='feed').status_code == 404
    for action in ('advance', 'unload', 'seek'):
        params = {'client_id': 'feed', 'position': 1}
        assert client.post('/live-client/replay/' + action, params=params,
                           headers={'origin': 'http://testserver'}).status_code == 404
    assert 'feed' in registry.client_ids()
