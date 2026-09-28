"""Conservative structural extractor for LandSandBoat Quest DSL Lua.

Quest behavior is projected into the same generic MissionStateMachine model used by
mission extraction. This adapter is intentionally source-literal and fails closed on
unsupported boolean structures rather than executing Lua or inventing semantics.
"""
from __future__ import annotations

from collections import Counter
import re

from .mission_state_machine import (
    DependencyGate,
    EventIdentity,
    MissionState,
    MissionStateMachine,
    MissionTransition,
    StateChannel,
    StateCondition,
    TransitionEffect,
)
from .mission_lsb_extract import (
    _balanced_function_blocks,
    _code,
    _handler_paths,
    _scoped_contexts,
    _structure_code,
    _structural_lua_lines,
    chain_event_transitions,
)


_QUEST_ID=re.compile(
    r"Quest:new\(xi\.questLog\.([A-Z0-9_]+),\s*xi\.quest\.id\.[A-Za-z0-9_]+\.([A-Z0-9_]+)\)"
)
_QUEST_REWARD_ITEM=re.compile(r"\bitem\s*=\s*xi\.item\.([A-Z0-9_]+)")
_QUEST_EVENT=re.compile(r"quest:(?:progressEvent|event|progressCutscene)\((\d+)")
_ZONE_IN_RETURN_EVENT=re.compile(r"\breturn\s+(\d+)\b")
_QUEST_DECL_EVENT=re.compile(
    r"\['([^']+)'\]\s*=\s*quest:(progressEvent|event|progressCutscene)\((\d+)\)(.*)"
)
_EVENT_FINISH_KEY=re.compile(r"\[(\d+)\]\s*=\s*function\(player,\s*csid")
_STATUS_COMPARE=re.compile(
    r"\bstatus\s*(==|~=)\s*xi\.questStatus\.([A-Z0-9_]+)"
)
_VAR_COMPARE=re.compile(
    r"\bvars\.([A-Za-z_][A-Za-z0-9_]*)\s*(==|~=|<=|>=|<|>)\s*(\d+)"
)
_GET_VAR_COMPARE=re.compile(
    r"quest:getVar\(player,\s*'([^']+)'\)\s*(==|~=|<=|>=|<|>)\s*(\d+)"
)
_GET_VAR_EXPR_COMPARE=re.compile(
    r"quest:getVar\(player,\s*'([^']+)'\)\s*(==|~=|<=|>=|<|>)\s*([A-Za-z_][A-Za-z0-9_]*\([^\)]*\)(?:\s*[+-]\s*\d+)?)"
)
_MUST_ZONE=re.compile(r"quest:getMustZone\(player\)")
_NOT_MUST_ZONE=re.compile(r"not\s+quest:getMustZone\(player\)")
_SET_MUST_ZONE=re.compile(r"quest:setMustZone\(player\)")
_GET_VAR_ALIAS=re.compile(
    r"local\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*quest:getVar\(player,\s*'([^']+)'\)"
)
_ALIAS_COMPARE=re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(==|~=|<=|>=|<|>)\s*(\d+)"
)
_COMPLETED_QUEST=re.compile(
    r"player:hasCompletedQuest\([^\)]*?xi\.quest\.id\.[A-Za-z0-9_]+\.([A-Z0-9_]+)\)"
)
_COMPLETED_MISSION=re.compile(
    r"player:hasCompletedMission\(xi\.mission\.log_id\.([A-Z0-9_]+),\s*"
    r"xi\.mission\.id\.[A-Za-z0-9_]+\.([A-Z0-9_]+)\)"
)
_CURRENT_MISSION=re.compile(
    r"player:getCurrentMission\(xi\.mission\.log_id\.([A-Z0-9_]+)\)"
    r"\s*(==|~=|<=|>=|<|>)\s*xi\.mission\.id\.[A-Za-z0-9_]+\.([A-Z0-9_]+)"
)
_HAS_KI=re.compile(r"player:hasKeyItem\(xi\.keyItem\.([A-Z0-9_]+)\)")
_LACKS_KI=re.compile(r"not\s+player:hasKeyItem\(xi\.keyItem\.([A-Z0-9_]+)\)")
_PREV_ZONE=re.compile(r"\bprevZone\s*(==|~=)\s*xi\.zone\.([A-Z0-9_]+)")
_TRADE_EXACT=re.compile(r"npcUtil\.tradeHasExactly\(trade,\s*\{([^}]*)\}\)")
_TRADE_ITEM=re.compile(r"xi\.item\.([A-Z0-9_]+)")
_TRADE_CALL=re.compile(r"npcUtil\.tradeHasExactly\(trade,\s*(\{.*?\})\s*\)",re.S)
_TRADE_ITEM_QTY=re.compile(r"xi\.item\.([A-Z0-9_]+)\s*,\s*(\d+)")
_TRADE_GIL=re.compile(r"['\"]gil['\"]\s*,\s*(\d+)")
_XQUEST_SET_VAR=re.compile(
    r"xi\.quest\.setVar\(player,\s*xi\.questLog\.[A-Z0-9_]+,\s*"
    r"xi\.quest\.id\.[A-Za-z0-9_]+\.([A-Z0-9_]+),\s*'([^']+)',\s*([^\)]+\)(?:\s*[+-]\s*\d+)?)"
)
_XQUEST_SET_MUST_ZONE=re.compile(
    r"xi\.quest\.setMustZone\(player,\s*xi\.questLog\.[A-Z0-9_]+,\s*"
    r"xi\.quest\.id\.[A-Za-z0-9_]+\.([A-Z0-9_]+)\)"
)
_SET_VAR=re.compile(r"quest:setVar\(player,\s*'([^']+)',\s*([^\)]+)\)")
_GIVE_KI=re.compile(
    r"(?:npcUtil\.giveKeyItem\(\s*player\s*,\s*|player:addKeyItem\(\s*)"
    r"xi\.keyItem\.([A-Z0-9_]+)"
)
_DEL_KI=re.compile(r"player:delKeyItem\(xi\.keyItem\.([A-Z0-9_]+)\)")
_SET_POS=re.compile(r"player:setPos\(([^\)]+)\)")
_BEGIN=re.compile(r"quest:begin\(player\)")
_COMPLETE=re.compile(r"quest:complete\(player\)")
_START_EVENT=re.compile(r"player:startEvent\((\d+)")
_TODO_AFTER_MISSION=re.compile(
    r"--\s*TODO:\s*(.*?)\bafter\s+(?:WOTG\s+)?Mission:\s*([A-Za-z0-9 '\-]+)",
    re.I,
)
_HELPER_DEF_START=re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_.]*)\s*=\s*function\(player\)"
)
_OP={"==":"EQ","~=":"NE","<":"LT","<=":"LE",">":"GT",">=":"GE"}


