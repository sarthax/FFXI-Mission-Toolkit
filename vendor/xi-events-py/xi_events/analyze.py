"""Static analysis of an event: storage slots, messages, entities, imed kinds."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .dataset import Fixture
from .disasm import disassemble

_PARAMS_LO = 0x1002
_PARAMS_HI = 0x1009
_STATE_LO = 0x1000
_STATE_HI = 0x105F
_SCRATCH_HI = 0x004F
_IMED_LO = 0x8000
_IMED_HI = 0x8FFF

# u32 sentinels (LocalPlayer, EventEntity, party slots, etc.). Filtered out
# of the entities list — they're VM placeholders, not real entity ids.
_SENTINEL_LO = 0x7FFFFFC0
_SENTINEL_HI = 0x7FFFFFFF
# Real entity ids look like 0x01000000 + N (FFXI server-id format).
_ENTITY_LO = 0x01000000
_ENTITY_HI = 0x01FFFFFF

_BRANCH_OPERAND_NAMES = {"target", "else_target", "jump_offset", "offset"}

# Operand-name -> imed-slot semantic kind. Driven by FFXI VM convention:
# the operand a value flows into determines what kind of value it is.
_OPERAND_KIND = {
    "message": "string",
    "msg": "string",
    "message_id": "string",
    "ticks": "ticks",
    "wait_value": "ticks",
    "scheduler_id": "ascii",
    "action_id": "ascii",
    "ext_scheduler_id": "ascii",
    "animation": "ascii",
    "animation_id": "ascii",
    "bit": "bit",
    "bit_index": "bit",
    "start_bit": "bit",
    "end_bit": "bit",
    "item": "item",
    "item_id": "item",
}


@dataclass
class EventInfo:
    params: list[int] = field(default_factory=list)
    state: list[int] = field(default_factory=list)
    scratch: list[int] = field(default_factory=list)
    string_refs: list[int] = field(default_factory=list)
    entities: list[int] = field(default_factory=list)
    uses_result: bool = False
    uses_result2: bool = False
    # Sparse: only slots this event actually consumes, mapped to
    # ``{"kind": "string"|"item"|"ticks"|"ascii"|"bit", "value": <imed_data[idx]>}``.
    # Self-contained — consumer doesn't need to join back against the actor record.
    imed: dict[int, dict] = field(default_factory=dict)


def analyze(fixture: Fixture) -> EventInfo:
    params: set[int] = set()
    state: set[int] = set()
    scratch: set[int] = set()
    string_refs: set[int] = set()
    entities: set[int] = set()
    imed_kind_votes: dict[int, Counter[str]] = {}
    uses_result = False
    uses_result2 = False
    imed = fixture.imed_data

    framed = b"\x00" * fixture.entrypoint + fixture.bytecode

    for inst in disassemble(framed, fixture.entrypoint):
        for name, type_ in inst.opdef.operands:
            value = getattr(inst.args, name, None)
            if value is None:
                continue

            if type_ == "u32":
                if _is_real_entity(value):
                    entities.add(value)
                continue

            if type_ != "u16" or name in _BRANCH_OPERAND_NAMES:
                continue

            if _IMED_LO <= value <= _IMED_HI:
                idx = value & 0x7FFF
                if name in _OPERAND_KIND:
                    imed_kind_votes.setdefault(idx, Counter())[_OPERAND_KIND[name]] += 1
                if _OPERAND_KIND.get(name) == "string" and idx < len(imed):
                    string_refs.add(imed[idx])
                continue

            if value == _STATE_LO:
                uses_result = True
            elif value == _STATE_LO + 1:
                uses_result2 = True
            elif _PARAMS_LO <= value <= _PARAMS_HI:
                params.add(value - _PARAMS_LO)
            elif _STATE_LO <= value <= _STATE_HI:
                state.add(value - _STATE_LO)
            elif value <= _SCRATCH_HI:
                scratch.add(value)

        # Variable-length opcodes (custom_parse) bypass the operand list, so
        # also scan their args dict for entity-shaped ints.
        if inst.opdef.custom_parse is not None:
            for v in vars(inst.args).values():
                if isinstance(v, int) and _is_real_entity(v):
                    entities.add(v)

    imed_out = {
        idx: {"kind": votes.most_common(1)[0][0], "value": imed[idx]}
        for idx, votes in imed_kind_votes.items()
        if idx < len(imed)
    }

    return EventInfo(
        params=sorted(params),
        state=sorted(state),
        scratch=sorted(scratch),
        string_refs=sorted(string_refs),
        entities=sorted(entities),
        uses_result=uses_result,
        uses_result2=uses_result2,
        imed=imed_out,
    )


def _is_real_entity(value: int) -> bool:
    if _SENTINEL_LO <= value <= _SENTINEL_HI:
        return False
    return _ENTITY_LO <= value <= _ENTITY_HI
