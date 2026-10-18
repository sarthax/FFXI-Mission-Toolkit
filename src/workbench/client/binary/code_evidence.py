"""Optional, bounded x86 instruction evidence from unpacked FFXiMain .text.

A chosen RVA is an arbitrary decode start, not a confirmed function boundary.
Capstone is optional; no executable bytes are modified or executed.
"""
from __future__ import annotations

from pathlib import Path
from workbench.client.pol1_unpack import unpack_pol1

MAX_WINDOW = 512
MAX_INSTRUCTIONS = 100


def decode_window(path: str | Path, rva: int, *, window: int = 160,
                  max_instructions: int = 48) -> dict:
    """Decode one explicitly selected RVA, retaining decoded instruction addresses."""
    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    except ImportError:
        return {"status": "DECODER_UNAVAILABLE",
                "reason": "Install optional capstone Python package to decode x86 instructions."}
    if not isinstance(rva, int) or isinstance(rva, bool):
        raise ValueError("rva must be an integer")
    if not 1 <= window <= MAX_WINDOW or not 1 <= max_instructions <= MAX_INSTRUCTIONS:
        raise ValueError("requested window exceeds bounded decoding limits")
    decoded = unpack_pol1(Path(path).read_bytes())
    offset = rva - decoded["base_rva"]
    code = decoded["bytes"]
    if offset < 0 or offset >= len(code):
        raise ValueError("RVA outside unpacked .text")
    engine = Cs(CS_ARCH_X86, CS_MODE_32)
    engine.detail = False
    rows = []
    for insn in engine.disasm(code[offset:offset + window], rva, count=max_instructions):
        rows.append({"rva": insn.address, "rva_hex": f"0x{insn.address:X}",
                     "size": insn.size, "bytes_hex": insn.bytes.hex(" "),
                     "mnemonic": insn.mnemonic, "operands": insn.op_str})
    return {"status": "DECODED_CANDIDATES", "start_rva": rva,
            "unpacked_sha256": decoded["sha256"], "instructions": rows,
            "warning": "Starting RVA is user-selected; instruction boundaries, function ownership and runtime reachability are not independently verified."}