def _symbolize_feature_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+","_",name.strip()).strip("_").upper()


def _documented_feature_requirements(lua: str) -> tuple[dict,...]:
    """Recover explicit source comments that document known-but-unenforced prerequisites."""
    out=[]
    for match in _TODO_AFTER_MISSION.finditer(lua):
        out.append({
            "subject":f"mission:{_symbolize_feature_name(match.group(2))}",
            "relation":"AFTER",
            "enforcement":"NOT_IMPLEMENTED",
            "source_kind":"SOURCE_TODO_COMMENT",
            "note":match.group(1).strip(),
        })
    return tuple(out)


def extract_feature_requirement_helpers(lua: str) -> dict[str,DependencyGate]:
    """Extract pure helper predicates that represent quest/mission prerequisites."""
    lines=lua.splitlines()
    out={}
    for start,_end,text in _balanced_function_blocks(lua):
        match=_HELPER_DEF_START.search(lines[start])
        if not match:
            continue
        executable=" ".join(
            line.strip() for line in _structural_lua_lines(text) if line.strip()
        )
        quest_conditions=[
            StateCondition(f"quest:{symbol}","COMPLETE",True)
            for symbol in _COMPLETED_QUEST.findall(executable)
        ]
        mission_conditions=[
            StateCondition(f"mission:{symbol}","COMPLETE",True)
            for _log,symbol in _COMPLETED_MISSION.findall(executable)
        ]
        conditions=[]
        for condition in (*quest_conditions,*mission_conditions):
            if condition not in conditions:
                conditions.append(condition)
        if not conditions:
            continue
        has_or=bool(re.search(r"\bor\b",executable))
        has_and=bool(re.search(r"\band\b",executable))
        if has_or and has_and:
            continue
        helper=match.group(1)
        out[helper]=DependencyGate(
            f"helper-feature-prerequisite:{helper}",
            "ANY" if has_or else "ALL",
            tuple(conditions),
        )
    return out


