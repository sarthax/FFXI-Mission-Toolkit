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


def test_gap_counts_distinguish_cross_zone_from_same_zone(tmp_path):
    frames = [json.loads(line) for line in CAPTURE.read_text().splitlines()[:4]]
    # The declared exporter cadence is one second; retain both source contexts.
    frames[1]['observed_at'] += 2
    frames[2]['observed_at'] += 2
    frames[3]['observed_at'] += 4
    frames[3]['position']['zone_id'] = 51
    path = tmp_path / 'gap-context.jsonl'
    path.write_text(''.join(json.dumps(frame) + '\n' for frame in frames))
    gaps = recording_report(path)['recording']['gap_summary']
    assert gaps['count'] == 2
    assert gaps['same_zone_gap_count'] == 1
    assert gaps['cross_zone_gap_count'] == 1
    assert gaps['observed_excess_interval_seconds'] == 4
    assert gaps['same_zone_excess_interval_seconds'] == 2
    assert gaps['cross_zone_excess_interval_seconds'] == 2
    assert [gap['excess_interval_seconds'] for gap in gaps['gaps']] == [2, 2]
    assert gaps['cause_verified'] is False
    assert gaps['interpolated_frames'] == 0


def test_gap_instance_context_separates_known_changes_from_unknown(tmp_path):
    frames = [json.loads(line) for line in CAPTURE.read_text().splitlines()[:4]]
    for index, frame in enumerate(frames):
        frame['observed_at'] += index * 2
    frames[0]['instance_hint'] = 'instance-a'
    frames[1]['instance_hint'] = 'instance-b'
    frames[2]['instance_hint'] = None
    frames[3]['instance_hint'] = 'instance-c'
    path = tmp_path / 'instance-gaps.jsonl'
    path.write_text(''.join(json.dumps(frame) + '\n' for frame in frames))
    gaps = recording_report(path)['recording']['gap_summary']
    assert gaps['count'] == 3
    assert gaps['known_instance_change_gap_count'] == 1
    assert gaps['unknown_instance_context_gap_count'] == 2
    assert gaps['cause_verified'] is False


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


def packet_file(tmp_path, **changes):
    row = dict(schema_version=1, kind='ashita_packet_observation', profile='event_emote',
               hook_stage='addon_callback_original', client_id='ashita-runtime-sample',
               source_recording=CAPTURE.stem, adapter='ashita-v4-api-experimental',
               client_version='unverified-ashita-v4-api', sequence=1, observed_at=1000,
               dropped_before=0, zone_id=50, opcode=0x1ff, size=4, raw_hex='00000000',
               direction='incoming', is_injected=False, is_blocked=False)
    row.update(changes)
    path = tmp_path / 'packets.jsonl'
    path.write_text(json.dumps(row)+'\n')
    return path


