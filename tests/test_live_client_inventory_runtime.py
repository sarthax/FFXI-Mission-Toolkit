"""Operator-supplied bounded inventory observations, not a supported-build claim."""
from pathlib import Path

import pytest

from workbench.runtime.live_client.recording import load_recorded_frames
from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.runtime_report import recording_report
from workbench.runtime.live_client.viewer import viewer_projection

FIXTURES = Path(__file__).parent / 'fixtures/live_client'


@pytest.mark.parametrize('label,frames,zone,total,distinct', [
    ('a', 30, 235, 613, 21), ('b', 24, 107, 422, 20),
])
def test_runtime_inventory_preserves_observations_and_unknown_diagnostics(label, frames, zone, total, distinct):
    path = FIXTURES / f'ashita_v4_inventory_runtime_{label}_anonymized.jsonl'
    report = recording_report(path)
    recording = report['recording']
    assert recording['frames'] == frames
    assert recording['duration_seconds'] == frames-1
    assert recording['context_transitions'] == []
    assert recording['zone_frame_counts'] == {str(zone): frames}
    assert recording['distinct_entity_observations'] == distinct
    summary = recording['entity_observation_summary']
    assert summary['scope_frame_counts'] == {'bounded_loaded_entities': frames}
    assert summary['total_observations'] == summary['observations_with_reported_server_id'] == total
    assert summary['truncated_frames'] == summary['observations_without_reported_server_id'] == 0
    assert report['validation']['build_verified'] is False
    assert summary['server_identity_verified'] is False
    replay = load_recorded_frames(path, client_id=f'ashita-inventory-runtime-{label}')
    seen = set()
    for _ in range(frames):
        frame = replay.advance()
        projection = viewer_projection(frame, zone_id=zone, client_id=frame.snapshot.client_id)
        assert len(projection['entities']) == len(frame.entities)
        assert not viewer_projection(frame, zone_id=zone+1, client_id=frame.snapshot.client_id)['visible']
        for entity in frame.entities:
            assert entity.server_entity_id and entity.position.zone_id == zone
            assert entity.kind.value == 'unknown'
            assert entity.raw_status is entity.raw_entity_type is entity.raw_spawn_flags is None
            assert entity.target_roles == () and entity.instance_hint is None
            seen.add((entity.client_index, entity.server_entity_id))
    assert len(seen) == distinct


def test_supplied_inventory_recordings_replay_independently():
    registry = ReplayRegistry()
    for label in ('a', 'b'):
        client = f'ashita-inventory-runtime-{label}'
        replay = load_recorded_frames(FIXTURES / f'ashita_v4_inventory_runtime_{label}_anonymized.jsonl', client_id=client)
        registry.add(client, replay)
    registry.advance('ashita-inventory-runtime-a')
    assert registry.frame('ashita-inventory-runtime-b') is None
    registry.advance('ashita-inventory-runtime-b')
    assert registry.frame('ashita-inventory-runtime-a').snapshot.position.zone_id == 235
    assert registry.frame('ashita-inventory-runtime-b').snapshot.position.zone_id == 107
    registry.remove('ashita-inventory-runtime-a')
    assert registry.frame('ashita-inventory-runtime-b').snapshot.position.zone_id == 107
