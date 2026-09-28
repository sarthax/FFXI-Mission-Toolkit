"""Conservative static extractor for LandSandBoat-style Mission/Quest Lua.

This first pass extracts only literal constructs that can be tied to source text
without executing Lua. Unsupported/dynamic expressions remain visible as findings.
"""
from __future__ import annotations

from collections import Counter
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
_KI_GIVE=re.compile(
    r"(?:npcUtil\.giveKeyItem\(\s*player\s*,\s*|player:addKeyItem\(\s*)"
    r"xi\.keyItem\.([A-Z0-9_]+)"
)
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
_STATUS_COMPARE=re.compile(
    r"player:getMissionStatus\([^\)]*?xi\.mission\.status\.[A-Z0-9_]+\.([A-Z0-9_]+)\s*\)"
    r"\s*(==|~=|<=|>=|<|>)\s*(\d+)"
)
_STATUS_ALIAS_COMPARE=re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(==|~=|<=|>=|<|>)\s*(\d+)"
)
_STATUS_COMPARE_OPERATOR={"==":"EQ","~=":"NE","<":"LT","<=":"LE",">":"GT",">=":"GE"}
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
_DISTANCE_OPERATOR={"<":"LT","<=":"LE",">":"GT",">=":"GE"}
_TRADE=re.compile(r"npcUtil\.tradeMatches\(trade,\s*(.+)\)")
_SETPOS=re.compile(r"player:setPos\(([^\)]+)\)")
_MESSAGE=re.compile(r"(?:player:messageSpecial|player:messageText|mission:messageSpecial|mission:messageName)\(([^\n]+)\)")
_HELPER_ASSIGN=re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*function\(player\)",re.M)
_LOCAL_PLAYER_HELPER=re.compile(r"^\s*local\s+function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*player\s*\)")


def _structural_lua_lines(lua: str) -> list[str]:
    """Remove Lua comments/string bodies while preserving executable punctuation/keywords."""
    out=[]
    in_block_comment=False
    in_long_string=False
    for line in lua.splitlines():
        visible=[]
        i=0
        while i<len(line):
            if in_block_comment:
                end=line.find("]]",i)
                if end<0:
                    i=len(line)
                    continue
                in_block_comment=False
                i=end+2
                continue
            if in_long_string:
                end=line.find("]]",i)
                if end<0:
                    i=len(line)
                    continue
                in_long_string=False
                i=end+2
                continue
            if line.startswith("--[[",i):
                in_block_comment=True
                i+=4
                continue
            if line.startswith("--",i):
                break
            if line.startswith("[[",i):
                in_long_string=True
                i+=2
                continue
            if line[i] in {"'","\""}:
                quote=line[i]
                i+=1
                while i<len(line):
                    if line[i]=="\\":
                        i+=2
                        continue
                    if line[i]==quote:
                        i+=1
                        break
                    i+=1
                continue
            visible.append(line[i])
            i+=1
        out.append("".join(visible))
    return out


def _balanced_function_blocks(lua: str):
    """Yield outermost executable Lua function blocks.

    Nested callbacks belong to their enclosing handler/helper and are not yielded as
    independent mission functions. Comment/string text containing Lua keywords is ignored.
    Unbalanced candidates fail closed.
    """
    lines=lua.splitlines()
    structural_lines=_structural_lua_lines(lua)
    claimed_until=-1
    for i,line in enumerate(lines):
        if i<=claimed_until:
            continue
        first=structural_lines[i]
        if not re.search(r"\bfunction\b",first):
            continue
        depth=0
        started=False
        for j in range(i,len(lines)):
            code=structural_lines[j]
            opens=len(re.findall(r"\b(function|if|for|while|repeat)\b",code))
            closes=len(re.findall(r"\bend\b",code))+len(re.findall(r"\buntil\b",code))
            if opens:
                started=True
            depth+=opens-closes
            if started and depth<=0:
                claimed_until=j
                yield i,j,"\n".join(lines[i:j+1])
                break



@dataclass(frozen=True)
class _HandlerPath:
    body: str
    guard_texts: tuple[str,...] = ()
    branch_path: tuple[str,...] = ()
    branch_source_lines: tuple[tuple[int,int],...] = ()
    guard_complete: bool = True
    guard_prefix_texts: tuple[str,...] = ()


_IF_HEADER=re.compile(r"^\s*if\s+(.+?)\s+then\s*$")
_ELSEIF_HEADER=re.compile(r"^\s*elseif\s+(.+?)\s+then\s*$")
_ELSE_HEADER=re.compile(r"^\s*else\s*$")


def _code(line: str) -> str:
    return line.split("--",1)[0].rstrip()


def _open_count(code: str) -> int:
    # elseif is not a fresh if block. Repeat is closed by until.
    return (
        len(re.findall(r"\bfunction\b",code))
        + len(re.findall(r"(?<!else)\bif\b",code))
        + len(re.findall(r"\bfor\b[^\n]*\bdo\b",code))
        + len(re.findall(r"\bwhile\b[^\n]*\bdo\b",code))
        + len(re.findall(r"\brepeat\b",code))
    )


