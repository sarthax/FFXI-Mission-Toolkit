"""Strict parser for stopped Ashita packet JSONL observations (pure; no Capture database access)."""
import json
import re

MAX_BYTES = 4 * 1024 * 1024


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('invalid Ashita packet integer')
    return value


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError('invalid Ashita packet source')
    return value


def parse_observations(data: bytes) -> list[tuple[dict, int, int, int]]:
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_BYTES:
        raise ValueError('Ashita packet source must be 1 byte to 4 MiB')
    if not data.endswith(b'\n'):
        raise ValueError('incomplete Ashita packet source; stop capture before import')
    rows, offset, previous, source = [], 0, None, None
    for number, line in enumerate(data.splitlines(keepends=True), 1):
        if len(line) > 4096 or len(rows) >= 10000:
            raise ValueError('Ashita packet line/count limit exceeded')
        row = json.loads(line.decode('utf-8'))
        if (not isinstance(row, dict) or type(row.get('schema_version')) is not int
                or row['schema_version'] != 1 or row.get('kind') != 'ashita_packet_observation'
                or row.get('profile') != 'event_emote'
                or row.get('hook_stage') != 'addon_callback_original'):
            raise ValueError('unsupported Ashita packet schema/profile/stage')
        identity = tuple(_text(row.get(key)) for key in
                         ('client_id', 'source_recording', 'adapter', 'client_version'))
        if source is not None and identity != source:
            raise ValueError('mixed Ashita packet sources')
        source = identity
        seq = _integer(row.get('sequence'), 1, 10000)
        timestamp = _integer(row.get('observed_at'), 0, 4102444800)
        dropped = _integer(row.get('dropped_before'), 0, 0xFFFFFFFF)
        _integer(row.get('zone_id'), 1, 65535)
        _integer(row.get('opcode'), 0, 511)
        size = _integer(row.get('size'), 4, 1024)
        raw = row.get('raw_hex')
        if not isinstance(raw, str) or len(raw) != size*2 or not re.fullmatch('[0-9A-Fa-f]+', raw):
            raise ValueError('invalid original packet bytes/size')
        if row.get('direction') not in ('incoming', 'outgoing'):
            raise ValueError('invalid Ashita packet direction')
        if any(type(row.get(key)) is not bool for key in ('is_injected', 'is_blocked')):
            raise ValueError('invalid hook-time packet flags')
        if seq != (previous[0]+1 if previous else 1) or (previous and (timestamp < previous[1] or dropped < previous[2])):
            raise ValueError('stale/nonsequential Ashita packet observations')
        previous = seq, timestamp, dropped
        rows.append((row, number, offset, offset+len(line)))
        offset += len(line)
    return rows
