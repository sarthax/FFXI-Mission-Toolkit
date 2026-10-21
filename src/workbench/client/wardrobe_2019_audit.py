"""Read-only exact-build inventory boundary audit for the archived 2019 FFXiMain.dll.

This does NOT patch binaries, decode arbitrary versions, or authorize the server
to send new container IDs. Static code windows are address-limited observations,
not a control-flow proof that any handler executes or lacks upstream guards.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct

from workbench.client.pol1_unpack import Pol1Error, _section, unpack_pol1


LEGACY_SHA256 = "514653a260c51eaec25d88510e51a86fb2a4abd9867f53d5f45a9ccf840f060f"
LEGACY_FILE_SIZE = 2_870_352
LEGACY_DECODED_SHA256 = "af2126c057d86559bfad2e164f7f7fd0a26bbc89ab29ea9cbde5cea807c7d2b8"
LEGACY_TEXT_RVA = 0x1000

RECORD_BASE = 0x9860
RECORD_BYTES = 44
SLOTS_PER_CONTAINER = 81
KNOWN_CAPACITY_COUNT = 13
CAPACITY8 = 0x152ED
CAPACITY16 = 0x152FA
CAPACITY16_END = CAPACITY16 + 13 * 2
OBSERVED_OTHER_STATE = 0x14F78

# Scoped to the verified 2019 decoded image. Never use these RVAs for another build.
# Compare scalar offsets and tiny generic instruction motifs without recording
# proprietary function bytes in the report or source control.
CODE_WINDOWS = (
    ("capacity_u8_reader", 0xE8C60, 28, (CAPACITY8,), ()),
    ("capacity_u16_reader", 0xE8C80, 28, (CAPACITY16,), ()),
    ("capacity_packet_copy_candidate", 0xE97C0, 65,
     (CAPACITY8, CAPACITY16), (bytes((0x8D, 0x50, 0x04)), bytes((0x8D, 0x70, 0x14)))),
    ("item_record_handler_candidate", 0xE9940, 85,
     (RECORD_BASE,), (bytes((0x8A, 0x43, 0x0E)), bytes((0x8A, 0x4B, 0x0F)))),
    ("inventory_mode_dispatch_candidate", 0x1D4CA0, 34, (0x101D4DF8,),
     (bytes((0x83, 0xC0, 0xFE)), bytes((0x83, 0xF8, 0x0A)))),
    ("inventory_cache_dispatch_candidate", 0x1D4E80, 32, (0x101D4F64,),
     (bytes((0x83, 0xC0, 0xFE)), bytes((0x83, 0xF8, 0x0A)))),
)


def _range_overlap(first: int, end: int, other_first: int, other_end: int) -> bool:
    return max(first, other_first) < min(end, other_end)


def legacy_layout_risk() -> dict:
    """Pure arithmetic: evaluate a *hypothetical* container-13 record range."""
    first = RECORD_BASE + KNOWN_CAPACITY_COUNT * SLOTS_PER_CONTAINER * RECORD_BYTES
    end = first + SLOTS_PER_CONTAINER * RECORD_BYTES
    return {
        "existing_capacity_entries": KNOWN_CAPACITY_COUNT,
        "record_base_offset": RECORD_BASE,
        "slot_count_per_container": SLOTS_PER_CONTAINER,
        "record_bytes_per_slot": RECORD_BYTES,
        "record_stride_bytes": SLOTS_PER_CONTAINER * RECORD_BYTES,
        "hypothetical_container_13_start": first,
        "hypothetical_container_13_end_exclusive": end,
        "observed_other_state_offset": OBSERVED_OTHER_STATE,
        "overlaps_observed_other_state": first <= OBSERVED_OTHER_STATE < end,
        "capacity8_offset": CAPACITY8,
        "capacity8_end_exclusive": CAPACITY16,
        "overlaps_capacity8": _range_overlap(first, end, CAPACITY8, CAPACITY16),
        "capacity16_offset": CAPACITY16,
        "capacity16_end_exclusive": CAPACITY16_END,
        "overlaps_capacity16": _range_overlap(first, end, CAPACITY16, CAPACITY16_END),
        "interpretation": "INFERRED_OVERLAP_NOT_A_VALID_ALLOCATION",
    }


def _verify_code_windows(decoded: bytes) -> list[dict]:
    observations = []
    for name, rva, width, immediates, motifs in CODE_WINDOWS:
        begin = rva - LEGACY_TEXT_RVA
        if begin < 0 or begin + width > len(decoded):
            raise Pol1Error("2019 evidence window is outside decoded code")
        view = decoded[begin:begin + width]
        if any(struct.pack("<I", value) not in view for value in immediates):
            raise Pol1Error(f"2019 evidence changed at {name} (offset)")
        if any(motif not in view for motif in motifs):
            raise Pol1Error(f"2019 evidence changed at {name} (instruction motif)")
        observations.append({
            "name": name,
            "rva": f"0x{rva:X}",
            "status": "VERIFIED_BYTES",
            "interpretation": (
                "INFERRED_PACKET_HANDLER" if name.endswith("_candidate")
                else "INFERRED_ACCESSOR"
            ),
        })
    return observations


def _extract_commands(image: bytes) -> list[dict]:
    data = _section(image, b".data")
    cmd_rva = 0x34B1B0
    offset = data["raw_start"] + cmd_rva - data["rva"]
    rows = (
        ("/wardrobe", 111), ("/wardrobe2", 112),
        ("/wardrobe3", 113), ("/wardrobe4", 114),
        ("/sendpost", 118), ("/layout", 119), ("/remodel", 120),
    )
    # First four contiguous, then skip three rows in the original table.
    indices = (0, 1, 2, 3, 7, 8, 9)
    results = []
    for (expected_name, expected_id), index in zip(rows, indices):
        pos = offset + index * 24
        if pos < data["raw_start"] or pos + 24 > data["raw_start"] + data["raw_size"]:
            raise Pol1Error("2019 command table escapes .data")
        name = image[pos:pos + 16].split(b"\x00", 1)[0].decode("ascii", errors="strict")
        command_id = struct.unpack_from("<H", image, pos + 20)[0]
        if (name, command_id) != (expected_name, expected_id):
            raise Pol1Error(f"2019 command table unexpected row {index}")
        results.append({"name": name, "command_id": command_id})
    return results


def audit_2019_wardrobe(image: bytes) -> dict:
    """Fail-closed evidence report for a single exact, untouched retail build."""
    if not isinstance(image, bytes) or len(image) != LEGACY_FILE_SIZE:
        raise Pol1Error("only exact-size original 2019 FFXiMain.dll is supported")
    source_hash = hashlib.sha256(image).hexdigest()
    if source_hash != LEGACY_SHA256:
        raise Pol1Error("exact 2019 original SHA-256 required; modified DLL rejected")
    result = unpack_pol1(image)
    if result["sha256"] != LEGACY_DECODED_SHA256 or result["base_rva"] != LEGACY_TEXT_RVA:
        raise Pol1Error("decoded 2019 .text identity mismatch")
    code = result["bytes"]
    return {
        "status": "VERIFIED_STATIC_EVIDENCE_NO_RUNTIME_ENABLEMENT",
        "source_sha256": source_hash,
        "decoded_sha256": result["sha256"],
        "decoded_size": result["size"],
        "code_window_evidence": _verify_code_windows(code),
        "observed_commands": _extract_commands(image),
        "hypothetical_container_extension": legacy_layout_risk(),
        "warnings": [
            "Original 2019 command IDs 118-120 are assigned to unrelated commands; do not copy later build IDs.",
            "Two 2019 inventory mode dispatch candidates compare (mode - 2) to 10 (11 branches for modes 2..12); do not add modes 13-16 without expanding every consumer.",
            "Observed record/capacity offsets overlap a hypothetical container-13 record range.",
            "Static window patterns do not establish complete handler control flow or caller bounds.",
            "Do not send container IDs 13-16 or modern-format packet 0x1C to this client.",
            "No code or packet patch is produced by this report.",
        ],
    }


def inspect_2019_wardrobe(path: str | Path) -> dict:
    """Read-only local path wrapper; never persist, return, or print DLL bytes."""
    p = Path(path)
    if p.stat().st_size != LEGACY_FILE_SIZE:
        raise Pol1Error("unexpected source size")
    return audit_2019_wardrobe(p.read_bytes())