def _close_count(code: str) -> int:
    return len(re.findall(r"\bend\b",code))+len(re.findall(r"\buntil\b",code))


def _split_first_if(lines: list[tuple[int,str]]):
    """Split the first top-level multiline if/elseif/else block in a handler path.

    Returned branches retain their absolute source-line indexes. Inline one-line ifs and
    malformed/unbalanced blocks are deliberately left unsplit rather than guessed.
    """
    depth=0
    for i,(line_no,line) in enumerate(lines):
        code=_code(line)
        if depth==0:
            match=_IF_HEADER.match(code)
            if match:
                start=i
                branch_kind="if"
                branch_guard=match.group(1)
                branch_header_line=line_no
                body_start=i+1
                inner_depth=1
                branches=[]
                for j in range(i+1,len(lines)):
                    child_no,child_line=lines[j]
                    child_code=_code(child_line)
                    if inner_depth==1:
                        elseif=_ELSEIF_HEADER.match(child_code)
                        if elseif:
                            body=lines[body_start:j]
                            end_line=body[-1][0] if body else branch_header_line
                            branches.append((branch_kind,branch_guard,branch_header_line,end_line,body))
                            branch_kind="elseif"
                            branch_guard=elseif.group(1)
                            branch_header_line=child_no
                            body_start=j+1
                            continue
                        if _ELSE_HEADER.match(child_code):
                            body=lines[body_start:j]
                            end_line=body[-1][0] if body else branch_header_line
                            branches.append((branch_kind,branch_guard,branch_header_line,end_line,body))
                            branch_kind="else"
                            branch_guard=None
                            branch_header_line=child_no
                            body_start=j+1
                            continue
                        if re.match(r"^\s*end\b",child_code):
                            body=lines[body_start:j]
                            end_line=body[-1][0] if body else branch_header_line
                            branches.append((branch_kind,branch_guard,branch_header_line,end_line,body))
                            return lines[:start],branches,lines[j+1:]
                    inner_depth+=_open_count(child_code)-_close_count(child_code)
                return None
        depth+=_open_count(code)-_close_count(code)
    return None


def _handler_paths(text: str, *, start_line: int) -> tuple[_HandlerPath,...]:
    """Enumerate conservative mutually-exclusive handler paths.

    The outer function declaration/end are stripped. Each multiline top-level if tree is
    recursively expanded. Common pre/post statements remain on every path. elseif/else paths
    are marked guard-incomplete because prior-branch falsehood is not synthesized.
    """
    raw=text.splitlines()
    if len(raw)>=2:
        raw=raw[1:-1]
        first_line=start_line+1
    else:
        first_line=start_line
    source=[(first_line+i,line) for i,line in enumerate(raw)]

    def expand(
        lines: list[tuple[int,str]],
        guards: tuple[str,...]=(),
        labels: tuple[str,...]=(),
        spans: tuple[tuple[int,int],...]=(),
        complete: bool=True,
        guard_prefixes: tuple[str,...]=(),
    ) -> list[_HandlerPath]:
        split=_split_first_if(lines)
        if split is None:
            return [_HandlerPath(
                "\n".join(line for _,line in lines),
                guards,labels,spans,complete,guard_prefixes,
            )]
        prefix,branches,suffix=split
        out=[]
        prefix_text="\n".join(line for _,line in prefix)
        for kind,guard,header_line,end_line,body in branches:
            next_guards=guards+((guard,) if guard else ())
            next_labels=labels+(kind,)
            next_spans=spans+((header_line+1,end_line+1),)
            next_complete=complete and kind=="if"
            next_prefixes=guard_prefixes+((prefix_text,) if guard else ())
            out.extend(expand(
                prefix+body+suffix,next_guards,next_labels,next_spans,next_complete,next_prefixes
            ))
        return out

    paths=expand(source)
    return tuple(paths or (_HandlerPath("\n".join(line for _,line in source)),))


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
        out.append(StateCondition(
            "player_to_actor_distance",
            _DISTANCE_OPERATOR[m.group(1)],
            float(m.group(2)),
        ))
    for m in _TRADE.finditer(text):
        out.append(StateCondition("trade","TRADE_MATCHES",m.group(1).strip()))
    for m in _SPAWNED.finditer(text):
        out.append(StateCondition(f"entity:{m.group(2).strip()}","ENTITY_NOT_SPAWNED" if m.group(1) else "ENTITY_SPAWNED",True))
    return tuple(out)


def _effects(text: str) -> tuple[TransitionEffect,...]:
    out=[]
    executable_text="\n".join(_structural_lua_lines(text))
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
    if "player:tradeComplete()" in executable_text:
        out.append(TransitionEffect("COMPLETE_TRADE","trade"))
    if _COMPLETE.search(executable_text):
        out.append(TransitionEffect("COMPLETE","mission"))
    for m in _MESSAGE.finditer(text):
        out.append(TransitionEffect("MESSAGE","message",m.group(1).strip()))
    if "mission:noAction()" in executable_text:
        out.append(TransitionEffect("NO_ACTION","interaction"))
    return tuple(out)


