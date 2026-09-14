"""Generate ``xi_events/opcodes_auto.py`` from the local opcode metadata
snapshot.

Reads ``xi_events/opcodes_meta.json`` (one record per opcode: code, name,
operands, terminal, branches, variable_length) and emits one ``@op(...)``
declaration per opcode. Variable-length opcodes reference parsers in
``xi_events.custom_parsers`` by code lookup.

Hand-refined entries in ``opcodes.py`` are NOT touched by this script — the
dict ``OPS`` lets the later @op call overwrite the earlier one, so refining is
just editing ``opcodes.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
META = ROOT / "xi_events" / "opcodes_meta.json"
OUT = ROOT / "xi_events" / "opcodes_auto.py"


HEADER = '''\
"""Auto-generated. Re-run scripts/generate_opcodes.py to refresh."""

from __future__ import annotations

from luaparser import astnodes as N

from . import work_area as W
from .custom_parsers import PARSERS as _CUSTOM_PARSERS
from .registry import op


_ASCII_HINT_NAMES = ("scheduler_id", "action_id", "animation", "ext_scheduler_id")
_SENTINEL_LO, _SENTINEL_HI = 0x7FFFFFC0, 0x7FFFFFFF
_ENTITY_LO, _ENTITY_HI = 0x01000000, 0x01FFFFFF

# u16 operand names that hold a *work-area address* (and should be rendered as
# ``scratch[N] / params[N] / state[N] / imed[N]`` etc). Anything not in this
# allow-list, and not suffixed with ``_offset``, is treated as a scalar literal
# — by far the more common case (server ids, durations, modes, coords, ...).
_WORK_ADDR_NAMES = frozenset(
    [
        "dest_value",
        "source_value",
        "val1",
        "val2",
        "input",
        "result",
        "source",
        "dest",
        "default_option",
        "x_input",
        "y_input",
    ]
)
_BRANCH_OPERAND_NAMES = frozenset(
    ["target", "else_target", "else_offset", "jump_offset", "offset", "first_offset", "second_offset"]
)


def _is_work_addr_u16(name):
    if name in _BRANCH_OPERAND_NAMES:
        return False
    if name in _WORK_ADDR_NAMES:
        return True
    return name.endswith("_offset") or name.endswith("_destination")


def _generic_emit(opname, operands=()):
    """Render an opcode invocation as ``vm:camelName(arg1, arg2, ...)``.

    Operand types from the catalog drive how each value is rendered:
    - ``u8`` → literal number (u8 fields can never be a work-area address).
    - ``u32`` → resolved as an entity name when in the sentinel or real-id
      ranges, an ASCII action id when shaped like one, else as a work value.
    - ``u16`` and unspecified → resolved as a work-area reference; ASCII-shaped
      values get rendered as quoted action ids.

    Variable-length opcodes go through ``custom_parse`` and bypass the operand
    list — their args appear in ``vars(a)`` and we fall back to the heuristic.
    """

    op_types = {name: type_ for name, type_ in operands}

    def emit(ctx, a):
        args = []
        for k, v in vars(a).items():
            if k == "raw":
                if isinstance(v, (bytes, bytearray)):
                    args.append(W.lua_string(v.hex()))
                continue
            type_ = op_types.get(k)
            if isinstance(v, int):
                args.append(_render_int(ctx, k, v, type_))
            elif isinstance(v, (bytes, bytearray)):
                args.append(W.lua_string(v.hex()))
            else:
                args.append(N.Name(str(v)))
        return ctx.invoke("vm", _camel(opname), args)

    return emit


def _render_int(ctx, name, value, type_):
    if type_ == "u8":
        return N.Number(value)
    if type_ == "u32":
        if _SENTINEL_LO <= value <= _SENTINEL_HI or _ENTITY_LO <= value <= _ENTITY_HI:
            return ctx.entity(value)
        if name in _ASCII_HINT_NAMES or _looks_ascii(value):
            return W.lua_string(W.action_id(value))
        return ctx.value(value)
    # u16 (and untyped fallback for custom-parsed opcodes).
    if _SENTINEL_LO <= value <= _SENTINEL_HI:
        return ctx.entity(value)
    if _ENTITY_LO <= value <= _ENTITY_HI:
        return ctx.entity(value)
    if name in _ASCII_HINT_NAMES or _looks_ascii(value):
        return W.lua_string(W.action_id(value))
    # IMED reference (the VM resolves these regardless of operand role).
    if 0x8000 <= value <= 0x8FFF:
        return ctx.value(value)
    if type_ == "u16" and not _is_work_addr_u16(name):
        return N.Number(value)
    return ctx.value(value)


def _camel(name):
    parts = name.lower().split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


def _looks_ascii(v):
    if not (0x20202020 <= v <= 0x7E7E7E7E):
        return False
    bs = (v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF)
    return all(0x20 <= b <= 0x7E for b in bs)
'''


def main():
    meta = json.loads(META.read_text(encoding="utf-8"))
    parts = [HEADER]

    for entry in meta:
        code = entry["code"]
        name = entry["name"]
        operands = entry["operands"]
        terminal = entry["terminal"]
        branch_op = entry["branch_operand"]
        variable = entry["variable_length"]

        decl = f"@op(0x{code:02X}, {name!r}"
        if not variable and operands:
            ops_repr = (
                "["
                + ", ".join(f'("{o["name"]}", "{o["type"]}")' for o in operands)
                + "]"
            )
            decl += f", operands={ops_repr}"
        if variable:
            decl += f", custom_parse=_CUSTOM_PARSERS[0x{code:02X}]"
        if terminal:
            decl += ", terminal=True"
        if branch_op:
            decl += f", branches=lambda a: [a.{branch_op}]"
        decl += ")"

        parts.append(decl)
        parts.append(f"def _auto_{code:02X}(ctx, a):")
        if not variable and operands:
            ops_repr = (
                "("
                + ", ".join(f'("{o["name"]}", "{o["type"]}")' for o in operands)
                + ",)"
            )
            parts.append(f"    return _generic_emit({name!r}, {ops_repr})(ctx, a)")
        else:
            parts.append(f"    return _generic_emit({name!r})(ctx, a)")
        parts.append("")

    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {OUT} ({len(meta)} opcodes)")


if __name__ == "__main__":
    main()
