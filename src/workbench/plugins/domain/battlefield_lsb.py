"""Conservative extraction of modern LSB battlefield policy surfaces."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


@dataclass(frozen=True)
class LsbBattlefieldPolicySurface:
    resolved_fields: dict[str, Any]
    unresolved_fields: dict[str, str]


_INT_FIELD_PATTERNS={
    "party_size":re.compile(r"\bmaxPlayers\s*=\s*(\d+)\s*,"),
}
_BOOL_FIELD_PATTERNS={
    "is_mission":re.compile(r"\bisMission\s*=\s*(true|false)\s*,",re.I),
}
_TIME_MINUTES_RE=re.compile(r"\btimeLimit\s*=\s*utils\.minutes\(\s*(\d+)\s*\)\s*,")
_LEVEL_CAP_RE=re.compile(r"\blevelCap\s*=\s*([^,\n]+)\s*,")


def extract_lsb_battlefield_policy(lua_text: str) -> LsbBattlefieldPolicySurface:
    resolved={}
    unresolved={}

    for logical_name,pattern in _INT_FIELD_PATTERNS.items():
        match=pattern.search(lua_text)
        if match:
            resolved[logical_name]=int(match.group(1))

    for logical_name,pattern in _BOOL_FIELD_PATTERNS.items():
        match=pattern.search(lua_text)
        if match:
            resolved[logical_name]=match.group(1).lower()=="true"

    match=_TIME_MINUTES_RE.search(lua_text)
    if match:
        resolved["time_limit"]=int(match.group(1))*60

    match=_LEVEL_CAP_RE.search(lua_text)
    if match:
        expression=match.group(1).strip()
        if re.fullmatch(r"\d+",expression):
            resolved["level_cap"]=int(expression)
        else:
            unresolved["level_cap"]=expression

    return LsbBattlefieldPolicySurface(
        resolved_fields=resolved,
        unresolved_fields=unresolved,
    )


def extract_lsb_mission_level_cap(policy_text: str, battlefield_symbol: str) -> int | None:
    """Resolve the era mission-level-cap table for one explicit battlefield symbol."""
    symbol=re.escape(battlefield_symbol)
    pattern=re.compile(rf"\b{symbol}\s*,\s*(\d+)\b")
    match=pattern.search(policy_text)
    return int(match.group(1)) if match else None


@dataclass(frozen=True)
class LsbBattlefieldMobGroups:
    groups: tuple[tuple[int, ...], ...]
    unresolved_expressions: tuple[str, ...]


_MOB_IDS_RE=re.compile(r"\bmobIds\s*=\s*\{")


def _balanced_block(text: str, open_index: int) -> tuple[str, int]:
    depth=0
    for index in range(open_index,len(text)):
        char=text[index]
        if char=="{":
            depth+=1
        elif char=="}":
            depth-=1
            if depth==0:
                return text[open_index:index+1],index+1
    raise ValueError("Unbalanced Lua table while reading mobIds")


def _immediate_child_tables(block: str) -> tuple[str, ...]:
    children=[]
    depth=0
    start=None
    for index,char in enumerate(block):
        if char=="{":
            depth+=1
            if depth==2:
                start=index
        elif char=="}":
            if depth==2 and start is not None:
                children.append(block[start:index+1])
                start=None
            depth-=1
    return tuple(children)


def _resolve_mob_expression(expression: str, symbols: Mapping[str,int]) -> int | None:
    expression=expression.strip()
    if not expression:
        return None
    if re.fullmatch(r"\d+",expression):
        return int(expression)
    match=re.fullmatch(r"([A-Za-z_][A-Za-z0-9_.]*)(?:\s*\+\s*(\d+))?",expression)
    if not match:
        return None
    symbol=match.group(1)
    if symbol not in symbols:
        return None
    return int(symbols[symbol])+int(match.group(2) or 0)


def extract_lsb_battlefield_mob_groups(
    lua_text: str,
    symbols: Mapping[str,int],
) -> LsbBattlefieldMobGroups:
    """Resolve immediate child groups from all literal mobIds tables.

    Only numeric IDs and explicit symbol or symbol+integer expressions are accepted.
    Any other expression is preserved as unresolved evidence instead of guessed.
    """
    groups=[]
    unresolved=[]
    position=0
    while True:
        match=_MOB_IDS_RE.search(lua_text,position)
        if not match:
            break
        open_index=lua_text.find("{",match.start())
        block,end=_balanced_block(lua_text,open_index)
        children=_immediate_child_tables(block)
        if not children:
            children=(block,)
        for child in children:
            inner=child[1:-1]
            expressions=[
                token.strip()
                for token in inner.split(",")
                if token.strip() and not token.strip().startswith("--")
            ]
            group=[]
            for expression in expressions:
                # Remove a trailing single-line comment without interpreting its text.
                expression=expression.split("--",1)[0].strip()
                if not expression:
                    continue
                value=_resolve_mob_expression(expression,symbols)
                if value is None:
                    unresolved.append(expression)
                else:
                    group.append(value)
            if group:
                groups.append(tuple(group))
        position=end

    return LsbBattlefieldMobGroups(
        groups=tuple(groups),
        unresolved_expressions=tuple(unresolved),
    )