def _structure_code(line: str) -> str:
    """Strip comments/quoted strings before counting Lua table braces."""
    code=_code(line)
    return re.sub(r"'(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\"", "", code)


def _table_assignment_spans(
    lines: list[str],
    pattern: re.Pattern,
    *,
    enclosing: tuple[tuple[int,int,str],...] | None=None,
) -> tuple[tuple[int,int,str],...]:
    """Return assignment-line through matching-table-close spans for literal table entries."""
    spans=[]
    for i,line in enumerate(lines):
        code=_code(line)
        match=pattern.search(code)
        if not match:
            continue
        if enclosing is not None and not any(start<=i<=end for start,end,_ in enclosing):
            continue
        rest=code[match.end():].strip()
        open_line=None
        if rest.startswith("{"):
            open_line=i
        elif not rest:
            j=i+1
            while j<len(lines) and not _code(lines[j]).strip():
                j+=1
            if j<len(lines) and _code(lines[j]).lstrip().startswith("{"):
                open_line=j
        if open_line is None:
            continue

        depth=0
        started=False
        for j in range(open_line,len(lines)):
            structural=_structure_code(lines[j])
            opens=structural.count("{")
            closes=structural.count("}")
            if opens:
                started=True
            depth+=opens-closes
            if started and depth<=0:
                spans.append((i,j,match.group(1)))
                break
    return tuple(spans)


def _literal_mission_section_spans(lua: str) -> tuple[tuple[int,int,str],...]:
    """Return zero-based line spans and text for literal top-level mission.sections entries."""
    lines=lua.splitlines()
    structural=_structural_lua_lines(lua)
    assignment=None
    for i,line in enumerate(structural):
        if re.search(r"\bmission\.sections\s*=",line):
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


def _section_check_analysis(section: str) -> dict:
    """Classify the mission-status eligibility fragment of one literal section check."""
    check=_section_check_block(section)
    if check is None:
        return {"check_present":False,"status":"NO_CHECK","conditions":(),"unresolved_reasons":()}

    structural=_structural_lua_lines(check)
    executable=" ".join(line.strip() for line in structural if line.strip())
    if re.search(r"\bor\b",executable):
        return {
            "check_present":True,
            "status":"UNRESOLVED",
            "conditions":(),
            "unresolved_reasons":("disjunction",),
        }

    out=[]
    for match in _STATUS_COMPARE.finditer(executable):
        condition=StateCondition(
            f"mission_status:{match.group(1)}",
            _STATUS_COMPARE_OPERATOR[match.group(2)],
            int(match.group(3)),
        )
        if condition not in out:
            out.append(condition)

    aliases={
        match.group(1):match.group(2)
        for match in re.finditer(
            r"\blocal\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"player:getMissionStatus\([^\)]*?xi\.mission\.status\.[A-Z0-9_]+\.([A-Z0-9_]+)\s*\)",
            executable,
        )
    }
    for match in _STATUS_ALIAS_COMPARE.finditer(executable):
        alias=match.group(1)
        channel=aliases.get(alias)
        if channel is None:
            continue
        condition=StateCondition(
            f"mission_status:{channel}",
            _STATUS_COMPARE_OPERATOR[match.group(2)],
            int(match.group(3)),
        )
        if condition not in out:
            out.append(condition)

    reasons=[]
    for reason,pattern in (
        ("mission_var_predicate",r"\bmission:getVar\s*\("),
        ("local_var_predicate",r"\bmission:getLocalVar\s*\("),
        ("key_item_predicate",r"\bplayer:hasKeyItem\s*\("),
    ):
        if re.search(pattern,executable):
            reasons.append(reason)

    helper_calls={
        match.group(1)
        for match in re.finditer(r"(?<![:.])\b([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*player\b",executable)
        if match.group(1)!="function"
    }
    if helper_calls:
        reasons.append("helper_predicate")

    conditions=tuple(out)
    status=("PARTIAL" if conditions else "UNRESOLVED") if reasons else (
        "MODELED" if conditions else "NO_STATUS_REQUIREMENTS"
    )
    return {
        "check_present":True,
        "status":status,
        "conditions":conditions,
        "unresolved_reasons":tuple(reasons),
    }


def _section_check_status_conditions(section: str) -> tuple[StateCondition,...]:
    """Backward-compatible view of modeled mission-status section conditions."""
    return _section_check_analysis(section)["conditions"]


def _section_contexts(lua: str):
    spans=_literal_mission_section_spans(lua)
    rows=[]
    for index,(start,end,text) in enumerate(spans,1):
        rows.append((start,end,index,_section_check_analysis(text)))

    def context(line_no: int):
        matches=[row for row in rows if row[0]<=line_no<=row[1]]
        if not matches:
            return None,None,(),None,(),False
        start,end,index,analysis=max(matches,key=lambda row:row[0])
        return (
            index,(start+1,end+1),analysis["conditions"],analysis["status"],
            analysis["unresolved_reasons"],analysis["check_present"],
        )

    return tuple(rows),context

