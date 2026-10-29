"""Exact December 2019 Wardrobe command -> UI-mode static evidence.

These are READ-ONLY opcode/table observations. The mode object values are not
recoverable from the four command handlers alone; no claim of a runnable new
Wardrobe, runtime execution, code patch, or complete UI state machine follows.
"""
from __future__ import annotations

import struct

from workbench.client.pol1_unpack import Pol1Error

IMAGE_BASE = 0x10000000
COMMAND_NAME_RVA = 0x34B1B0
COMMAND_HANDLER_TABLE_RVA = 0x34C068
COMMAND_NAME_RECORD_BYTES = 24
HANDLER_RECORD_BYTES = 12
COMMAND_HELPER_RVA = 0x1D1680
UI_SELECTOR_RVA = 0x1D4E70
UI_JUMP_TABLE_RVA = 0x1D4F64
MODE_FIRST = 2
MODE_LAST = 12
MODE_DEFAULT_TARGET_RVA = 0x1D4EFA
MODE_CASE_TARGETS = (
    0x1D4EB6, 0x1D4EFA, 0x1D4EC0, 0x1D4EAB,
    0x1D4EA3, 0x1D4E99, 0x1D4EC8, 0x1D4EF0,
    0x1D4ED3, 0x1D4EDD, 0x1D4EE5,
)
MODE_CASE_UI_POINTER_GLOBALS = (
    0x10621FC4, 0x10621FC0, 0x10621FCC, 0x10621FD0,
    0x10621FD4, 0x10621FD8, 0x10621FDC, 0x10621FEC,
    0x10621FE0, 0x10621FE4, 0x10621FE8,
)
# command ID, name, handler code RVA, runtime mode-object global pointer VA
WARDROBE_COMMANDS = (
    (111, "/wardrobe", 0x7CE80, 0x1061E5D0),
    (112, "/wardrobe2", 0x7CEA0, 0x1061E5D4),
    (113, "/wardrobe3", 0x7CEC0, 0x1061E5D8),
    (114, "/wardrobe4", 0x7CEE0, 0x1061E5DC),
)
# Exact x86 sequence after the getter: add eax,-2; cmp eax,10; ja default;
# jmp absolute jump-table[eax]. For 13..16, the ja is taken.
MODE_SELECTOR_BYTES = bytes.fromhex("83c0fe83f80a7768ff2485644f1d10")
MODE_GETTER_BYTES = bytes.fromhex("8b11ff5254")
MODE_FORWARD_BYTES = bytes.fromhex("8b4424048b0d88e5611050e870370000")


def _section_slice(data: bytes, base_rva: int, at_rva: int,
                   length: int) -> bytes | None:
    """Return an exact bounded immutable section slice or None."""
    offset = at_rva - base_rva
    if offset < 0 or length < 0 or offset + length > len(data):
        return None
    return data[offset:offset + length]


# Separate original .rdata constructor/vtable chain proves which UI mode
# the four command pointers return. This mapping is NOT inferred from IDs 111-114.
# name, ctor RVA, vtable VA, object global VA, getter RVA, returned mode
WARDROBE_MODE_OBJECTS = (
    ("/wardrobe", 0x1D4332, 0x1032DB00, 0x1061E5D0, 0x1D47C0, 8),
    ("/wardrobe2", 0x1D435B, 0x1032DAA0, 0x1061E5D4, 0x1D47E0, 10),
    ("/wardrobe3", 0x1D4384, 0x1032DA40, 0x1061E5D8, 0x1D4800, 11),
    ("/wardrobe4", 0x1D43AD, 0x1032D9E0, 0x1061E5DC, 0x1D4820, 12),
)


