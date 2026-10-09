"""Read-only handoffs to existing Capture packets, never a decoder or entity join."""
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import time


def attach_capture_locators(evidence: dict, rows, database: Path, capture_id: int) -> None:
    """Match one supplied byte snapshot to canonical stored rows in one read transaction."""
    if type(capture_id) is not int or not 1 <= capture_id <= 0x7FFFFFFFFFFFFFFF:
        raise ValueError('capture ID must be a positive SQLite integer')
    source_rows = {line: row for row, line, _, _ in rows}
    counts = Counter()
    try:
        with closing(sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True,
                                    timeout=2, isolation_level=None)) as con:
            con.row_factory = sqlite3.Row
            con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 65536)
            deadline = time.monotonic() + 5
            con.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            con.execute('PRAGMA query_only=ON')
            con.execute('BEGIN')
            if not con.execute('SELECT 1 FROM captures WHERE capture_id=?', (capture_id,)).fetchone():
                raise ValueError('selected Capture does not exist')
            for candidate in evidence['candidates']:
                locators = con.execute(
                    """SELECT filename,substr(row_key,1,257) AS row_key,
                              substr(details_json,1,8193) AS details_json
                       FROM capture_row_locators
                       WHERE capture_id=? AND target_table='capture_raw_packets'
                         AND source_sha256=? AND locator_basis='line'
                         AND start_line=? AND end_line=? AND start_offset=? AND end_offset=?
                       LIMIT 2""",
                    (capture_id, evidence['sha256'], candidate['packet_line'], candidate['packet_line'],
                     candidate['packet_start_offset'], candidate['packet_end_offset']),
                ).fetchall()
                status = 'not_imported'
                if len(locators) > 1:
                    status = 'ambiguous_locator'
                elif locators:
                    status = 'stored_evidence_mismatch'
                    locator = locators[0]
                    row = source_rows[candidate['packet_line']]
                    try:
                        key = json.loads(locator['row_key'])
                        details = json.loads(locator['details_json'])
                        seq = key['seq']
                        if (set(key) != {'seq'} or type(seq) is not int or not 0 <= seq <= 0x7FFFFFFFFFFFFFFF
                                or not isinstance(details, dict)):
                            raise ValueError('invalid row locator')
                    except (ValueError, TypeError, KeyError):
                        counts[status] += 1
                        candidate['capture_lookup'] = status
                        continue
                    stored = con.execute(
                        """SELECT ts,direction,opcode,substr(raw_hex,1,2049) AS raw_hex,zone_id,
                                  packet_size,is_injected,is_blocked,source_format,source_native_id
                           FROM capture_raw_packets WHERE capture_id=? AND seq=?""", (capture_id, seq),
                    ).fetchone()
                    detail_keys = ('client_id', 'source_recording', 'adapter', 'client_version', 'profile',
                                   'hook_stage', 'sequence', 'observed_at', 'dropped_before')
                    expected = {
                        'ts': datetime.fromtimestamp(row['observed_at'], timezone.utc).isoformat(),
                        'direction': row['direction'], 'opcode': f"0x{row['opcode']:03X}",
                        'raw_hex': row['raw_hex'].upper(), 'zone_id': row['zone_id'],
                        'packet_size': row['size'], 'is_injected': int(row['is_injected']),
                        'is_blocked': int(row['is_blocked']), 'source_format': 'ashita_packets',
                        'source_native_id': f"{locator['filename']}:{row['source_recording']}:{row['sequence']}",
                    }
                    if (stored is not None and dict(stored) == expected
                            and all(type(details.get(k)) is type(row[k]) and details[k] == row[k]
                                    for k in detail_keys)):
                        status = 'exact_imported_packet'
                        candidate['capture_locator'] = {'capture_id': capture_id, 'packet_seq': seq,
                            'source_filename': locator['filename'],
                            'href': f'/captures/{capture_id}/packets/{seq}',
                            'binding': 'source_sha256_span_and_stored_packet',
                            'runtime_identity_verified': False}
                counts[status] += 1
                candidate['capture_lookup'] = status
    except sqlite3.Error as exc:
        raise ValueError(f'Capture lookup failed: {exc}') from exc
    evidence['capture_lookup'] = {'capture_id': capture_id, 'database_filename': Path(database).name,
                                 'classification_counts': dict(sorted(counts.items())),
                                 'scope': 'retained_candidates_only', 'read_only': True}
