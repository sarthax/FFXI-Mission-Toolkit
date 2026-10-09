"""Persistent observation library workflows with strict, atomic imports."""
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from workbench.runtime.live_client.recording import load_recorded_frames
from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.waypoint_library import WaypointLibrary
from workbench.runtime.live_client.waypoint_library_api import create_waypoint_library_router
from workbench.runtime.live_client.waypoints import parse_waypoints

CAPTURE = Path(__file__).parent / 'fixtures/live_client/ashita_v4_runtime_anonymized.jsonl'
ORIGIN = {'origin': 'http://testserver'}


def setup(tmp_path, capacity=1000):
    library = WaypointLibrary(tmp_path / 'library.db', max_waypoints=capacity)
    replay = load_recorded_frames(CAPTURE, client_id='ashita-runtime-sample')
    replay.advance()
    registry = ReplayRegistry()
    session = registry.add_recording(replay, label='Runtime capture')
    app = FastAPI(); app.include_router(create_waypoint_library_router(library, registry))
    return TestClient(app), library, replay, session


def imported(name='Imported stairs', zone=50):
    return {'schema_version': 1, 'kind': 'live_client_waypoints', 'waypoints': [
        {'name': name, 'source': 'import',
         'position': {'zone_id': zone, 'x': 1, 'y': 2, 'z': -6, 'heading': 4}}]}


def upload(client, document):
    return client.post('/live-client/waypoints/import', headers=ORIGIN,
        files={'waypoints': ('waypoints.json', json.dumps(document), 'application/json')})


def test_capture_persistence_search_rename_delete_and_portable_roundtrip(tmp_path):
    client, library, replay, session = setup(tmp_path)
    assert client.get('/live-client/waypoints').json() == {'waypoints': []}
    assert not library.path.exists()
    response = client.post('/live-client/waypoints/capture', headers=ORIGIN,
                          params={'client_id': session, 'name': 'Runtime stairs'})
    assert response.status_code == 200
    row, = response.json()['added']
    assert row['provenance']['client_id'] == 'ashita-runtime-sample'
    assert row['provenance']['session_id'] == session
    assert row['provenance']['version_verified'] is False
    assert row['position']['zone_id'] == 50
    assert replay.position == 1
    assert WaypointLibrary(library.path).entries() == [row]
    assert client.get('/live-client/waypoints', params={'search': 'STAIRS', 'zone_id': 50}).json()['waypoints'] == [row]
    assert client.get('/live-client/waypoints', params={'zone_id': 51}).json()['waypoints'] == []
    assert client.post('/live-client/waypoints/'+row['id']+'/rename', headers=ORIGIN,
                       params={'name': 'Renamed landing'}).status_code == 200
    doc = client.get('/live-client/waypoints/export').json()
    point, = parse_waypoints(doc)
    assert point.name == 'Renamed landing'
    assert doc['waypoints'][0]['provenance'] == row['provenance']
    other = WaypointLibrary(tmp_path / 'other.db'); other.add_document(doc)
    assert other.export_document() == doc
    assert client.delete('/live-client/waypoints/'+row['id'], headers=ORIGIN).status_code == 200
    assert library.entries() == []
    assert replay.position == 1


def test_target_capture_retains_unknown_server_id_and_raw_coordinates(tmp_path):
    client, library, replay, session = setup(tmp_path)
    frames = [json.loads(line) for line in CAPTURE.read_text().splitlines()]
    index = next(i for i, frame in enumerate(frames, 1) if frame['entities'])
    frame = replay.seek(index); entity = frame.entities[0]
    response = client.post('/live-client/waypoints/capture', headers=ORIGIN, params={
        'client_id': session, 'name': 'Target stairs', 'entity_index': entity.client_index})
    assert response.status_code == 200
    row, = library.entries()
    assert row['observation']['server_entity_id'] is None
    assert row['observation']['client_index'] == entity.client_index
    point, = parse_waypoints(library.export_document())
    assert point.position == entity.position
    assert replay.position == index
    assert client.post('/live-client/waypoints/capture', headers=ORIGIN, params={
        'client_id': session, 'name': 'Missing', 'entity_index': 65535}).status_code == 404
    assert len(library.entries()) == 1


