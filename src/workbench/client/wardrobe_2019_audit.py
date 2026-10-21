"""Exact-build read-only evidence gate for 2019 FFXiMain.dll Wardrobe research.

Do not treat a static anchor as proof that any handler executes, that a
binary patch is safe, or that unobserved features are absent. No binary writes.
"""
from __future__ import annotations

import hashlib
import struct

from workbench.client.pol1_unpack import Pol1Error, _section, unpack_pol1
from workbench.client.wardrobe_2019_sidecar_model import describe_hypothetical_sidecar

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
    "legacy_per_container_stride": (0xE883E, "81c1ec0d0000"),
    "global_fixed_buffer_address_and_clear_count": (
        0xF6BA7, "bf60db9610b97dfb0000"
    ),
    "global_buffer_clear_dwords": (0xF6BBE, "f3ab"),
    "active_store_pointer_init": (0xF6C33, "a308da4c10"),
    "field_immediately_after_inventory_zero": (
        0xE885E, "c7805c4d010000000000"
    ),
    "field_immediately_after_inventory_pointer": (
        0xE8881, "8990604d0100"
    ),
    "active_store_selects_manager_slot": (0xF710A, "8b3490b920ec0000"),
    "active_store_slot_assignment": (0xF7116, "893508da4c10"),
    "active_store_dispatch_assignment": (0xF7295, "893508da4c10"),
    "active_store_manager_reset": (0xF9B3C, "a308da4c10"),
    "manager_slot_bound_read": (0xF6FFC, "8b8888b00300"),
    "manager_slot_selection_for_teardown": (0xF7009, "8b04b0"),
    "manager_store_cleanup_call": (0xF700D, "e81e000000"),
    "manager_active_reset": (0xF6FE0, "33c0a308da4c10a304da4c10"),
    "active_store_cleared_at_teardown": (0xF70D6, "c70508da4c1000000000"),
    "per_store_zero_dword_count": (0xF710D, "b920ec0000"),
    "per_store_zero_dwords_instruction": (0xF711E, "f3ab"),
    "primary_manager_slot_count_initialization": (
        0xF6C01, "c78288b0030001000000"
    ),
    "active_store_set_during_secondary_init": (0xF73E1, "893508da4c10"),
    "active_store_set_during_reentry": (0xF740E, "893508da4c10"),
    "inventory_cursor_reads_after_array": (0xE8896, "8b82604d0100"),
    "inventory_cursor_slots_bound": (0xE88A6, "83f951"),
    "inventory_cursor_pointer_reset": (
        0xE88CC, "c782604d010000000000"
    ),
    "store_transfer_size_site0": (0x3FA1, "6880b00300"),
    "store_transfer_size_site1": (0x40EC, "6880b00300"),
    "store_transfer_size_site2": (0x418C, "6880b00300"),
    "store_transfer_size_site3": (0x431B, "6880b00300"),
    "store_transfer_size_site4": (0x43B9, "6880b00300"),
    "store_transfer_size_site5": (0x445F, "6880b00300"),
    "store_transfer_size_site6": (0x45B0, "6880b00300"),
    "store_transfer_size_site7": (0x464D, "6880b00300"),
    "store_transfer_size_site8": (0x46ED, "6880b00300"),
    "store_transfer_size_site9": (0x478D, "6880b00300"),
    "store_transfer_size_site10": (0x4818, "6880b00300"),
    "manager_other_active_store_writer": (0x3FA7, "893d08da4c10"),
    "store_pointer_secondary_restore": (0xF6D4D, "a308da4c10"),
    "store_pointer_secondary_dispatch": (0xF7694, "893508da4c10"),
    "store_pointer_secondary_shutdown": (0xF76ED, "893508da4c10"),
    "store_pointer_secondary_reopen": (0xF8A55, "893508da4c10"),
    "manager_index_narrowed_to_16_bits": (0xF6EEA, "25ffff0000"),
    "manager_index_compared_to_slot_count": (0xF6EEF, "3b8188b00300"),
    "manager_index_rejects_unknown": (0xF6EF7, "33c0c3"),
    "manager_slot_indexed_load": (0xF6EFA, "8b0481"),
    "fixed_read_local0_source": (0x40E5, "8d8c2404b40300"),
    "fixed_read_local1_source": (0x4185, "8d942484030000"),
    "fixed_read_local2_source": (0x4314, "8d842484030000"),
    "fixed_read_local3_source": (0x43B2, "8d8c2404b40300"),
    "fixed_read_local4_source": (0x4458, "8d942484640700"),
    "fixed_write_argument0_source": (0x45A6, "8b842410010000"),
    "fixed_write_argument1_source": (0x4643, "8b84240c010000"),
    "fixed_write_argument2_source": (0x46E3, "8b84240c010000"),
    "fixed_write_argument3_source": (0x4783, "8b84240c010000"),
    "fixed_write_active_store_source": (0x4810, "a108da4c10"),
    "direct_store_read_evb_literal": (0x3EE4, "680c473410"),
    "direct_store_read_mode_literal": (0x3F8A, "68d0423410"),
    "direct_store_write_evb_literal": (0x47E3, "680c473410"),
    "direct_store_write_mode_literal": (0x47FC, "681c473410"),
    "evb_caller_buffer0_filename": (0x4579, "6820473410"),
    "evb_caller_buffer1_filename": (0x4616, "6830473410"),
    "evb_caller_buffer2_filename": (0x46B6, "6838473410"),
    "evb_caller_buffer3_filename": (0x4756, "6844473410"),
    "evb_caller_buffer0_stack_frame": (0x4525, "81ec04010000"),
    "evb_caller_buffer1_stack_frame": (0x45F5, "81ec04010000"),
    "evb_caller_buffer2_stack_frame": (0x4695, "81ec04010000"),
    "evb_caller_buffer3_stack_frame": (0x4735, "81ec04010000"),
}


