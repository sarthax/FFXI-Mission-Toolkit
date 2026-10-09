"""Raw comparison never joins unrelated sessions, sources or recorded visits."""
import json
from math import dist
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from workbench.runtime.live_client.recording import load_recorded_frames
from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.replay import RecordedTelemetryReplay
from workbench.runtime.live_client.waypoint_library import WaypointLibrary
from workbench.runtime.live_client.waypoint_library_api import create_waypoint_library_router

CAPTURE = Path(__file__).parent / 'fixtures/live_client/ashita_v4_runtime_anonymized.jsonl'
CLIENT = 'ashita-runtime-sample'
ORIGIN = {'origin': 'http://testserver'}


def setup(tmp_path, frames=None):
    replay = load_recorded_frames(CAPTURE, client_id=CLIENT) if frames is None else RecordedTelemetryReplay(CLIENT, frames)
    replay.advance(); registry = ReplayRegistry()
    session = registry.add_recording(replay, label='Runtime source')
    library = WaypointLibrary(tmp_path / 'library.db')
    app = FastAPI(); app.include_router(create_waypoint_library_router(library, registry))
    client = TestClient(app)
    response = client.post('/live-client/waypoints/capture', headers=ORIGIN,
                          params={'client_id': session, 'name': 'Recorded origin'})
    assert response.status_code == 200
    return client, registry, replay, session, library


def relative(client, session, **params):
    return client.get('/live-client/waypoints/relative', params={'client_id': session, **params})


def test_real_runtime_delta_distance_rewind_and_duplicate_identity_isolation(tmp_path):
    client, registry, replay, session, library = setup(tmp_path)
    first = replay.feed.snapshot().position
    assert relative(client, session).json()['waypoints'][0]['distance_raw'] == 0
    last = replay.seek(121).snapshot.position
    response = relative(client, session, observed_at=1120)
    assert response.status_code == 200
    result = response.json(); waypoint, = result['waypoints']
    assert waypoint['distance_raw'] == pytest.approx(dist((first.x, first.y, first.z), (last.x, last.y, last.z)))
    assert waypoint['delta'] == {'x': first.x-last.x, 'y': first.y-last.y, 'z': first.z-last.z}
    assert all(result[field] is False for field in ('instance_verified', 'route_verified', 'coordinate_transform_verified'))
    assert result['units'] == 'raw_unverified'
    assert replay.position == 121
    assert relative(client, session, observed_at=1000).status_code == 409
    other = load_recorded_frames(CAPTURE, client_id=CLIENT); other.advance()
    twin = registry.add_recording(other, label='Same embedded client ID')
    result = relative(client, twin).json()
    assert result['waypoints'] == []
    assert result['excluded'][0]['reason'] == 'different_or_unknown_session'
    replay.restart()
    assert relative(client, session).json()['waypoints'][0]['distance_raw'] == 0
    assert len(library.entries()) == 1


def test_return_zone_visit_is_excluded_even_when_instance_hint_unknown(tmp_path):
    frames = [json.loads(line) for line in CAPTURE.read_text().splitlines()[:3]]
    frames[1]['position']['zone_id'] = 51
    client, registry, replay, session, library = setup(tmp_path, frames)
    assert library.entries()[0]['provenance']['recorded_segment'] == 0
    replay.seek(2)
    assert relative(client, session).json()['excluded'][0]['reason'] == 'different_zone'
    replay.seek(3)
    result = relative(client, session).json()
    assert result['waypoints'] == []
    assert result['excluded'][0]['reason'] == 'different_recorded_visit'
    replay.restart()
    assert len(relative(client, session).json()['waypoints']) == 1