def _literal_quest_section_spans(lua: str) -> tuple[tuple[int,int,str],...]:
    """Return zero-based line spans and text for literal top-level quest.sections rows."""
    lines=lua.splitlines()
    structural=_structural_lua_lines(lua)
    assignment=None
    for i,line in enumerate(structural):
        if re.search(r"\bquest\.sections\s*=",line):
            assignment=i
            break
    if assignment is None:
        return ()

    outer_start=None
    for i in range(assignment,len(lines)):
        if "{" in _structure_code(lines[i]):
            outer_start=i
            break
        if i>assignment and _code(lines[i]).strip():
            return ()
    if outer_start is None:
        return ()

    depth=0
    outer_open=False
    section_start=None
    sections=[]
    for i in range(outer_start,len(lines)):
        code=_structure_code(lines[i])
        opens=code.count("{")
        closes=code.count("}")
        before=depth
        if not outer_open:
            if not opens:
                continue
            outer_open=True
        elif before==1 and section_start is None and opens:
            section_start=i

        depth+=opens-closes
        if section_start is not None and depth==1:
            sections.append((section_start,i,"\n".join(lines[section_start:i+1])))
            section_start=None
        if outer_open and depth<=0:
            break

    if depth!=0 or section_start is not None:
        return ()
    return tuple(sections)


def _section_check_block(section: str) -> str | None:
    lines=section.splitlines()
    for start,_end,text in _balanced_function_blocks(section):
        if re.search(r"^\s*check\s*=\s*function\b",lines[start]):
            return text
    return None


def _section_analysis(
    section: str,
    helper_feature_gates: dict[str,DependencyGate] | None=None,
) -> dict:
    check=_section_check_block(section)
    if check is None:
        return {
            "check_present":False,
            "status":"NO_CHECK",
            "conditions":(),
            "feature_requirement_gates":(),
            "unresolved_reasons":(),
        }
    executable=" ".join(
        line.strip() for line in _structural_lua_lines(check) if line.strip()
    )
    if re.search(r"\bor\b",executable):
        return {
            "check_present":True,
            "status":"UNRESOLVED",
            "conditions":(),
            "feature_requirement_gates":(),
            "unresolved_reasons":("disjunction",),
        }

    out=[]
    for match in _STATUS_COMPARE.finditer(executable):
        out.append(StateCondition("quest_status",_OP[match.group(1)],match.group(2)))
    for match in _VAR_COMPARE.finditer(executable):
        out.append(StateCondition(
            f"quest_var:{match.group(1)}",
            _OP[match.group(2)],
            int(match.group(3)),
        ))
    for match in _COMPLETED_QUEST.finditer(executable):
        out.append(StateCondition(f"quest:{match.group(1)}","COMPLETE",True))
    for match in _COMPLETED_MISSION.finditer(executable):
        out.append(StateCondition(f"mission:{match.group(2)}","COMPLETE",True))
    for match in _CURRENT_MISSION.finditer(executable):
        out.append(StateCondition(
            f"mission:{match.group(1)}:current",
            _OP[match.group(2)],
            match.group(3),
        ))

    lacked=set(_LACKS_KI.findall(executable))
    for symbol in lacked:
        out.append(StateCondition(f"key_item:{symbol}","LACKS",True))
    for symbol in _HAS_KI.findall(executable):
        if symbol not in lacked:
            out.append(StateCondition(f"key_item:{symbol}","HAS",True))

    dedup=[]
    for condition in out:
        if condition not in dedup:
            dedup.append(condition)

    helper_gates=[]
    for helper,gate in (helper_feature_gates or {}).items():
        if re.search(rf"(?<![A-Za-z0-9_.]){re.escape(helper)}\(\s*player\s*\)",executable):
            helper_gates.append(gate)

    return {
        "check_present":True,
        "status":"MODELED" if (dedup or helper_gates) else "NO_STATUS_REQUIREMENTS",
        "conditions":tuple(dedup),
        "feature_requirement_gates":tuple(helper_gates),
        "unresolved_reasons":(),
    }