LEGACY_CONTAINER_COUNT = 13
SLOTS_PER_CONTAINER = 81
ITEM_RECORD_BYTES = 44
ITEM_STORE_OFFSET = 0x9860
PACKET_LOCATION_FIELDS = {
    0x1E: (0x08, 0x09),
    0x1F: (0x0A, 0x0B),
    0x20: (0x0E, 0x0F),
}

PER_STORE_CLEAR_DWORDS = 0xEC20
MANAGER_SLOT_COUNT_FIELD_OFFSET = 0x3B088
INVENTORY_CURSOR_COUNT_OFFSET = 0x14D5C
INVENTORY_CURSOR_POINTER_OFFSET = 0x14D60
INVENTORY_CURSOR_MAX_SLOTS = 0x51
ORIGINAL_STORE_GLOBAL_ADDRESS = 0x1096DB60
GLOBAL_INITIALIZED_DWORDS = 0xFB7D
# 2019 active store pointer resolves to global buffer base + 4 in observed init.
ACTIVE_STORE_BASE_OFFSET = 4
ORIGINAL_ITEM_ARRAY_END = ITEM_STORE_OFFSET + LEGACY_CONTAINER_COUNT * SLOTS_PER_CONTAINER * ITEM_RECORD_BYTES
EXPANDED_CONTAINER_COUNT = 18
PROJECTED_18_CONTAINER_END = ITEM_STORE_OFFSET + EXPANDED_CONTAINER_COUNT * SLOTS_PER_CONTAINER * ITEM_RECORD_BYTES


def inspect_2019_store_layout(decoded_sites_verified: bool) -> dict:
    """Record fixed-buffer layout arithmetic, not an implementation or new capacity.

    References after the item array are anchored in the original decoded code.
    No arbitrary replacement pointer, relocated field or patch site is proposed.
    """
    total_buffer_bytes = GLOBAL_INITIALIZED_DWORDS * 4
    extra_needed = (EXPANDED_CONTAINER_COUNT - LEGACY_CONTAINER_COUNT) * (
        SLOTS_PER_CONTAINER * ITEM_RECORD_BYTES
    )
    return {
        "evidence_status": (
            "VERIFIED_STATIC_ANCHORS" if decoded_sites_verified else
            "UNVERIFIED_STATIC_ANCHORS"
        ),
        "fixed_global_base_va": f"0x{ORIGINAL_STORE_GLOBAL_ADDRESS:X}",
        "global_zero_init_bytes": total_buffer_bytes,
        "active_store_offset_from_global_base": ACTIVE_STORE_BASE_OFFSET,
        "active_store_pointer_global_va": "0x104CDA08",
        "observed_runtime_store_reassignment_rvas": [
            "0xF7116", "0xF7295", "0xF9B3C"
        ],
        "store_lifetime_mapped_completely": False,
        "legacy_container_count": LEGACY_CONTAINER_COUNT,
        "legacy_item_array_start_offset": ITEM_STORE_OFFSET,
        "legacy_item_array_exclusive_end_offset": ORIGINAL_ITEM_ARRAY_END,
        "observed_following_scalar_field_offset": 0x14D5C,
        "observed_following_pointer_field_offset": 0x14D60,
        "projected_18_container_array_exclusive_end_offset": PROJECTED_18_CONTAINER_END,
        "extra_bytes_for_five_containers": extra_needed,
        "proposed_in_place_growth_overlaps_observed_fields": (
            ORIGINAL_ITEM_ARRAY_END == 0x14D5C
            and PROJECTED_18_CONTAINER_END > 0x14D60
        ) if decoded_sites_verified else None,
        "safety_decision": "NO_GO_IN_PLACE_ARRAY_GROWTH",
        "caution": (
            "Static offsets from exact-build x86 instruction anchors. The global "
            "buffer has additional fields and many consumers. A separate allocation, "
            "relocation, lifetime, accessor and packet audit is required."
        ),
    }


