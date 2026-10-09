"""Bounded offline runtime evidence reports. Never load or execute client binaries."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .recording import load_recorded_bytes


def bounded_bytes(path: Path, limit: int) -> bytes:
    with Path(path).open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f'{Path(path).name} exceeds size limit')
    return data


def binary_fingerprint(path: Path) -> dict:
    """Hash and parse PE resource metadata only; no running-process verification."""
    path = Path(path)
    if path.suffix.lower() not in {'.exe', '.dll'}:
        raise ValueError('binary metadata requires an EXE or DLL')
    data = bounded_bytes(path, 64 * 1024 * 1024)
    try:
        import pefile
    except ImportError as exc:
        raise ValueError('install pefile to inspect optional EXE/DLL metadata') from exc
    try:
        with pefile.PE(data=data, fast_load=True) as pe:
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
            info = getattr(pe, 'VS_FIXEDFILEINFO', [])
            def version(ms, ls):
                return '.'.join(str(n) for n in (ms >> 16, ms & 65535, ls >> 16, ls & 65535))
            return {'filename': path.name, 'size_bytes': len(data),
                    'sha256': hashlib.sha256(data).hexdigest(),
                    'pe_machine': f'0x{pe.FILE_HEADER.Machine:04x}',
                    'file_version': version(info[0].FileVersionMS, info[0].FileVersionLS) if info else None,
                    'product_version': version(info[0].ProductVersionMS, info[0].ProductVersionLS) if info else None,
                    'running_identity_verified': False}
    except pefile.PEFormatError as exc:
        raise ValueError(f'{path.name} is not a valid PE file') from exc


def entity_observation_summary(frames) -> dict:
    """Summarize supplied observation coverage, never infer target roles or identity."""
    scopes = Counter(frame.observation_scope for frame in frames)
    counts = Counter(len(frame.entities) for frame in frames)
    reported = sum(entity.server_entity_id not in (None, 0)
                   for frame in frames for entity in frame.entities)
    total = sum(len(frame.entities) for frame in frames)
    return {'scope_frame_counts': dict(sorted(scopes.items())),
            'truncated_frames': sum(frame.entities_truncated for frame in frames),
            'entity_count_distribution': [{'entities': count, 'frames': number}
                                          for count, number in sorted(counts.items())],
            'total_observations': total,
            'observations_with_reported_server_id': reported,
            'observations_without_reported_server_id': total - reported,
            'raw_field_coverage': {field: sum(getattr(entity, field) is not None
                                            for frame in frames for entity in frame.entities)
                                   for field in ('raw_entity_type', 'raw_spawn_flags', 'raw_status')},
            'observations_with_target_roles': sum(bool(entity.target_roles)
                                                 for frame in frames for entity in frame.entities),
            'target_roles_verified': False,
            'complete_inventory_verified': False,
            'server_identity_verified': False}


def recording_gap_summary(snapshots) -> dict:
    """Describe observed gaps against declared exporter cadence, never infer causes."""
    exporters = {'ashita-v4-api-experimental', 'windower-api-experimental'}
    gaps, count, classified = [], 0, 0
    cross_zone_gaps = same_zone_gaps = 0
    known_instance_change_gaps = unknown_instance_context_gaps = 0
    observed_excess_seconds = cross_zone_excess_seconds = same_zone_excess_seconds = 0
    for number, (before, after) in enumerate(zip(snapshots, snapshots[1:]), 2):
        if (before.adapter not in exporters or
                (before.client_id, before.adapter, before.version) !=
                (after.client_id, after.adapter, after.version)):
            continue
        classified += 1
        interval = after.observed_at - before.observed_at
        if interval <= 1:
            continue
        count += 1
        excess_seconds = interval - 1
        observed_excess_seconds += excess_seconds
        if before.instance_hint is None or after.instance_hint is None:
            unknown_instance_context_gaps += 1
        elif before.instance_hint != after.instance_hint:
            known_instance_change_gaps += 1
        if before.position.zone_id != after.position.zone_id:
            cross_zone_gaps += 1
            cross_zone_excess_seconds += excess_seconds
        else:
            same_zone_gaps += 1
            same_zone_excess_seconds += excess_seconds
        if len(gaps) < 1000:
            gaps.append({'from_frame': number-1, 'to_frame': number,
                         'interval_seconds': interval, 'expected_interval_seconds': 1,
                         'excess_interval_seconds': excess_seconds,
                         'from_zone': before.position.zone_id, 'to_zone': after.position.zone_id,
                         'from_instance': before.instance_hint, 'to_instance': after.instance_hint})
    return {'count': count, 'cross_zone_gap_count': cross_zone_gaps,
            'same_zone_gap_count': same_zone_gaps,
            'known_instance_change_gap_count': known_instance_change_gaps,
            'unknown_instance_context_gap_count': unknown_instance_context_gaps,
            'observed_excess_interval_seconds': observed_excess_seconds,
            'cross_zone_excess_interval_seconds': cross_zone_excess_seconds,
            'same_zone_excess_interval_seconds': same_zone_excess_seconds,
            'gaps': gaps, 'detail_limit': 1000,
            'details_truncated': count > len(gaps),
            'classified_intervals': classified,
            'unclassified_intervals': max(0, len(snapshots)-1-classified),
            'basis': 'declared Ashita/Windower exporter one-second cadence',
            'cause_verified': False, 'interpolated_frames': 0}


def recording_report(path: Path, *, game_version: str | None = None,
                     binaries: list[Path] | None = None,
                     packet_observations: Path | None = None,
                     capture_database: Path | None = None, capture_id: int | None = None) -> dict:
    if ((capture_database is None) != (capture_id is None)
            or (capture_database is not None and packet_observations is None)):
        raise ValueError('Capture lookup requires packet observations, database and capture ID together')
    data = bounded_bytes(path, 16 * 1024 * 1024)
    lines = [line for line in data.splitlines() if line.strip()]
    if not lines:
        raise ValueError('recording contains no frames')
    try:
        client_id = json.loads(lines[0].decode('utf-8-sig'))['client_id']
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise ValueError('invalid first recording frame') from exc
    replay = load_recorded_bytes(data, client_id=client_id)
    if game_version is not None and (not game_version.strip() or len(game_version) > 200):
        raise ValueError('invalid reported game version')
    frames = [replay.advance() for _ in range(replay.total)]
    snapshots = [frame.snapshot for frame in frames]
    zones = Counter(s.position.zone_id for s in snapshots)
    deltas = Counter(b.observed_at-a.observed_at for a, b in zip(snapshots, snapshots[1:]))
    transitions = []
    for i, (a, b) in enumerate(zip(snapshots, snapshots[1:]), 2):
        if (a.position.zone_id, a.instance_hint) != (b.position.zone_id, b.instance_hint):
            transitions.append({'frame': i, 'from_zone': a.position.zone_id, 'to_zone': b.position.zone_id,
                                'from_instance': a.instance_hint, 'to_instance': b.instance_hint})
    ranges = {}
    for snapshot in snapshots:
        zone = ranges.setdefault(str(snapshot.position.zone_id), {})
        for axis in ('x', 'y', 'z', 'heading'):
            value = getattr(snapshot.position, axis)
            span = zone.setdefault(axis, {'min': value, 'max': value})
            span['min'] = min(span['min'], value)
            span['max'] = max(span['max'], value)
    report = {'schema_version': 1, 'kind': 'live_client_runtime_report',
            'recording': {'filename': Path(path).name, 'sha256': hashlib.sha256(data).hexdigest(),
                          'size_bytes': len(data), 'client_id': client_id,
                          'frames': len(frames), 'duration_seconds': snapshots[-1].observed_at-snapshots[0].observed_at,
                          'adapters': sorted({s.adapter for s in snapshots}),
                          'reported_client_versions': sorted({s.version for s in snapshots}),
                          'zone_frame_counts': {str(k): v for k, v in sorted(zones.items())},
                          'frame_intervals': [{'seconds': k, 'count': v} for k, v in sorted(deltas.items())],
                          'gap_summary': recording_gap_summary(snapshots),
                          'context_transitions': transitions, 'raw_axis_ranges_by_zone': ranges,
                          'frames_with_entities': sum(bool(f.entities) for f in frames),
                          'distinct_entity_observations': len({(f.snapshot.adapter, f.snapshot.version,
                                                               e.position.zone_id, e.instance_hint, e.client_index,
                                                               (e.server_entity_id or None), e.name)
                                                               for f in frames for e in f.entities}),
                          'entity_observation_summary': entity_observation_summary(frames)},
            'operator_reported_game_version': game_version,
            'supplied_binaries': [binary_fingerprint(p) for p in binaries or []],
            'validation': {'all_frames_decoded': True, 'build_verified': False,
                           'coordinate_transform_verified': False, 'supports_game_writes': False,
                           'lifecycle_verified': False}}
    if packet_observations is not None:
        report['packet_evidence'] = packet_evidence_report(packet_observations, Path(path).stem, frames,
                                                         capture_database=capture_database, capture_id=capture_id)
    return report


def packet_evidence_report(path: Path, recording_label: str, frames, *,
                           capture_database: Path | None = None, capture_id: int | None = None) -> dict:
    """Exact source/time candidates only; reuse Capture validation without decoding."""
    from workbench.captures.ashita_packet_ingest import MAX_BYTES, parse_observations

    data = bounded_bytes(path, MAX_BYTES)
    rows = parse_observations(data)
    # Never interpolate across gaps, zones, instances, restarts, or clock changes.
    index = {}
    for number, frame in enumerate(frames, 1):
        s = frame.snapshot
        key = (s.client_id, s.adapter, s.version, s.position.zone_id, s.observed_at)
        index.setdefault(key, []).append(number)
    counts = Counter()
    candidates = []
    for row, line, start, end in rows:
        if row['source_recording'] != recording_label:
            counts['source_label_mismatch'] += 1
            continue
        key = (row['client_id'], row['adapter'], row['client_version'], row['zone_id'], row['observed_at'])
        matches = index.get(key, [])
        if not matches:
            counts['no_exact_source_zone_time_frame'] += 1
        elif len(matches) != 1:
            counts['ambiguous_frame'] += 1
        else:
            counts['exact_label_source_zone_time_candidate'] += 1
            if len(candidates) < 1000:
                candidates.append({'packet_sequence': row['sequence'], 'packet_line': line,
                                   'packet_start_offset': start, 'packet_end_offset': end,
                                   'telemetry_frame': matches[0], 'observed_at': row['observed_at'],
                                   'zone_id': row['zone_id'], 'direction': row['direction'],
                                   'reported_opcode': row['opcode'], 'dropped_before': row['dropped_before']})
    evidence = {'filename': Path(path).name, 'sha256': hashlib.sha256(data).hexdigest(),
            'size_bytes': len(data), 'packets': len(rows),
            'classification_counts': dict(sorted(counts.items())), 'candidates': candidates,
            'candidate_limit': 1000,
            'candidates_truncated': counts['exact_label_source_zone_time_candidate'] > len(candidates),
            'source_binding': 'declared_recording_filename_stem',
            'instance_identity_available': False, 'recording_identity_verified': False,
            'clock_alignment_verified': False, 'server_identity_verified': False,
            'packet_semantics_verified': False, 'causal_relationship_verified': False,
            'wire_verified': False}
    if capture_database is not None:
        from .capture_evidence import attach_capture_locators
        attach_capture_locators(evidence, rows, capture_database, capture_id)
    return evidence


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording', type=Path)
    parser.add_argument('--game-version', help='Operator-reported version, not independently verified')
    parser.add_argument('--binary', type=Path, action='append', default=[], help='Optional EXE/DLL metadata only; repeatable')
    parser.add_argument('--output', type=Path, help='New report file; existing reports are never overwritten')
    parser.add_argument('--packet-observations', type=Path, help='Stopped Ashita packet JSONL; exact-time research candidates only')
    parser.add_argument('--capture-database', type=Path, help='Existing Toolkit Capture SQLite database, opened read-only')
    parser.add_argument('--capture-id', type=int, help='Explicit Capture ID for source-hash/span-qualified packet links')
    args = parser.parse_args(argv)
    try:
        report = recording_report(args.recording, game_version=args.game_version, binaries=args.binary,
                                  packet_observations=args.packet_observations,
                                  capture_database=args.capture_database, capture_id=args.capture_id)
        text = json.dumps(report, indent=2) + '\n'
        if args.output:
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(text)
        else:
            print(text, end='')
    except (OSError, ValueError) as exc:
        parser.exit(2, f'Runtime report failed: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
