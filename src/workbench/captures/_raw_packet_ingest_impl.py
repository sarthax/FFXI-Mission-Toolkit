"""Raw FFXI packet-source adapters shared by capture ingestion.

This module keeps source-specific parsing separate from the canonical capture_raw_packets table.
Packet evidence is never merged across sources here: each source observation keeps its own row and
provenance; packet_correlation is responsible for linking equivalent observations later.
"""
from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

from workbench.core.services import capture_integrity
from workbench.core.services import capture_chat

_HEX = re.compile(r"^[0-9A-Fa-f]{2}$")
_PACKETEER_DIRECTION = {
    "[s->c]": "incoming",
    "[c->s]": "outgoing",
}


def normalize_raw_hex(value) -> str | None:
    if value is None:
        return None
    raw = re.sub(r"[^0-9A-Fa-f]", "", str(value))
    if not raw or len(raw) % 2:
        return None
    try:
        bytes.fromhex(raw)
    except ValueError:
        return None
    return raw.upper()


def decode_packet_header(raw_hex: str | None) -> dict:
    """Decode the four-byte FFXI packet header exactly as PacketDB/VieweD do."""
    raw = normalize_raw_hex(raw_hex)
    if not raw:
        return {"opcode": None, "packet_size": None, "sync_id": None}
    data = bytes.fromhex(raw)
    if len(data) < 4:
        return {"opcode": None, "packet_size": len(data), "sync_id": None}
    opcode = data[0] + ((data[1] & 0x01) * 0x100)
    packet_size = (data[1] & 0xFE) * 2
    sync_id = data[2] + (data[3] * 0x100)
    return {"opcode": opcode, "packet_size": packet_size, "sync_id": sync_id}


def _next_seq(con: sqlite3.Connection, capture_id: int) -> int:
    row = con.execute(
        "SELECT COALESCE(MAX(seq), -1) + 1 FROM capture_raw_packets WHERE capture_id=?",
        (capture_id,),
    ).fetchone()
    return int(row[0] or 0)


def _existing_seq(
    con: sqlite3.Connection,
    capture_id: int,
    source_format: str,
    source_native_id: str | None,
) -> int | None:
    if not source_native_id:
        return None
    row = con.execute(
        """SELECT seq FROM capture_raw_packets
           WHERE capture_id=? AND source_format=? AND source_native_id=?""",
        (capture_id, source_format, source_native_id),
    ).fetchone()
    return int(row[0]) if row else None


def _source_sequence_state(
    con: sqlite3.Connection,
    capture_id: int,
    source_format: str,
) -> tuple[dict[str, int], int]:
    """Load source-native sequence ownership once for a bulk importer."""
    existing = {
        str(native_id): int(seq)
        for native_id, seq in con.execute(
            """SELECT source_native_id,seq FROM capture_raw_packets
               WHERE capture_id=? AND source_format=? AND source_native_id IS NOT NULL""",
            (capture_id, source_format),
        )
    }
    return existing, _next_seq(con, capture_id)


def _utf8_offsets_for_positions(text: str, positions) -> dict[int, int]:
    """Resolve many UTF-8 byte offsets in one forward pass."""
    wanted = sorted(set(int(p) for p in positions))
    out: dict[int, int] = {}
    prev_char = 0
    prev_bytes = 0
    for pos in wanted:
        if pos < prev_char or pos < 0 or pos > len(text):
            continue
        prev_bytes += len(text[prev_char:pos].encode("utf-8"))
        out[pos] = prev_bytes
        prev_char = pos
    return out


