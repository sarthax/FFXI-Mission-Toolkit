"""Lossless PCAP/PCAPNG ingestion for FFXI capture research.

This adapter preserves network frames and decoded IP/transport metadata. It deliberately does
NOT insert network payloads into capture_raw_packets: a raw socket capture may contain encrypted,
framed, lobby/world, search, or unrelated traffic, so claiming that an arbitrary TCP/UDP payload
is an already-decoded FFXI application packet would fabricate semantics.
"""
from __future__ import annotations

import ipaddress
import json
import struct

from workbench.core.services import capture_integrity


PCAP_MAGICS = {
    b"\xd4\xc3\xb2\xa1": ("<", 1_000_000.0),
    b"\xa1\xb2\xc3\xd4": (">", 1_000_000.0),
    b"\x4d\x3c\xb2\xa1": ("<", 1_000_000_000.0),
    b"\xa1\xb2\x3c\x4d": (">", 1_000_000_000.0),
}
PCAPNG_MAGIC = b"\x0a\x0d\x0d\x0a"

# LandSandBoat's documented network surface; this is a transport-level hint only.
KNOWN_FFXI_PORT_HINTS = {
    54230: "zone/map",
    54231: "zone/map-alt",
    54001: "login/lobby",
    54002: "login/lobby",
    51220: "search/world",
}


def sniff_format(data: bytes) -> str | None:
    if len(data) >= 4 and data[:4] in PCAP_MAGICS:
        return "pcap"
    if len(data) >= 12 and data[:4] == PCAPNG_MAGIC:
        return "pcapng"
    return None


def _service_hint(src_port: int | None, dst_port: int | None) -> str | None:
    hints = []
    for port in (src_port, dst_port):
        if port in KNOWN_FFXI_PORT_HINTS:
            hints.append(f"{port}:{KNOWN_FFXI_PORT_HINTS[port]}")
    return ",".join(dict.fromkeys(hints)) or None


def _ipv4(data: bytes):
    if len(data) < 20 or data[0] >> 4 != 4:
        return None
    ihl = (data[0] & 0x0F) * 4
    if ihl < 20 or len(data) < ihl:
        return None
    total_len = struct.unpack("!H", data[2:4])[0]
    proto = data[9]
    src = str(ipaddress.IPv4Address(data[12:16]))
    dst = str(ipaddress.IPv4Address(data[16:20]))
    payload_end = min(len(data), total_len or len(data))
    return src, dst, proto, data[ihl:payload_end]


def _ipv6(data: bytes):
    if len(data) < 40 or data[0] >> 4 != 6:
        return None
    next_header = data[6]
    payload_len = struct.unpack("!H", data[4:6])[0]
    src = str(ipaddress.IPv6Address(data[8:24]))
    dst = str(ipaddress.IPv6Address(data[24:40]))
    # Extension-header walking is intentionally not guessed here. Common direct TCP/UDP frames
    # are decoded; extension-header traffic stays as IP-level evidence with no transport fields.
    end = min(len(data), 40 + payload_len)
    return src, dst, next_header, data[40:end]