def _section_contexts(
    lua: str,
    helper_feature_gates: dict[str,DependencyGate] | None=None,
):
    rows=[]
    for index,(start,end,text) in enumerate(_literal_quest_section_spans(lua),1):
        rows.append((start,end,index,_section_analysis(text,helper_feature_gates)))

    def context(line_no: int):
        matches=[row for row in rows if row[0]<=line_no<=row[1]]
        if not matches:
            return None,None,(),(),None,(),False
        start,end,index,analysis=max(matches,key=lambda row:row[0])
        return (
            index,
            (start+1,end+1),
            analysis["conditions"],
            analysis["feature_requirement_gates"],
            analysis["status"],
            analysis["unresolved_reasons"],
            analysis["check_present"],
        )

    return tuple(rows),context


def _handler_conditions(text: str) -> tuple[StateCondition,...]:
    out=[]
    for match in _GET_VAR_COMPARE.finditer(text):
        out.append(StateCondition(
            f"quest_var:{match.group(1)}",
            _OP[match.group(2)],
            int(match.group(3)),
        ))
    for match in _GET_VAR_EXPR_COMPARE.finditer(text):
        out.append(StateCondition(
            f"quest_var:{match.group(1)}",
            _OP[match.group(2)],
            match.group(3).strip(),
        ))
    aliases={match.group(1):match.group(2) for match in _GET_VAR_ALIAS.finditer(text)}
    for match in _ALIAS_COMPARE.finditer(text):
        channel=aliases.get(match.group(1))
        if channel:
            out.append(StateCondition(
                f"quest_var:{channel}",
                _OP[match.group(2)],
                int(match.group(3)),
            ))
    if _NOT_MUST_ZONE.search(text):
        out.append(StateCondition("quest_must_zone","EQ",False))
    elif _MUST_ZONE.search(text):
        out.append(StateCondition("quest_must_zone","EQ",True))
    lacked=set(_LACKS_KI.findall(text))
    for symbol in lacked:
        out.append(StateCondition(f"key_item:{symbol}","LACKS",True))
    for symbol in _HAS_KI.findall(text):
        if symbol not in lacked:
            out.append(StateCondition(f"key_item:{symbol}","HAS",True))
    for match in _PREV_ZONE.finditer(text):
        out.append(StateCondition("previous_zone",_OP[match.group(1)],match.group(2)))
    trade_calls=list(_TRADE_CALL.finditer(text))
    if trade_calls:
        for match in trade_calls:
            body=match.group(1)
            quantities=tuple(
                (symbol,int(quantity))
                for symbol,quantity in _TRADE_ITEM_QTY.findall(body)
            )
            gil=_TRADE_GIL.search(body)
            if quantities:
                out.append(StateCondition("trade","TRADE_MATCHES",quantities))
            elif gil:
                out.append(StateCondition("trade","TRADE_MATCHES",(("gil",int(gil.group(1))),)))
            else:
                items=tuple(_TRADE_ITEM.findall(body))
                if items:
                    out.append(StateCondition("trade","TRADE_MATCHES",items))
    else:
        for match in _TRADE_EXACT.finditer(text):
            items=tuple(_TRADE_ITEM.findall(match.group(1)))
            if items:
                out.append(StateCondition("trade","TRADE_MATCHES",items))
    dedup=[]
    for condition in out:
        if condition not in dedup:
            dedup.append(condition)
    return tuple(dedup)


def _quest_effects(text: str) -> tuple[TransitionEffect,...]:
    out=[]
    for match in _SET_VAR.finditer(text):
        raw=match.group(2).strip()
        value=int(raw) if raw.isdigit() else raw
        out.append(TransitionEffect("SET_VAR",f"quest_var:{match.group(1)}",value))
    for match in _XQUEST_SET_VAR.finditer(text):
        raw=match.group(3).strip()
        value=int(raw) if raw.isdigit() else raw
        out.append(TransitionEffect(
            "SET_VAR",
            f"quest:{match.group(1)}:var:{match.group(2)}",
            value,
        ))
    for match in _XQUEST_SET_MUST_ZONE.finditer(text):
        out.append(TransitionEffect(
            "SET_STATE",
            f"quest:{match.group(1)}:must_zone",
            True,
        ))
    for symbol in _GIVE_KI.findall(text):
        out.append(TransitionEffect("GRANT",f"key_item:{symbol}"))
    for symbol in _DEL_KI.findall(text):
        out.append(TransitionEffect("REMOVE",f"key_item:{symbol}"))
    if _BEGIN.search(text):
        out.append(TransitionEffect("START","quest"))
    if _COMPLETE.search(text):
        out.append(TransitionEffect("COMPLETE","quest"))
    if _SET_MUST_ZONE.search(text):
        out.append(TransitionEffect("SET_STATE","quest_must_zone",True))
    for match in _START_EVENT.finditer(text):
        out.append(TransitionEffect("START","event",int(match.group(1))))
    if "player:confirmTrade()" in text:
        out.append(TransitionEffect("COMPLETE_TRADE","trade"))
    for match in _SET_POS.finditer(text):
        out.append(TransitionEffect("TELEPORT","player",match.group(1).strip()))
    dedup=[]
    for effect in out:
        if effect not in dedup:
            dedup.append(effect)
    return tuple(dedup)


