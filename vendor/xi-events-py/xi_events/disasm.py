"""Recursive-descent disassembler. END_REQSTACK / END_EVENT are returns,
not file-end markers — events have code past them reachable via branches."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from functools import cache
from types import SimpleNamespace

from luaparser import astnodes as N

from .registry import OPS, OpDef

_FMT = {"u8": "<B", "u16": "<H", "s16": "<h", "u32": "<I"}
_SIZE = {"u8": 1, "u16": 2, "s16": 2, "u32": 4}


@dataclass
class Instruction:
    offset: int
    opdef: OpDef
    args: SimpleNamespace
    size: int

    @property
    def name(self) -> str:
        return self.opdef.name

    @property
    def terminal(self) -> bool:
        return self.opdef.terminal

    @property
    def branch_targets(self) -> list[int]:
        return list(self.opdef.branches(self.args)) if self.opdef.branches else []


def disassemble(bytecode: bytes, entrypoint: int) -> list[Instruction]:
    seen: dict[int, Instruction] = {}
    queue: list[int] = [entrypoint]

    while queue:
        pos = queue.pop()
        while pos < len(bytecode) and pos not in seen:
            opcode_byte = bytecode[pos]
            opdef = OPS.get(opcode_byte) or _placeholder(opcode_byte)

            if opdef.custom_parse is not None:
                size, args_dict = opdef.custom_parse(bytecode, pos)
            else:
                size = 1 + _operand_size(opdef.operands)
                if pos + size > len(bytecode):
                    break
                args_dict = _parse_operands(bytecode, pos + 1, opdef.operands)

            inst = Instruction(
                offset=pos,
                opdef=opdef,
                size=size,
                args=SimpleNamespace(**args_dict),
            )
            seen[pos] = inst

            for target in inst.branch_targets:
                if target not in seen and 0 <= target < len(bytecode):
                    queue.append(target)

            if opdef.terminal:
                break
            pos += size

    return [seen[off] for off in sorted(seen)]


def _operand_size(operands: list[tuple[str, str]]) -> int:
    return sum(_SIZE[t] for _, t in operands)


def _parse_operands(data: bytes, base: int, defs: list[tuple[str, str]]) -> dict:
    out, cursor = {}, base
    for name, type_ in defs:
        out[name] = struct.unpack_from(_FMT[type_], data, cursor)[0]
        cursor += _SIZE[type_]
    return out


@cache
def _placeholder(code: int) -> OpDef:
    """Treat unknown bytes as 1-byte opcodes so disassembly continues."""

    def emit(ctx, a):
        return N.Invoke(
            source=N.Name("vm"), func=N.Name(f"unknown_0x{code:02X}"), args=[]
        )

    return OpDef(
        code=code,
        name=f"UNKNOWN_0x{code:02X}",
        operands=[],
        terminal=False,
        branches=None,
        emit=emit,
        custom_parse=None,
    )
