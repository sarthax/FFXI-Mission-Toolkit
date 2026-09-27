"""Conservative static extractor for LandSandBoat-style Mission/Quest Lua.

This first pass extracts only literal constructs that can be tied to source text
without executing Lua. Unsupported/dynamic expressions remain visible as findings.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .mission_state_machine import EventIdentity, StateChannel, StateCondition, TransitionEffect


@dataclass(frozen=True)
class LsbMissionFinding:
    kind: str
    value: str
    zone: str | None = None
    actor: str | None = None
    event_id: int | None = None


_ZONE=re.compile(r"\[xi\.zone\.([A-Z0-9_]+)\]\s*=")
_ACTOR=re.compile(r"\['([^']+)'\]\s*=")
_EVENT=re.compile(r"mission:(?:progressEvent|event|progressCutscene)\((\d+)")
_STATUS_SET=re.compile(r"player:setMissionStatus\([^\n]*?,\s*(\d+)\s*,\s*xi\.mission\.status\.[A-Z0-9_]+\.([A-Z0-9_]+)\)")
_VAR_SET=re.compile(r"mission:setVar\(player,\s*'([^']+)',\s*([^\)]+)\)")
_LOCAL_SET=re.compile(r"mission:setLocalVar\(player,\s*'([^']+)',\s*([^\)]+)\)")
_KI_GIVE=re.compile(r"(?:npcUtil\.giveKeyItem|player:addKeyItem)\(player?,?\s*xi\.keyItem\.([A-Z0-9_]+)")
_KI_DEL=re.compile(r"player:delKeyItem\(xi\.keyItem\.([A-Z0-9_]+)\)")
_BATTLEFIELD=re.compile(r"battlefieldWin'\)\s*==\s*xi\.battlefield\.id\.([A-Z0-9_]+)")
_SPAWN=re.compile(r"SpawnMob\([^\n]*?([A-Z0-9_]+)\)")
_TITLE=re.compile(r"player:addTitle\(xi\.title\.([A-Z0-9_]+)\)")
_TIMER=re.compile(r"player:timer\(([^,]+),")
_COMPLETE=re.compile(r"mission:complete\(player\)")


def extract_lsb_mission_findings(lua: str) -> tuple[LsbMissionFinding,...]:
    findings=[]
    zone=None
    actor=None
    for line in lua.splitlines():
        zm=_ZONE.search(line)
        if zm:
            zone=zm.group(1); actor=None
        am=_ACTOR.search(line)
        if am:
            actor=am.group(1)
        for m in _EVENT.finditer(line):
            findings.append(LsbMissionFinding("event",m.group(1),zone,actor,int(m.group(1))))
        for m in _STATUS_SET.finditer(line):
            findings.append(LsbMissionFinding("status_set",f"{m.group(2)}={m.group(1)}",zone,actor))
        for m in _VAR_SET.finditer(line):
            findings.append(LsbMissionFinding("var_set",f"{m.group(1)}={m.group(2).strip()}",zone,actor))
        for m in _LOCAL_SET.finditer(line):
            findings.append(LsbMissionFinding("local_set",f"{m.group(1)}={m.group(2).strip()}",zone,actor))
        for m in _KI_GIVE.finditer(line):
            findings.append(LsbMissionFinding("key_item_grant",m.group(1),zone,actor))
        for m in _KI_DEL.finditer(line):
            findings.append(LsbMissionFinding("key_item_remove",m.group(1),zone,actor))
        for m in _BATTLEFIELD.finditer(line):
            findings.append(LsbMissionFinding("battlefield_win",m.group(1),zone,actor))
        for m in _SPAWN.finditer(line):
            findings.append(LsbMissionFinding("spawn_entity",m.group(1),zone,actor))
        for m in _TITLE.finditer(line):
            findings.append(LsbMissionFinding("title_grant",m.group(1),zone,actor))
        for m in _TIMER.finditer(line):
            findings.append(LsbMissionFinding("timer",m.group(1).strip(),zone,actor))
        if _COMPLETE.search(line):
            findings.append(LsbMissionFinding("mission_complete","true",zone,actor))
    return tuple(findings)


def channels_from_findings(findings: Iterable[LsbMissionFinding]) -> tuple[StateChannel,...]:
    persistent={}; local={}
    for f in findings:
        if f.kind=="status_set":
            channel,value=f.value.split("=",1)
            persistent.setdefault(f"mission_status:{channel}",set()).add(int(value))
        elif f.kind=="var_set":
            name,value=f.value.split("=",1)
            persistent.setdefault(f"mission_var:{name}",set()).add(value)
        elif f.kind=="local_set":
            name,value=f.value.split("=",1)
            local.setdefault(f"local_var:{name}",set()).add(value)
    return tuple(
        [StateChannel(k,"PERSISTENT",tuple(sorted(v,key=str))) for k,v in sorted(persistent.items())]+
        [StateChannel(k,"LOCAL",tuple(sorted(v,key=str))) for k,v in sorted(local.items())]
    )
