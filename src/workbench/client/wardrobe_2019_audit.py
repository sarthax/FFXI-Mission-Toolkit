"""Exact-build read-only evidence gate for 2019 FFXiMain.dll Wardrobe research.

Do not treat a static anchor as proof that any handler executes, that a
binary patch is safe, or that unobserved features are absent. No binary writes.
"""
from __future__ import annotations

import hashlib
import struct

from workbench.client.pol1_unpack import Pol1Error, _section, unpack_pol1

EXPECTED_SHA256 = "514653a260c51eaec25d88510e51a86fb2a4abd9867f53d5f45a9ccf840f060f"
EXPECTED_DECODED_SHA256 = "af2126c057d86559bfad2e164f7f7fd0a26bbc89ab29ea9cbde5cea807c7d2b8"
MAX_INPUT_BYTES = 16 * 1024 * 1024
# Observed .data command records are 24 bytes each; these RVAs belong ONLY to
# the exact SHA-verified 2019 retail build.
FIRST_WARDROBE_COMMAND_RVA = 0x34B1B0
RECORD_BYTES = 24
EXPECTED_COMMAND_IDS = {
    "/wardrobe": 111, "/wardrobe2": 112,
    "/wardrobe3": 113, "/wardrobe4": 114,
}
# Verified short code-byte anchors with separately inspected x86 disassembly.
# These are addresses in *decoded* .text, not on-disk PE offsets.
ANCHORS = {
    "packet_0x1c_registration": (0xE85D0, "68c0970e106a1c"),
    "capacity_u8_getter": (0xE8C70, "8a8408ed520100"),
    "capacity_u16_getter": (0xE8C92, "668b8448fa520100"),
    "packet_0x1c_u8_destination": (0xE97CD, "8db1ed520100"),
    "packet_0x1c_u16_destination": (0xE97E3, "8db9fa520100"),
    "item_13_container_sentinel": (0xE8844, "83f80d"),
    "packet_0x1e_item_record_base": (0xE9823, "8dbc8260980000"),
    "packet_0x1f_item_record_base": (0xE9883, "8d948160980000"),
    "packet_0x20_item_record_base": (0xE996D, "8d948160980000"),
}


def inspect_command_table(data: bytes, data_rva: int) -> dict:
    """Report exact table entries and their IDs; do not infer runtime support."""
    offset = FIRST_WARDROBE_COMMAND_RVA - data_rva
    entries = []
    for i, (name, expected_id) in enumerate(EXPECTED_COMMAND_IDS.items()):
        at = offset + i * RECORD_BYTES
        if at < 0 or at + RECORD_BYTES > len(data):
            entries.append({"name": name, "rva": FIRST_WARDROBE_COMMAND_RVA + i * RECORD_BYTES,
                            "expected_id": expected_id, "observed_id": None,
                            "exact_record_match": False})
            continue
        raw = data[at:at + RECORD_BYTES]
        observed_id = struct.unpack_from("<H", raw, 0x14)[0]
        expected_name = name.encode("ascii").ljust(16, b"\0")
        entries.append({
            "name": name, "rva": FIRST_WARDROBE_COMMAND_RVA + i * RECORD_BYTES,
            "expected_id": expected_id, "observed_id": observed_id,
            "exact_record_match": raw[:16] == expected_name and observed_id == expected_id,
        })
    new_names = ("/wardrobe5", "/wardrobe6", "/wardrobe7", "/wardrobe8")
    new_entries_found = {
        name: data.find(name.encode("ascii").ljust(16, b"\0")) >= 0
        for name in new_names
    }
    return {"record_size_bytes": RECORD_BYTES, "entries": entries,
            "additional_command_records_found": new_entries_found,
            "legacy_commands_verified": all(x["exact_record_match"] for x in entries),
            "caution": "Nonmatch is UNKNOWN for runtime feature support, not proof of absence."}


def inspect_decoded_sites(decoded: bytes, decoded_rva: int = 0x1000) -> dict:
    """Conservatively compare selected static opcode anchors at decoded RVAs."""
    checks = {}
    for name, (rva, hex_pattern) in ANCHORS.items():
        expected = bytes.fromhex(hex_pattern)
        off = rva - decoded_rva
        checks[name] = {
            "rva": f"0x{rva:X}",
            "matches_expected_bytes": (
                off >= 0 and off + len(expected) <= len(decoded)
                and decoded[off:off + len(expected)] == expected
            ),
        }
    return {"anchors": checks, "all_static_anchors_match": all(
        item["matches_expected_bytes"] for item in checks.values()
    ), "caution": "Static bytes only; full control flow, packet bounds, and execution unverified."}


def audit_2019_wardrobe(image: bytes) -> dict:
    """Read-only, exact-hash gated summary; never returns decoded executable bytes."""
    if not isinstance(image, bytes) or not 0 < len(image) <= MAX_INPUT_BYTES:
        raise Pol1Error("expected nonempty DLL bytes within the 16 MiB limit")
    source_hash = hashlib.sha256(image).hexdigest()
    if source_hash != EXPECTED_SHA256:
        return {"status": "UNKNOWN_BUILD_FINGERPRINT", "source_sha256": source_hash,
                "expected_sha256": EXPECTED_SHA256, "do_not_apply_2019_assumptions": True}
    section = _section(image, b".data")
    at, size = section["raw_start"], section["raw_size"]
    if at > len(image) or size > len(image) - at or size <= 0:
        raise Pol1Error("invalid .data raw bounds")
    original = unpack_pol1(image)
    commands = inspect_command_table(image[at:at + size], section["rva"])
    decoded_hash_ok = original["sha256"] == EXPECTED_DECODED_SHA256
    sites = inspect_decoded_sites(original["bytes"], original["base_rva"])
    proven = commands["legacy_commands_verified"] and decoded_hash_ok and sites["all_static_anchors_match"]
    return {
        "status": "LEGACY_2019_STATIC_GATES_VERIFIED" if proven else "INCOMPLETE_STATIC_EVIDENCE",
        "source_sha256": source_hash, "decoded_sha256": original["sha256"],
        "decoded_sha256_verified": decoded_hash_ok,
        "commands": commands, "decoded_sites": sites,
        "observed_legacy_container_sentinel": 13 if proven else None,
        "unsafe_to_assume_supported_container_ids": [13, 14, 15, 16],
        "evidence_scope": "Exact 2019 build, static x86/code/data observations only.",
        "safety_decision": "NO_GO_SEND_NEW_CONTAINER_IDS_TO_2019_CLIENT",
        "not_established": [
            "All packet ingress paths or complete container bounds checks",
            "Runtime invocation of the observed functions",
            "2019 support for expanded item-storage allocation",
            "2019 Wardrobe 5-8 menus, command handlers or packet protocol",
        ],
    }