def inspect_2019_mode_object_getters(rdata: bytes, rdata_rva: int,
                                     decoded_text: bytes, text_rva: int = 0x1000
                                     ) -> dict:
    """Read-only constructor -> vtable[+0x54] -> constant mode verification.

    Does not establish object lifetime, mode activation, user-visible menus
    or the semantics of any other virtual method.
    """
    if (not isinstance(rdata, bytes) or not isinstance(decoded_text, bytes)
            or type(rdata_rva) is not int or type(text_rva) is not int):
        raise Pol1Error("mode-object scan requires immutable sections and integer RVAs")
    if len(rdata) > 8 * 1024 * 1024 or len(decoded_text) > 8 * 1024 * 1024:
        raise Pol1Error("mode-object section exceeds safety bounds")
    results = []
    for name, ctor, vtable, object_global, getter, mode in WARDROBE_MODE_OBJECTS:
        expected_ctor = (
            bytes.fromhex("c700") + struct.pack("<I", vtable)
            + bytes([0xA3]) + struct.pack("<I", object_global)
        )
        ctor_code = _section_slice(decoded_text, text_rva, ctor,
                                   len(expected_ctor))
        vtable_getter_bytes = _section_slice(
            rdata, rdata_rva, (vtable - IMAGE_BASE) + 0x54, 4)
        vtable_getter = (
            struct.unpack("<I", vtable_getter_bytes)[0]
            if vtable_getter_bytes is not None else None
        )
        expected_getter = bytes([0xB8]) + struct.pack("<I", mode) + bytes([0xC3])
        getter_code = _section_slice(decoded_text, text_rva, getter,
                                     len(expected_getter))
        results.append({
            "command": name,
            "constructor_rva": f"0x{ctor:X}",
            "object_global_va": f"0x{object_global:X}",
            "vtable_va": f"0x{vtable:X}",
            "vtable_getter_slot": "0x54",
            "getter_rva": f"0x{getter:X}",
            "reported_mode": mode,
            "constructor_sets_expected_vtable_and_global": (
                ctor_code == expected_ctor
            ),
            "vtable_slot_points_to_getter": (
                vtable_getter == IMAGE_BASE + getter
            ),
            "getter_returns_constant_mode": (
                getter_code == expected_getter
            ),
            "within_original_2_to_12_mode_switch": (
                MODE_FIRST <= mode <= MODE_LAST
            ),
        })
    verified = all(
        x["constructor_sets_expected_vtable_and_global"]
        and x["vtable_slot_points_to_getter"]
        and x["getter_returns_constant_mode"]
        and x["within_original_2_to_12_mode_switch"]
        for x in results
    )
    return {
        "status": "EXACT_MODE_OBJECT_CHAIN_VERIFIED" if verified
                  else "INCOMPLETE_STATIC_EVIDENCE",
        "mode_objects": results,
        "command_to_mode_mapping_proved_by_static_getters": verified,
        "mode_9_is_not_one_of_four_wardrobe_commands": True if verified else None,
        "object_creation_or_ui_runtime_execution_verified": False,
        "object_lifetime_and_other_virtual_methods_audited": False,
        "client_mode_13_to_16_implemented": False,
        "safety_decision": "NO_GO_ASSUME_MORE_MODES_ARE_SUPPORTED",
        "caution": (
            "Exact constructor/vtable/getter byte chain only. The reported "
            "mode values are constant for these original object classes, "
            "not evidence that a new mode or Wardrobe functionality works."
        ),
    }


# The adjacent slash command /bank2 (115) occupies original UI mode 9.
# It uses a different command helper from Wardrobes 1-4.
BANK2_COMMAND_RVA = 0x34B210
BANK2_HANDLER_RECORD_RVA = 0x34C098
BANK2_HANDLER_RVA = 0x7CF00
BANK2_POINTER_READ_RVA = 0x7CF24
BANK2_HELPER_CALL_RVA = 0x7CF36
BANK2_HELPER_RVA = 0x1D1570
BANK2_OBJECT_GLOBAL_VA = 0x1061E5E0
BANK2_CTOR_RVA = 0x1D43D6
BANK2_VTABLE_VA = 0x1032D980
BANK2_GETTER_RVA = 0x1D4840


