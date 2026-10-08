"""Evidence summaries distinguish supplied files from verified running clients."""
import hashlib
import json
from pathlib import Path

import pytest

from workbench.runtime.live_client.runtime_report import binary_fingerprint, bounded_bytes, main, recording_report
from workbench.runtime.live_client.recording import load_recorded_bytes

CAPTURE = Path(__file__).parent / 'fixtures/live_client/ashita_v4_runtime_anonymized.jsonl'


def test_runtime_recording_summary_and_claim_boundaries():
    report = recording_report(CAPTURE, game_version='30191204_1')
    capture = report['recording']
    assert capture['sha256'] == hashlib.sha256(CAPTURE.read_bytes()).hexdigest()
    assert capture['frames'] == 121 and capture['duration_seconds'] == 120
    assert capture['zone_frame_counts'] == {'50': 121}
    assert capture['frame_intervals'] == [{'seconds': 1, 'count': 120}]
    assert capture['frames_with_entities'] == 35
    assert capture['distinct_entity_observations'] == 8
    summary = capture['entity_observation_summary']
    assert summary['scope_frame_counts'] == {'unspecified': 121}
    assert summary['truncated_frames'] == 0
    assert summary['total_observations'] == 35
    assert summary['observations_with_reported_server_id'] == 0
    assert summary['complete_inventory_verified'] is False
    assert capture['context_transitions'] == []
    assert capture['raw_axis_ranges_by_zone']['50']['z'] == {'min': -6, 'max': 0}
    assert report['operator_reported_game_version'] == '30191204_1'
    assert report['supplied_binaries'] == []
    assert report['validation']['all_frames_decoded'] is True
    assert all(value is False for key, value in report['validation'].items() if key != 'all_frames_decoded')


def test_context_transitions_and_irregular_sample_intervals(tmp_path):
    frames = [json.loads(line) for line in CAPTURE.read_text().splitlines()[:3]]
    frames[1]['position']['zone_id'] = 51
    frames[1]['instance_hint'] = 'other-instance'
    frames[2]['observed_at'] += 2
    path = tmp_path / 'transitions.jsonl'
    path.write_text(''.join(json.dumps(f)+'\n' for f in frames))
    report = recording_report(path)['recording']
    assert report['zone_frame_counts'] == {'50': 2, '51': 1}
    assert report['frame_intervals'] == [{'seconds': 1, 'count': 1}, {'seconds': 3, 'count': 1}]
    assert [t['frame'] for t in report['context_transitions']] == [2, 3]
    assert report['context_transitions'][0]['to_instance'] == 'other-instance'


def test_malformed_recordings_limits_and_invalid_pe_are_rejected(tmp_path):
    path = tmp_path / 'bad.jsonl'; path.write_text('{}\n')
    with pytest.raises(ValueError):
        recording_report(path)
    with pytest.raises(ValueError):
        bounded_bytes(CAPTURE, 10)
    with pytest.raises(ValueError):
        recording_report(CAPTURE, game_version=' ')
    binary = tmp_path / 'fake.dll'; binary.write_bytes(b'not a PE file')
    with pytest.raises(ValueError, match='valid PE'):
        binary_fingerprint(binary)


def test_cli_output_and_existing_report_preservation(tmp_path, capsys):
    output = tmp_path / 'report.json'
    assert main([str(CAPTURE), '--output', str(output)]) == 0
    original = output.read_bytes()
    assert json.loads(original)['recording']['frames'] == 121
    with pytest.raises(SystemExit) as failure:
        main([str(CAPTURE), '--output', str(output)])
    assert failure.value.code == 2
    assert output.read_bytes() == original
    assert main([str(CAPTURE)]) == 0
    assert json.loads(capsys.readouterr().out)['kind'] == 'live_client_runtime_report'


def test_immutable_recording_snapshot_uses_the_same_strict_validation(tmp_path):
    data = CAPTURE.read_bytes()
    replay = load_recorded_bytes(data, client_id='ashita-runtime-sample')
    assert replay.total == 121
    with pytest.raises(ValueError, match='client mismatch'):
        load_recorded_bytes(data, client_id='other')
    with pytest.raises(ValueError, match='byte limit'):
        load_recorded_bytes(data, client_id='ashita-runtime-sample', max_bytes=10)
    with pytest.raises(ValueError, match='must be bytes'):
        load_recorded_bytes('not bytes', client_id='ashita-runtime-sample')