def _channels(lua: str) -> tuple[StateChannel,...]:
    values={}
    for match in _SET_VAR.finditer(lua):
        raw=match.group(2).strip()
        value=int(raw) if raw.isdigit() else raw
        values.setdefault(f"quest_var:{match.group(1)}",set()).add(value)
    statuses=set(match.group(2) for match in _STATUS_COMPARE.finditer(lua))
    channels=[
        StateChannel(channel,"PERSISTENT",tuple(sorted(observed,key=str)))
        for channel,observed in sorted(values.items())
    ]
    if statuses:
        channels.insert(0,StateChannel("quest_status","PERSISTENT",tuple(sorted(statuses))))
    return tuple(channels)


def _implementation_gap_note(lines: list[str], start: int) -> str | None:
    window="\n".join(lines[max(0,start-3):start+1])
    for line in window.splitlines():
        text=line.strip().lstrip("-").strip()
        if re.search(r"\b(?:not implemented|unimplemented|TODO)\b",text,re.I):
            return text
    return None


def correlate_lsb_quest_handlers(
    lua: str,
    *,
    feature_id: str="quest:unknown",
    helper_feature_gates: dict[str,DependencyGate] | None=None,
) -> MissionStateMachine:
    """Correlate literal LSB Quest DSL handlers into the generic state-machine model."""
    identity=_QUEST_ID.search(lua)
    reward=_QUEST_REWARD_ITEM.search(lua)
    lines,_zone_spans,_actor_spans,context=_scoped_contexts(lua)
    _section_rows,section_context=_section_contexts(lua,helper_feature_gates)

    transitions=[]
    states={"source:any":MissionState("source:any","Source state")}
    serial=0
    source_handler_count=0
    modeled_source_handler_count=0
    unmodeled_source_handler_lines=[]

    for start,end,text in _balanced_function_blocks(lua):
        first=lines[start]
        ef=_EVENT_FINISH_KEY.search(first)
        zone,actor=context(start)
        (
            section_index,
            section_source_lines,
            section_conditions,
            section_feature_requirement_gates,
            section_status,
            section_unresolved_reasons,
            section_check_present,
        )=section_context(start)

        trigger=None
        handler_event=None
        if ef:
            trigger="EVENT_FINISH"
            handler_event=EventIdentity(zone or "UNKNOWN",int(ef.group(1)),actor)
        elif "onTrigger" in first:
            trigger="NPC_INTERACT"
        elif "onTrade" in first:
            trigger="TRADE"
        elif "onZoneIn" in first:
            trigger="ZONE_IN"
        elif "onZoneOut" in first:
            trigger="ZONE_OUT"
        elif "onMobDeath" in first:
            trigger="MOB_DEATH"
        if not trigger:
            continue

        source_handler_count+=1
        transition_count_before=len(transitions)
        paths=_handler_paths(text,start_line=start)
        for path_index,path in enumerate(paths,1):
            unresolved_nested=bool(re.search(r"^\s*(?:if|elseif|else)\b",path.body,re.M))
            guard_text="\n".join(path.guard_texts)
            if unresolved_nested:
                guard_text+="\n"+path.body
            conditions=_handler_conditions(guard_text)
            effect_text=path.body+"\n"+guard_text
            effects=_quest_effects(effect_text)
            event=handler_event
            returned=_QUEST_EVENT.search(path.body)
            if returned and event is None:
                event=EventIdentity(zone or "UNKNOWN",int(returned.group(1)),actor)
            elif trigger=="ZONE_IN" and event is None:
                returned_zone_event=_ZONE_IN_RETURN_EVENT.search(path.body)
                if returned_zone_event:
                    event=EventIdentity(
                        zone or "UNKNOWN",
                        int(returned_zone_event.group(1)),
                        actor,
                    )
            if not (conditions or effects or event):
                continue

            serial+=1
            guard_has_or=bool(re.search(r"\bor\b",guard_text))
            trade_only_disjunction=bool(
                guard_has_or
                and conditions
                and all(condition.subject=="trade" for condition in conditions)
            )
            guard_complete=(
                path.guard_complete
                and not unresolved_nested
                and (not guard_has_or or trade_only_disjunction)
            )
            gate=DependencyGate(
                f"quest-source-gate:{serial}",
                "ANY" if trade_only_disjunction else "ALL",
                conditions if (not guard_has_or or trade_only_disjunction) else (),
            ) if conditions and (not guard_has_or or trade_only_disjunction) else None
            gap_note=_implementation_gap_note(lines,start)
            transitions.append(MissionTransition(
                f"quest-source-transition:{serial}",
                "source:any",
                "source:any",
                trigger,
                gate=gate,
                event=event,
                effects=effects,
                confidence="INFERRED" if guard_complete else "UNKNOWN",
                implementation_status="IMPLEMENTATION_GAP" if gap_note else "PRESENT",
                metadata={
                    "zone":zone,
                    "actor":actor,
                    "source_lines":(start+1,end+1),
                    "literal_correlation":True,
                    "context_basis":"table_scope",
                    "section_index":section_index,
                    "section_source_lines":section_source_lines,
                    "section_eligibility_conditions":tuple(
                        {
                            "subject":condition.subject,
                            "operator":condition.operator,
                            "value":condition.value,
                        }
                        for condition in section_conditions
                    ),
                    "section_feature_requirement_gates":tuple(
                        {
                            "gate_id":gate.gate_id,
                            "logic":gate.logic,
                            "conditions":tuple(
                                {
                                    "subject":condition.subject,
                                    "operator":condition.operator,
                                    "value":condition.value,
                                }
                                for condition in gate.conditions
                            ),
                        }
                        for gate in section_feature_requirement_gates
                    ),
                    "section_eligibility_status":section_status,
                    "section_eligibility_unresolved_reasons":tuple(section_unresolved_reasons),
                    "section_check_present":section_check_present,
                    "branch_alternative":len(paths)>1,
                    "branch_index":path_index,
                    "branch_path":path.branch_path,
                    "branch_guard_texts":path.guard_texts,
                    "branch_source_lines":path.branch_source_lines,
                    "branch_guard_complete":guard_complete,
                    "unexpanded_nested_branch":unresolved_nested,
                    "guard_disjunction":guard_has_or,
                    "trade_disjunction_modeled":trade_only_disjunction,
                    "implementation_gap_note":gap_note,
                    "started_event_id":(
                        int(started.group(1))
                        if (started:=_START_EVENT.search(path.body))
                        else None
                    ),
                },
            ))
        if len(transitions)>transition_count_before:
            modeled_source_handler_count+=1
        else:
            unmodeled_source_handler_lines.append((start+1,end+1))

    # Declarative actor handlers are unconditional NPC interactions.
    for line_no,line in enumerate(lines):
        match=_QUEST_DECL_EVENT.search(line)
        if not match:
            continue
        zone,_=context(line_no)
        (
            section_index,
            section_source_lines,
            section_conditions,
            section_feature_requirement_gates,
            section_status,
            section_unresolved_reasons,
            section_check_present,
        )=section_context(line_no)
        source_handler_count+=1
        modeled_source_handler_count+=1
        serial+=1
        transitions.append(MissionTransition(
            f"quest-source-transition:{serial}",
            "source:any",
            "source:any",
            "NPC_INTERACT",
            event=EventIdentity(zone or "UNKNOWN",int(match.group(3)),match.group(1)),
            confidence="VERIFIED",
            metadata={
                "zone":zone,
                "actor":match.group(1),
                "source_lines":(line_no+1,line_no+1),
                "literal_correlation":True,
                "declarative_handler":True,
                "section_index":section_index,
                "section_source_lines":section_source_lines,
                "section_eligibility_conditions":tuple(
                    {
                        "subject":condition.subject,
                        "operator":condition.operator,
                        "value":condition.value,
                    }
                    for condition in section_conditions
                ),
                "section_feature_requirement_gates":tuple(
                    {
                        "gate_id":gate.gate_id,
                        "logic":gate.logic,
                        "conditions":tuple(
                            {
                                "subject":condition.subject,
                                "operator":condition.operator,
                                "value":condition.value,
                            }
                            for condition in gate.conditions
                        ),
                    }
                    for gate in section_feature_requirement_gates
                ),
                "section_eligibility_status":section_status,
                "section_eligibility_unresolved_reasons":tuple(section_unresolved_reasons),
                "section_check_present":section_check_present,
                "replace_default":any(token in (match.group(4) or "") for token in (":replaceDefault()",".replaceDefault()")),
                "important_event":any(token in (match.group(4) or "") for token in (":importantEvent()",".importantEvent()")),
            },
        ))

    return MissionStateMachine(
        machine_id=f"machine:{feature_id}",
        feature_id=feature_id,
        states=tuple(states.values()),
        transitions=tuple(transitions),
        entry_state_ids=("source:any",),
        channels=_channels(lua),
        metadata={
            "extractor":"lsb_quest_static_literal",
            "quest_log":identity.group(1) if identity else None,
            "quest_symbol":identity.group(2) if identity else None,
            "reward_item":reward.group(1) if reward else None,
            "transition_count":len(transitions),
            "source_handler_count":source_handler_count,
            "modeled_source_handler_count":modeled_source_handler_count,
            "unmodeled_source_handler_count":len(unmodeled_source_handler_lines),
            "unmodeled_source_handler_lines":tuple(unmodeled_source_handler_lines),
            "documented_feature_requirements":_documented_feature_requirements(lua),
        },
    )


