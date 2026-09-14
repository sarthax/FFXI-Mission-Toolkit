"""Pipeline: Fixture -> Lua source text."""

from __future__ import annotations

# Side-effect imports register opcode handlers in registry.OPS.
# opcodes_auto provides 218 placeholders, opcodes overwrites the ~50
# we hand-refined.
from . import opcodes_auto  # noqa: F401
from . import opcodes  # noqa: F401

from .analyze import EventInfo, analyze
from .cfg import build as build_cfg
from .dataset import Fixture
from .disasm import disassemble
from .emit import EmitContext, render
from .structure import recover
from .work_area import action_id

_PREVIEW_MAX = 70
_JUMP_TO_POSITION = 0x1A


def decompile(fixture: Fixture, *, comments: bool = True) -> str:
    """Decompile an event to Lua source.

    ``comments=False`` produces bare Lua: no leading imed/params header, no
    inline ``-- "preview..."`` annotations, no dialog branch labels. Use this
    when you intend to resolve string ids out-of-band (e.g. to write a
    parquet column where lookups happen at render time).
    """
    ctx = EmitContext(
        imed=fixture.imed_data,
        strings=fixture.strings if comments else {},
        entities=fixture.entities,
        actor_id=fixture.actor_id,
    )

    # Branch and JUMP_TO_POSITION operands are absolute offsets in the
    # actor-block frame. Use ``block_bytecode`` (all events in the block
    # stitched at their absolute offsets) when available so subs that live in
    # sibling events resolve correctly. Fall back to per-event padding for
    # hand-built fixtures.
    if fixture.block_bytecode is not None:
        framed = fixture.block_bytecode
    else:
        framed = b"\x00" * fixture.entrypoint + fixture.bytecode

    main_src, sub_targets = _render_one(
        framed, fixture.entrypoint, f"event_{fixture.event_id}", ctx
    )

    seen, queue = {fixture.entrypoint}, list(sub_targets)
    sub_pairs: list[tuple[int, str]] = []
    while queue:
        target = queue.pop()
        if target in seen:
            continue
        seen.add(target)
        try:
            sub_src, more = _render_one(framed, target, f"sub_{target:04X}", ctx)
            sub_pairs.append((target, sub_src))
            queue.extend(more)
        except Exception:
            pass

    sub_srcs = [s for _, s in sorted(sub_pairs)]
    parts = sub_srcs + [main_src]

    if comments:
        info = analyze(fixture)
        header = _summary_lines(info, fixture)
        if header:
            return "\n".join(header) + "\n" + "\n\n".join(parts)
    return "\n\n".join(parts)


def _render_one(
    bytecode: bytes, entrypoint: int, name: str, ctx: EmitContext
) -> tuple[str, set[int]]:
    instructions = disassemble(bytecode, entrypoint)
    cfg = build_cfg(instructions)
    stmts = recover(cfg)
    src = render(stmts, name, ctx)
    sub_targets = {
        i.args.target for i in instructions if i.opdef.code == _JUMP_TO_POSITION
    }
    return src, sub_targets


def _summary_lines(info: EventInfo, fixture: Fixture) -> list[str]:
    lines = []
    if info.params:
        lines.append(f"-- params: {', '.join(map(str, info.params))}")
    if info.state:
        lines.append(f"-- state:  {', '.join(map(str, info.state))}")
    if info.scratch:
        lines.append(f"-- scratch: {', '.join(map(str, info.scratch))}")

    written = []
    if info.uses_result:
        written.append("result")
    if info.uses_result2:
        written.append("result2")
    if written:
        lines.append(f"-- writes:  {', '.join(written)}")

    imed_lines = _imed_table(info, fixture)
    if imed_lines:
        if lines:
            lines.append("--")
        lines.extend(imed_lines)
    return lines


def _imed_table(info: EventInfo, fixture: Fixture) -> list[str]:
    if not info.imed:
        return []
    out = ["-- imed:"]
    for idx in sorted(info.imed):
        slot = info.imed[idx]
        annot = _annotate_imed_slot(slot["value"], slot["kind"], fixture)
        if annot is None:
            continue
        out.append(f"--   [{idx:>2}] = {slot['value']:<10} {annot}")
    return out if len(out) > 1 else []


def _annotate_imed_slot(value: int, kind: str | None, fixture: Fixture) -> str | None:
    if kind == "string":
        text = fixture.strings.get(value)
        if text:
            preview = (
                text[: _PREVIEW_MAX - 3] + "..." if len(text) > _PREVIEW_MAX else text
            )
            preview = preview.replace("\n", " ")
            return f'string "{preview}"'
        return "string ?"
    if kind == "item":
        name = fixture.items.get(value)
        return f"item {name!r}" if name else "item ?"
    if kind == "ticks":
        return f"ticks ({value / 60:.1f}s)"
    if kind == "ascii":
        return f'ascii "{action_id(value)}"'
    if kind == "bit":
        return "bit"
    return None