# Proven observed immediate/callee combinations in the exact Dec 2019 build.
# Only a bounded byte-pattern corroboration, NOT a CFG or call-site proof.
FIXED_TRANSFER_BYTES = 0x3B080
READ_LIKE_RVA = 0x307CFF
WRITE_LIKE_RVA = 0x307E16
EXPECTED_READ_LIKE_TRANSFER_RVAS = (
    0x3FA1, 0x40EC, 0x418C, 0x431B, 0x43B9, 0x445F,
)
EXPECTED_WRITE_LIKE_TRANSFER_RVAS = (
    0x45B0, 0x464D, 0x46ED, 0x478D, 0x4818,
)
# Exact .data string RVAs; the EVB text is nearby but a direct relationship
# to any individual transfer remains unverified.
FIXED_TRANSFER_DATA_STRINGS = {
    "read_open_mode": (0x3442D0, b"rb\x00"),
    "write_open_mode": (0x34471C, b"wb\x00"),
    "adjacent_evb_filename": (0x34470C, b"ZSU.evb\x00"),
    "adjacent_evb_glob": (0x344714, b"*.evb\x00"),
    "caller0_evb_pattern": (0x344720, b"RCN%04d[%d].evb\x00"),
    "caller1_evb_filename": (0x344730, b"REC.evb\x00"),
    "caller2_evb_filename": (0x344738, b"RECN.evb\x00"),
    "caller3_evb_filename": (0x344744, b"RECS.evb\x00"),
}


def inspect_fixed_transfer_data_strings(data: bytes, data_rva: int) -> dict:
    """Anchor literal file modes without returning game data."""
    if not isinstance(data, bytes) or type(data_rva) is not int:
        raise Pol1Error("transfer string observation needs .data bytes and RVA")
    out = {}
    for name, (rva, value) in FIXED_TRANSFER_DATA_STRINGS.items():
        offset = rva - data_rva
        out[name] = {
            "rva": f"0x{rva:X}",
            "exact_match": (
                offset >= 0 and offset + len(value) <= len(data)
                and data[offset:offset + len(value)] == value
            ),
        }
    return {"anchors": out, "all_expected_strings_match": all(
        value["exact_match"] for value in out.values()
    ), "evb_file_purpose_confirmed": False}


def inspect_2019_fixed_transfer_calls(decoded: bytes, decoded_rva: int = 0x1000) -> dict:
    """Find fixed-size immediate/call pairs in bounded *untrusted* x86 bytes.

    This identifies code-shaped occurrences, not reachable, aligned or executed
    x86 instructions. Require independent disassembly and exact build identity
    before promoting any observation.
    """
    if not isinstance(decoded, bytes) or type(decoded_rva) is not int:
        raise Pol1Error("decoded data must be bytes and RVA an integer")
    if len(decoded) > 8 * 1024 * 1024:
        raise Pol1Error("decoded transfer scan exceeds 8 MiB bound")
    needle = b"\x68" + struct.pack("<I", FIXED_TRANSFER_BYTES)
    at = 0
    sites = []
    while True:
        off = decoded.find(needle, at)
        if off < 0:
            break
        at = off + 1
        candidate = {"rva": f"0x{decoded_rva + off:X}",
                     "target": "UNCONFIRMED", "call_rva": None}
        # Search only the next short instruction region; this is a candidate,
        # not a disassembler. No file bytes are returned.
        for call_off in range(off + len(needle), min(off + 18, len(decoded) - 4)):
            if decoded[call_off] != 0xE8:
                continue
            delta = struct.unpack_from("<i", decoded, call_off + 1)[0]
            target = decoded_rva + call_off + 5 + delta
            if target in (READ_LIKE_RVA, WRITE_LIKE_RVA):
                candidate["target"] = (
                    "READ_LIKE" if target == READ_LIKE_RVA else "WRITE_LIKE"
                )
                candidate["call_rva"] = f"0x{decoded_rva + call_off:X}"
                break
        sites.append(candidate)
    observed = {
        "READ_LIKE": {int(s["rva"], 16) for s in sites
                      if s["target"] == "READ_LIKE"},
        "WRITE_LIKE": {int(s["rva"], 16) for s in sites
                       if s["target"] == "WRITE_LIKE"},
    }
    return {
        "sites": sites,
        "total_fixed_size_immediate_occurrences": len(sites),
        "read_like_count": len(observed["READ_LIKE"]),
        "write_like_count": len(observed["WRITE_LIKE"]),
        "all_2019_expected_sites_match": (
            observed["READ_LIKE"] == set(EXPECTED_READ_LIKE_TRANSFER_RVAS)
            and observed["WRITE_LIKE"] == set(EXPECTED_WRITE_LIKE_TRANSFER_RVAS)
            and len(sites) == 11
        ),
        "transfer_is_inventory_save_format": None,
        "caution": "Byte-level code-shape candidates only; no CFG, file purpose or execution proof.",
    }


