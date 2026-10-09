"""Portable paths preserve source/instance context and never join discontinuities."""
from dataclasses import replace
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from workbench.runtime.live_client.models import PathSample, Position
from workbench.runtime.live_client.recording import load_recorded_bytes
from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.registry_api import create_registry_router
from workbench.runtime.live_client.spatial import split_path_by_zone
from workbench.runtime.live_client.waypoints import parse_path, path_document
from workbench.runtime.live_client.service import LiveClientSession, ReplayAdapter
from workbench.runtime.live_client.telemetry import decode_frame

CAPTURE = Path(__file__).parent / 'fixtures/live_client/ashita_v4_runtime_anonymized.jsonl'


def test_export_parse_roundtrip_keeps_visit_source_scope_heading_and_generation():
    frames = [json.loads(line) for line in CAPTURE.read_text().splitlines()[:5]]
    frames[1]['instance_hint'] = 'A'
    frames[2]['adapter'] = 'other-adapter'
    frames[3]['client_version'] = 'other-version'
    frames[4].update(observation_scope='bounded_loaded_entities', entities_truncated=True)
    data = ''.join(json.dumps(frame)+'\n' for frame in frames).encode()
    replay = load_recorded_bytes(data, client_id=frames[0]['client_id']); replay.seek(5)
    registry = ReplayRegistry(); session = registry.add_recording(replay, label='Path')
    app = FastAPI(); app.include_router(create_registry_router(registry)); client = TestClient(app)
    document = client.get('/live-client/replay/path', params={'client_id': session}).json()
    samples = parse_path(document)
    assert [sample.recorded_segment for sample in samples] == [0, 1, 2, 3, 4]
    assert [point['segment'] for point in replay.path_points()] == [0, 1, 2, 3, 4]
    assert samples[1].instance_hint == 'A'
    assert samples[2].adapter == 'other-adapter'
    assert samples[3].client_version == 'other-version'
    assert samples[4].observation_scope == 'bounded_loaded_entities'
    assert samples[4].entities_truncated is True
    assert all(sample.session_id == session for sample in samples)
    assert len({sample.session_generation for sample in samples}) == 1
    assert samples[-1].position.heading == frames[-1]['position']['heading']
    assert path_document(samples)['samples'] == document['samples']
    assert [len(segment) for segment in split_path_by_zone(samples)] == [1, 1, 1, 1, 1]
    replacement = load_recorded_bytes(data, client_id=frames[0]['client_id']); replacement.seek(5)
    registry.add_recording(replacement, label='Replacement', replace_session=session)
    newer = parse_path(client.get('/live-client/replay/path', params={'client_id': session}).json())
    assert newer[0].session_generation != samples[0].session_generation
    assert replay.position == 5


@pytest.mark.parametrize('patch', [
    {'instance_hint': 'other-instance'}, {'adapter': 'other-source'}, {'client_version': 'v2'},
    {'session_id': 'other-session'}, {'session_generation': 'replacement'}, {'recorded_segment': 1},
    {'observed_at': 1}, {'observed_at': 0},
])
def test_same_zone_paths_do_not_bridge_context_or_time_changes(patch):
    first = PathSample(1, Position(50, 1, 2, 3), 'client', instance_hint='A',
                       adapter='source', client_version='v1', session_id='session',
                       session_generation='generation', recorded_segment=0)
    second = replace(first, observed_at=2, **{k:v for k,v in patch.items() if k != 'observed_at'})
    if 'observed_at' in patch:
        second = replace(second, observed_at=patch['observed_at'])
    assert [len(segment) for segment in split_path_by_zone([first, second])] == [1, 1]


def test_legacy_defaults_and_session_capture_keep_known_context():
    row = {'observed_at': 1, 'client_id': 'client', 'position': {'zone_id': 50, 'x': 1, 'y': 2, 'z': 3}}
    sample, = parse_path({'schema_version': 1, 'kind': 'live_client_path', 'samples': [row]})
    assert sample.instance_hint is None and sample.adapter is None
    assert sample.observation_scope == 'unspecified'
    payload = json.loads(CAPTURE.read_text().splitlines()[0]); payload['instance_hint'] = 'A'
    snapshot = decode_frame(payload).snapshot
    captured = LiveClientSession(ReplayAdapter([snapshot])).record_sample()
    assert (captured.instance_hint, captured.adapter, captured.client_version) == ('A', snapshot.adapter, snapshot.version)
    assert captured.session_generation is None


@pytest.mark.parametrize('patch', [{'observed_at': True}, {'instance_hint': 123},
    {'adapter': ''}, {'session_generation': ' '}, {'recorded_segment': True},
    {'recorded_segment': -1}, {'observation_scope': 'invented'}, {'entities_truncated': 1}])
def test_malformed_portable_context_is_rejected(patch):
    sample = PathSample(1, Position(50, 1, 2, 3), 'client')
    document = path_document([sample]); document['samples'][0].update(patch)
    with pytest.raises(ValueError):
        parse_path(document)
