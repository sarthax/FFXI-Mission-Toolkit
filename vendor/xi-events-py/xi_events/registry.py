"""Opcode registry. ``opcodes_auto`` registers placeholders, then
``opcodes`` re-registers refined entries (last writer wins)."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable

EmitFn = Callable[[Any, SimpleNamespace], Any]
BranchFn = Callable[[SimpleNamespace], list[int]]
ParseFn = Callable[[bytes, int], tuple[int, dict]]


@dataclass
class OpDef:
    code: int
    name: str
    operands: list[tuple[str, str]]
    terminal: bool
    branches: BranchFn | None
    emit: EmitFn
    custom_parse: ParseFn | None = None


OPS: dict[int, OpDef] = {}


def op(
    code: int,
    name: str,
    *,
    operands: list[tuple[str, str]] | tuple = (),
    terminal: bool = False,
    branches: BranchFn | None = None,
    custom_parse: ParseFn | None = None,
) -> Callable[[EmitFn], EmitFn]:
    def deco(fn: EmitFn) -> EmitFn:
        OPS[code] = OpDef(
            code=code,
            name=name,
            operands=list(operands),
            terminal=terminal,
            branches=branches,
            emit=fn,
            custom_parse=custom_parse,
        )
        return fn

    return deco
