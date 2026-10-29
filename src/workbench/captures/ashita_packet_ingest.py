"""Strict Ashita hook-source adapter into canonical Capture raw rows, not a decoder."""
from datetime import datetime, timezone
import json
import re

from workbench.runtime.live_client.ashita_packets import MAX_BYTES, _integer, _text, parse_observations  # noqa: F401

from . import integrity
from . import raw_packet_ingest

def ingest_ashita_packets(con, capture_id: int, src, relname: str) -> int:
    data = src.read_bytes(relname)
    rows = parse_observations(data)  # Validate the complete source before any mutation.
    digest = integrity.sha256_bytes(data)
    con.execute('SAVEPOINT ashita_packet_ingest')
    try:
        for row, line, start, end in rows:
            header = raw_packet_ingest.decode_packet_header(row['raw_hex'])
            raw_packet_ingest.insert_raw_packet(
                con, capture_id, ts=datetime.fromtimestamp(row['observed_at'], timezone.utc).isoformat(),
                direction=row['direction'], opcode=row['opcode'], raw_hex=row['raw_hex'],
                zone_id=row['zone_id'], packet_size=row['size'],
                is_injected=row['is_injected'], is_blocked=row['is_blocked'],
                source_format='ashita_packets',
                source_native_id=f"{relname}:{row['source_recording']}:{row['sequence']}",
                filename=relname, source_sha256=digest, locator_basis='line',
                start_line=line, end_line=line, start_offset=start, end_offset=end,
                details={key: row[key] for key in ('client_id', 'source_recording', 'adapter',
                    'client_version', 'profile', 'hook_stage', 'sequence', 'observed_at', 'dropped_before')}
                    | {'flags_scope': 'addon_callback', 'wire_verified': False,
                       'client_version_verified': False, 'opcode_semantics_verified': False,
                       'header_opcode': header['opcode'], 'header_packet_size': header['packet_size']},
            )
        con.execute('RELEASE ashita_packet_ingest')
    except Exception:
        con.execute('ROLLBACK TO ashita_packet_ingest'); con.execute('RELEASE ashita_packet_ingest')
        raise
    return len(rows)