def inspect_2019_bank2_mode9(data: bytes, data_rva: int,
                              rdata: bytes, rdata_rva: int,
                              decoded_text: bytes, text_rva: int = 0x1000) -> dict:
    """Confirm mode 9 is already used by original /bank2, without execution."""
    if (not isinstance(data, bytes) or not isinstance(rdata, bytes)
            or not isinstance(decoded_text, bytes)
            or any(type(v) is not int for v in (data_rva, rdata_rva, text_rva))):
        raise Pol1Error("bank2 evidence needs immutable sections and integer RVAs")
    if (len(data) > 16 * 1024 * 1024 or len(rdata) > 8 * 1024 * 1024
            or len(decoded_text) > 8 * 1024 * 1024):
        raise Pol1Error("bank2 evidence exceeds section safety bounds")
    name = _section_slice(data, data_rva, BANK2_COMMAND_RVA, 24)
    record = _section_slice(data, data_rva, BANK2_HANDLER_RECORD_RVA, 12)
    expected_name = b"/bank2".ljust(16, bytes(1))
    name_ok = (name is not None and name[:16] == expected_name
               and struct.unpack_from("<HH", name, 20) == (115, 0x51))
    table_ok = (record is not None and struct.unpack("<III", record)
                == (115, IMAGE_BASE + BANK2_HANDLER_RVA, 0))
    ptr_load = _section_slice(decoded_text, text_rva,
                              BANK2_POINTER_READ_RVA, 6)
    ptr_ok = ptr_load == bytes.fromhex("8b0d") + struct.pack(
        "<I", BANK2_OBJECT_GLOBAL_VA)
    helper_call = _section_slice(decoded_text, text_rva,
                                 BANK2_HELPER_CALL_RVA, 5)
    helper_ok = (
        helper_call is not None and helper_call[0] == 0xE8
        and BANK2_HELPER_CALL_RVA + 5 + struct.unpack_from(
            "<i", helper_call, 1)[0] == BANK2_HELPER_RVA
    )
    expected_ctor = (
        bytes.fromhex("c700") + struct.pack("<I", BANK2_VTABLE_VA)
        + bytes([0xA3]) + struct.pack("<I", BANK2_OBJECT_GLOBAL_VA)
    )
    ctor_ok = (_section_slice(decoded_text, text_rva, BANK2_CTOR_RVA,
                              len(expected_ctor)) == expected_ctor)
    getter_ptr = _section_slice(rdata, rdata_rva,
                                BANK2_VTABLE_VA - IMAGE_BASE + 0x54, 4)
    vtable_ok = (getter_ptr is not None and struct.unpack(
        "<I", getter_ptr)[0] == IMAGE_BASE + BANK2_GETTER_RVA)
    getter_ok = (_section_slice(decoded_text, text_rva, BANK2_GETTER_RVA, 6)
                 == bytes([0xB8]) + struct.pack("<I", 9) + bytes([0xC3]))
    checks = {
        "command_name_and_id_match": bool(name_ok),
        "dispatch_record_matches": bool(table_ok),
        "handler_loads_mode_object": bool(ptr_ok),
        "handler_calls_separate_helper": bool(helper_ok),
        "constructor_sets_mode_object": bool(ctor_ok),
        "vtable_getter_pointer_matches": bool(vtable_ok),
        "getter_returns_mode_9": bool(getter_ok),
    }
    proven = all(checks.values())
    return {
        "status": "ORIGINAL_BANK2_MODE_9_VERIFIED" if proven
                  else "INCOMPLETE_STATIC_EVIDENCE",
        "command": "/bank2", "command_id": 115,
        "handler_rva": "0x7CF00", "helper_rva": "0x1D1570",
        "mode_object_global_va": "0x1061E5E0",
        "getter_rva": "0x1D4840", "returned_mode": 9,
        "static_checks": checks,
        "mode9_reserved_for_original_bank2_path": True if proven else None,
        "runtime_execution_or_complete_ui_semantics_proved": False,
        "safety_decision": "NO_GO_REPURPOSE_ORIGINAL_MODE_9",
    }


