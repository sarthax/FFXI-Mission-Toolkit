"""Bounded PCAP/PCAPNG capture ingestion for FFXI research.

This adapter preserves network frames exactly and promotes UDP payloads into canonical FFXI packet
chunks only when the payload is already plaintext and the entire byte stream validates as known
4-byte-header FFXI chunks. It does not guess Blowfish keys, zlib state, session role, or direction.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import ipaddress
import json
import sqlite3
import struct

from workbench.core.services import capture_integrity, raw_packet_ingest


PCAP_MAGICS = {
    b"\xd4\xc3\xb2\xa1": ("<", 1_000_000),
    b"\xa1\xb2\xc3\xd4": (">", 1_000_000),
    b"\x4d\x3c\xb2\xa1": ("<", 1_000_000_000),
    b"\xa1\xb2\x3c\x4d": (">", 1_000_000_000),
}
PCAPNG_MAGIC = b"\x0a\x0d\x0d\x0a"


def sniff_pcap_format(data: bytes) -> str | None:
    if data[:4] in PCAP_MAGICS:
        return "pcap"
    if data[:4] == PCAPNG_MAGIC and len(data) >= 12:
        return "pcapng"
    return None


def _iso_utc(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    return _dt.datetime.fromtimestamp(seconds, tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _pcap_frames(data: bytes):
    endian, divisor = PCAP_MAGICS[data[:4]]
    if len(data) < 24:
        raise ValueError("truncated PCAP global header")
    _magic, _maj, _min, _tz, _sig, _snap, linktype = struct.unpack_from(endian + "IHHIIII", data, 0)
    pos = 24
    frame_no = 0
    while pos + 16 <= len(data):
        record_start = pos
        ts_sec, ts_frac, incl_len, orig_len = struct.unpack_from(endian + "IIII", data, pos)
        pos += 16
        if incl_len > len(data) - pos:
            raise ValueError(f"truncated PCAP frame {frame_no + 1}")
        frame = data[pos:pos + incl_len]
        pos += incl_len
        frame_no += 1
        yield {
            "frame_no": frame_no,
            "timestamp_seconds": ts_sec + (ts_frac / divisor),
            "linktype": int(linktype),
            "captured_len": int(incl_len),
            "original_len": int(orig_len),
            "frame": frame,
            "start_offset": record_start,
            "end_offset": pos,
            "format": "pcap",
            "interface_id": 0,
        }
    if pos != len(data):
        # A partial record header is corruption, not padding in classic PCAP.
        raise ValueError("trailing truncated PCAP record header")


def _pcapng_options(body: bytes, endian: str):
    pos = 0
    while pos + 4 <= len(body):
        code, length = struct.unpack_from(endian + "HH", body, pos)
        pos += 4
        if code == 0:
            break
        value = body[pos:pos + length]
        pos += (length + 3) & ~3
        yield code, value


def _pcapng_frames(data: bytes):
    pos = 0
    endian = None
    interfaces = {}
    frame_no = 0
    while pos + 12 <= len(data):
        block_start = pos
        block_type_raw = data[pos:pos + 4]
        if block_type_raw == PCAPNG_MAGIC:
            if pos + 12 > len(data):
                raise ValueError("truncated PCAPNG section header")
            bom = data[pos + 8:pos + 12]
            if bom == b"\x4d\x3c\x2b\x1a":
                endian = "<"
            elif bom == b"\x1a\x2b\x3c\x4d":
                endian = ">"
            else:
                raise ValueError("invalid PCAPNG byte-order magic")
            interfaces = {}
        if endian is None:
            raise ValueError("PCAPNG block encountered before section header")
        block_type, block_len = struct.unpack_from(endian + "II", data, pos)
        if block_len < 12 or block_len % 4 or pos + block_len > len(data):
            raise ValueError("invalid/truncated PCAPNG block")
        trailer = struct.unpack_from(endian + "I", data, pos + block_len - 4)[0]
        if trailer != block_len:
            raise ValueError("PCAPNG block length trailer mismatch")
        body_start = pos + 8
        body_end = pos + block_len - 4
        body = data[body_start:body_end]

        if block_type == 1:  # Interface Description Block
            if len(body) < 8:
                raise ValueError("truncated PCAPNG interface block")
            linktype = struct.unpack_from(endian + "H", body, 0)[0]
            ts_resolution = 1e-6
            for code, value in _pcapng_options(body[8:], endian):
                if code == 9 and value:
                    raw = value[0]
                    ts_resolution = (2.0 ** -(raw & 0x7F)) if raw & 0x80 else (10.0 ** -raw)
            interfaces[len(interfaces)] = {
                "linktype": int(linktype),
                "ts_resolution": ts_resolution,
            }
        elif block_type == 6:  # Enhanced Packet Block
            if len(body) < 20:
                raise ValueError("truncated PCAPNG enhanced packet block")
            iface, ts_hi, ts_lo, cap_len, orig_len = struct.unpack_from(endian + "IIIII", body, 0)
            iface_spec = interfaces.get(int(iface))
            if iface_spec is None:
                raise ValueError(f"PCAPNG frame references unknown interface {iface}")
            packet_start = body_start + 20
            packet_end = packet_start + cap_len
            if packet_end > body_end:
                raise ValueError("truncated PCAPNG packet data")
            frame_no += 1
            ticks = (int(ts_hi) << 32) | int(ts_lo)
            yield {
                "frame_no": frame_no,
                "timestamp_seconds": ticks * iface_spec["ts_resolution"],
                "linktype": iface_spec["linktype"],
                "captured_len": int(cap_len),
                "original_len": int(orig_len),
                "frame": data[packet_start:packet_end],
                "start_offset": block_start,
                "end_offset": pos + block_len,
                "format": "pcapng",
                "interface_id": int(iface),
            }
        elif block_type == 3:  # Simple Packet Block: no timestamp/interface id
            if len(body) >= 4:
                orig_len = struct.unpack_from(endian + "I", body, 0)[0]
                frame_bytes = body[4:]
                cap_len = min(int(orig_len), len(frame_bytes))
                iface_spec = interfaces.get(0, {"linktype": -1})
                frame_no += 1
                yield {
                    "frame_no": frame_no,
                    "timestamp_seconds": None,
                    "linktype": iface_spec["linktype"],
                    "captured_len": cap_len,
                    "original_len": int(orig_len),
                    "frame": frame_bytes[:cap_len],
                    "start_offset": block_start,
                    "end_offset": pos + block_len,
                    "format": "pcapng",
                    "interface_id": 0,
                }
        pos += block_len
    if pos != len(data):
        raise ValueError("trailing truncated PCAPNG block")


def parse_capture_frames(data: bytes):
    fmt = sniff_pcap_format(data)
    if fmt == "pcap":
        return list(_pcap_frames(data))
    if fmt == "pcapng":
        return list(_pcapng_frames(data))
    raise ValueError("not a PCAP/PCAPNG file")


def _ip_text(raw: bytes) -> str:
    return str(ipaddress.ip_address(raw))


def decode_network_frame(frame: bytes, linktype: int) -> dict:
    out = {
        "linktype": int(linktype),
        "network": None,
        "transport": None,
        "src_ip": None,
        "dst_ip": None,
        "src_port": None,
        "dst_port": None,
        "transport_payload_hex": None,
        "fragmented": False,
        "decode_status": "unsupported_linktype",
    }
    offset = 0
    ethertype = None
    if linktype == 1:  # Ethernet
        if len(frame) < 14:
            out["decode_status"] = "truncated_ethernet"
            return out
        offset = 14
        ethertype = struct.unpack_from("!H", frame, 12)[0]
        while ethertype in (0x8100, 0x88A8):
            if len(frame) < offset + 4:
                out["decode_status"] = "truncated_vlan"
                return out
            ethertype = struct.unpack_from("!H", frame, offset + 2)[0]
            offset += 4
    elif linktype == 101:  # Raw IP
        if not frame:
            out["decode_status"] = "truncated_raw_ip"
            return out
        version = frame[0] >> 4
        ethertype = 0x0800 if version == 4 else (0x86DD if version == 6 else None)
    elif linktype == 113:  # Linux cooked v1
        if len(frame) < 16:
            out["decode_status"] = "truncated_linux_sll"
            return out
        ethertype = struct.unpack_from("!H", frame, 14)[0]
        offset = 16
    elif linktype == 276:  # Linux cooked v2
        if len(frame) < 20:
            out["decode_status"] = "truncated_linux_sll2"
            return out
        ethertype = struct.unpack_from("!H", frame, 0)[0]
        offset = 20
    else:
        return out

    proto = None
    if ethertype == 0x0800:
        out["network"] = "ipv4"
        if len(frame) < offset + 20:
            out["decode_status"] = "truncated_ipv4"
            return out
        version_ihl = frame[offset]
        if version_ihl >> 4 != 4:
            out["decode_status"] = "invalid_ipv4"
            return out
        ihl = (version_ihl & 0x0F) * 4
        if ihl < 20 or len(frame) < offset + ihl:
            out["decode_status"] = "invalid_ipv4_header"
            return out
        total_len = struct.unpack_from("!H", frame, offset + 2)[0]
        frag = struct.unpack_from("!H", frame, offset + 6)[0]
        out["fragmented"] = bool(frag & 0x3FFF)
        proto = frame[offset + 9]
        out["src_ip"] = _ip_text(frame[offset + 12:offset + 16])
        out["dst_ip"] = _ip_text(frame[offset + 16:offset + 20])
        end = min(len(frame), offset + total_len) if total_len else len(frame)
        offset += ihl
        network_end = end
    elif ethertype == 0x86DD:
        out["network"] = "ipv6"
        if len(frame) < offset + 40 or frame[offset] >> 4 != 6:
            out["decode_status"] = "truncated_or_invalid_ipv6"
            return out
        payload_len = struct.unpack_from("!H", frame, offset + 4)[0]
        proto = frame[offset + 6]
        out["src_ip"] = _ip_text(frame[offset + 8:offset + 24])
        out["dst_ip"] = _ip_text(frame[offset + 24:offset + 40])
        network_end = min(len(frame), offset + 40 + payload_len)
        offset += 40
        if proto not in (6, 17):
            out["decode_status"] = "ipv6_extension_or_unsupported_transport"
            return out
    else:
        out["decode_status"] = "unsupported_network_protocol"
        return out

    if out["fragmented"]:
        out["decode_status"] = "fragmented_ip_not_reassembled"
        return out
    if proto == 17:
        out["transport"] = "udp"
        if network_end < offset + 8:
            out["decode_status"] = "truncated_udp"
            return out
        src_port, dst_port, udp_len = struct.unpack_from("!HHH", frame, offset)
        payload_start = offset + 8
        payload_end = min(network_end, offset + udp_len) if udp_len >= 8 else network_end
        out["src_port"], out["dst_port"] = int(src_port), int(dst_port)
        out["transport_payload_hex"] = frame[payload_start:payload_end].hex().upper()
        out["decode_status"] = "udp_payload"
    elif proto == 6:
        out["transport"] = "tcp"
        if network_end < offset + 20:
            out["decode_status"] = "truncated_tcp"
            return out
        src_port, dst_port = struct.unpack_from("!HH", frame, offset)
        data_offset = ((frame[offset + 12] >> 4) & 0x0F) * 4
        if data_offset < 20 or network_end < offset + data_offset:
            out["decode_status"] = "invalid_tcp_header"
            return out
        out["src_port"], out["dst_port"] = int(src_port), int(dst_port)
        out["transport_payload_hex"] = frame[offset + data_offset:network_end].hex().upper()
        out["decode_status"] = "tcp_payload"
    else:
        out["decode_status"] = f"unsupported_ip_protocol_{proto}"
    return out


def _known_opcodes() -> set[int]:
    try:
        import packet_decode
        return {int(row["opcode"]) for row in packet_decode.list_opcodes("")}
    except Exception:
        return set()


def carve_plaintext_ffxi_chunks(payload: bytes) -> list[dict]:
    """Return chunks only when the complete payload is a structurally valid known FFXI chunk stream."""
    if len(payload) < 4:
        return []
    known = _known_opcodes()
    if not known:
        return []
    chunks = []
    pos = 0
    while pos < len(payload):
        if len(payload) - pos < 4:
            return []
        header = raw_packet_ingest.decode_packet_header(payload[pos:pos + 4].hex())
        opcode = header["opcode"]
        size = header["packet_size"]
        if opcode is None or size is None or size < 4 or size % 4 or pos + size > len(payload):
            return []
        if opcode not in known:
            return []
        raw = payload[pos:pos + size]
        chunks.append({
            "chunk_index": len(chunks),
            "opcode": opcode,
            "packet_size": size,
            "sync_id": header["sync_id"],
            "raw_hex": raw.hex().upper(),
        })
        pos += size
    return chunks if pos == len(payload) else []


def ingest_pcap(con: sqlite3.Connection, capture_id: int, src, relname: str) -> tuple[int, int]:
    data = src.read_bytes(relname)
    fmt = sniff_pcap_format(data)
    if not fmt:
        raise ValueError("not a PCAP/PCAPNG file")
    sha = capture_integrity.sha256_bytes(data)

    # Reingestion owns only rows whose source_file/source_format point back to this exact file.
    con.execute(
        "DELETE FROM capture_structured_records WHERE capture_id=? AND source_file=? AND family='pcap_network'",
        (capture_id, relname),
    )
    old_raw = con.execute(
        """SELECT row_key FROM capture_row_locators
           WHERE capture_id=? AND filename=? AND target_table='capture_raw_packets'""",
        (capture_id, relname),
    ).fetchall()
    for (row_key_raw,) in old_raw:
        try:
            seq = json.loads(row_key_raw).get("seq")
        except Exception:
            seq = None
        if seq is not None:
            con.execute(
                "DELETE FROM capture_raw_packets WHERE capture_id=? AND seq=?",
                (capture_id, int(seq)),
            )
    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND filename=?
             AND target_table IN ('capture_structured_records','capture_raw_packets')""",
        (capture_id, relname),
    )

    frames = parse_capture_frames(data)
    frame_count = chunk_count = 0
    for row in frames:
        decoded = decode_network_frame(row["frame"], row["linktype"])
        ts = _iso_utc(row["timestamp_seconds"])
        key = str(row["frame_no"])
        payload = {
            "pcap_format": row["format"],
            "frame_no": row["frame_no"],
            "interface_id": row["interface_id"],
            "linktype": row["linktype"],
            "captured_len": row["captured_len"],
            "original_len": row["original_len"],
            "timestamp_seconds": row["timestamp_seconds"],
            "timestamp_utc": ts,
            "frame_sha256": hashlib.sha256(row["frame"]).hexdigest(),
            "captured_frame_hex": row["frame"].hex().upper(),
            **decoded,
        }
        con.execute(
            """INSERT OR REPLACE INTO capture_structured_records
               (capture_id,source_file,family,record_key,record_type,ts,zone,entity_id,
                entity_name,item_id,item_name,price,payload_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                capture_id, relname, "pcap_network", key,
                (decoded.get("transport") or decoded.get("network") or "FRAME").upper(),
                ts, None, None, None, None, None, None,
                json.dumps(payload, sort_keys=True),
            ),
        )
        capture_integrity.record_row_locator(
            con, capture_id, relname, "capture_structured_records",
            json.dumps({
                "source_file": relname,
                "family": "pcap_network",
                "record_key": key,
            }, sort_keys=True),
            "pcap-frame",
            source_sha256=sha,
            start_offset=row["start_offset"],
            end_offset=row["end_offset"],
            details={
                "pcap_format": row["format"],
                "frame_no": row["frame_no"],
                "interface_id": row["interface_id"],
                "linktype": row["linktype"],
                "decode_status": decoded["decode_status"],
            },
        )
        frame_count += 1

        if decoded.get("transport") != "udp" or not decoded.get("transport_payload_hex"):
            continue
        udp_payload = bytes.fromhex(decoded["transport_payload_hex"])
        chunks = carve_plaintext_ffxi_chunks(udp_payload)
        for chunk in chunks:
            raw_packet_ingest.insert_raw_packet(
                con, capture_id,
                ts=ts,
                direction="unknown",
                opcode=chunk["opcode"],
                raw_hex=chunk["raw_hex"],
                packet_size=chunk["packet_size"],
                sync_id=chunk["sync_id"],
                source_format="pcap_plaintext_chunk",
                source_native_id=(
                    f"{relname}:frame:{row['frame_no']}:chunk:{chunk['chunk_index']}"
                ),
                filename=relname,
                source_sha256=sha,
                locator_basis="pcap-frame",
                start_offset=row["start_offset"],
                end_offset=row["end_offset"],
                details={
                    "frame_no": row["frame_no"],
                    "chunk_index": chunk["chunk_index"],
                    "src_ip": decoded.get("src_ip"),
                    "dst_ip": decoded.get("dst_ip"),
                    "src_port": decoded.get("src_port"),
                    "dst_port": decoded.get("dst_port"),
                    "direction_basis": "unknown_no_client_server_role_in_pcap",
                    "promotion_basis": "complete_udp_payload_is_known_ffxi_chunk_stream",
                },
            )
            chunk_count += 1
    return frame_count, chunk_count