def _scoped_contexts(lua: str):
    lines=lua.splitlines()
    zone_spans=_table_assignment_spans(lines,_ZONE)
    actor_spans=_table_assignment_spans(lines,_ACTOR,enclosing=zone_spans)

    def context(line_no: int):
        zones=[span for span in zone_spans if span[0]<=line_no<=span[1]]
        zone_span=max(zones,key=lambda span:span[0]) if zones else None
        zone=zone_span[2] if zone_span else None
        actors=[
            span for span in actor_spans
            if span[0]<=line_no<=span[1]
            and (zone_span is None or zone_span[0]<=span[0]<=span[1]<=zone_span[1])
        ]
        actor=max(actors,key=lambda span:span[0])[2] if actors else None
        return zone,actor

    return lines,zone_spans,actor_spans,context


def correlate_lsb_handlers(lua: str, *, feature_id: str="mission:unknown") -> MissionStateMachine:
    """Correlate literal Mission DSL handler blocks into conservative transitions."""
    lines,zone_spans,actor_spans,context=_scoped_contexts(lua)
    section_rows,section_context=_section_contexts(lua)

    transitions=[]
    states={"source:any":MissionState("source:any","Source state")}
    completion_helpers=extract_dynamic_completion_gates(lua)
    helper_names=set()
    for helper_start,_helper_end,helper_text in _balanced_function_blocks(lua):
        helper_match=_HELPER_ASSIGN.search(lines[helper_start])
        if helper_match:
            helper_names.add(helper_match.group(1))
    serial=0
    branch_alternatives=0
    incomplete_branch_guards=0
    source_handler_count=0
    modeled_source_handler_count=0
    unmodeled_source_handler_lines=[]
    for start,end,text in _balanced_function_blocks(lua):
        first=lines[start]
        trigger=None; handler_event=None
        ef=_EVENT_FINISH_KEY.search(first)
        zone,actor=context(start)
        section_index,section_source_lines,section_conditions,section_eligibility_status,section_unresolved_reasons,section_check_present=section_context(start)
        if ef:
            trigger="EVENT_FINISH"
            handler_event=EventIdentity(zone or "UNKNOWN",int(ef.group(1)),actor)
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

        source_handler_count+=1
        transition_count_before=len(transitions)
        paths=_handler_paths(text,start_line=start)
        if len(paths)>1:
            branch_alternatives+=len(paths)
        for path_index,path in enumerate(paths,1):
            unresolved_nested_branch=bool(re.search(r"^\s*(?:if|elseif|else)\b",path.body,re.M))
            aliases="\n".join(
                line for line in path.body.splitlines()
                if _STATUS_ALIAS.search(line)
            )
            guard_parts=[x for x in (aliases,*path.guard_texts) if x]
            # Unsupported/multiline/nested branches retain the previous literal condition
            # extraction, but are explicitly marked incomplete rather than treated as a
            # fully correlated path.
            if unresolved_nested_branch:
                guard_parts.append(path.body)
            guard_context="\n".join(guard_parts)
            conds=list(_conditions(guard_context))
            post_effect_conditions=[]
            post_effect_basis=[]
            invoked_helpers=[]
            for helper_name,dynamic in completion_helpers.items():
                call_pattern=re.compile(
                    rf"\b{re.escape(helper_name)}\s*\(\s*player\s*\)"
                )
                guard_indexes=[
                    index for index,guard in enumerate(path.guard_texts)
                    if call_pattern.search(guard)
                ]
                unresolved_code="\n".join(_code(line) for line in path.body.splitlines())
                in_unresolved_body=bool(
                    unresolved_nested_branch and call_pattern.search(unresolved_code)
                )
                if not guard_indexes and not in_unresolved_body:
                    continue
                invoked_helpers.append(helper_name)
                handled_dynamic=False
                if not unresolved_nested_branch:
                    for guard_index in guard_indexes:
                        prefix=(
                            path.guard_prefix_texts[guard_index]
                            if guard_index < len(path.guard_prefix_texts)
                            else ""
                        )
                        writes={
                            effect.subject
                            for effect in _effects(prefix)
                            if effect.effect in {"SET_VAR","SET_CHANNEL"}
                        }
                        gate_subjects={condition.subject for condition in dynamic.conditions}
                        overlap=tuple(sorted(writes & gate_subjects))
                        if overlap:
                            for condition in dynamic.conditions:
                                if condition not in post_effect_conditions:
                                    post_effect_conditions.append(condition)
                            post_effect_basis.extend(x for x in overlap if x not in post_effect_basis)
                            handled_dynamic=True
                if not handled_dynamic:
                    for condition in dynamic.conditions:
                        if condition not in conds:
                            conds.append(condition)

            effects=list(_effects(path.body))
            executable_body="\n".join(_code(line) for line in path.body.splitlines())
            helper_calls=tuple(sorted(
                helper_name for helper_name in helper_names
                if re.search(rf"\b{re.escape(helper_name)}\s*\(\s*player\s*\)",executable_body)
            ))
            transport_effects=client_transport_effects(path.body)
            effects.extend(effect for effect in transport_effects if effect not in effects)
            event=handler_event
            returned=_EVENT.search(path.body)
            if returned and event is None:
                event=EventIdentity(zone or "UNKNOWN",int(returned.group(1)),actor)
            if not (conds or effects or event):
                continue

            guard_complete=path.guard_complete and not unresolved_nested_branch
            if not guard_complete:
                incomplete_branch_guards+=1

            serial+=1
            gate=DependencyGate(f"source-gate:{serial}","ALL",tuple(conds)) if conds else None
            post_effect_gate=DependencyGate(
                f"source-post-effect-gate:{serial}","ALL",tuple(post_effect_conditions)
            ) if post_effect_conditions else None
            transitions.append(MissionTransition(
                f"source-transition:{serial}","source:any","source:any",trigger,
                gate=gate,event=event,effects=tuple(effects),
                confidence="INFERRED" if guard_complete else "UNKNOWN",
                metadata={
                    "zone":zone,"actor":actor,"source_lines":(start+1,end+1),"literal_correlation":True,
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
                    "section_eligibility_basis":(
                        "literal_section_check_status_conjuncts" if section_conditions else None
                    ),
                    "section_check_present":section_check_present,
                    "section_eligibility_status":section_eligibility_status,
                    "section_eligibility_unresolved_reasons":tuple(section_unresolved_reasons),
                    "priority":(int(pm.group(1)) if (pm:=re.search(r"setPriority\((\d+)\)",text)) else None),
                    "important_event":".importantEvent()" in text,
                    "replace_default":".replaceDefault()" in text,
                    "client_transport":bool(transport_effects),
                    "branch_alternative":len(paths)>1,
                    "branch_index":path_index,
                    "branch_path":path.branch_path,
                    "branch_guard_texts":path.guard_texts,
                    "branch_source_lines":path.branch_source_lines,
                    "branch_guard_complete":guard_complete,
                    "unexpanded_nested_branch":unresolved_nested_branch,
                    "post_effect_gate_basis":tuple(post_effect_basis),
                    "completion_helpers":tuple(invoked_helpers),
                    "helper_calls":helper_calls,
                },
                post_effect_gate=post_effect_gate,
            ))
        if len(transitions)>transition_count_before:
            modeled_source_handler_count+=1
        else:
            unmodeled_source_handler_lines.append((start+1,end+1))
    # Declarative actor handlers are equivalent to unconditional NPC triggers.
    for line_no,line in enumerate(lines):
        dm=_DECL_EVENT.search(line)
        if not dm:
            continue
        zone,_=context(line_no)
        section_index,section_source_lines,section_conditions,section_eligibility_status,section_unresolved_reasons,section_check_present=section_context(line_no)
        actor=dm.group(1); event_id=int(dm.group(3)); suffix=dm.group(4) or ""
        source_handler_count+=1
        modeled_source_handler_count+=1
        serial+=1
        transitions.append(MissionTransition(
            f"source-transition:{serial}","source:any","source:any","NPC_INTERACT",
            event=EventIdentity(zone or "UNKNOWN",event_id,actor),confidence="VERIFIED",
            metadata={
                "zone":zone,"actor":actor,"source_lines":(line_no+1,line_no+1),
                "literal_correlation":True,"declarative_handler":True,
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
                "section_eligibility_basis":(
                    "literal_section_check_status_conjuncts" if section_conditions else None
                ),
                    "section_check_present":section_check_present,
                    "section_eligibility_status":section_eligibility_status,
                    "section_eligibility_unresolved_reasons":tuple(section_unresolved_reasons),
                "replace_default":".replaceDefault()" in suffix,
                "important_event":".importantEvent()" in suffix,
            },
        ))

    findings=extract_lsb_mission_findings(lua)
    completion_gate=extract_section_completion_gate(lua)
    return MissionStateMachine(
        f"machine:{feature_id}",feature_id,tuple(states.values()),tuple(transitions),
        ("source:any",),channels=channels_from_findings(findings),
        completion_gate=completion_gate,
        metadata={
            "extractor":"lsb_static_literal","transition_count":len(transitions),
            "branch_alternatives":branch_alternatives,
            "incomplete_branch_guards":incomplete_branch_guards,
            "source_handler_count":source_handler_count,
            "modeled_source_handler_count":modeled_source_handler_count,
            "unmodeled_source_handler_count":len(unmodeled_source_handler_lines),
            "unmodeled_source_handler_lines":tuple(unmodeled_source_handler_lines),
        },
    )