def insert_raw_packet(
    con: sqlite3.Connection,
    capture_id: int,
    *,
    ts: str | None,
    direction: str,
    opcode,
    raw_hex,
    zone_id: int | None = None,
    packet_size: int | None = None,
    sync_id: int | None = None,
    is_injected: bool | int | None = None,
    is_blocked: bool | int | None = None,
    source_format: str,
    source_native_id: str | None,
    filename: str,
    source_sha256: str,
    locator_basis: str,
    start_line: int | None = None,
    end_line: int | None = None,
    start_offset: int | None = None,
    end_offset: int | None = None,
    details: dict | None = None,
    seq: int | None = None,
) -> int:
    raw = normalize_raw_hex(raw_hex)
    if not raw:
        raise ValueError("raw packet data is empty or malformed")
    header = decode_packet_header(raw)
    if opcode is None:
        opcode = header["opcode"]
    if packet_size is None:
        packet_size = header["packet_size"]
    if sync_id is None:
        sync_id = header["sync_id"]
    if isinstance(opcode, int):
        opcode = f"0x{opcode:03X}"
    elif opcode is not None:
        opcode = str(opcode)

    if seq is None:
        existing = _existing_seq(con, capture_id, source_format, source_native_id)
        seq = existing if existing is not None else _next_seq(con, capture_id)

    con.execute(
        """INSERT OR REPLACE INTO capture_raw_packets
           (capture_id,seq,ts,direction,opcode,raw_hex,zone_id,packet_size,sync_id,
            is_injected,is_blocked,source_format,source_native_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            capture_id, seq, ts, direction, opcode, raw, zone_id, packet_size, sync_id,
            None if is_injected is None else int(bool(is_injected)),
            None if is_blocked is None else int(bool(is_blocked)),
            source_format, source_native_id,
        ),
    )
    locator_details = {
        "source_format": source_format,
        "source_native_id": source_native_id,
        "opcode": opcode,
        "direction": direction,
        "timestamp": ts,
        "zone_id": zone_id,
        "packet_size": packet_size,
        "sync_id": sync_id,
    }
    if details:
        locator_details.update(details)
    capture_integrity.record_row_locator(
        con, capture_id, filename, "capture_raw_packets",
        json.dumps({"seq": seq}, sort_keys=True), locator_basis,
        source_sha256=source_sha256,
        start_line=start_line, end_line=end_line,
        start_offset=start_offset, end_offset=end_offset,
        details=locator_details,
    )
    return seq


def ingest_packetdb(con: sqlite3.Connection, capture_id: int, src, relname: str) -> int:
    """Ingest MalRD PacketDB PACKETS rows without discarding its native packet metadata."""
    source_bytes = src.read_bytes(relname)
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.write(source_bytes)
    tmp.close()
    rows = []
    chat_rows = []
    try:
        db = sqlite3.connect(tmp.name)
        try:
            cols = {r[1].upper() for r in db.execute("PRAGMA table_info(PACKETS)")}
            required = {
                "PACKET_ID", "RECEIVED_DT", "DIRECTION", "ZONE_ID",
                "PACKET_TYPE", "PACKET_SIZE", "PACKET_SYNC", "PACKET_DATA",
            }
            if not required <= cols:
                raise ValueError("PacketDB PACKETS schema is missing required columns")
            rows = db.execute(
                """SELECT PACKET_ID,RECEIVED_DT,DIRECTION,ZONE_ID,PACKET_TYPE,
                          PACKET_SIZE,PACKET_SYNC,PACKET_DATA
                   FROM PACKETS ORDER BY RECEIVED_DT,PACKET_ID"""
            ).fetchall()
            chat_cols = {r[1].upper() for r in db.execute("PRAGMA table_info(CHATLOG)")}
            chat_required = {"CHAT_ID","RECEIVED_DT","DIRECTION","ZONE_ID","CHAT_TEXT"}
            if chat_required <= chat_cols:
                chat_rows = db.execute(
                    """SELECT CHAT_ID,RECEIVED_DT,DIRECTION,ZONE_ID,CHAT_TEXT
                       FROM CHATLOG ORDER BY RECEIVED_DT,CHAT_ID"""
                ).fetchall()
        finally:
            db.close()
    finally:
        try:
            Path(tmp.name).unlink()
        except OSError:
            pass

    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND filename=?
             AND target_table IN ('capture_raw_packets','capture_chat_observations')""",
        (capture_id, relname),
    )
    count = 0
    existing_seq, next_seq = _source_sequence_state(con, capture_id, "packetdb")
    for packet_id, ts, direction, zone_id, packet_type, packet_size, sync_id, packet_data in rows:
        direction_name = "incoming" if int(direction) == 0 else (
            "outgoing" if int(direction) == 1 else "unknown"
        )
        native_id = f"{relname}:{packet_id}"
        assigned_seq = existing_seq.get(native_id)
        if assigned_seq is None:
            assigned_seq = next_seq
            next_seq += 1
        insert_raw_packet(
            con, capture_id,
            ts=str(ts) if ts is not None else None,
            direction=direction_name,
            opcode=int(packet_type),
            raw_hex=packet_data,
            zone_id=int(zone_id) if zone_id is not None else None,
            packet_size=int(packet_size) if packet_size is not None else None,
            sync_id=int(sync_id) if sync_id is not None else None,
            source_format="packetdb",
            source_native_id=native_id,
            filename=relname,
            source_sha256=source_sha256,
            locator_basis="sqlite-row",
            details={"packetdb_packet_id": packet_id},
            seq=assigned_seq,
        )
        count += 1

    for chat_id, ts, direction, zone_id, chat_text in chat_rows:
        direction_name = "incoming" if int(direction) == 0 else (
            "outgoing" if int(direction) == 1 else "unknown"
        )
        capture_chat.insert_chat_observation(
            con, capture_id,
            ts=str(ts) if ts is not None else None,
            direction=direction_name,
            zone_id=int(zone_id) if zone_id is not None else None,
            zone_db=None,
            text=str(chat_text),
            source_format="packetdb_chatlog",
            source_native_id=f"{relname}:chat:{chat_id}",
            filename=relname,
            source_sha256=source_sha256,
            locator_basis="sqlite-row",
            details={"packetdb_chat_id": chat_id, "source_table": "CHATLOG"},
        )
        count += 1
    return count


def _packeteer_blocks(text: str):
    lines = text.splitlines(keepends=True)
    blocks = []
    current = []
    char_pos = 0
    block_start = 0
    start_line = 1
    for lineno, raw_line in enumerate(lines, 1):
        line = raw_line.rstrip("\r\n")
        if line.strip():
            if not current:
                block_start = char_pos
                start_line = lineno
            current.append(line)
        elif current:
            blocks.append((current, block_start, char_pos, start_line, lineno))
            current = []
        char_pos += len(raw_line)
    if current:
        blocks.append((current, block_start, len(text), start_line, len(lines)))
    return blocks


