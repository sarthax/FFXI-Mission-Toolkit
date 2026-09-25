"""Experimental source-text probes for unregistered migration routes.

Probes never advertise converter support. They run existing deterministic converters
against representative source text and report unresolved/flagged output so a dedicated
backend can be designed from evidence.
"""
from __future__ import annotations

from dataclasses import dataclass

import backport_lua_convert as legacy_lua


@dataclass(frozen=True)
class LuaRouteProbe:
    route: str
    converted_text: str
    flagged_count: int
    leftover_count: int
    flagged: tuple[dict, ...]
    leftovers: tuple[dict, ...]
    status: str


def probe_lsb_to_dsp_lua(text: str) -> LuaRouteProbe:
    result=legacy_lua.convert(text,target="old_dsp_reference")
    leftovers=tuple(result.unflagged_leftovers())
    flagged=tuple(result.flagged)
    if flagged or leftovers:
        status="GAPS_FOUND"
    else:
        status="CANDIDATE_CLEAN"
    return LuaRouteProbe(
        route="LSB->DSP:LUA",
        converted_text=result.converted,
        flagged_count=len(flagged),
        leftover_count=len(leftovers),
        flagged=flagged,
        leftovers=leftovers,
        status=status,
    )