def inspect_2019_store_lifecycle(decoded_sites_verified: bool) -> dict:
    """Conservative fixed-layout and observed pointer-transition metadata.

    This is a selected anchor summary, not complete CFG recovery.
    """
    return {
        "evidence_status": (
            "VERIFIED_STATIC_ANCHORS" if decoded_sites_verified else
            "UNVERIFIED_STATIC_ANCHORS"
        ),
        "per_store_zero_clear_bytes": PER_STORE_CLEAR_DWORDS * 4,
        "per_store_zero_clear_rva": "0xF711E",
        "fixed_size_transfer_value_bytes": PER_STORE_CLEAR_DWORDS * 4,
        "fixed_size_transfer_immediate_rvas": [
            "0x3FA1", "0x40EC", "0x418C", "0x431B", "0x43B9",
            "0x445F", "0x45B0", "0x464D", "0x46ED", "0x478D", "0x4818"
        ],
        "fixed_size_transfer_semantics_confirmed": False,
        "read_like_stream_callee_rva": "0x307CFF",
        "write_like_stream_callee_rva": "0x307E16",
        "read_like_fixed_transfer_immediate_rvas": [
            "0x3FA1", "0x40EC", "0x418C", "0x431B",
            "0x43B9", "0x445F",
        ],
        "write_like_fixed_transfer_immediate_rvas": [
            "0x45B0", "0x464D", "0x46ED", "0x478D", "0x4818",
        ],
        "persistent_file_format_and_schema_confirmed": False,
        "fixed_transfer_source_observations": {
            "direct_active_store": ["0x3FA1", "0x4818"],
            "stack_local_buffer": [
                "0x40EC", "0x418C", "0x431B", "0x43B9", "0x445F",
            ],
            "caller_supplied_first_argument_pointer": [
                "0x45B0", "0x464D", "0x46ED", "0x478D",
            ],
            "caller_supplied_pointer_contents_and_aliases_known": False,
        },
        "all_transfer_pointers_alias_active_store": None,
        "direct_active_store_evb_path_evidence": {
            "observed_shared_filename": "ZSU.evb",
            "read_side_filename_push_rva": "0x3EE4",
            "read_side_mode_push_rva": "0x3F8A",
            "read_side_transfer_push_rva": "0x3FA1",
            "write_side_filename_push_rva": "0x47E3",
            "write_side_mode_push_rva": "0x47FC",
            "write_side_transfer_push_rva": "0x4818",
            "full_runtime_file_name_proved": False,
            "is_character_inventory_persistence": None,
            "caller_supplied_evb_files": [
                {"site_rva": "0x45B0", "filename": "RCN%04d[%d].evb"},
                {"site_rva": "0x464D", "filename": "REC.evb"},
                {"site_rva": "0x46ED", "filename": "RECN.evb"},
                {"site_rva": "0x478D", "filename": "RECS.evb"},
            ],
            "caller_supplied_buffer_content_known": False,
        },
        "linear_disassembly_candidate_reference_count": 1045,
        "manager_slot_count_field_offset": MANAGER_SLOT_COUNT_FIELD_OFFSET,
        "manager_default_slot_count": 1,
        "manager_slot_selection_rvas": ["0xF710A", "0xF7009"],
        "separate_manager_index_validation_rva": "0xF6EE0",
        "manager_index_truncated_to_16_bits": True if decoded_sites_verified else None,
        "manager_index_guarded_by_slot_count": True if decoded_sites_verified else None,
        "manager_guard_proves_inventory_container_safety": False,
        "manager_teardown_loop_rva": "0xF6FF0",
        "manager_cleanup_call_rva": "0xF700D",
        "active_store_pointer_clear_rvas": ["0xF70D6", "0xF6FE2"],
        "active_store_pointer_set_rvas": [
            "0x3FA7", "0xF6C33", "0xF6D4D", "0xF7116",
            "0xF7295", "0xF73E1", "0xF740E", "0xF7694",
            "0xF76ED", "0xF8A55", "0xF9B3C",
        ],
        "post_inventory_cursor": {
            "count_offset": INVENTORY_CURSOR_COUNT_OFFSET,
            "pointer_offset": INVENTORY_CURSOR_POINTER_OFFSET,
            "maximum_slots": INVENTORY_CURSOR_MAX_SLOTS,
            "bounded_cursor_loop_rva": "0xE8890",
            "cursor_pointer_clear_rva": "0xE88CC",
        },
        "observed_direct_global_writer_instruction_count": 15,
        "global_writer_sites_independently_cfg_confirmed": False,
        "complete_pointer_writer_inventory": False,
        "store_object_allocation_size_proved_for_all_instances": False,
        "store_object_lifetime_proved": False,
        "cursor_uses_existing_inventory_records": True if decoded_sites_verified else None,
        "safety_decision": "NO_GO_MOVE_OR_EXTEND_EXISTING_ARRAY",
        "caution": (
            "Selected static anchors establish manager-slot enumeration, store"
            " clearing, and existing inventory cursor references. These are"
            " incomplete life-cycle and ownership observations, not an approved"
            " object relocation design."
        ),
    }