def _packeteer_line_bytes(line: str) -> list[str]:
    # VieweD reads the 16 two-character byte cells beginning at column 4.
    if len(line) < 6:
        return []
    out = []
    for index in range(16):
        pos = 4 + index * 3
        if pos + 2 > len(line):
            break
        token = line[pos:pos + 2]
        if _HEX.fullmatch(token):
            out.append(token)
    return out


def parse_packeteer_records(text: str) -> list[dict]:
    out = []
    for block_index, (lines, start_char, end_char, start_line, end_line) in enumerate(_packeteer_blocks(text)):
        header = lines[0]
        lower = header.lower()
        if "[s->c]" in lower:
            direction = "incoming"
        elif "[c->s]" in lower:
            direction = "outgoing"
        else:
            continue

        hex_bytes = []
        for line in lines[1:]:
            if line.lstrip().startswith("--"):
                continue
            hex_bytes.extend(_packeteer_line_bytes(line))
        raw_hex = "".join(hex_bytes)
        decoded = decode_packet_header(raw_hex)
        if decoded["opcode"] is None:
            continue

        header_opcode = None
        match = re.search(r"PacketId:\s*([0-9A-Fa-f]{1,4})", header, re.IGNORECASE)
        if match:
            header_opcode = int(match.group(1), 16)
        # The byte header is authoritative; retain the rendered header value for diagnostics.
        ts = None
        for bracket in re.findall(r"\[([^\]]+)\]", header):
            if len(bracket) > 8 and not re.fullmatch(r"[SC]->[SC]", bracket, re.IGNORECASE):
                ts = bracket
                break
        out.append({
            "block_index": block_index,
            "direction": direction,
            "opcode": decoded["opcode"],
            "header_opcode": header_opcode,
            "packet_size": decoded["packet_size"],
            "sync_id": decoded["sync_id"],
            "raw_hex": normalize_raw_hex(raw_hex),
            "ts": ts,
            "header": header,
            "start_char": start_char,
            "end_char": end_char,
            "start_line": start_line,
            "end_line": end_line,
        })
    return out


def ingest_packeteer(con: sqlite3.Connection, capture_id: int, src, relname: str) -> int:
    source_bytes = src.read_bytes(relname)
    text = source_bytes.decode("utf-8", "replace")
    exact_offsets = text.encode("utf-8") == source_bytes
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND filename=? AND target_table='capture_raw_packets'""",
        (capture_id, relname),
    )
    count = 0
    records = parse_packeteer_records(text)
    byte_offsets = (
        _utf8_offsets_for_positions(
            text,
            [pos for row in records for pos in (row["start_char"], row["end_char"])],
        )
        if exact_offsets else {}
    )
    existing_seq, next_seq = _source_sequence_state(con, capture_id, "packeteer")
    for row in records:
        native_id = f"{relname}:block:{row['block_index']}"
        assigned_seq = existing_seq.get(native_id)
        if assigned_seq is None:
            assigned_seq = next_seq
            next_seq += 1
        insert_raw_packet(
            con, capture_id,
            ts=row["ts"],
            direction=row["direction"],
            opcode=row["opcode"],
            raw_hex=row["raw_hex"],
            packet_size=row["packet_size"],
            sync_id=row["sync_id"],
            source_format="packeteer",
            source_native_id=native_id,
            filename=relname,
            source_sha256=source_sha256,
            locator_basis="block",
            start_line=row["start_line"],
            end_line=row["end_line"],
            start_offset=byte_offsets.get(row["start_char"]) if exact_offsets else None,
            end_offset=byte_offsets.get(row["end_char"]) if exact_offsets else None,
            details={
                "header": row["header"],
                "header_opcode": row["header_opcode"],
            },
            seq=assigned_seq,
        )
        count += 1
    return count


def promote_npclogger_raw_packet(
    con: sqlite3.Connection,
    capture_id: int,
    *,
    relname: str,
    source_sha256: str,
    line_number: int,
    raw_hex,
    start_offset: int | None,
    end_offset: int | None,
    entity_id: int,
) -> int | None:
    """Promote NPCLogger's preserved incoming raw packet into canonical packet evidence."""
    raw = normalize_raw_hex(raw_hex)
    if not raw:
        return None
    header = decode_packet_header(raw)
    if header["opcode"] is None:
        return None
    native_id = f"{relname}:line:{line_number}"
    return insert_raw_packet(
        con, capture_id,
        ts=None,
        direction="incoming",
        opcode=header["opcode"],
        raw_hex=raw,
        packet_size=header["packet_size"],
        sync_id=header["sync_id"],
        source_format="npclogger_lua",
        source_native_id=native_id,
        filename=relname,
        source_sha256=source_sha256,
        locator_basis="line",
        start_line=line_number,
        end_line=line_number,
        start_offset=start_offset,
        end_offset=end_offset,
        details={"entity_id": entity_id, "preserved_field": "raw_packet"},
    )