def inspect_2019_command_ui_dispatch(data: bytes, data_rva: int,
                                     decoded_text: bytes, text_rva: int = 0x1000
                                     ) -> dict:
    """Correlate command names, handler table and selected UI mode switch.

    Caller must gate this with the *exact original 2019 source SHA-256* and
    decoded .text hash before treating any RVA as build-specific evidence.
    """
    if (not isinstance(data, bytes) or not isinstance(decoded_text, bytes)
            or type(data_rva) is not int or type(text_rva) is not int):
        raise Pol1Error("UI evidence expects immutable sections and integer RVAs")
    if len(data) > 16 * 1024 * 1024 or len(decoded_text) > 8 * 1024 * 1024:
        raise Pol1Error("UI evidence exceeds bounded section scan sizes")
    commands = []
    for index, (command_id, name, handler_rva, object_global) in enumerate(
            WARDROBE_COMMANDS):
        name_rva = COMMAND_NAME_RVA + index * COMMAND_NAME_RECORD_BYTES
        record_rva = COMMAND_HANDLER_TABLE_RVA + index * HANDLER_RECORD_BYTES
        name_bytes = _section_slice(data, data_rva, name_rva, 24)
        handler_bytes = _section_slice(data, data_rva, record_rva, 12)
        code = _section_slice(decoded_text, text_rva, handler_rva, 13)
        expected_name = name.encode("ascii").ljust(16, b"\0")
        name_ok = (name_bytes is not None
                   and name_bytes[:16] == expected_name
                   and struct.unpack_from("<HH", name_bytes, 20) ==
                   (command_id, 0x51))
        handler_ok = (handler_bytes is not None
                      and struct.unpack("<III", handler_bytes) ==
                      (command_id, IMAGE_BASE + handler_rva, 0))
        code_ok = bool(code is not None and len(code) == 13
                       and code[:1] == b"\xA1"
                       and struct.unpack_from("<I", code, 1)[0] == object_global
                       and code[5:9] == bytes.fromhex("6a0050e8")
                       and handler_rva + 13 + struct.unpack_from(
                           "<i", code, 9)[0] == COMMAND_HELPER_RVA)
        commands.append({
            "command": name, "command_id": command_id,
            "name_record_rva": f"0x{name_rva:X}",
            "handler_table_record_rva": f"0x{record_rva:X}",
            "handler_rva": f"0x{handler_rva:X}",
            "mode_object_global_va": f"0x{object_global:X}",
            "name_and_id_match": bool(name_ok),
            "handler_table_matches": bool(handler_ok),
            "loads_object_and_calls_shared_helper": bool(code_ok),
        })

    forward = _section_slice(decoded_text, text_rva, 0x1D16F0,
                             len(MODE_FORWARD_BYTES))
    getter = _section_slice(decoded_text, text_rva, 0x1D4E85,
                            len(MODE_GETTER_BYTES))
    selector = _section_slice(decoded_text, text_rva, 0x1D4E8A,
                              len(MODE_SELECTOR_BYTES))
    table = _section_slice(decoded_text, text_rva, UI_JUMP_TABLE_RVA,
                            len(MODE_CASE_TARGETS) * 4)
    observed_targets = (
        struct.unpack("<" + "I" * len(MODE_CASE_TARGETS), table)
        if table is not None else ()
    )
    targets_ok = (observed_targets == tuple(
        IMAGE_BASE + rva for rva in MODE_CASE_TARGETS
    ))
    modes = []
    for index, (target_rva, expected_global) in enumerate(zip(
            MODE_CASE_TARGETS, MODE_CASE_UI_POINTER_GLOBALS)):
        insn = _section_slice(decoded_text, text_rva, target_rva, 6)
        if insn is None:
            actual_global = None
        elif insn[:1] == b"\xA1":
            actual_global = struct.unpack_from("<I", insn, 1)[0]
        elif insn[:2] in (b"\x8b\x0d", b"\x8b\x15"):
            actual_global = struct.unpack_from("<I", insn, 2)[0]
        else:
            actual_global = None
        modes.append({
            "mode": MODE_FIRST + index,
            "branch_target_rva": f"0x{target_rva:X}",
            "ui_source_global_va": f"0x{expected_global:X}",
            "case_global_matches": actual_global == expected_global,
            "uses_same_branch_as_default": target_rva == MODE_DEFAULT_TARGET_RVA,
        })

    selector_ok = (getter == MODE_GETTER_BYTES
                   and selector == MODE_SELECTOR_BYTES
                   and forward == MODE_FORWARD_BYTES
                   and targets_ok
                   and all(x["case_global_matches"] for x in modes))
    complete = bool(all(
        x["name_and_id_match"] and x["handler_table_matches"]
        and x["loads_object_and_calls_shared_helper"]
        for x in commands
    ) and selector_ok)
    return {
        "status": "EXACT_STATIC_ANCHORS_MATCH" if complete
                  else "INCOMPLETE_STATIC_EVIDENCE",
        "commands": commands,
        "shared_command_helper_rva": "0x1D1680",
        "forwarder_to_ui_selector_rva": "0x1D16F0",
        "ui_selector_rva": "0x1D4E70",
        "mode_getter_vtable_offset": "0x54",
        "selector_uses_mode_minus_two": bool(selector == MODE_SELECTOR_BYTES),
        "switch_first_mode": MODE_FIRST,
        "switch_last_mode": MODE_LAST,
        "switch_entry_count": len(MODE_CASE_TARGETS),
        "ui_mode_cases": modes,
        "jump_table_matches": bool(targets_ok),
        "helper_forward_getter_and_selector_match": bool(selector_ok),
        "proposed_modes_13_16_use_default_in_original": (
            True if selector_ok else None
        ),
        "default_branch_rva": "0x1D4EFA",
        "command_to_runtime_mode_id_mapping_proved": False,
        "new_wardrobe_commands_or_mode_cases_present": False if complete else None,
        "complete_menu_builder_and_ui_state_recovered": False,
        "safety_decision": "NO_GO_ASSUME_2019_MODE_13_16_SUPPORTED",
        "caution": (
            "Exact original-build tables/instruction windows, not a complete "
            "runtime call graph. Mode-object getter values, construction "
            "lifetimes and full menu behavior are unverified."
        ),
    }
