"""Exact-build, read-only 2019 UI-object update/teardown evidence.

Only the selected static instruction windows are checked. The 13 globals
are not asserted to be independent inventory stores, and this module does
not create, mutate or destroy anything in the retail client.
"""
from __future__ import annotations

import struct

from workbench.client.pol1_unpack import Pol1Error

UI_OBJECT_GLOBAL_FIRST = 0x10621FBC
UI_OBJECT_GLOBAL_COUNT = 13
UI_UPDATE_CALLEE_RVA = 0x212A00
UI_CLEANUP_CALLEE_RVA = 0x212670
UI_DEALLOC_CALLEE_RVA = 0x3077A0
UI_CLEANUP_FIRST_RVA = 0x160200
UI_CLEANUP_STRIDE = 0x20


def _window(decoded: bytes, text_rva: int, at_rva: int, length: int) -> bytes | None:
    off = at_rva - text_rva
    if off < 0 or length < 0 or off + length > len(decoded):
        return None
    return decoded[off:off + length]


def _call_target(window: bytes, index: int, insn_rva: int) -> int | None:
    if index < 0 or index + 5 > len(window) or window[index] != 0xE8:
        return None
    return insn_rva + 5 + struct.unpack_from("<i", window, index + 1)[0]


def inspect_2019_ui_object_lifecycle(decoded_text: bytes, text_rva: int = 0x1000) -> dict:
    """Corroborate 13 original UI object update and teardown call sites.

    This byte-window recognizer is deliberately narrower than a full CFG.
    Parent client audit must verify exact original DLL + decoded SHA first.
    """
    if not isinstance(decoded_text, bytes) or type(text_rva) is not int:
        raise Pol1Error("UI lifecycle evidence requires immutable code bytes and int RVA")
    if len(decoded_text) > 8 * 1024 * 1024:
        raise Pol1Error("UI lifecycle decoded image exceeds 8 MiB safety bound")
    entries = []
    for index in range(UI_OBJECT_GLOBAL_COUNT):
        global_va = UI_OBJECT_GLOBAL_FIRST + index * 4
        init_rva = (
            0x159826 if index == 0 else
            0x159831 if index == 1 else
            0x15983C + (index - 2) * 0xF
        )
        init_len = 11 if index < 2 else 15
        init = _window(decoded_text, text_rva, init_rva, init_len)
        expected_load = bytes.fromhex("8b0d") + struct.pack("<I", global_va)
        has_expected_load = init is not None and init[:6] == expected_load
        if index < 2:
            init_call_offset = 6
            init_guard_ok = True if init is not None else False
        else:
            init_call_offset = 10
            init_guard_ok = (
                init is not None
                and init[6:10] == bytes.fromhex("85c97405")
            )
        init_call = _call_target(
            init or b"", init_call_offset, init_rva + init_call_offset
        )
        init_ok = bool(
            has_expected_load and init_guard_ok
            and init_call == UI_UPDATE_CALLEE_RVA
        )

        cleanup_rva = UI_CLEANUP_FIRST_RVA + index * UI_CLEANUP_STRIDE
        cleanup = _window(decoded_text, text_rva, cleanup_rva, 32)
        cleanup_ok = bool(
            cleanup is not None
            and cleanup[:2] == bytes.fromhex("8b35")
            and struct.unpack_from("<I", cleanup, 2)[0] == global_va
            and cleanup[6:12] == bytes.fromhex("3bf774168bce")
            and _call_target(cleanup, 12, cleanup_rva + 12) ==
                UI_CLEANUP_CALLEE_RVA
            and cleanup[17:18] == bytes.fromhex("56")
            and _call_target(cleanup, 18, cleanup_rva + 18) ==
                UI_DEALLOC_CALLEE_RVA
            and cleanup[23:26] == bytes.fromhex("83c404")
            and cleanup[26:28] == bytes.fromhex("893d")
            and struct.unpack_from("<I", cleanup, 28)[0] == global_va
        )
        entries.append({
            "index": index,
            "global_va": f"0x{global_va:X}",
            "selected_update_callsite_rva": f"0x{init_rva:X}",
            "selected_cleanup_block_rva": f"0x{cleanup_rva:X}",
            "update_path_matches": init_ok,
            "cleanup_free_and_clear_path_matches": cleanup_ok,
        })
    matched = all(
        row["update_path_matches"]
        and row["cleanup_free_and_clear_path_matches"]
        for row in entries
    )
    return {
        "status": "EXACT_13_UI_OBJECT_PATHS_VERIFIED" if matched
                  else "INCOMPLETE_STATIC_EVIDENCE",
        "selected_ui_object_pointer_count": UI_OBJECT_GLOBAL_COUNT,
        "selected_update_callee_rva": f"0x{UI_UPDATE_CALLEE_RVA:X}",
        "selected_cleanup_callee_rva": f"0x{UI_CLEANUP_CALLEE_RVA:X}",
        "selected_free_callee_rva": f"0x{UI_DEALLOC_CALLEE_RVA:X}",
        "entries": entries,
        "all_selected_paths_match": matched,
        "global_object_allocation_and_ctor_fully_mapped": False,
        "all_ui_owner_aliases_and_menu_lifetimes_mapped": False,
        "new_ui_object_instances_13_16_exist": False,
        "safety_decision": "NO_GO_APPEND_UI_OBJECT_POINTERS_IN_PLACE",
        "caution": (
            "A selected update sequence and a selected cleanup/free/clear "
            "sequence exist for 13 globals. Their complete allocation, "
            "ownership and live execution remain unknown."
        ),
    }