def decode_frame(frame: bytes, linktype: int) -> dict:
    network = frame
    ethertype = None
    if linktype == 1:  # DLT_EN10MB
        if len(frame) < 14:
            return {}
        ethertype = struct.unpack("!H", frame[12:14])[0]
        offset = 14
        if ethertype in (0x8100, 0x88A8) and len(frame) >= 18:
            ethertype = struct.unpack("!H", frame[16:18])[0]
            offset = 18
        network = frame[offset:]
    elif linktype == 101:  # DLT_RAW
        version = network[0] >> 4 if network else 0
        ethertype = 0x0800 if version == 4 else (0x86DD if version == 6 else None)
    else:
        return {"linktype": linktype}

    decoded = _ipv4(network) if ethertype == 0x0800 else (
        _ipv6(network) if ethertype == 0x86DD else None
    )
    if not decoded:
        return {"linktype": linktype, "ethertype": ethertype}

    src_ip, dst_ip, proto, transport_data = decoded
    out = {
        "linktype": linktype,
        "ethertype": ethertype,
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "ip_protocol": proto,
        "transport": {6: "TCP", 17: "UDP"}.get(proto, str(proto)),
        "src_port": None,
        "dst_port": None,
        "payload_hex": None,
    }
    if proto == 6 and len(transport_data) >= 20:
        src_port, dst_port = struct.unpack("!HH", transport_data[:4])
        data_offset = (transport_data[12] >> 4) * 4
        payload = transport_data[data_offset:] if data_offset >= 20 else b""
        out.update(src_port=src_port, dst_port=dst_port, payload_hex=payload.hex().upper())
    elif proto == 17 and len(transport_data) >= 8:
        src_port, dst_port, udp_len = struct.unpack("!HHH", transport_data[:6])
        end = min(len(transport_data), udp_len) if udp_len >= 8 else len(transport_data)
        payload = transport_data[8:end]
        out.update(src_port=src_port, dst_port=dst_port, payload_hex=payload.hex().upper())
    out["service_hint"] = _service_hint(out["src_port"], out["dst_port"])
    return out


def parse_pcap(data: bytes) -> list[dict]:
    if len(data) < 24 or data[:4] not in PCAP_MAGICS:
        raise ValueError("not a supported classic PCAP file")
    endian, fraction_scale = PCAP_MAGICS[data[:4]]
    _magic, _major, _minor, _tz, _sig, _snap, linktype = struct.unpack(
        endian + "IHHIIII", data[:24]
    )
    records = []
    offset = 24
    index = 0
    while offset + 16 <= len(data):
        record_start = offset
        ts_sec, ts_frac, caplen, origlen = struct.unpack(endian + "IIII", data[offset:offset+16])
        offset += 16
        if caplen > len(data) - offset:
            break
        frame = data[offset:offset+caplen]
        offset += caplen
        meta = decode_frame(frame, linktype)
        records.append({
            "index": index,
            "ts": ts_sec + (ts_frac / fraction_scale),
            "linktype": linktype,
            "captured_len": caplen,
            "frame_len": origlen,
            "frame_hex": frame.hex().upper(),
            "start_offset": record_start,
            "end_offset": offset,
            **meta,
        })
        index += 1
    return records


def _pcapng_options(data: bytes, endian: str) -> dict[int, list[bytes]]:
    out: dict[int, list[bytes]] = {}
    pos = 0
    while pos + 4 <= len(data):
        code, length = struct.unpack(endian + "HH", data[pos:pos+4])
        pos += 4
        if code == 0:
            break
        value = data[pos:pos+length]
        pos += (length + 3) & ~3
        out.setdefault(code, []).append(value)
    return out


