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
            'target_roles_verified': False,
            'complete_inventory_verified': False,
            'server_identity_verified': False}


def recording_report(path: Path, *, game_version: str | None = None,
                     binaries: list[Path] | None = None) -> dict:
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
    return {'schema_version': 1, 'kind': 'live_client_runtime_report',
            'recording': {'filename': Path(path).name, 'sha256': hashlib.sha256(data).hexdigest(),
                          'size_bytes': len(data), 'client_id': client_id,
                          'frames': len(frames), 'duration_seconds': snapshots[-1].observed_at-snapshots[0].observed_at,
                          'adapters': sorted({s.adapter for s in snapshots}),
                          'reported_client_versions': sorted({s.version for s in snapshots}),
                          'zone_frame_counts': {str(k): v for k, v in sorted(zones.items())},
                          'frame_intervals': [{'seconds': k, 'count': v} for k, v in sorted(deltas.items())],
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording', type=Path)
    parser.add_argument('--game-version', help='Operator-reported version, not independently verified')
    parser.add_argument('--binary', type=Path, action='append', default=[], help='Optional EXE/DLL metadata only; repeatable')
    parser.add_argument('--output', type=Path, help='New report file; existing reports are never overwritten')
    args = parser.parse_args(argv)
    try:
        report = recording_report(args.recording, game_version=args.game_version, binaries=args.binary)
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
