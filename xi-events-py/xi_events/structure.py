"""Structural analysis: CFG -> tree of Raw / IfNode statements.

Merge points are recovered as immediate post-dominators, computed via
Cooper-Harvey-Kennedy directly on our adjacency dicts. FFXI's
IF_CONDITIONAL has semantics ``IF !(cond) GOTO else`` so the fall-through
path runs when the condition is true; emit returns the condition AS-WRITTEN.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from .cfg import CFG, EDGE_BRANCH, EDGE_FALLTHROUGH
from .disasm import Instruction


@dataclass
class Raw:
    inst: Instruction


@dataclass
class IfNode:
    cond_inst: Instruction
    then: list
    else_: list
    cond: Any = None  # populated by emit


def recover(cfg: CFG) -> list:
    if not cfg:
        return []
    return _walk(
        cfg,
        start=cfg.entry,
        stop=None,
        ipdoms=_immediate_post_dominators(cfg),
        # shared across recursion so back-edges in loops terminate the walk
        visited=set(),
    )


# Known limitation: ``visited`` is shared globally across the entire walk to
# prevent infinite recursion on back-edges. Side effect: if a block (typically
# a popular merge point reached by multiple ifs) is visited via an early
# walk path, later branches that target it will see it as visited and exit
# empty. Symptom in output: ``if cond then end`` where the body should have
# been the merge code. A targeted fix would require dropping the global
# visited (relying on ``stop=merge`` post-dominator boundaries) and handling
# back-edges via per-walk-stack cycle detection — non-trivial because
# ``_immediate_post_dominators`` currently filters function-exit-bound merges
# to ``None``, which the walker treats as "walk until exit".


def _walk(
    cfg: CFG,
    start: int | None,
    stop: int | None,
    ipdoms: dict[int, int],
    visited: set[int],
) -> list:
    out: list = []
    cur = start
    while cur is not None and cur != stop and cur not in visited:
        visited.add(cur)
        block = cfg.blocks[cur]
        last = block[-1]

        for inst in block[:-1]:
            out.append(Raw(inst))

        if last.name == "GOTO":
            target = last.branch_targets[0] if last.branch_targets else None
            cur = target if target in cfg.blocks else None
            continue

        # Any non-terminal opcode with branch_targets is a conditional
        # (IF_CONDITIONAL, TEST_BIT_AND_BRANCH, IF_ENTITY_VALID, ...).
        if not last.terminal and last.branch_targets:
            then_start = cfg.successor(cur, EDGE_FALLTHROUGH)
            else_start = cfg.successor(cur, EDGE_BRANCH)
            merge = ipdoms.get(cur)

            then_stmts = (
                _walk(cfg, then_start, merge, ipdoms, visited) if then_start else []
            )
            else_stmts = (
                []
                if merge == else_start
                else (
                    _walk(cfg, else_start, merge, ipdoms, visited) if else_start else []
                )
            )

            out.append(IfNode(cond_inst=last, then=then_stmts, else_=else_stmts))
            cur = merge
            continue

        if last.terminal:
            out.append(Raw(last))
            return out

        out.append(Raw(last))
        succs = cfg.successors(cur)
        cur = succs[0] if succs else None

    return out


# Sentinel for the virtual exit added when computing post-dominators.
_EXIT = -1


def _immediate_post_dominators(cfg: CFG) -> dict[int, int]:
    """Immediate post-dominators of ``cfg``, computed as Cooper-Harvey-Kennedy
    immediate dominators on the reversed CFG rooted at a virtual exit.

    In the reversed CFG: predecessors of ``n`` are its original successors,
    and successors of ``n`` are its original predecessors. The virtual
    ``_EXIT`` has edges to every real exit (nodes with no original successors).
    """
    succ = {n: cfg.successors(n) for n in cfg.blocks}
    real_exits = [n for n, s in succ.items() if not s]
    if not real_exits:
        return {}

    fwd_preds: dict[int, list[int]] = {n: [] for n in cfg.blocks}
    for src, tgts in succ.items():
        for t in tgts:
            fwd_preds[t].append(src)

    # Reversed-CFG predecessors / successors.
    rev_preds = {n: list(succ[n]) for n in cfg.blocks}
    for n in real_exits:
        rev_preds[n].append(_EXIT)
    rev_preds[_EXIT] = []
    rev_succs: dict[int, list[int]] = {_EXIT: list(real_exits), **fwd_preds}

    # Iterative DFS for postorder of the reversed CFG starting at _EXIT.
    order: list[int] = []
    seen: set[int] = {_EXIT}
    stack: list[tuple[int, Iterator[int]]] = [(_EXIT, iter(rev_succs[_EXIT]))]
    while stack:
        node, it = stack[-1]
        try:
            child = next(it)
            if child not in seen:
                seen.add(child)
                stack.append((child, iter(rev_succs.get(child, ()))))
        except StopIteration:
            order.append(node)
            stack.pop()

    rpo = list(reversed(order))
    rpo_index = {n: i for i, n in enumerate(rpo)}

    idom: dict[int, int] = {_EXIT: _EXIT}

    def intersect(b1: int, b2: int) -> int:
        f1, f2 = b1, b2
        while f1 != f2:
            while rpo_index[f1] > rpo_index[f2]:
                f1 = idom[f1]
            while rpo_index[f2] > rpo_index[f1]:
                f2 = idom[f2]
        return f1

    changed = True
    while changed:
        changed = False
        for b in rpo:
            if b == _EXIT:
                continue
            preds = [p for p in rev_preds[b] if p in idom]
            if not preds:
                continue
            new_idom = preds[0]
            for p in preds[1:]:
                new_idom = intersect(p, new_idom)
            if idom.get(b) != new_idom:
                idom[b] = new_idom
                changed = True

    return {n: d for n, d in idom.items() if n != _EXIT and d != _EXIT and n != d}
