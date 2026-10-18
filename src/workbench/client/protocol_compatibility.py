"""Read-only versioned client packet-layout evidence records.

This is deliberately separate from binary presence probes: an address/offset assertion
requires traceable analysis provenance, and no record by itself proves runtime compatibility.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

STATUSES = frozenset({"VERIFIED", "INFERRED", "UNKNOWN"})
HEX = re.compile(r"^0x[0-9a-fA-F]+$")
SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


def _offset(value: str) -> int:
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ValueError("offset must be a hex string such as 0x14")
    return int(value, 16)


def validate_record(record: dict) -> dict:
    """Validate and return a defensive copy; do not promote assertions to VERIFIED."""
    if not isinstance(record, dict) or record.get("schema_version") != 1:
        raise ValueError("unsupported protocol record schema_version")
    if not isinstance(record.get("packet_id"), str) or not HEX.fullmatch(record["packet_id"]):
        raise ValueError("packet_id must be hexadecimal")
    if int(record["packet_id"], 16) > 0x1FF:
        raise ValueError("packet_id exceeds FFXI packet ID range")
    if record.get("direction") not in ("server_to_client", "client_to_server"):
        raise ValueError("direction is required")
    builds = record.get("builds")
    if not isinstance(builds, list) or not builds:
        raise ValueError("at least one build is required")
    seen = set()
    for build in builds:
        if not isinstance(build, dict):
            raise ValueError("build must be an object")
        name, digest = build.get("build"), build.get("sha256")
        if not isinstance(name, str) or not name.strip() or not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ValueError("build name and full binary sha256 required")
        if digest.lower() in seen:
            raise ValueError("duplicate binary fingerprint")
        seen.add(digest.lower())
        status = build.get("status")
        if status not in STATUSES:
            raise ValueError("explicit evidence status required")
        sources = build.get("sources")
        if not isinstance(sources, list) or not sources or any(not isinstance(s, str) or not s.strip() for s in sources):
            raise ValueError("source references required")
        fields = build.get("fields")
        if not isinstance(fields, list) or not fields:
            raise ValueError("field evidence required")
        field_names = set()
        for field in fields:
            if not isinstance(field, dict):
                raise ValueError("field must be an object")
            key = field.get("name")
            if not isinstance(key, str) or not key.strip() or key in field_names:
                raise ValueError("unique field name required")
            field_names.add(key)
            start = _offset(field.get("offset"))
            width = field.get("width_bytes")
            count = field.get("count")
            if type(width) is not int or width < 1 or type(count) is not int or count < 1:
                raise ValueError("positive integer width_bytes and count required")
            if start + width * count > 0x10000:
                raise ValueError("unreasonably large field span")
            if field.get("status") not in STATUSES:
                raise ValueError("field evidence status required")
            if not isinstance(field.get("source"), str) or not field["source"].strip():
                raise ValueError("field source required")
    return json.loads(json.dumps(record))


def load_record(path: str | Path) -> dict:
    return validate_record(json.loads(Path(path).read_text(encoding="utf-8")))


def compare_builds(record: dict) -> list[dict]:
    """Report field differences without declaring two client builds compatible."""
    record = validate_record(record)
    builds = record["builds"]
    if len(builds) != 2:
        raise ValueError("comparison requires exactly two builds")
    by_build = [{f["name"]: f for f in b["fields"]} for b in builds]
    changes = []
    for name in sorted(set(by_build[0]) | set(by_build[1])):
        left, right = by_build[0].get(name), by_build[1].get(name)
        if left is None or right is None:
            changes.append({"field": name, "change": "missing_in_one_build"})
        elif any(left[k] != right[k] for k in ("offset", "width_bytes", "count")):
            changes.append({"field": name, "change": "layout_changed",
                            "old": {k: left[k] for k in ("offset", "width_bytes", "count")},
                            "new": {k: right[k] for k in ("offset", "width_bytes", "count")}})
    return changes
