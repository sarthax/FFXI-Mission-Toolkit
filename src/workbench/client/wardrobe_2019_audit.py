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
        "linear_disassembly_candidate_reference_count": 1045,
        "manager_slot_count_field_offset": MANAGER_SLOT_COUNT_FIELD_OFFSET,
        "manager_default_slot_count": 1,
        "manager_slot_selection_rvas": ["0xF710A", "0xF7009"],
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
    proven = commands["legacy_commands_verified"] and decoded_hash_ok and sites["all_static_anchors_match"]
    return {
        "status": "LEGACY_2019_STATIC_GATES_VERIFIED" if proven else "INCOMPLETE_STATIC_EVIDENCE",
        "source_sha256": source_hash, "decoded_sha256": original["sha256"],
        "decoded_sha256_verified": decoded_hash_ok,
        "commands": commands, "decoded_sites": sites,
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