def materialize_quest_progress_states(machine: MissionStateMachine) -> MissionStateMachine:
    """Materialize proven quest status/Prog endpoints without changing guard semantics."""
    states={state.state_id:state for state in machine.states}
    transitions=[]
    for transition in machine.transitions:
        section_conditions=transition.metadata.get("section_eligibility_conditions",())
        progress=[
            row for row in section_conditions
            if row.get("operator")=="EQ" and str(row.get("subject","")).startswith("quest_var:")
        ]
        status=[
            row for row in section_conditions
            if row.get("operator")=="EQ" and row.get("subject")=="quest_status"
        ]
        writes=[
            effect for effect in transition.effects
            if effect.effect=="SET_VAR" and effect.subject.startswith("quest_var:")
        ]

        from_state=transition.from_state
        to_state=transition.to_state
        if len(progress)==1:
            row=progress[0]
            from_state=f"state:{row['subject']}={row['value']}"
            states.setdefault(from_state,MissionState(from_state,f"{row['subject']} = {row['value']}"))
        elif len(status)==1:
            row=status[0]
            from_state=f"state:quest_status={row['value']}"
            states.setdefault(from_state,MissionState(from_state,f"quest_status = {row['value']}"))

        if len(writes)==1:
            effect=writes[0]
            to_state=f"state:{effect.subject}={effect.value}"
            states.setdefault(to_state,MissionState(to_state,f"{effect.subject} = {effect.value}"))
        elif any(effect.effect=="START" and effect.subject=="quest" for effect in transition.effects):
            to_state="state:quest_status=QUEST_ACCEPTED"
            states.setdefault(to_state,MissionState(to_state,"quest_status = QUEST_ACCEPTED"))
        elif any(effect.effect=="COMPLETE" and effect.subject=="quest" for effect in transition.effects):
            to_state="state:quest_status=QUEST_COMPLETED"
            states.setdefault(to_state,MissionState(
                to_state,"quest_status = QUEST_COMPLETED",terminal=True
            ))

        transitions.append(MissionTransition(
            transition.transition_id,
            from_state,
            to_state,
            transition.trigger,
            transition.gate,
            transition.event,
            transition.effects,
            transition.confidence,
            transition.evidence_ids,
            transition.implementation_status,
            {
                **transition.metadata,
                "quest_state_materialized":from_state!="source:any" or to_state!="source:any",
            },
            post_effect_gate=transition.post_effect_gate,
        ))

    entry=tuple(
        state_id for state_id in (
            "state:quest_status=QUEST_AVAILABLE",
            "source:any",
        )
        if state_id in states
    )
    return MissionStateMachine(
        machine.machine_id,
        machine.feature_id,
        tuple(states.values()),
        tuple(transitions),
        entry or machine.entry_state_ids,
        machine.channels,
        machine.completion_gate,
        machine.metadata,
    )


