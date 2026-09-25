"""Symbol-aware comparison helpers for instance entity membership.

Numeric entity IDs can remain present across forks while their symbolic/script
identity shifts. This module keeps numeric and semantic overlap separate.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Any


@dataclass(frozen=True)
class EntityIdentity:
    entity_id: int
    symbol: str | None = None
    entity_type: str | None = None
    source: str | None = None


@dataclass(frozen=True)
class EntityIdentityDrift:
    symbol: str
    source_id: int
    target_id: int
    classification: str = "RENUMBER"


def compare_symbol_maps(
    source: Mapping[str,int],
    target: Mapping[str,int],
) -> dict[str,Any]:
    shared_symbols=sorted(set(source) & set(target))
    renumbered=[
        EntityIdentityDrift(symbol,sid:=source[symbol],target[symbol])
        for symbol in shared_symbols
        if (sid:=source[symbol]) != target[symbol]
    ]
    stable=[
        {"symbol":symbol,"entity_id":source[symbol]}
        for symbol in shared_symbols
        if source[symbol] == target[symbol]
    ]
    return {
        "stable":stable,
        "renumbered":renumbered,
        "source_only_symbols":sorted(set(source)-set(target)),
        "target_only_symbols":sorted(set(target)-set(source)),
    }


def semantic_membership(
    entity_ids: set[int],
    symbols: Mapping[str,int],
) -> dict[str,Any]:
    by_id={entity_id:symbol for symbol,entity_id in symbols.items()}
    return {
        "symbols":sorted(
            [{"symbol":by_id[i],"entity_id":i} for i in entity_ids if i in by_id],
            key=lambda row:(row["symbol"],row["entity_id"]),
        ),
        "unresolved_ids":sorted(i for i in entity_ids if i not in by_id),
    }
