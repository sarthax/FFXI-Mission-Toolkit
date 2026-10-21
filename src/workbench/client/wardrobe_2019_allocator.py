"""Exact-build, read-only static-arena and active-context evidence for 2019 FFXiMain.

Returns metadata only. The evidence is constrained to the authenticated original
2019 decoded image by the caller's full-file and decoded-image fingerprint
checks. Instruction windows do not establish all control flow or allocations.
No DLL writer, hook, process access, or packet mutator exists here.
"""
from __future__ import annotations

from workbench.client.pol1_unpack import Pol1Error, _section

TEXT_RVA = 0x1000
IMAGE_BASE = 0x10000000
STATIC_BACKING_VA = 0x1096DB60
STATIC_FIRST_CONTEXT_VA = STATIC_BACKING_VA + 4
STATIC_ARENA_ZERO_DWORDS = 0xFB7D
STATIC_ARENA_ZERO_BYTES = STATIC_ARENA_ZERO_DWORDS * 4
CONTEXT_RESET_DWORDS = 0xEC20
CONTEXT_RESET_BYTES = CONTEXT_RESET_DWORDS * 4
ACTIVE_CONTEXT_GLOBAL_VA = 0x104CDA08
CONTEXT_ROOT_GLOBAL_VA = 0x104CDA04
CONTEXT_TABLE_COUNT_OFFSET = 0x3B088
LEGACY_CONTAINERS = 13
FUTURE_CONTAINERS = 18
SLOTS_PER_CONTAINER = 81
RECORD_BYTES = 44
RECORD_BASE_OFFSET = 0x9860
EXTENSION_START = RECORD_BASE_OFFSET + LEGACY_CONTAINERS * SLOTS_PER_CONTAINER * RECORD_BYTES
EXTENSION_BYTES = (FUTURE_CONTAINERS - LEGACY_CONTAINERS) * SLOTS_PER_CONTAINER * RECORD_BYTES

# Anchored at exact decoded code RVAs; these are short generic x86 motifs.
# A fingerprint mismatch in the caller rejects any unrecognized binary.
LIFECYCLE_MOTIFS = (
    ("static_arena_address", 0xF6BA7, "bf 60 db 96 10"),
    ("static_arena_zero_count", 0xF6BAC, "b9 7d fb 00 00"),
    ("static_arena_zero_loop", 0xF6BBE, "f3 ab"),
    ("first_context_root_plus_four", 0xF6C26, "8d 48 04"),
    ("first_context_root_slot_write", 0xF6C29, "89 08"),
    ("first_active_context_set", 0xF6C33, "a3 08 da 4c 10"),
    ("context_switch_zero_count", 0xF710D, "b9 20 ec 00 00"),
    ("context_switch_active_set", 0xF7116, "89 35 08 da 4c 10"),
    ("context_switch_zero_loop", 0xF711E, "f3 ab"),
    ("return_to_root_context", 0xF6D4D, "a3 08 da 4c 10"),
    ("context_init_active_set", 0xF7295, "89 35 08 da 4c 10"),
    ("context_dispatch_active_set", 0xF73E1, "89 35 08 da 4c 10"),
    ("login_root_context_set", 0xF9B3C, "a3 08 da 4c 10"),
    ("original_record_table_address", 0xE8780, "8d ba 60 98 00 00"),
    ("original_container_loop_count", 0xE8786, "ba 0d 00 00 00"),
)


def _verify_lifecycle_motifs(decoded: bytes) -> list[dict]:
    """Fail on a single altered anchor; never include code bytes in output."""
    findings = []
    for name, rva, needle in LIFECYCLE_MOTIFS:
        needle_bytes = bytes.fromhex(needle)
        pos = rva - TEXT_RVA
        if pos < 0 or pos + len(needle_bytes) > len(decoded):
            raise Pol1Error("2019 arena evidence window outside decoded .text")
        if decoded[pos:pos + len(needle_bytes)] != needle_bytes:
            raise Pol1Error(f"2019 lifecycle anchor changed: {name}")
        findings.append({"name": name, "rva": f"0x{rva:X}", "status": "VERIFIED_BYTES"})
    return findings


def describe_2019_allocator(image: bytes, decoded: bytes) -> dict:
    """Verify original first-context backing and bound an extension proposal."""
    data = _section(image, b".data")
    root_rva = STATIC_BACKING_VA - IMAGE_BASE
    root_end = root_rva + STATIC_ARENA_ZERO_BYTES
    if not (data["rva"] <= root_rva < root_end <= data["rva"] + data["virtual_size"]):
        raise Pol1Error("2019 static backing not contained in virtual .data")
    findings = _verify_lifecycle_motifs(decoded)
    return {
        "status": "VERIFIED_STATIC_INITIALIZATION_NOT_FULL_ALLOCATION_AUDIT",
        "root_global_va": f"0x{CONTEXT_ROOT_GLOBAL_VA:X}",
        "active_context_global_va": f"0x{ACTIVE_CONTEXT_GLOBAL_VA:X}",
        "first_root_static_backing_va": f"0x{STATIC_BACKING_VA:X}",
        "first_context_va": f"0x{STATIC_FIRST_CONTEXT_VA:X}",
        "first_root_in_virtual_data": True,
        "initial_arena_zero_bytes": STATIC_ARENA_ZERO_BYTES,
        "per_context_reset_zero_bytes": CONTEXT_RESET_BYTES,
        "first_context_pointer_table_count_offset": f"0x{CONTEXT_TABLE_COUNT_OFFSET:X}",
        "multiple_active_context_assignment_sites": True,
        "existing_record_containers": LEGACY_CONTAINERS,
        "future_record_containers_requested": FUTURE_CONTAINERS,
        "hypothetical_new_records_start": f"0x{EXTENSION_START:X}",
        "hypothetical_five_container_record_bytes": EXTENSION_BYTES,
        "hypothetical_new_records_end_exclusive": f"0x{EXTENSION_START + EXTENSION_BYTES:X}",
        "extension_overlaps_existing_context_fields": True,
        "anchor_evidence": findings,
        "interpretation": (
            "2019 first context has statically backed state; the global active-context "
            "pointer is reassigned on multiple paths, and each context has a fixed "
            "reset span. The extra record range would overwrite existing context "
            "fields rather than extend a reserved record array. Further contexts "
            "and any heap allocation paths remain UNKNOWN."
        ),
        "gate": (
            "DO_NOT_EXTEND_IN_PLACE_OR_REPOINT_ONLY_ONE_CONTEXT; map every item "
            "reader/writer and all context creation/switch/teardown paths before "
            "designing a sidecar or relocation."
        ),
    }