def _chain_started_events(machine: MissionStateMachine) -> MissionStateMachine:
    """Collapse literal EVENT_FINISH -> player:startEvent -> EVENT_FINISH relays."""
    finishes={}
    for transition in machine.transitions:
        if transition.trigger=="EVENT_FINISH" and transition.event:
            finishes.setdefault((transition.event.zone,transition.event.event_id),[]).append(transition)

    consumed=set()
    relays=[]
    serial=0
    for transition in machine.transitions:
        started_event_id=transition.metadata.get("started_event_id")
        if (
            transition.trigger!="EVENT_FINISH"
            or not transition.event
            or started_event_id is None
        ):
            continue
        candidates=[
            candidate for candidate in finishes.get(
                (transition.event.zone,int(started_event_id)),()
            )
            if candidate.transition_id!=transition.transition_id
        ]
        if len(candidates)!=1:
            continue
        finish=candidates[0]
        serial+=1
        consumed.update((transition.transition_id,finish.transition_id))
        conditions=[]
        for gate in (transition.gate,finish.gate):
            if gate:
                conditions.extend(gate.conditions)
        gate=DependencyGate(
            f"quest-event-relay-gate:{serial}","ALL",tuple(conditions)
        ) if conditions else None
        relays.append(MissionTransition(
            f"quest-event-relay:{transition.transition_id}:{finish.transition_id}",
            transition.from_state,
            finish.to_state,
            "EVENT_FINISH",
            gate=gate,
            event=transition.event,
            effects=tuple(transition.effects)+tuple(finish.effects),
            confidence=(
                "UNKNOWN"
                if "UNKNOWN" in {transition.confidence,finish.confidence}
                else "INFERRED"
            ),
            implementation_status=(
                "PRESENT"
                if transition.implementation_status=="PRESENT"
                and finish.implementation_status=="PRESENT"
                else "PARTIAL"
            ),
            metadata={
                **transition.metadata,
                "logical_event_relay":True,
                "relay_started_event_id":int(started_event_id),
                "relay_finish_source_lines":finish.metadata.get("source_lines"),
                "relay_finish_transition_id":finish.transition_id,
            },
        ))

    if not relays:
        return machine
    remaining=[
        transition for transition in machine.transitions
        if transition.transition_id not in consumed
    ]
    return MissionStateMachine(
        machine.machine_id,
        machine.feature_id,
        machine.states,
        tuple(remaining+relays),
        machine.entry_state_ids,
        machine.channels,
        machine.completion_gate,
        {
            **machine.metadata,
            "event_relay_count":len(relays),
        },
    )


