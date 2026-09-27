"""Conservative static extractor for LandSandBoat-style Mission/Quest Lua.

This first pass extracts only literal constructs that can be tied to source text
without executing Lua. Unsupported/dynamic expressions remain visible as findings.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .mission_state_machine import DependencyGate, EventIdentity, MissionState, MissionStateMachine, MissionTransition, StateChannel, StateCondition, TransitionEffect


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
_DECL_EVENT=re.compile(r"\['([^']+)'\]\s*=\s*mission:(progressEvent|event|progressCutscene)\((\d+)\)(.*)")
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


_FUNC_START=re.compile(r"(onTrigger|onTrade|onMobDeath|onZoneIn)\s*=\s*function")
_EVENT_FINISH_KEY=re.compile(r"\[(\d+)\]\s*=\s*function\(player,\s*csid")
_STATUS_EQ=re.compile(r"player:getMissionStatus\([^\n]*?xi\.mission\.status\.[A-Z0-9_]+\.([A-Z0-9_]+)\)\s*==\s*(\d+)")
_STATUS_NE=re.compile(r"player:getMissionStatus\([^\n]*?xi\.mission\.status\.[A-Z0-9_]+\.([A-Z0-9_]+)\)\s*~=\s*(\d+)")
_XPOS_EQ=re.compile(r"player:getXPos\(\)\s*==\s*(-?[0-9.]+)")
_POP_QM=re.compile(r"npcUtil\.popFromQM\([^\n]*?,\s*([^,\n]+),")
_VAR_EQ=re.compile(r"mission:getVar\(player,\s*'([^']+)'\)\s*==\s*(\d+)")
_LOCAL_EQ=re.compile(r"mission:getLocalVar\(player,\s*'([^']+)'\)\s*==\s*([A-Za-z0-9_\.]+)")
_STATUS_ALIAS=re.compile(r"local\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*player:getMissionStatus\([^\n]*?xi\.mission\.status\.[A-Z0-9_]+\.([A-Z0-9_]+)\)")
_ALIAS_EQ=re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*==\s*(\d+)")
_SPAWNED=re.compile(r"(not\s+)?GetMobByID\(([^\)]+)\):isSpawned\(\)")
_HAS_KI=re.compile(r"player:hasKeyItem\(xi\.keyItem\.([A-Z0-9_]+)\)")
_LACKS_KI=re.compile(r"not\s+player:hasKeyItem\(xi\.keyItem\.([A-Z0-9_]+)\)")
_DISTANCE=re.compile(r"player:checkDistance\(npc\)\s*([<>]=?)\s*([0-9.]+)")
_TRADE=re.compile(r"npcUtil\.tradeMatches\(trade,\s*(.+)\)")
_SETPOS=re.compile(r"player:setPos\(([^\)]+)\)")
_MESSAGE=re.compile(r"(?:player:messageSpecial|player:messageText|mission:messageSpecial|mission:messageName)\(([^\n]+)\)")
_HELPER_ASSIGN=re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*function\(player\)",re.M)


def _balanced_function_blocks(lua: str):
    """Yield (start_line, end_line, text) for simple Lua function blocks.

    Token counting is intentionally conservative; comments/strings are not treated
    as executable syntax. This is sufficient for Mission DSL handlers and fails
    closed when a block cannot be balanced.
    """
    lines=lua.splitlines()
    for i,line in enumerate(lines):
        if "function" not in line:
            continue
        depth=0
        started=False
        for j in range(i,len(lines)):
            code=lines[j].split("--",1)[0]
            opens=len(re.findall(r"\b(function|if|for|while|repeat)\b",code))
            closes=len(re.findall(r"\bend\b",code))+len(re.findall(r"\buntil\b",code))
            if opens:
                started=True
            depth+=opens-closes
            if started and depth<=0:
                yield i,j,"\n".join(lines[i:j+1])
                break


def _conditions(text: str) -> tuple[StateCondition,...]:
    out=[]
    for m in _STATUS_EQ.finditer(text):
        out.append(StateCondition(f"mission_status:{m.group(1)}","EQ",int(m.group(2))))
    for m in _STATUS_NE.finditer(text):
        out.append(StateCondition(f"mission_status:{m.group(1)}","NE",int(m.group(2))))
    for m in _XPOS_EQ.finditer(text):
        out.append(StateCondition("player:x","AT_POSITION",float(m.group(1))))
    aliases={m.group(1):m.group(2) for m in _STATUS_ALIAS.finditer(text)}
    for m in _ALIAS_EQ.finditer(text):
        if m.group(1) in aliases:
            out.append(StateCondition(f"mission_status:{aliases[m.group(1)]}","EQ",int(m.group(2))))
    for m in _VAR_EQ.finditer(text):
        out.append(StateCondition(f"mission_var:{m.group(1)}","EQ",int(m.group(2))))
    for m in _LOCAL_EQ.finditer(text):
        out.append(StateCondition(f"local_var:{m.group(1)}","EQ",m.group(2)))
    lacked=set(_LACKS_KI.findall(text))
    for symbol in lacked:
        out.append(StateCondition(f"key_item:{symbol}","LACKS",True))
    for symbol in _HAS_KI.findall(text):
        if symbol not in lacked:
            out.append(StateCondition(f"key_item:{symbol}","HAS",True))
    for m in _BATTLEFIELD.finditer(text):
        out.append(StateCondition(f"battlefield:{m.group(1)}","BATTLEFIELD_WON",True))
    for m in _DISTANCE.finditer(text):
        out.append(StateCondition("player_to_actor","WITHIN_DISTANCE",float(m.group(2))))
    for m in _TRADE.finditer(text):
        out.append(StateCondition("trade","TRADE_MATCHES",m.group(1).strip()))
    for m in _SPAWNED.finditer(text):
        out.append(StateCondition(f"entity:{m.group(2).strip()}","ENTITY_NOT_SPAWNED" if m.group(1) else "ENTITY_SPAWNED",True))
    return tuple(out)


def _effects(text: str) -> tuple[TransitionEffect,...]:
    out=[]
    for m in _STATUS_SET.finditer(text):
        out.append(TransitionEffect("SET_CHANNEL",f"mission_status:{m.group(2)}",int(m.group(1))))
    for m in _VAR_SET.finditer(text):
        out.append(TransitionEffect("SET_VAR",f"mission_var:{m.group(1)}",m.group(2).strip()))
    for m in _LOCAL_SET.finditer(text):
        out.append(TransitionEffect("SET_VAR",f"local_var:{m.group(1)}",m.group(2).strip()))
    for m in _KI_GIVE.finditer(text):
        out.append(TransitionEffect("GRANT",f"key_item:{m.group(1)}"))
    for m in _KI_DEL.finditer(text):
        out.append(TransitionEffect("REMOVE",f"key_item:{m.group(1)}"))
    for m in _SPAWN.finditer(text):
        out.append(TransitionEffect("SPAWN_ENTITY",f"entity:{m.group(1)}"))
    for m in _POP_QM.finditer(text):
        out.append(TransitionEffect("SPAWN_ENTITY",f"entity:{m.group(1).strip()}"))
    for m in _TITLE.finditer(text):
        out.append(TransitionEffect("GRANT_TITLE",f"title:{m.group(1)}"))
    for m in _TIMER.finditer(text):
        out.append(TransitionEffect("START_TIMER","timer",m.group(1).strip()))
    for m in _SETPOS.finditer(text):
        out.append(TransitionEffect("TELEPORT","player",m.group(1).strip()))
    if "player:tradeComplete()" in text:
        out.append(TransitionEffect("COMPLETE_TRADE","trade"))
    if _COMPLETE.search(text):
        out.append(TransitionEffect("COMPLETE","mission"))
    for m in _MESSAGE.finditer(text):
        out.append(TransitionEffect("MESSAGE","message",m.group(1).strip()))
    if "mission:noAction()" in text:
        out.append(TransitionEffect("NO_ACTION","interaction"))
    return tuple(out)


def correlate_lsb_handlers(lua: str, *, feature_id: str="mission:unknown") -> MissionStateMachine:
    """Correlate literal Mission DSL handler blocks into conservative transitions."""
    lines=lua.splitlines()
    zones=[(i,m.group(1)) for i,line in enumerate(lines) if (m:=_ZONE.search(line))]
    actors=[(i,m.group(1)) for i,line in enumerate(lines) if (m:=_ACTOR.search(line))]
    def context(line_no):
        zone=next((z for i,z in reversed(zones) if i<=line_no),None)
        actor=next((a for i,a in reversed(actors) if i<=line_no and not any(zi>i and zi<=line_no for zi,_ in zones)),None)
        return zone,actor

    transitions=[]
    states={"source:any":MissionState("source:any","Source state")}
    serial=0
    for start,end,text in _balanced_function_blocks(lua):
        first=lines[start]
        trigger=None; event=None
        ef=_EVENT_FINISH_KEY.search(first)
        zone,actor=context(start)
        if ef:
            trigger="EVENT_FINISH"
            event=EventIdentity(zone or "UNKNOWN",int(ef.group(1)),actor)
        elif "onTrigger" in first:
            trigger="NPC_INTERACT"
        elif "onTrade" in first:
            trigger="TRADE"
        elif "onMobDeath" in first:
            trigger="MOB_DEATH"
        elif "onZoneIn" in first:
            trigger="ZONE_IN"
        elif "onZoneOut" in first:
            trigger="ZONE_OUT"
        if not trigger:
            continue
        conds=_conditions(text); effects=_effects(text)
        returned=_EVENT.search(text)
        if returned and not event:
            event=EventIdentity(zone or "UNKNOWN",int(returned.group(1)),actor)
        if not (conds or effects or event):
            continue
        serial+=1
        gate=DependencyGate(f"source-gate:{serial}","ALL",conds) if conds else None
        transitions.append(MissionTransition(
            f"source-transition:{serial}","source:any","source:any",trigger,
            gate=gate,event=event,effects=effects,confidence="INFERRED",
            metadata={"zone":zone,"actor":actor,"source_lines":(start+1,end+1),"literal_correlation":True},
        ))
    # Declarative actor handlers are equivalent to unconditional NPC triggers.
    for line_no,line in enumerate(lines):
        dm=_DECL_EVENT.search(line)
        if not dm:
            continue
        zone,_=context(line_no)
        actor=dm.group(1); event_id=int(dm.group(3)); suffix=dm.group(4) or ""
        serial+=1
        transitions.append(MissionTransition(
            f"source-transition:{serial}","source:any","source:any","NPC_INTERACT",
            event=EventIdentity(zone or "UNKNOWN",event_id,actor),confidence="VERIFIED",
            metadata={
                "zone":zone,"actor":actor,"source_lines":(line_no+1,line_no+1),
                "literal_correlation":True,"declarative_handler":True,
                "replace_default":".replaceDefault()" in suffix,
                "important_event":".importantEvent()" in suffix,
            },
        ))

    findings=extract_lsb_mission_findings(lua)
    return MissionStateMachine(
        f"machine:{feature_id}",feature_id,tuple(states.values()),tuple(transitions),
        ("source:any",),channels=channels_from_findings(findings),
        metadata={"extractor":"lsb_static_literal","transition_count":len(transitions)},
    )


def materialize_channel_states(machine: MissionStateMachine) -> MissionStateMachine:
    """Replace source:any endpoints when one channel guard/write proves an edge."""
    states={s.state_id:s for s in machine.states}
    transitions=[]
    for t in machine.transitions:
        before=None; after=None
        if t.gate:
            eq=[c for c in t.gate.conditions if c.operator=="EQ" and c.subject.startswith(("mission_var:","mission_status:","local_var:"))]
            if len(eq)==1:
                before=(eq[0].subject,eq[0].value)
        writes=[e for e in t.effects if e.effect in {"SET_VAR","SET_CHANNEL"} and e.subject.startswith(("mission_var:","mission_status:","local_var:"))]
        if len(writes)==1:
            after=(writes[0].subject,writes[0].value)
        from_state=t.from_state; to_state=t.to_state
        if before:
            from_state=f"state:{before[0]}={before[1]}"
            states.setdefault(from_state,MissionState(from_state,f"{before[0]} = {before[1]}"))
        if after:
            to_state=f"state:{after[0]}={after[1]}"
            states.setdefault(to_state,MissionState(to_state,f"{after[0]} = {after[1]}"))
        transitions.append(MissionTransition(
            t.transition_id,from_state,to_state,t.trigger,t.gate,t.event,t.effects,t.confidence,
            t.evidence_ids,t.implementation_status,{**t.metadata,"state_edge_basis":"single_literal_channel" if before or after else "unresolved"},
        ))
    return MissionStateMachine(
        machine.machine_id,machine.feature_id,tuple(states.values()),tuple(transitions),
        machine.entry_state_ids,machine.channels,machine.completion_gate,machine.metadata,
    )


def chain_event_transitions(machine: MissionStateMachine) -> MissionStateMachine:
    """Collapse trigger-return + matching event-finish into one logical edge.

    Matching is deliberately zone+CSID scoped. The initiating actor is preserved,
    while both source spans remain in metadata. Unmatched handlers remain intact.
    """
    finishes={}
    for t in machine.transitions:
        if t.trigger=="EVENT_FINISH" and t.event:
            finishes.setdefault((t.event.zone,t.event.event_id),[]).append(t)

    consumed=set()
    chained=[]
    for t in machine.transitions:
        if t.trigger not in {"NPC_INTERACT","ZONE_IN","TRADE"} or not t.event:
            continue
        candidates=finishes.get((t.event.zone,t.event.event_id),[])
        if len(candidates)!=1:
            continue
        f=candidates[0]
        consumed.add(f.transition_id)
        effects=tuple(t.effects)+tuple(f.effects)
        # Trigger guards establish the precondition. Finish-handler guards also
        # matter (options/battlefield/etc.) and are conjoined when present.
        conds=[]
        if t.gate: conds.extend(t.gate.conditions)
        if f.gate: conds.extend(f.gate.conditions)
        gate=DependencyGate(
            f"chain-gate:{t.transition_id}:{f.transition_id}","ALL",tuple(conds)
        ) if conds else None
        chained.append(MissionTransition(
            f"chain:{t.transition_id}:{f.transition_id}",
            t.from_state,f.to_state,t.trigger,gate,
            EventIdentity(t.event.zone,t.event.event_id,t.event.actor),
            effects,
            "VERIFIED" if t.confidence=="VERIFIED" and f.confidence=="VERIFIED" else "INFERRED",
            tuple(dict.fromkeys(t.evidence_ids+f.evidence_ids)),
            "PRESENT" if t.implementation_status=="PRESENT" and f.implementation_status=="PRESENT" else "PARTIAL",
            {
                "logical_event_chain":True,
                "trigger_source_lines":t.metadata.get("source_lines"),
                "finish_source_lines":f.metadata.get("source_lines"),
                "trigger_transition_id":t.transition_id,
                "finish_transition_id":f.transition_id,
                "zone":t.event.zone,
                "actor":t.event.actor,
            },
        ))
        consumed.add(t.transition_id)

    remaining=[t for t in machine.transitions if t.transition_id not in consumed]
    out=MissionStateMachine(
        machine.machine_id,machine.feature_id,machine.states,
        tuple(remaining+chained),machine.entry_state_ids,machine.channels,
        machine.completion_gate,{**machine.metadata,"event_chains":len(chained)},
    )
    return materialize_channel_states(out)


def extract_section_completion_gate(lua: str) -> DependencyGate | None:
    """Recover a literal multi-channel completion check from a mission section."""
    pairs=[]
    pattern=re.compile(
        r"player:getMissionStatus\([^\n]*?xi\.mission\.status\.[A-Z0-9_]+\.([A-Z0-9_]+)\)\s*==\s*(\d+)"
    )
    for m in pattern.finditer(lua):
        pair=(m.group(1),int(m.group(2)))
        if pair not in pairs:
            pairs.append(pair)
    # Conservative: a convergence gate requires distinct named status channels
    # sharing the same terminal literal and an actual mission completion call.
    if "mission:complete(player)" not in lua:
        return None
    by_value={}
    for channel,value in pairs:
        by_value.setdefault(value,[]).append(channel)
    candidates=[(v,chs) for v,chs in by_value.items() if len(set(chs))>=2]
    if not candidates:
        return None
    value,channels=max(candidates,key=lambda x:len(set(x[1])))
    return DependencyGate(
        "section:completion-convergence","ALL",
        tuple(StateCondition(f"mission_status:{ch}","EQ",value) for ch in sorted(set(channels))),
    )


def extract_helper_transitions(lua: str) -> tuple[MissionTransition,...]:
    """Extract player helper functions that carry mission behavior (e.g. timers)."""
    lines=lua.splitlines()
    out=[]
    serial=0
    for start,end,text in _balanced_function_blocks(lua):
        first=lines[start]
        hm=_HELPER_ASSIGN.search(first)
        if not hm:
            continue
        effects=_effects(text)
        conds=_conditions(text)
        if not effects and not conds:
            continue
        serial+=1
        trigger="TIMER" if _TIMER.search(text) or "GetSystemTime()" in text else "PLACEHOLDER"
        gate=DependencyGate(f"helper-gate:{serial}","ALL",conds) if conds else None
        out.append(MissionTransition(
            f"helper:{hm.group(1)}:{serial}","source:any","source:any",trigger,gate,None,effects,
            "INFERRED",metadata={"helper":hm.group(1),"source_lines":(start+1,end+1),"helper_behavior":True},
        ))
    return tuple(out)


def extract_mission_reward_metadata(lua: str) -> dict:
    block=re.search(r"mission\.reward\s*=\s*\{(.*?)\n\}",lua,re.S)
    if not block:
        return {}
    text=block.group(1)
    out={}
    title=re.search(r"title\s*=\s*xi\.title\.([A-Z0-9_]+)",text)
    nxt=re.search(r"nextMission\s*=\s*\{\s*([^,]+),\s*([^\}]+)\}",text)
    if title: out["title"]=title.group(1)
    if nxt: out["next_mission"]=(nxt.group(1).strip(),nxt.group(2).strip())
    return out


def extract_dynamic_completion_gate(lua: str) -> DependencyGate | None:
    """Recover helper loops that require a contiguous named status range at one value."""
    helper=re.search(r"local function isMissionComplete\(player\)(.*?)\nend",lua,re.S)
    if not helper:
        return None
    body=helper.group(1)
    loop=re.search(
        r"for\s+\w+\s*=\s*xi\.mission\.status\.[A-Z0-9_]+\.([A-Z0-9_]+)\s*,\s*xi\.mission\.status\.[A-Z0-9_]+\.([A-Z0-9_]+)\s+do",
        body,
    )
    required=re.search(r"getMissionStatus\([^\)]*\)\s*~=\s*(\d+)",body)
    if not loop or not required:
        return None
    # Resolve the named range from status symbols observed elsewhere in this source.
    symbols=[]
    for m in re.finditer(r"xi\.mission\.status\.[A-Z0-9_]+\.([A-Z0-9_]+)",lua):
        if m.group(1) not in symbols: symbols.append(m.group(1))
    try:
        lo=symbols.index(loop.group(1)); hi=symbols.index(loop.group(2))
    except ValueError:
        return None
    if lo>hi: lo,hi=hi,lo
    names=symbols[lo:hi+1]
    value=int(required.group(1))
    return DependencyGate(
        "helper:isMissionComplete","ALL",
        tuple(StateCondition(f"mission_status:{name}","EQ",value) for name in names),
    )
