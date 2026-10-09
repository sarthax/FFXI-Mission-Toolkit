"""Observed zoning evidence and cadence gaps never promote lifecycle compatibility."""
from dataclasses import replace
from pathlib import Path

from workbench.runtime.live_client.recording import load_recorded_frames
from workbench.runtime.live_client.runtime_report import recording_gap_summary, recording_report

D = Path(__file__).parent / 'fixtures/live_client/ashita_v4_zoning_runtime_d_anonymized.jsonl'


def test_supplied_four_transition_recording_preserves_gaps_visits_and_unknown_identity():
    report = recording_report(D)
    recording = report['recording']
    assert recording['frames'] == 131 and recording['duration_seconds'] == 146
    assert recording['zone_frame_counts'] == {'48': 9, '51': 37, '52': 85}
    assert recording['entity_observation_summary']['total_observations'] == 623
    assert recording['entity_observation_summary']['raw_field_coverage'] == {
        'raw_entity_type': 623, 'raw_spawn_flags': 623, 'raw_status': 623}
    assert recording['entity_observation_summary']['observations_with_target_roles'] == 0
    transitions = recording['context_transitions']
    assert [(t['from_zone'], t['to_zone']) for t in transitions] == [(52,51), (51,52), (52,48), (48,52)]
    gap = recording['gap_summary']
    assert gap['count'] == 4 and gap['classified_intervals'] == 130
    assert [g['to_frame'] for g in gap['gaps']] == [25,62,91,100]
    assert all(g['interval_seconds'] == 5 for g in gap['gaps'])
    assert gap['cause_verified'] is False and gap['interpolated_frames'] == 0
    assert report['validation']['lifecycle_verified'] is False
    assert report['validation']['build_verified'] is False
    replay = load_recorded_frames(D, client_id='ashita-zoning-runtime-d')
    replay.seek(131)
    points = replay.path_points()
    assert {p['segment'] for p in points if p['zone_id']==52} == {0,2,4}
    assert len(replay.path_points(max_points=2)) == 2
    assert replay.path_points(max_points=2)[-1]['segment'] == 4
    for t in transitions:
        replay.seek(t['frame'])
        assert all(e.position.zone_id == t['to_zone'] for e in replay.feed.entities())
        assert all(e.kind.value == 'unknown' for e in replay.feed.entities())


def test_unknown_provider_or_changed_source_does_not_invent_expected_cadence():
    sample = load_recorded_frames(D, client_id='ashita-zoning-runtime-d').advance().snapshot
    other = replace(sample, observed_at=sample.observed_at+5)
    same_zone = recording_gap_summary([sample, other])
    assert same_zone['count'] == 1
    assert same_zone['gaps'][0]['from_zone'] == same_zone['gaps'][0]['to_zone']
    for changed in (replace(other, adapter='custom'), replace(other, version='different'),
                    replace(other, client_id='different')):
        summary = recording_gap_summary([sample, changed])
        assert summary['count'] == 0 and summary['unclassified_intervals'] == 1
    summary = recording_gap_summary([replace(sample, adapter='custom'), replace(other, adapter='custom')])
    assert summary['count'] == 0 and summary['unclassified_intervals'] == 1


def test_gap_details_are_bounded_without_losing_counts():
    sample = load_recorded_frames(D, client_id='ashita-zoning-runtime-d').advance().snapshot
    summary = recording_gap_summary([replace(sample, observed_at=i*5) for i in range(1003)])
    assert summary['count'] == 1002 and len(summary['gaps']) == 1000
    assert summary['details_truncated'] is True
    assert recording_gap_summary([])['count'] == 0
    assert recording_gap_summary([sample])['count'] == 0
