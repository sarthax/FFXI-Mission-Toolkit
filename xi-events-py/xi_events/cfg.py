"""Basic-block CFG. Nodes are leader offsets; edges are kind-typed."""

from __future__ import annotations

from dataclasses import dataclass, field

from .disasm import Instruction

EDGE_FALLTHROUGH = "fallthrough"
EDGE_BRANCH = "branch"
EDGE_GOTO = "goto"


@dataclass
class CFG:
    entry: int = 0
    blocks: dict[int, list[Instruction]] = field(default_factory=dict)
    # leader -> [(successor_leader, edge_kind), ...]; order matters for the
    # structural pass (fallthrough first, branch second on conditionals).
    edges: dict[int, list[tuple[int, str]]] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.blocks)

    def successor(self, leader: int, kind: str) -> int | None:
        for tgt, k in self.edges.get(leader, ()):
            if k == kind:
                return tgt
        return None

    def successors(self, leader: int) -> list[int]:
        return [tgt for tgt, _ in self.edges.get(leader, ())]


def build(instructions: list[Instruction]) -> CFG:
    if not instructions:
        return CFG()

    by_offset = {i.offset: i for i in instructions}
    leaders = sorted(_find_leaders(instructions, by_offset))
    blocks = {leader: _slice_block(instructions, leader, leaders) for leader in leaders}

    cfg = CFG(entry=leaders[0], blocks=blocks)

    for idx, leader in enumerate(leaders):
        last = blocks[leader][-1]
        next_leader = leaders[idx + 1] if idx + 1 < len(leaders) else None
        _wire_successors(cfg, leader, last, next_leader, blocks)

    return cfg


def successor(cfg: CFG, leader: int, kind: str) -> int | None:
    return cfg.successor(leader, kind)


def _find_leaders(
    instructions: list[Instruction], by_offset: dict[int, Instruction]
) -> set[int]:
    leaders = {instructions[0].offset}
    for idx, inst in enumerate(instructions):
        for target in inst.branch_targets:
            if target in by_offset:
                leaders.add(target)
        if (inst.terminal or inst.branch_targets) and idx + 1 < len(instructions):
            leaders.add(instructions[idx + 1].offset)
    return leaders


def _slice_block(
    instructions: list[Instruction], leader: int, leaders: list[int]
) -> list[Instruction]:
    end = next((l for l in leaders if l > leader), float("inf"))
    return [i for i in instructions if leader <= i.offset < end]


def _wire_successors(
    cfg: CFG,
    leader: int,
    last: Instruction,
    next_leader: int | None,
    blocks: dict[int, list[Instruction]],
) -> None:
    edges: list[tuple[int, str]] = []

    if last.terminal and not last.branch_targets:
        pass
    elif last.terminal and last.branch_targets:
        target = last.branch_targets[0]
        if target in blocks:
            edges.append((target, EDGE_GOTO))
    elif last.branch_targets:
        if next_leader is not None:
            edges.append((next_leader, EDGE_FALLTHROUGH))
        for target in last.branch_targets:
            if target in blocks:
                edges.append((target, EDGE_BRANCH))
    elif next_leader is not None:
        edges.append((next_leader, EDGE_FALLTHROUGH))

    if edges:
        cfg.edges[leader] = edges