@pytest.mark.parametrize('field,value,reason', [
    ('session_generation', None, 'recording_generation_unknown'),
    ('session_generation', '', 'recording_generation_unknown'),
    ('session_generation', 'another-recording', 'different_recording_generation'),
    ('adapter', 'different-api', 'different_or_unknown_source'),
    ('client_id', 'other-client', 'different_or_unknown_source'),
    ('reported_client_version', 'another-build', 'different_or_unknown_source'),
    ('instance_hint', 'other-instance', 'different_instance_hint'),
    ('recorded_segment', None, 'recorded_visit_unknown'),
])
def test_imported_incompatible_or_legacy_provenance_is_not_projected(tmp_path, field, value, reason):
    client, registry, replay, session, library = setup(tmp_path)
    doc = library.export_document(); entry = doc['waypoints'][0]
    entry['provenance'][field] = value
    library.delete(library.entries()[0]['id']); library.add_document(doc)
    result = relative(client, session).json()
    assert result['waypoints'] == []
    assert result['excluded'][0]['reason'] == reason
    assert replay.position == 1


def test_identical_replacement_excludes_saved_waypoints_and_allows_new_capture(tmp_path):
    client, registry, replay, session, library = setup(tmp_path)
    old_generation = library.entries()[0]['provenance']['session_generation']
    exported = library.export_document()
    library.delete(library.entries()[0]['id'])
    library.add_document(exported)
    assert relative(client, session).json()['waypoints'][0]['distance_raw'] == 0
    replacement = load_recorded_frames(CAPTURE, client_id=CLIENT)
    replacement.advance()
    registry.add_recording(replacement, label='Identical replacement', replace_session=session)
    result = relative(client, session).json()
    assert result['waypoints'] == []
    assert result['excluded'][0]['reason'] == 'different_recording_generation'
    response = client.post('/live-client/waypoints/capture', headers=ORIGIN,
                           params={'client_id': session, 'name': 'New recording origin'})
    assert response.status_code == 200
    entries = library.entries()
    assert len(entries) == 2
    new_entry = next(entry for entry in entries if entry['name'] == 'New recording origin')
    assert new_entry['provenance']['session_generation'] != old_generation
    result = relative(client, session).json()
    assert [row['name'] for row in result['waypoints']] == ['New recording origin']
    replacement.seek(121)
    assert len(relative(client, session).json()['waypoints']) == 1
    replacement.restart()
    assert relative(client, session).json()['waypoints'][0]['distance_raw'] == 0


def test_extreme_finite_coordinates_do_not_return_infinite_json_differences(tmp_path):
    frames = [json.loads(CAPTURE.read_text().splitlines()[0])]
    frames[0]['position']['x'] = -1e308
    client, registry, replay, session, library = setup(tmp_path, frames)
    doc = library.export_document(); doc['waypoints'][0]['position']['x'] = 1e308
    library.delete(library.entries()[0]['id']); library.add_document(doc)
    response = relative(client, session)
    assert response.status_code == 200
    assert response.json()['waypoints'] == []
    assert response.json()['excluded'][0]['reason'] == 'difference_out_of_numeric_range'


def test_unknown_and_unobserved_session_errors(tmp_path):
    client, registry, replay, session, library = setup(tmp_path)
    assert relative(client, 'missing').status_code == 404
    registry.add(CLIENT, load_recorded_frames(CAPTURE, client_id=CLIENT))
    assert relative(client, CLIENT).status_code == 409
    assert client.post('/live-client/waypoints/relative').status_code == 405


def test_cursor_change_during_context_capture_does_not_mix_visits(tmp_path, monkeypatch):
    client, registry, replay, session, library = setup(tmp_path)
    original = replay.path_points
    def changed(**kwargs):
        points = original(**kwargs)
        replay.seek(2)
        return points
    monkeypatch.setattr(replay, 'path_points', changed)
    response = relative(client, session)
    assert response.status_code == 422
    assert 'observation changed' in response.json()['detail']
    replay.restart()
    response = client.post('/live-client/waypoints/capture', headers=ORIGIN,
                           params={'client_id': session, 'name': 'Racing capture'})
    assert response.status_code == 422
    assert len(library.entries()) == 1
