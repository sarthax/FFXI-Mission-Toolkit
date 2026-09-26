"""Experimental source-text probes for unregistered migration routes.

Probes never advertise converter support. They run existing deterministic converters
against representative source text and report unresolved/flagged output so a dedicated
backend can be designed from evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

import backport_lua_convert as legacy_lua


LSB_FRAMEWORK_METHODS=frozenset({
    "complete",
    "entryRequirement",
    "event",
    "getVar",
    "new",
    "progressEvent",
    "register",
    "replaceDefault",
    "setVar",
})

_METHOD_RE=re.compile(r":([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_METHOD_DEFINITION_RE=re.compile(r"function\s+[A-Za-z_][A-Za-z0-9_.]*:([A-Za-z_][A-Za-z0-9_]*)\s*\(")


@dataclass(frozen=True)
class LuaMethodSurface:
    framework_methods: tuple[str, ...]
    binding_candidate_methods: tuple[str, ...]
    method_definitions: tuple[str, ...]


def classify_lsb_lua_methods(text: str) -> LuaMethodSurface:
    definitions=set(_METHOD_DEFINITION_RE.findall(text))
    methods=set(_METHOD_RE.findall(text))-definitions
    framework=methods & set(LSB_FRAMEWORK_METHODS)
    bindings=methods-framework
    return LuaMethodSurface(
        framework_methods=tuple(sorted(framework)),
        binding_candidate_methods=tuple(sorted(bindings)),
        method_definitions=tuple(sorted(definitions)),
    )


@dataclass(frozen=True)
class LuaRouteProbe:
    route: str
    converted_text: str
    flagged_count: int
    leftover_count: int
    flagged: tuple[dict, ...]
    leftovers: tuple[dict, ...]
    status: str
    method_surface: LuaMethodSurface | None = None


def probe_lsb_to_dsp_lua(text: str) -> LuaRouteProbe:
    result=legacy_lua.convert(text,target="old_dsp_reference")
    leftovers=tuple(result.unflagged_leftovers())
    flagged=tuple(result.flagged)
    method_surface=classify_lsb_lua_methods(text)
    if flagged or leftovers:
        status="GAPS_FOUND"
    elif method_surface.framework_methods:
        status="FRAMEWORK_ADAPTATION_REQUIRED"
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
        method_surface=method_surface,
    )