def test_report_hash_and_frames_survive_source_change_after_snapshot(tmp_path, monkeypatch):
    from workbench.runtime.live_client import runtime_report
    path = tmp_path / 'capture.jsonl'; original = CAPTURE.read_bytes(); path.write_bytes(original)
    read = runtime_report.bounded_bytes
    def changing_source(source, limit):
        data = read(source, limit)
        path.write_bytes(b'changed after read\n')
        return data
    monkeypatch.setattr(runtime_report, 'bounded_bytes', changing_source)
    report = runtime_report.recording_report(path)['recording']
    assert report['frames'] == 121
    assert report['sha256'] == hashlib.sha256(original).hexdigest()


def test_inventory_and_legacy_scopes_and_reported_ids_remain_distinct(tmp_path):
    frames = [json.loads(line) for line in CAPTURE.read_text().splitlines()[:3]]
    def entity(index, server_id):
        return {'client_index': index, 'server_entity_id': server_id, 'name': 'Same name',
                'position': {'zone_id': 50, 'x': 1, 'y': 2, 'z': 3}}
    frames[0]['entities'] = [entity(42, 11)]
    frames[1].update(observation_scope='selected_targets', entities=[entity(42, 22)])
    frames[2].update(observation_scope='bounded_loaded_entities', entities_truncated=True,
                     entities=[entity(42, 22), entity(43, None), entity(44, 0)])
    path = tmp_path / 'mixed.jsonl'
    path.write_text(''.join(json.dumps(frame)+'\n' for frame in frames))
    report = recording_report(path)
    assert report['recording']['distinct_entity_observations'] == 4
    summary = report['recording']['entity_observation_summary']
    assert summary['scope_frame_counts'] == {'unspecified': 1, 'selected_targets': 1, 'bounded_loaded_entities': 1}
    assert summary['truncated_frames'] == 1
    assert summary['entity_count_distribution'] == [{'entities': 1, 'frames': 2}, {'entities': 3, 'frames': 1}]
    assert summary['total_observations'] == 5
    assert summary['observations_with_reported_server_id'] == 3
    assert summary['observations_without_reported_server_id'] == 2
    assert all(summary[key] is False for key in ('target_roles_verified', 'complete_inventory_verified', 'server_identity_verified'))
    assert report['validation']['build_verified'] is False
    assert report['validation']['lifecycle_verified'] is False


def test_observation_counts_do_not_merge_contexts_or_sources(tmp_path):
    frames = [json.loads(line) for line in CAPTURE.read_text().splitlines()[:3]]
    for frame in frames:
        frame['entities'] = [{'client_index': 42, 'server_entity_id': 11, 'name': 'Same name',
                              'position': {'zone_id': 50, 'x': 1, 'y': 2, 'z': 3}}]
    frames[1]['instance_hint'] = 'another-instance'
    frames[2]['adapter'] = 'another-source'
    path = tmp_path / 'contexts.jsonl'
    path.write_text(''.join(json.dumps(frame)+'\n' for frame in frames))
    assert recording_report(path)['recording']['distinct_entity_observations'] == 3


def test_zero_and_absent_server_ids_both_remain_unknown(tmp_path):
    frames = [json.loads(line) for line in CAPTURE.read_text().splitlines()[:2]]
    for frame, server_id in zip(frames, (None, 0)):
        frame['entities'] = [{'client_index': 42, 'server_entity_id': server_id, 'name': 'Same name',
                              'position': {'zone_id': 50, 'x': 1, 'y': 2, 'z': 3}}]
    path = tmp_path / 'unknown.jsonl'
    path.write_text(''.join(json.dumps(frame)+'\n' for frame in frames))
    recording = recording_report(path)['recording']
    assert recording['distinct_entity_observations'] == 1
    assert recording['entity_observation_summary']['observations_without_reported_server_id'] == 2