def parse_pcapng(data: bytes) -> list[dict]:
    if len(data) < 12 or data[:4] != PCAPNG_MAGIC:
        raise ValueError("not a PCAPNG file")
    records = []
    interfaces = {}
    offset = 0
    endian = "<"
    index = 0
    while offset + 12 <= len(data):
        block_start = offset
        block_type_raw = data[offset:offset+4]
        if block_type_raw == PCAPNG_MAGIC:
            bom = data[offset+8:offset+12]
            if bom == b"\x4d\x3c\x2b\x1a":
                endian = "<"
            elif bom == b"\x1a\x2b\x3c\x4d":
                endian = ">"
            else:
                raise ValueError("PCAPNG section has unknown byte-order magic")
        block_type = struct.unpack(endian + "I", block_type_raw)[0]
        total_len = struct.unpack(endian + "I", data[offset+4:offset+8])[0]
        if total_len < 12 or offset + total_len > len(data):
            break
        body = data[offset+8:offset+total_len-4]
        trailer = struct.unpack(endian + "I", data[offset+total_len-4:offset+total_len])[0]
        if trailer != total_len:
            raise ValueError("PCAPNG block length mismatch")

        if block_type == 1 and len(body) >= 8:  # Interface Description Block
            linktype, _reserved, snaplen = struct.unpack(endian + "HHI", body[:8])
            opts = _pcapng_options(body[8:], endian)
            ts_scale = 1_000_000.0
            if 9 in opts and opts[9] and opts[9][0]:
                raw = opts[9][0][0]
                ts_scale = float(2 ** (raw & 0x7F)) if raw & 0x80 else float(10 ** raw)
            interfaces[len(interfaces)] = {
                "linktype": linktype,
                "snaplen": snaplen,
                "ts_scale": ts_scale,
            }
        elif block_type == 6 and len(body) >= 20:  # Enhanced Packet Block
            interface_id, ts_high, ts_low, caplen, origlen = struct.unpack(
                endian + "IIIII", body[:20]
            )
            info = interfaces.get(interface_id, {"linktype": 1, "ts_scale": 1_000_000.0})
            packet_start = 20
            frame = body[packet_start:packet_start+caplen]
            ticks = (ts_high << 32) | ts_low
            meta = decode_frame(frame, int(info["linktype"]))
            records.append({
                "index": index,
                "ts": ticks / float(info["ts_scale"]),
                "linktype": int(info["linktype"]),
                "captured_len": caplen,
                "frame_len": origlen,
                "frame_hex": frame.hex().upper(),
                "start_offset": block_start,
                "end_offset": offset + total_len,
                **meta,
            })
            index += 1
        offset += total_len
    return records


def ingest_network_capture(con, capture_id: int, src, relname: str, source_format: str) -> int:
    source_bytes = src.read_bytes(relname)
    source_sha256 = capture_integrity.sha256_bytes(source_bytes)
    rows = parse_pcap(source_bytes) if source_format == "pcap" else parse_pcapng(source_bytes)
    con.execute(
        """DELETE FROM capture_row_locators
           WHERE capture_id=? AND filename=? AND target_table='capture_network_observations'""",
        (capture_id, relname),
    )
    # Existing source-native rows are reused on re-ingest so unrelated network sources keep IDs.
    existing = {
        native: seq for seq, native in con.execute(
            """SELECT seq,source_native_id FROM capture_network_observations
               WHERE capture_id=? AND source_format=? AND source_native_id LIKE ?""",
            (capture_id, source_format, f"{relname}:%"),
        ).fetchall()
    }
    for row in rows:
        native = f"{relname}:frame:{row['index']}"
        seq = existing.get(native)
        if seq is None:
            seq = int(con.execute(
                "SELECT COALESCE(MAX(seq),-1)+1 FROM capture_network_observations WHERE capture_id=?",
                (capture_id,),
            ).fetchone()[0])
        con.execute(
            """INSERT OR REPLACE INTO capture_network_observations
               (capture_id,seq,ts,linktype,src_ip,dst_ip,src_port,dst_port,transport,
                payload_hex,frame_hex,frame_len,captured_len,service_hint,source_format,source_native_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                capture_id, seq, row.get("ts"), row.get("linktype"),
                row.get("src_ip"), row.get("dst_ip"), row.get("src_port"), row.get("dst_port"),
                row.get("transport"), row.get("payload_hex"), row.get("frame_hex"),
                row.get("frame_len"), row.get("captured_len"), row.get("service_hint"),
                source_format, native,
            ),
        )
        capture_integrity.record_row_locator(
            con, capture_id, relname, "capture_network_observations",
            json.dumps({"seq": seq}, sort_keys=True), "binary-frame",
            source_sha256=source_sha256,
            start_offset=row.get("start_offset"), end_offset=row.get("end_offset"),
            details={
                "source_format": source_format,
                "source_native_id": native,
                "linktype": row.get("linktype"),
                "src_ip": row.get("src_ip"),
                "dst_ip": row.get("dst_ip"),
                "src_port": row.get("src_port"),
                "dst_port": row.get("dst_port"),
                "transport": row.get("transport"),
                "service_hint": row.get("service_hint"),
            },
        )
    return len(rows)
