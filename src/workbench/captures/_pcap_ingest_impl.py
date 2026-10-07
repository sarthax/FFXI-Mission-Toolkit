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

from workbench.core.services import capture_integrity, raw_packet_ingest, lobby_ingest


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
        out["tcp_seq"] = struct.unpack_from("!I", frame, offset + 4)[0]
        out["tcp_ack"] = struct.unpack_from("!I", frame, offset + 8)[0]
        flags = frame[offset + 13]
        out["tcp_flags"] = {
            "fin": bool(flags & 0x01),
            "syn": bool(flags & 0x02),
            "rst": bool(flags & 0x04),
            "psh": bool(flags & 0x08),
            "ack": bool(flags & 0x10),
            "urg": bool(flags & 0x20),
            "ece": bool(flags & 0x40),
            "cwr": bool(flags & 0x80),
        }
        out["transport_payload_hex"] = frame[offset + data_offset:network_end].hex().upper()
        out["decode_status"] = "tcp_payload"
    else:
        out["decode_status"] = f"unsupported_ip_protocol_{proto}"
    return out


def _endpoint_key(ip: str, port: int) -> str:
    return f"{ip}:{port}"


def reconstruct_tcp_flows(frame_rows: list[dict]) -> list[dict]:
    """Reconstruct contiguous TCP byte ranges conservatively from decoded frames.

    Missing bytes remain explicit gaps. Retransmitted identical bytes are recorded as retransmits.
    Conflicting overlaps are recorded and the first observed byte wins so reconstruction is
    deterministic without inventing a preferred packet.
    """
    flows: dict[tuple, dict] = {}
    for row in frame_rows:
        decoded = row.get("decoded") or {}
        if decoded.get("transport") != "tcp":
            continue
        src_ip, dst_ip = decoded.get("src_ip"), decoded.get("dst_ip")
        src_port, dst_port = decoded.get("src_port"), decoded.get("dst_port")
        if None in (src_ip, dst_ip, src_port, dst_port):
            continue
        ep1 = (src_ip, int(src_port))
        ep2 = (dst_ip, int(dst_port))
        a, b = sorted((ep1, ep2))
        key = (a, b)
        flow = flows.setdefault(key, {
            "endpoint_a": {"ip": a[0], "port": a[1]},
            "endpoint_b": {"ip": b[0], "port": b[1]},
            "segments": {"a_to_b": [], "b_to_a": []},
            "frames": [],
        })
        direction = "a_to_b" if ep1 == a else "b_to_a"
        payload_hex = decoded.get("transport_payload_hex") or ""
        payload = bytes.fromhex(payload_hex) if payload_hex else b""
        flags = decoded.get("tcp_flags") or {}
        flow["frames"].append({
            "frame_no": row["frame_no"],
            "direction": direction,
            "seq": decoded.get("tcp_seq"),
            "ack": decoded.get("tcp_ack"),
            "payload_len": len(payload),
            "flags": flags,
            "timestamp_seconds": row.get("timestamp_seconds"),
        })
        if payload and decoded.get("tcp_seq") is not None:
            payload_seq = (int(decoded["tcp_seq"]) + (1 if flags.get("syn") else 0)) & 0xFFFFFFFF
            flow["segments"][direction].append({
                "frame_no": row["frame_no"],
                "seq": payload_seq,
                "payload": payload,
                "timestamp_seconds": row.get("timestamp_seconds"),
                "start_offset": row.get("start_offset"),
                "end_offset": row.get("end_offset"),
            })

    out = []
    for (a, b), flow in sorted(flows.items()):
        flow_id = f"tcp:{a[0]}:{a[1]}-{b[0]}:{b[1]}"
        flow_out = {
            "flow_id": flow_id,
            "endpoint_a": flow["endpoint_a"],
            "endpoint_b": flow["endpoint_b"],
            "transport": "tcp",
            "frames": flow["frames"],
            "directions": {},
        }
        for direction in ("a_to_b", "b_to_a"):
            segs = sorted(flow["segments"][direction], key=lambda s: (s["seq"], s["frame_no"]))
            if not segs:
                flow_out["directions"][direction] = {
                    "ranges": [],
                    "gaps": [],
                    "retransmissions": [],
                    "overlaps": [],
                    "conflicting_overlaps": [],
                }
                continue

            ranges = []
            gaps = []
            retransmissions = []
            overlaps = []
            conflicts = []
            current_start = None
            current_end = None
            byte_map: dict[int, int] = {}
            byte_frames: dict[int, list[int]] = {}
            min_seq = min(s["seq"] for s in segs)
            max_end = max(s["seq"] + len(s["payload"]) for s in segs)

            for seg in segs:
                seq = seg["seq"]
                payload = seg["payload"]
                fully_seen_same = True
                had_existing = False
                for i, value in enumerate(payload):
                    pos = seq + i
                    if pos in byte_map:
                        had_existing = True
                        byte_frames.setdefault(pos, []).append(seg["frame_no"])
                        if byte_map[pos] != value:
                            fully_seen_same = False
                            conflicts.append({
                                "seq": pos,
                                "first_byte": byte_map[pos],
                                "new_byte": value,
                                "frame_no": seg["frame_no"],
                            })
                    else:
                        fully_seen_same = False
                        byte_map[pos] = value
                        byte_frames[pos] = [seg["frame_no"]]
                if had_existing:
                    overlaps.append({
                        "frame_no": seg["frame_no"],
                        "seq_start": seq,
                        "seq_end": seq + len(payload),
                    })
                    if fully_seen_same:
                        retransmissions.append({
                            "frame_no": seg["frame_no"],
                            "seq_start": seq,
                            "seq_end": seq + len(payload),
                        })

            pos = min_seq
            while pos < max_end:
                if pos not in byte_map:
                    gap_start = pos
                    while pos < max_end and pos not in byte_map:
                        pos += 1
                    gaps.append({"seq_start": gap_start, "seq_end": pos, "length": pos - gap_start})
                    continue
                range_start = pos
                buf = bytearray()
                contributing = set()
                first_ts = last_ts = None
                while pos < max_end and pos in byte_map:
                    buf.append(byte_map[pos])
                    for frame_no in byte_frames.get(pos, []):
                        contributing.add(frame_no)
                    pos += 1
                for seg in segs:
                    seg_end = seg["seq"] + len(seg["payload"])
                    if seg["seq"] < pos and seg_end > range_start:
                        ts = seg.get("timestamp_seconds")
                        if ts is not None:
                            first_ts = ts if first_ts is None else min(first_ts, ts)
                            last_ts = ts if last_ts is None else max(last_ts, ts)
                ranges.append({
                    "seq_start": range_start,
                    "seq_end": pos,
                    "length": len(buf),
                    "payload_hex": bytes(buf).hex().upper(),
                    "frame_numbers": sorted(contributing),
                    "first_timestamp_seconds": first_ts,
                    "last_timestamp_seconds": last_ts,
                })

            flow_out["directions"][direction] = {
                "ranges": ranges,
                "gaps": gaps,
                "retransmissions": retransmissions,
                "overlaps": overlaps,
                "conflicting_overlaps": conflicts,
            }
        out.append(flow_out)
    return out