@pytest.mark.parametrize('bad', [True, '3', float('nan'), float('inf'), 10**400])
def test_invalid_import_is_atomic_and_preserves_existing_entries(tmp_path, bad):
    client, library, replay, session = setup(tmp_path)
    assert upload(client, imported()).status_code == 200
    before = library.entries()
    document = imported('Valid prefix')
    invalid = imported('Invalid suffix')['waypoints'][0]; invalid['position']['x'] = bad
    document['waypoints'].append(invalid)
    assert upload(client, document).status_code == 422
    assert library.entries() == before


def test_import_does_not_promote_claims_or_merge_distinct_named_points(tmp_path):
    client, library, replay, session = setup(tmp_path)
    document = imported()
    document['provenance'] = {'version_verified': True, 'coordinates': 'calibrated',
                              'instance_hint': 'Instance A', 'client_id': 'external'}
    assert upload(client, document).status_code == 200
    assert upload(client, document).status_code == 200
    rows = library.entries()
    assert len(rows) == 2 and rows[0]['id'] != rows[1]['id']
    assert rows[0]['provenance']['version_verified'] is False
    assert rows[0]['provenance']['coordinates'] == 'raw'
    assert rows[0]['provenance']['instance_hint'] == 'Instance A'


def test_missing_origins_and_cross_origin_mutations_are_denied(tmp_path):
    client, library, replay, session = setup(tmp_path)
    for headers in ({}, {'origin': 'https://other.example'}):
        assert client.post('/live-client/waypoints/capture', headers=headers,
            params={'client_id': session, 'name': 'Here'}).status_code == 403
        assert client.post('/live-client/waypoints/import', headers=headers,
            files={'waypoints': ('points.json', '{}')}).status_code == 403
        assert client.post('/live-client/waypoints/missing/rename', headers=headers,
            params={'name': 'Rename'}).status_code == 403
        assert client.delete('/live-client/waypoints/missing', headers=headers).status_code == 403
    assert not library.path.exists()


def test_capacity_and_invalid_names_preserve_library(tmp_path):
    client, library, replay, session = setup(tmp_path, capacity=1)
    assert upload(client, imported()).status_code == 200
    before = library.entries()
    assert upload(client, imported('Overflow')).status_code == 422
    assert library.entries() == before
    for name in ('', ' ', 'a'*201):
        assert client.post('/live-client/waypoints/'+before[0]['id']+'/rename', headers=ORIGIN,
            params={'name': name}).status_code == 422
    assert library.entries() == before
    assert upload(client, {'schema_version': 1, 'kind': 'live_client_waypoints', 'waypoints': []}).status_code == 200


def test_storage_error_preserves_existing_file_and_import_bounds(tmp_path):
    client, library, replay, session = setup(tmp_path)
    library.path.write_bytes(b'corrupt database retained')
    assert client.get('/live-client/waypoints').status_code == 503
    assert library.path.read_bytes() == b'corrupt database retained'
    assert client.post('/live-client/waypoints/import', headers=ORIGIN,
        files={'waypoints': ('points.json', b'x'*(1024*1024+1))}).status_code == 413
    assert client.post('/live-client/waypoints/import', headers=ORIGIN,
        files={'waypoints': ('points.json', b'not JSON')}).status_code == 422


def test_aggregate_library_size_preserves_portable_export_and_existing_data(tmp_path, monkeypatch):
    from workbench.runtime.live_client import waypoint_library
    monkeypatch.setattr(waypoint_library, 'MAX_DOCUMENT_BYTES', 600)
    library = WaypointLibrary(tmp_path / 'library.db')
    library.add_document(imported('One'))
    before = library.entries()
    with pytest.raises(ValueError, match='portable document size'):
        library.add_document(imported('Two'))
    assert library.entries() == before