def bounded_2019_record_offset(container_id: int, slot_id: int) -> int | None:
    """Model known 2019 record math with explicit bounds, never dereference.

    This is an offline reference oracle, NOT a byte-level client patch.
    """
    if type(container_id) is not int or type(slot_id) is not int:
        return None
    if not (0 <= container_id < LEGACY_CONTAINER_COUNT):
        return None
    if not (0 <= slot_id < SLOTS_PER_CONTAINER):
        return None
    return ITEM_STORE_OFFSET + (container_id * SLOTS_PER_CONTAINER + slot_id) * ITEM_RECORD_BYTES


def inspect_2019_item_packet_location(packet_id: int, payload: bytes) -> dict:
    """Offline packet-location guard oracle; returns no retail packet bytes."""
    if type(packet_id) is not int or packet_id not in PACKET_LOCATION_FIELDS:
        return {"status": "UNKNOWN_PACKET_NO_ADDRESS", "safe_record_offset": None}
    if not isinstance(payload, bytes):
        return {"status": "INVALID_PACKET_BUFFER", "safe_record_offset": None}
    location_byte, slot_byte = PACKET_LOCATION_FIELDS[packet_id]
    if len(payload) <= max(location_byte, slot_byte):
        return {"status": "TRUNCATED_PACKET", "safe_record_offset": None}
    container_id, slot_id = payload[location_byte], payload[slot_byte]
    offset = bounded_2019_record_offset(container_id, slot_id)
    return {
        "status": "LEGACY_BOUNDS_OK" if offset is not None else "REJECT_LEGACY_BOUNDS",
        "packet_id": packet_id,
        "container_id": container_id, "slot_id": slot_id,
        "safe_record_offset": offset,
        "caution": "Synthetic bounds oracle only; not a parsed wire packet or live packet filter.",
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
    strings = inspect_fixed_transfer_data_strings(
        image[at:at + size], section["rva"]
    )
    transfers = inspect_2019_fixed_transfer_calls(
        original["bytes"], original["base_rva"]
    )
    proven = (
        commands["legacy_commands_verified"] and decoded_hash_ok
        and sites["all_static_anchors_match"]
        and strings["all_expected_strings_match"]
        and transfers["all_2019_expected_sites_match"]
    )
    return {
        "status": "LEGACY_2019_STATIC_GATES_VERIFIED" if proven else "INCOMPLETE_STATIC_EVIDENCE",
        "source_sha256": source_hash, "decoded_sha256": original["sha256"],
        "decoded_sha256_verified": decoded_hash_ok,
        "commands": commands, "decoded_sites": sites,
        "hypothetical_extension_design": describe_hypothetical_sidecar(),
        "fixed_transfer_data_strings": strings,
        "fixed_transfer_call_candidates": transfers,
        "store_layout": inspect_2019_store_layout(
            decoded_hash_ok and sites["all_static_anchors_match"]
        ),
        "store_lifecycle": inspect_2019_store_lifecycle(
            decoded_hash_ok and sites["all_static_anchors_match"]
        ),
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