def chain_quest_event_transitions(machine: MissionStateMachine) -> MissionStateMachine:
    """Chain quest event relays, then generic trigger/finish pairs and progression."""
    relayed=_chain_started_events(machine)
    return materialize_quest_progress_states(chain_event_transitions(relayed))


def quest_extraction_metrics(machine: MissionStateMachine) -> dict:
    """Compact coverage metrics for Quest DSL structural extraction."""
    return {
        "transition_count":len(machine.transitions),
        "event_transition_count":sum(1 for t in machine.transitions if t.event),
        "event_chain_count":int(machine.metadata.get("event_chains",0)),
        "event_relay_count":int(machine.metadata.get("event_relay_count",0)),
        "section_status_counts":dict(sorted(Counter(
            t.metadata.get("section_eligibility_status")
            for t in machine.transitions
            if t.metadata.get("section_eligibility_status")
        ).items())),
        "implementation_gap_transition_count":sum(
            1 for t in machine.transitions if t.implementation_status=="IMPLEMENTATION_GAP"
        ),
        "quest_state_materialized_count":sum(
            1 for t in machine.transitions if t.metadata.get("quest_state_materialized")
        ),
        "source_handler_count":int(machine.metadata.get("source_handler_count",0)),
        "modeled_source_handler_count":int(machine.metadata.get("modeled_source_handler_count",0)),
        "unmodeled_source_handler_count":int(machine.metadata.get("unmodeled_source_handler_count",0)),
    }