def test_packet_report_preserves_locators_and_unknown_semantics(tmp_path):
    path = packet_file(tmp_path)
    evidence = recording_report(CAPTURE, packet_observations=path)['packet_evidence']
    assert evidence['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert evidence['classification_counts'] == {'exact_label_source_zone_time_candidate': 1}
    candidate, = evidence['candidates']
    assert candidate['telemetry_frame'] == 1 and candidate['packet_line'] == 1
    assert candidate['reported_opcode'] == 0x1ff
    assert candidate['packet_start_offset'] == 0 and candidate['packet_end_offset'] == path.stat().st_size
    assert all(value is False for key, value in evidence.items() if key.endswith('_verified'))
    assert evidence['instance_identity_available'] is False


@pytest.mark.parametrize('change,classification', [
    ({'source_recording': 'different-recording'}, 'source_label_mismatch'),
    ({'client_id': 'other-client'}, 'no_exact_source_zone_time_frame'),
    ({'adapter': 'other-provider'}, 'no_exact_source_zone_time_frame'),
    ({'client_version': 'other-version'}, 'no_exact_source_zone_time_frame'),
    ({'zone_id': 51}, 'no_exact_source_zone_time_frame'),
    ({'observed_at': 999}, 'no_exact_source_zone_time_frame'),
])
def test_packet_candidates_do_not_cross_source_context_or_time(tmp_path, change, classification):
    report = recording_report(CAPTURE, packet_observations=packet_file(tmp_path, **change))
    assert report['packet_evidence']['candidates'] == []
    assert report['packet_evidence']['classification_counts'] == {classification: 1}


def test_paired_acceptance_flags_missing_context_and_source_drops(tmp_path):
    packet = packet_file(tmp_path)
    row = json.loads(packet.read_text())
    packet.write_text(''.join(json.dumps(item) + '\n' for item in (
        row,
        row | {'sequence': 2, 'observed_at': 1001, 'dropped_before': 3},
        row | {'sequence': 3, 'observed_at': 1001, 'zone_id': 51, 'dropped_before': 3},
    )))
    summary = recording_report(CAPTURE, packet_observations=packet)['packet_evidence']['offline_acceptance']
    assert summary['packet_rows_checked'] == 3
    assert summary['exact_context_candidates'] == 2
    assert summary['unmatched_or_ambiguous_rows'] == 1
    assert summary['reported_rate_drops_at_last_row'] == 3
    assert summary['all_rows_have_unique_context_candidate'] is False
    assert summary['candidate_details_complete'] is True
    assert summary['runtime_packet_fidelity_verified'] is False
    assert summary['independent_capture_comparison_performed'] is False


def test_paired_acceptance_all_context_candidates_still_not_wire_verified(tmp_path):
    summary = recording_report(CAPTURE, packet_observations=packet_file(tmp_path))['packet_evidence']['offline_acceptance']
    assert summary['all_rows_have_unique_context_candidate'] is True
    assert summary['runtime_packet_fidelity_verified'] is False


def test_packet_report_rejects_incomplete_source_before_output(tmp_path):
    path = packet_file(tmp_path); path.write_bytes(path.read_bytes().rstrip(b'\n'))
    output = tmp_path / 'report.json'
    with pytest.raises(SystemExit):
        main([str(CAPTURE), '--packet-observations', str(path), '--output', str(output)])
    assert not output.exists()


def test_packet_report_bounds_candidates_without_losing_counts(tmp_path):
    path = packet_file(tmp_path)
    row = json.loads(path.read_text())
    path.write_text(''.join(json.dumps(row | {'sequence': n})+'\n' for n in range(1, 1003)))
    evidence = recording_report(CAPTURE, packet_observations=path)['packet_evidence']
    assert len(evidence['candidates']) == 1000 and evidence['candidates_truncated'] is True
    assert evidence['classification_counts']['exact_label_source_zone_time_candidate'] == 1002


def test_duplicate_time_frames_remain_ambiguous_even_with_different_instances(tmp_path):
    from workbench.runtime.live_client.runtime_report import packet_evidence_report
    from dataclasses import replace
    replay = load_recorded_bytes(CAPTURE.read_bytes(), client_id='ashita-runtime-sample')
    frame = replay.advance()
    other = replace(frame, snapshot=replace(frame.snapshot, instance_hint='different-instance'))
    evidence = packet_evidence_report(packet_file(tmp_path), CAPTURE.stem, [frame, other])
    assert evidence['classification_counts'] == {'ambiguous_frame': 1}
    assert evidence['candidates'] == []

def test_paired_packet_evidence_is_bounded_by_exact_telemetry_context(tmp_path):
    packet = packet_file(tmp_path)
    row = json.loads(packet.read_text())
    rows = [
        row,
        row | {'sequence': 2, 'observed_at': 1001},
        row | {'sequence': 3, 'observed_at': 1001, 'zone_id': 51},
    ]
    packet.write_text(''.join(json.dumps(item) + '\n' for item in rows))
    report = recording_report(CAPTURE, packet_observations=packet)
    evidence = report['packet_evidence']
    assert evidence['packets'] == 3
    assert evidence['classification_counts'] == {
        'exact_label_source_zone_time_candidate': 2,
        'no_exact_source_zone_time_frame': 1,
    }
    assert [(candidate['packet_sequence'], candidate['telemetry_frame'])
            for candidate in evidence['candidates']] == [(1, 1), (2, 2)]
    assert evidence['recording_identity_verified'] is False
    assert evidence['wire_verified'] is False
    assert evidence['causal_relationship_verified'] is False