def _known_opcodes() -> set[int]:
    try:
        from workbench.packets import decode as packet_decode
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


def ingest_pcap(con: sqlite3.Connection, capture_id: int, src, relname: str) -> tuple[int, int, int, int]:
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
        "DELETE FROM capture_network_messages WHERE capture_id=? AND source_file=?",
        (capture_id, relname),
    )
    con.execute(
        "DELETE FROM capture_network_ranges WHERE capture_id=? AND source_file=?",
        (capture_id, relname),
    )
    con.execute(
        "DELETE FROM capture_network_flows WHERE capture_id=? AND source_file=?",
        (capture_id, relname),
    )
    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND filename=?
             AND target_table IN (
                 'capture_structured_records','capture_raw_packets',
                 'capture_network_flows','capture_network_ranges','capture_network_messages'
             )""",
        (capture_id, relname),
    )

    frames = parse_capture_frames(data)
    decoded_frames = []
    frame_count = chunk_count = 0
    for row in frames:
        decoded = decode_network_frame(row["frame"], row["linktype"])
        decoded_frames.append({**row, "decoded": decoded})
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

    flow_count = range_count = message_count = 0
    for flow in reconstruct_tcp_flows(decoded_frames):
        classification = lobby_ingest.classify_flow(flow["directions"])
        frame_meta = flow["frames"]
        timestamps = [f["timestamp_seconds"] for f in frame_meta if f["timestamp_seconds"] is not None]
        payload_frames = sum(1 for f in frame_meta if f["payload_len"] > 0)
        flow_details = {
            "endpoint_role_basis": (
                "validated_lobby_command_direction"
                if classification["endpoint_roles"] else "canonical_endpoint_sort_only"
            ),
            "protocol_family": classification["protocol_family"],
            "classification_validated": classification["classification_validated"],
            "classification_basis": classification.get("validation_basis"),
            "endpoint_roles": classification.get("endpoint_roles"),
            "role_status": classification.get("role_status"),
            "frames": frame_meta,
            "direction_summaries": {},
        }
        for direction, d in flow["directions"].items():
            flow_details["direction_summaries"][direction] = {
                "range_count": len(d["ranges"]),
                "gap_count": len(d["gaps"]),
                "retransmission_count": len(d["retransmissions"]),
                "overlap_count": len(d["overlaps"]),
                "conflicting_overlap_count": len(d["conflicting_overlaps"]),
                "gaps": d["gaps"],
                "retransmissions": d["retransmissions"],
                "overlaps": d["overlaps"],
                "conflicting_overlaps": d["conflicting_overlaps"],
            }

        flow_count += 1
        con.execute(
            """INSERT OR REPLACE INTO capture_network_flows
               (capture_id,source_file,flow_id,transport,
                endpoint_a_ip,endpoint_a_port,endpoint_b_ip,endpoint_b_port,
                first_ts,last_ts,frame_count,payload_frame_count,metadata_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                capture_id, relname, flow["flow_id"], "tcp",
                flow["endpoint_a"]["ip"], flow["endpoint_a"]["port"],
                flow["endpoint_b"]["ip"], flow["endpoint_b"]["port"],
                _iso_utc(min(timestamps)) if timestamps else None,
                _iso_utc(max(timestamps)) if timestamps else None,
                len(frame_meta), payload_frames,
                json.dumps(flow_details, sort_keys=True),
            ),
        )
        capture_integrity.record_row_locator(
            con, capture_id, relname, "capture_network_flows",
            json.dumps({
                "source_file": relname,
                "flow_id": flow["flow_id"],
            }, sort_keys=True),
            "pcap-flow",
            source_sha256=sha,
            details={
                "flow_id": flow["flow_id"],
                "frame_numbers": [f["frame_no"] for f in frame_meta],
                "transport": "tcp",
            },
        )

        for direction, d in flow["directions"].items():
            for range_index, rr in enumerate(d["ranges"]):
                anomalies = {
                    "gaps_before_or_after": d["gaps"],
                    "retransmissions": [
                        x for x in d["retransmissions"]
                        if x["seq_start"] < rr["seq_end"] and x["seq_end"] > rr["seq_start"]
                    ],
                    "overlaps": [
                        x for x in d["overlaps"]
                        if x["seq_start"] < rr["seq_end"] and x["seq_end"] > rr["seq_start"]
                    ],
                    "conflicting_overlaps": [
                        x for x in d["conflicting_overlaps"]
                        if rr["seq_start"] <= x["seq"] < rr["seq_end"]
                    ],
                    "missing_bytes_fabricated": False,
                    "byte_selection_rule": "first_observed_byte_wins_conflicts_recorded",
                }
                range_count += 1
                con.execute(
                    """INSERT OR REPLACE INTO capture_network_ranges
                       (capture_id,source_file,flow_id,direction,range_index,
                        seq_start,seq_end,first_ts,last_ts,payload_hex,
                        frame_numbers_json,anomalies_json)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        capture_id, relname, flow["flow_id"], direction, range_index,
                        rr["seq_start"], rr["seq_end"],
                        _iso_utc(rr["first_timestamp_seconds"]),
                        _iso_utc(rr["last_timestamp_seconds"]),
                        rr["payload_hex"],
                        json.dumps(rr["frame_numbers"]),
                        json.dumps(anomalies, sort_keys=True),
                    ),
                )
                contributing_frames = [
                    row for row in decoded_frames if row["frame_no"] in set(rr["frame_numbers"])
                ]
                start_offsets = [row["start_offset"] for row in contributing_frames if row.get("start_offset") is not None]
                end_offsets = [row["end_offset"] for row in contributing_frames if row.get("end_offset") is not None]
                capture_integrity.record_row_locator(
                    con, capture_id, relname, "capture_network_ranges",
                    json.dumps({
                        "source_file": relname,
                        "flow_id": flow["flow_id"],
                        "direction": direction,
                        "range_index": range_index,
                    }, sort_keys=True),
                    "pcap-tcp-range",
                    source_sha256=sha,
                    start_offset=min(start_offsets) if start_offsets else None,
                    end_offset=max(end_offsets) if end_offsets else None,
                    details={
                        "flow_id": flow["flow_id"],
                        "direction": direction,
                        "seq_start": rr["seq_start"],
                        "seq_end": rr["seq_end"],
                        "frame_numbers": rr["frame_numbers"],
                        "locator_note": "offset span covers contributing frames; exact frames listed explicitly",
                    },
                )
        for message in classification["messages"]:
            validation = message["validation"]
            fields = message.get("fields") or {}
            direction = message["direction"]
            range_index = int(message["range_index"])
            message_index = int(message["message_index"])
            seq_start = int(message["seq_start"])
            seq_end = int(message["seq_end"])
            direction_frames = []
            for fm in frame_meta:
                if fm["direction"] != direction or fm["payload_len"] <= 0 or fm.get("seq") is None:
                    continue
                payload_seq = (int(fm["seq"]) + (1 if (fm.get("flags") or {}).get("syn") else 0)) & 0xFFFFFFFF
                payload_end = payload_seq + int(fm["payload_len"])
                if payload_seq < seq_end and payload_end > seq_start:
                    direction_frames.append(int(fm["frame_no"]))
            direction_frames = sorted(set(direction_frames))

            provenance = {
                "validation_basis": classification.get("validation_basis"),
                "md5_valid": bool(validation.get("md5_valid")),
                "declared_packet_size": validation.get("packet_size"),
                "command_direction": validation.get("command_direction"),
                "endpoint_roles": classification.get("endpoint_roles"),
                "role_status": classification.get("role_status"),
                "frame_numbers": direction_frames,
                "sensitive_field_policy": "raw_packet_retained_decoded_fields_omit_auth_password_material",
            }
            con.execute(
                """INSERT OR REPLACE INTO capture_network_messages
                   (capture_id,source_file,flow_id,protocol_family,direction,range_index,
                    message_index,seq_start,seq_end,command,command_name,validation_status,
                    raw_hex,fields_json,provenance_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    capture_id, relname, flow["flow_id"], "ffxi_lobby", direction,
                    range_index, message_index, seq_start, seq_end,
                    int(validation["command"]), validation["command_name"], "MD5_VALID",
                    message["raw_hex"], json.dumps(fields, sort_keys=True),
                    json.dumps(provenance, sort_keys=True),
                ),
            )
            contributing = [
                row for row in decoded_frames if row["frame_no"] in set(direction_frames)
            ]
            offsets_start = [row["start_offset"] for row in contributing if row.get("start_offset") is not None]
            offsets_end = [row["end_offset"] for row in contributing if row.get("end_offset") is not None]
            capture_integrity.record_row_locator(
                con, capture_id, relname, "capture_network_messages",
                json.dumps({
                    "source_file": relname,
                    "flow_id": flow["flow_id"],
                    "direction": direction,
                    "range_index": range_index,
                    "message_index": message_index,
                }, sort_keys=True),
                "pcap-tcp-message",
                source_sha256=sha,
                start_offset=min(offsets_start) if offsets_start else None,
                end_offset=max(offsets_end) if offsets_end else None,
                details={
                    "flow_id": flow["flow_id"],
                    "protocol_family": "ffxi_lobby",
                    "command": int(validation["command"]),
                    "command_name": validation["command_name"],
                    "seq_start": seq_start,
                    "seq_end": seq_end,
                    "frame_numbers": direction_frames,
                    "md5_valid": True,
                },
            )
            message_count += 1

    return frame_count, chunk_count, flow_count, range_count, message_count