def mission_extraction_metrics(machine: MissionStateMachine) -> dict:
    """Summarize extractor coverage/complexity without changing interpretation."""
    trigger_counts=Counter(t.trigger for t in machine.transitions)
    guard_counts=Counter(
        condition.operator
        for transition in machine.transitions
        for gate in (transition.gate,transition.post_effect_gate)
        if gate
        for condition in gate.conditions
    )
    effect_counts=Counter(
        effect.effect
        for transition in machine.transitions
        for effect in transition.effects
    )
    event_transitions=[t for t in machine.transitions if t.event]
    branch_rows=[t for t in machine.transitions if t.metadata.get("branch_alternative")]
    incomplete_rows=[
        t for t in machine.transitions
        if t.metadata.get("branch_guard_complete") is False
        or t.metadata.get("unexpanded_nested_branch")
    ]
    helper_calls=Counter(
        helper
        for transition in machine.transitions
        for helper in transition.metadata.get("helper_calls",())
    )
    return {
        "transition_count":len(machine.transitions),
        "transitions_by_trigger":dict(sorted(trigger_counts.items())),
        "event_transition_count":len(event_transitions),
        "branch_transition_count":len(branch_rows),
        "incomplete_branch_transition_count":len(incomplete_rows),
        "channel_count":len(machine.channels),
        "completion_gate_condition_count":len(machine.completion_gate.conditions) if machine.completion_gate else 0,
        "section_scoped_transition_count":sum(
            1 for transition in machine.transitions
            if transition.metadata.get("section_index") is not None
        ),
        "section_eligibility_transition_count":sum(
            1 for transition in machine.transitions
            if transition.metadata.get("section_eligibility_conditions")
        ),
        "section_eligibility_partial_transition_count":sum(
            1 for transition in machine.transitions
            if transition.metadata.get("section_eligibility_status")=="PARTIAL"
        ),
        "section_eligibility_unresolved_transition_count":sum(
            1 for transition in machine.transitions
            if transition.metadata.get("section_eligibility_status")=="UNRESOLVED"
        ),
        "section_eligibility_status_counts":dict(sorted(Counter(
            transition.metadata.get("section_eligibility_status")
            for transition in machine.transitions
            if transition.metadata.get("section_eligibility_status")
        ).items())),
        "section_eligibility_unresolved_reason_counts":dict(sorted(Counter(
            reason for transition in machine.transitions
            for reason in transition.metadata.get("section_eligibility_unresolved_reasons",())
        ).items())),
        "guard_operator_counts":dict(sorted(guard_counts.items())),
        "effect_kind_counts":dict(sorted(effect_counts.items())),
        "helper_call_counts":dict(sorted(helper_calls.items())),
        "source_handler_count":int(machine.metadata.get("source_handler_count",0)),
        "modeled_source_handler_count":int(machine.metadata.get("modeled_source_handler_count",0)),
        "unmodeled_source_handler_count":int(machine.metadata.get("unmodeled_source_handler_count",0)),
        "unmodeled_source_handler_lines":tuple(machine.metadata.get("unmodeled_source_handler_lines",())),
        "event_chains":int(machine.metadata.get("event_chains",0)),
        "event_chain_branch_fanout":int(machine.metadata.get("event_chain_branch_fanout",0)),
        "event_chain_ambiguous_groups":int(machine.metadata.get("event_chain_ambiguous_groups",0)),
        "event_chain_unmatched_triggers":int(machine.metadata.get("event_chain_unmatched_triggers",0)),
    }


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
        if before and after and before[0]!=after[0]:
            state_edge_basis="cross_channel_ambiguous"
        else:
            if before:
                from_state=f"state:{before[0]}={before[1]}"
                states.setdefault(from_state,MissionState(from_state,f"{before[0]} = {before[1]}"))
            if after:
                to_state=f"state:{after[0]}={after[1]}"
                states.setdefault(to_state,MissionState(to_state,f"{after[0]} = {after[1]}"))
            if before and after:
                state_edge_basis="same_literal_channel"
            elif before:
                state_edge_basis="guard_only_literal_channel"
            elif after:
                state_edge_basis="write_only_literal_channel"
            else:
                state_edge_basis="unresolved"
        transitions.append(MissionTransition(
            t.transition_id,from_state,to_state,t.trigger,t.gate,t.event,t.effects,t.confidence,
            t.evidence_ids,t.implementation_status,{
                **t.metadata,
                "state_edge_basis":state_edge_basis,
                "state_guard_subject":before[0] if before else None,
                "state_write_subject":after[0] if after else None,
            },
            post_effect_gate=t.post_effect_gate,
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
            finishes.setdefault((t.event.zone,t.event.event_id,t.event.actor),[]).append(t)

    consumed=set()
    chained=[]
    ambiguous_groups=0
    unmatched_triggers=0
    for t in machine.transitions:
        if t.trigger not in {"NPC_INTERACT","ZONE_IN","TRADE"} or not t.event:
            continue
        exact=finishes.get((t.event.zone,t.event.event_id,t.event.actor),[])
        generic=finishes.get((t.event.zone,t.event.event_id,None),[])
        candidates=exact if exact else generic
        if not candidates:
            unmatched_triggers+=1
            continue
        if len(candidates)>1 and not all(candidate.metadata.get("branch_alternative") for candidate in candidates):
            ambiguous_groups+=1
        consumed.add(t.transition_id)
        for f in candidates:
            consumed.add(f.transition_id)
            effects=tuple(t.effects)+tuple(f.effects)
            # Trigger guards establish the precondition. Each branch-specific finish
            # outcome contributes only its own guards/effects.
            conds=[]
            if t.gate: conds.extend(t.gate.conditions)
            if f.gate: conds.extend(f.gate.conditions)
            gate=DependencyGate(
                f"chain-gate:{t.transition_id}:{f.transition_id}","ALL",tuple(conds)
            ) if conds else None
            post_conds=[]
            for candidate_gate in (t.post_effect_gate,f.post_effect_gate):
                if not candidate_gate:
                    continue
                for condition in candidate_gate.conditions:
                    if condition not in post_conds:
                        post_conds.append(condition)
            post_effect_gate=DependencyGate(
                f"chain-post-effect-gate:{t.transition_id}:{f.transition_id}","ALL",tuple(post_conds)
            ) if post_conds else None
            if "UNKNOWN" in {t.confidence,f.confidence}:
                confidence="UNKNOWN"
            elif t.confidence=="VERIFIED" and f.confidence=="VERIFIED":
                confidence="VERIFIED"
            else:
                confidence="INFERRED"
            chained.append(MissionTransition(
                f"chain:{t.transition_id}:{f.transition_id}",
                t.from_state,f.to_state,t.trigger,gate,
                EventIdentity(t.event.zone,t.event.event_id,t.event.actor),
                effects,
                confidence,
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
                    "trigger_branch_path":t.metadata.get("branch_path",()),
                    "finish_branch_path":f.metadata.get("branch_path",()),
                    "section_index":t.metadata.get("section_index"),
                    "section_source_lines":t.metadata.get("section_source_lines"),
                    "section_eligibility_conditions":tuple(
                        t.metadata.get("section_eligibility_conditions",())
                    ),
                    "section_eligibility_basis":t.metadata.get("section_eligibility_basis"),
                    "section_check_present":t.metadata.get("section_check_present"),
                    "section_eligibility_status":t.metadata.get("section_eligibility_status"),
                    "section_eligibility_unresolved_reasons":tuple(t.metadata.get("section_eligibility_unresolved_reasons",())),
                    "branch_guard_complete":bool(
                        t.metadata.get("branch_guard_complete",True)
                        and f.metadata.get("branch_guard_complete",True)
                    ),
                    "post_effect_gate_basis":tuple(dict.fromkeys(
                        tuple(t.metadata.get("post_effect_gate_basis",()))
                        + tuple(f.metadata.get("post_effect_gate_basis",()))
                    )),
                },
                post_effect_gate=post_effect_gate,
            ))

    remaining=[t for t in machine.transitions if t.transition_id not in consumed]
    out=MissionStateMachine(
        machine.machine_id,machine.feature_id,machine.states,
        tuple(remaining+chained),machine.entry_state_ids,machine.channels,
        machine.completion_gate,{
            **machine.metadata,
            "event_chains":len(chained),
            "event_chain_branch_fanout":sum(max(0,len(v)-1) for v in finishes.values()),
            "event_chain_actor_scope":True,
            "event_chain_ambiguous_groups":ambiguous_groups,
            "event_chain_unmatched_triggers":unmatched_triggers,
        },
    )
    return materialize_channel_states(out)


def _literal_mission_section_bodies(lua: str) -> tuple[str,...]:
    """Return literal top-level mission.sections entry bodies."""
    return tuple(text for _start,_end,text in _literal_mission_section_spans(lua))


def _section_check_block(section: str) -> str | None:
    """Return the literal top-level check function for one section."""
    lines=section.splitlines()
    for start,_end,text in _balanced_function_blocks(section):
        if re.search(r"^\s*check\s*=\s*function\b",lines[start]):
            return text
    return None


def extract_section_completion_gate(lua: str) -> DependencyGate | None:
    """Recover an unambiguous literal completion gate from one completing section.

    Status checks are read only from the completing section's check handler. Unrelated
    mission sections are never combined. Multiple completing sections must prove the
    same convergence gate; disagreement fails closed as unresolved.
    """
    candidates=[]
    for section in _literal_mission_section_bodies(lua):
        executable="\n".join(_structural_lua_lines(section))
        if not _COMPLETE.search(executable):
            continue

        conditions=_section_check_status_conditions(section)
        pairs=[
            (condition.subject.split(":",1)[1],int(condition.value))
            for condition in conditions
            if condition.operator=="EQ"
            and condition.subject.startswith("mission_status:")
            and isinstance(condition.value,int)
        ]
        by_value={}
        for channel,value in pairs:
            by_value.setdefault(value,[]).append(channel)
        section_candidates=[
            (value,tuple(sorted(set(channels))))
            for value,channels in by_value.items()
            if len(set(channels))>=2
        ]
        if len(section_candidates)!=1:
            return None
        candidates.append(section_candidates[0])

    if not candidates:
        return None
    if any(candidate!=candidates[0] for candidate in candidates[1:]):
        return None

    value,channels=candidates[0]
    return DependencyGate(
        "section:completion-convergence","ALL",
        tuple(StateCondition(f"mission_status:{channel}","EQ",value) for channel in channels),
    )


def extract_helper_transitions(lua: str) -> tuple[MissionTransition,...]:
    """Extract helper behavior as conservative branch-specific transitions."""
    lines=lua.splitlines()
    out=[]
    serial=0
    for start,end,text in _balanced_function_blocks(lua):
        first=lines[start]
        hm=_HELPER_ASSIGN.search(first)
        if not hm:
            continue
        helper_name=hm.group(1)
        paths=_handler_paths(text,start_line=start)
        for path_index,path in enumerate(paths,1):
            unresolved_nested_branch=bool(re.search(r"^\s*(?:if|elseif|else)\b",path.body,re.M))
            guard_parts=list(path.guard_texts)
            if unresolved_nested_branch:
                guard_parts.append(path.body)
            conds=_conditions("\n".join(guard_parts))
            effects=_effects(path.body)
            if not effects and not conds:
                continue
            serial+=1
            trigger="TIMER" if _TIMER.search(path.body) or "GetSystemTime()" in path.body else "PLACEHOLDER"
            gate=DependencyGate(f"helper-gate:{serial}","ALL",conds) if conds else None
            guard_complete=path.guard_complete and not unresolved_nested_branch
            executable_body="\n".join(_code(line) for line in path.body.splitlines())
            recursive=bool(re.search(rf"\b{re.escape(helper_name)}\s*\(\s*player\s*\)",executable_body))
            out.append(MissionTransition(
                f"helper:{helper_name}:{serial}","source:any","source:any",trigger,gate,None,effects,
                "INFERRED" if guard_complete else "UNKNOWN",
                metadata={
                    "helper":helper_name,
                    "source_lines":(start+1,end+1),
                    "helper_behavior":True,
                    "branch_alternative":len(paths)>1,
                    "branch_index":path_index,
                    "branch_path":path.branch_path,
                    "branch_guard_complete":guard_complete,
                    "unexpanded_nested_branch":unresolved_nested_branch,
                    "recursive_helper_call":recursive,
                },
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


def extract_dynamic_completion_gates(lua: str) -> dict[str,DependencyGate]:
    """Recover structurally proven mission-completion helper loops.

    Helper names are intentionally irrelevant. A candidate must be a local player helper
    that iterates one mission-status enum range, returns false when one member differs from
    a literal terminal value, and has a true return path.
    """
    lines=lua.splitlines()
    out={}
    for start,_end,text in _balanced_function_blocks(lua):
        match=_LOCAL_PLAYER_HELPER.match(lines[start])
        if not match:
            continue
        helper_name=match.group(1)
        code_text="\n".join(_code(line) for line in text.splitlines())
        if "return false" not in code_text or "return true" not in code_text:
            continue
        loop=re.search(
            r"for\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"xi\.mission\.status\.([A-Z0-9_]+)\.([A-Z0-9_]+)\s*,\s*"
            r"xi\.mission\.status\.([A-Z0-9_]+)\.([A-Z0-9_]+)\s+do",
            code_text,
        )
        if not loop or loop.group(2)!=loop.group(4):
            continue
        iterator,family,first,_family2,last=loop.groups()
        required=re.search(
            rf"getMissionStatus\([^\)]*?,\s*{re.escape(iterator)}\s*\)\s*~=\s*(\d+)",
            code_text,
        )
        if not required:
            continue

        symbols=[]
        family_pattern=re.compile(
            rf"xi\.mission\.status\.{re.escape(family)}\.([A-Z0-9_]+)"
        )
        source_code="\n".join(_code(line) for line in lua.splitlines())
        for symbol_match in family_pattern.finditer(source_code):
            symbol=symbol_match.group(1)
            if symbol not in symbols:
                symbols.append(symbol)
        try:
            lo=symbols.index(first); hi=symbols.index(last)
        except ValueError:
            continue
        if lo>hi:
            lo,hi=hi,lo
        names=symbols[lo:hi+1]
        if not names:
            continue
        value=int(required.group(1))
        out[helper_name]=DependencyGate(
            f"helper:{helper_name}","ALL",
            tuple(StateCondition(f"mission_status:{name}","EQ",value) for name in names),
        )
    return out


def extract_dynamic_completion_gate(lua: str) -> DependencyGate | None:
    """Backward-compatible single-gate view of structurally discovered helpers."""
    gates=extract_dynamic_completion_gates(lua)
    if "isMissionComplete" in gates:
        return gates["isMissionComplete"]
    if len(gates)==1:
        return next(iter(gates.values()))
    return None


def client_transport_effects(lua: str) -> tuple[TransitionEffect,...]:
    """Preserve explicit source annotations that transport is client handled."""
    out=[]
    for line in lua.splitlines():
        lowered=line.lower()
        if "handled by the client" in lowered and ("transport" in lowered or "exit" in lowered):
            out.append(TransitionEffect("CLIENT_TRANSPORT","player",line.strip().lstrip("-").strip()))
    return tuple(out)
