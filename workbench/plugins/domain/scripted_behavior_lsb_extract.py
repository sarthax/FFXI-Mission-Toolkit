"""Conservative LSB Lua extractor for generic scripted-entity behavior.

This extractor recognizes static source structures only. It does not execute Lua, evaluate helper
functions, or infer retail behavior from comments. Unsupported/dynamic behavior remains unmodeled
and is reported through extraction metrics rather than guessed.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .scripted_behavior import (
    BehaviorCondition,
    BehaviorEffect,
    BehaviorRule,
    ScriptedBehaviorMap,
)


_HOOK_HEADER=re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\."
    r"(on[A-Za-z0-9_]+|registryRequirements|entryRequirements|afterInstanceRegister)"
    r"\s*=\s*function\s*\(([^)]*)\)"
)
_LOCAL_HELPER_HEADER=re.compile(
    r"^\s*local\s+(?:function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)|"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*function\s*\(([^)]*)\))"
)
_ENTITY_HELPER_HEADER=re.compile(
    r"^\s*entity\.([A-Za-z_][A-Za-z0-9_]*)\s*=\s*function\s*\(([^)]*)\)"
)
_HPP=re.compile(r"\b(?:mob|mobArg|target):getHPP\(\)\s*(<=|>=|<|>)\s*(\d+)")
_RANDOM_RANGE=re.compile(r"math\.randomInt\(\s*(\d+)\s*,\s*(\d+)\s*\)")
_RANDOM_PERCENT=re.compile(
    r"math\.randomInt\(\s*1\s*,\s*100\s*\)\s*<=\s*(\d+)"
)
_TIMER_MS=re.compile(r"\b(?:mob|mobArg|target|player):timer\(\s*(\d+)")
_SPAWN_SYMBOL=re.compile(r"SpawnMob\(\s*ID\.mob\.([A-Z0-9_]+)\s*\)")
_GETMOB_SYMBOL=re.compile(r"GetMobByID\(\s*ID\.mob\.([A-Z0-9_]+)\s*\)")
_LOCAL_READ=re.compile(r"getLocalVar\(\s*['\"]([^'\"]+)['\"]\s*\)")
_DROP_ID=re.compile(r"setDropID\(\s*(\d+)\s*\)")
_MOD_CALL=re.compile(
    r"\b(?:setMod|addMod|delMod|setMobMod|addMobMod|delMobMod)\(\s*"
    r"xi\.(?:mod|mobMod)\.([A-Z0-9_]+)"
)
_DESPAWN=re.compile(r"\bDespawnMob\(")
_SPELL_OVERRIDE=re.compile(r"\bspell:set(?:AoE|Radius|Animation|MPCost|CastTime|Recast)\(")
_ENMITY_TRANSFER=re.compile(r"\b(?:updateEnmity|updateClaim)\s*\(")
_KEYITEM_GIVE=re.compile(r"npcUtil\.giveKeyItem\(\s*player\s*,\s*xi\.keyItem\.([A-Z0-9_]+)")
_KEYITEM_DEL=re.compile(r"player:delKeyItem\(\s*xi\.keyItem\.([A-Z0-9_]+)")
_ITEM_GIVE=re.compile(r"npcUtil\.giveItem\(\s*player\s*,\s*([^\n\)]+)")
_ADD_GIL=re.compile(r"player:addGil\(\s*([^\)]+)\)")
_DEL_GIL=re.compile(r"player:delGil\(\s*([^\)]+)\)")
_CHAR_READ=re.compile(r"player:getCharVar\(\s*['\"]([^'\"]+)['\"]\s*\)")
_CHAR_SET=re.compile(r"player:setCharVar\(\s*['\"]([^'\"]+)['\"]\s*,\s*([^\)]+)\)")
_START_EVENT=re.compile(r"player:startEvent\(\s*(\d+)")
_UPDATE_EVENT=re.compile(r"player:updateEvent\(")
_CSID_LITERAL_COMPARE=re.compile(
    r"\bcsid\s*==\s*(\d+)"
)
_EVENT_OUTCOME_LITERAL_COMPARE=re.compile(
    r"\b(option|result)\s*==\s*(-?\d+|true|false|['\"][^'\"]+['\"])"
)
_CONFIRM_TRADE=re.compile(r"player:(?:confirmTrade|tradeComplete)\(\)")
_TRADE_PREDICATE=re.compile(r"npcUtil\.(tradeHas|tradeHasExactly|tradeMatches)\(")
_OPEN_DOOR=re.compile(r"(?:GetNPCByID\([^\n]+?\)|\b(?:npc|door)\b):openDoor\(\s*([^\)]*)\)")
_SET_ANIMATION=re.compile(r"\b(?:npc|door|mob|mobArg|npcArg):setAnimation\(\s*([^\)]+)\)")
_SET_STATUS=re.compile(r"\b(?:npc|door|mob|mobArg|npcArg|bombMob):setStatus\(\s*([^\)]+)\)")
_SET_UNTARGETABLE=re.compile(r"\b(?:npc|door|mob|mobArg|npcArg):setUntargetable\(\s*([^\)]+)\)")
_SET_POS=re.compile(r"\b(?:npc|door|mob|mobArg|npcArg|bombMob):setPos\(")
_PATH_CALL=re.compile(r"\b(?:mob|mobArg|npc|npcArg):(pathTo|pathThrough)\(")
_SYSTEM_HELPER=re.compile(r"\bxi\.([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_METHOD_API_CALL=re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
    r":([A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_DOTTED_API_CALL=re.compile(
    r"\b((?:[A-Za-z_][A-Za-z0-9_]*\.)+[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_GLOBAL_API_CALL=re.compile(r"(?<![\w\.:])([A-Z][A-Za-z0-9_]*)\s*\(")
_NAMED_STATE_GET=re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*):(getLocalVar|getCharVar)\(\s*['\"]([^'\"]+)['\"]\s*\)"
)
_NAMED_STATE_SET=re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*):(setLocalVar|setCharVar)\(\s*['\"]([^'\"]+)['\"]\s*,\s*(.+)\)\s*$"
)
_SERVER_STATE_GET=re.compile(r"\bGetServerVariable\(\s*['\"]([^'\"]+)['\"]\s*\)")
_SERVER_STATE_SET=re.compile(r"\bSetServerVariable\(\s*['\"]([^'\"]+)['\"]\s*,\s*(.+)\)\s*$")
_INSTANCE_LIFECYCLE_GET=re.compile(
    r"\b(instance):(getStage|getProgress)\(\s*\)"
)
_INSTANCE_LIFECYCLE_SET=re.compile(
    r"\b(instance):(setStage|setProgress)\(\s*(.+)\)\s*$"
)
_STATE_ALIAS_ASSIGN=re.compile(
    r"\blocal\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"([A-Za-z_][A-Za-z0-9_]*):(getLocalVar|getCharVar)\(\s*['\"]([^'\"]+)['\"]\s*\)"
)
_SERVER_ALIAS_ASSIGN=re.compile(
    r"\blocal\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*GetServerVariable\(\s*['\"]([^'\"]+)['\"]\s*\)"
)
_INSTANCE_LIFECYCLE_ALIAS_ASSIGN=re.compile(
    r"\blocal\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(instance):(getStage|getProgress)\(\s*\)"
)
_SWITCH_SELECTOR=re.compile(r"\bswitch\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*:\s*caseof")
_SWITCH_CASE=re.compile(r"^\s*\[([^\]]+)\]\s*=\s*function\s*\(")
_ALIAS_IF_LITERAL_EQUALS=re.compile(
    r"^\s*if\s+([A-Za-z_][A-Za-z0-9_]*)\s*==\s*"
    r"(-?\d+|true|false|['\"][^'\"]+['\"])\s+then\b"
)
_SERVER_DIRECT_IF_LITERAL_EQUALS=re.compile(
    r"^\s*if\s+GetServerVariable\(\s*['\"]([^'\"]+)['\"]\s*\)\s*==\s*"
    r"(-?\d+|true|false|['\"][^'\"]+['\"])\s+then\b"
)
_INSTANCE_DIRECT_IF_LITERAL_EQUALS=re.compile(
    r"^\s*if\s+(instance):(getStage|getProgress)\(\s*\)\s*==\s*"
    r"(-?\d+|true|false|['\"][^'\"]+['\"])\s+then\b"
)
_TIME_ALIAS_ASSIGN=re.compile(
    r"\blocal\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(VanadielHour|VanadielDay|VanadielDayOfTheWeek)\(\)"
)
_TIME_RANGE=re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*>=\s*(-?\d+)\s+and\s+\1\s*<=\s*(-?\d+)"
)
_WEATHER_ELEMENT_COMPARE=re.compile(
    r"xi\.data\.element\.getWeatherElement\(([^\)]+)\)\s*(==|~=)\s*xi\.element\.([A-Z0-9_]+)"
)
_POSITION_COMPARE=re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*):get([XYZ])Pos\(\)\s*(<=|>=|<|>|==|~=)\s*(-?\d+(?:\.\d+)?)"
)
_DISTANCE_COMPARE=re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*):(?:checkDistance|getDistance)\(([^\)]*)\)\s*(<=|>=|<|>|==|~=)\s*(\d+(?:\.\d+)?)"
)
_GROUP_ACCESS=re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*):(getParty|getAlliance)\(\)"
)
_DIRECT_ENTITY_EXPR=re.compile(
    r"\b(GetNPCByID|GetMobByID|SpawnMob|DespawnMob)\(\s*"
    r"(ID\.(npc|mob)\.([A-Z0-9_]+)(?:\s*([+-])\s*(\d+))?)"
    r"(?=\s*(?:,|\)))"
)
_ENTITY_ALIAS_ASSIGN=re.compile(
    r"\blocal\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"ID\.(npc|mob)\.([A-Z0-9_]+)(?:\s*([+-])\s*(\d+))?"
)
_RUNTIME_ENTITY_ID_ALIAS_ASSIGN=re.compile(
    r"\blocal\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"([A-Za-z_][A-Za-z0-9_]*):getID\(\s*\)"
)
_ENTITY_ALIAS_CALL=re.compile(
    r"\b(GetNPCByID|GetMobByID|SpawnMob|DespawnMob)\(\s*"
    r"([A-Za-z_][A-Za-z0-9_]*)(?:\s*([+-])\s*(\d+))?\s*\)"
)
_NUMERIC_FOR=re.compile(
    r"^\s*for\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(-?\d+)\s*,\s*(-?\d+)"
    r"(?:\s*,\s*(-?\d+))?\s+do\b"
)
_SYMBOLIC_FOR=re.compile(
    r"^\s*for\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"ID\.(npc|mob)\.([A-Z0-9_]+)(?:\s*([+-])\s*(\d+))?\s*,\s*"
    r"ID\.(npc|mob)\.([A-Z0-9_]+)(?:\s*([+-])\s*(\d+))?"
    r"(?:\s*,\s*(-?\d+))?\s+do\b"
)


@dataclass(frozen=True)
class HookBlock:
    hook: str
    args: tuple[str,...]
    start_line: int
    end_line: int
    body: str
    owner: str = "entity"


@dataclass(frozen=True)
class HelperBlock:
    name: str
    args: tuple[str,...]
    start_line: int
    end_line: int
    body: str
    owner: str = "local"


@dataclass(frozen=True)
class CallbackBlock:
    callback_type: str
    receiver: str | None
    trigger: str
    args: tuple[str,...]
    call_line: int
    start_line: int
    end_line: int
    body: str
    delay_source: str | None = None
    event_name: str | None = None


def _structural_lua_lines(lua: str) -> list[str]:
    """Strip comments/string contents while retaining Lua structure and call punctuation."""
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
                visible.append(" ")
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


def _open_count(code: str) -> int:
    return (
        len(re.findall(r"\bfunction\b",code))
        + len(re.findall(r"(?<!else)\bif\b",code))
        + len(re.findall(r"\bfor\b[^\n]*\bdo\b",code))
        + len(re.findall(r"\bwhile\b[^\n]*\bdo\b",code))
        + len(re.findall(r"\brepeat\b",code))
    )


def _close_count(code: str) -> int:
    return len(re.findall(r"\bend\b",code))+len(re.findall(r"\buntil\b",code))


def extract_hook_blocks(lua: str) -> tuple[HookBlock,...]:
    """Return balanced top-level scripted hook functions with exact source line ranges."""
    raw=lua.splitlines()
    structural=_structural_lua_lines(lua)
    out=[]
    claimed_until=-1
    for i,code in enumerate(structural):
        if i<=claimed_until:
            continue
        match=_HOOK_HEADER.match(code)
        if not match:
            continue
        owner,hook,args_text=match.groups()
        depth=0
        started=False
        for j in range(i,len(raw)):
            row=structural[j]
            opens=_open_count(row)
            closes=_close_count(row)
            if opens:
                started=True
            depth+=opens-closes
            if started and depth<=0:
                claimed_until=j
                args=tuple(
                    part.strip() for part in args_text.split(",") if part.strip()
                )
                out.append(HookBlock(
                    hook,args,i+1,j+1,"\n".join(raw[i:j+1]),owner
                ))
                break
    return tuple(out)


def extract_helper_blocks(lua: str) -> tuple[HelperBlock,...]:
    """Return balanced local/entity helper functions, excluding entity.on* hooks."""
    raw=lua.splitlines()
    structural=_structural_lua_lines(lua)
    out=[]
    claimed=set()
    for i,code in enumerate(structural):
        local_match=_LOCAL_HELPER_HEADER.match(code)
        entity_match=_ENTITY_HELPER_HEADER.match(code)
        name=None
        args_text=""
        owner="local"
        if local_match:
            name=local_match.group(1) or local_match.group(3)
            args_text=local_match.group(2) or local_match.group(4) or ""
        elif entity_match and not entity_match.group(1).startswith("on"):
            name=entity_match.group(1)
            args_text=entity_match.group(2) or ""
            owner="entity"
        if not name or i in claimed:
            continue
        depth=0
        started=False
        for j in range(i,len(raw)):
            row=structural[j]
            opens=_open_count(row)
            closes=_close_count(row)
            if opens:
                started=True
            depth+=opens-closes
            if started and depth<=0:
                claimed.update(range(i,j+1))
                args=tuple(part.strip() for part in args_text.split(",") if part.strip())
                out.append(HelperBlock(name,args,i+1,j+1,"\n".join(raw[i:j+1]),owner))
                break
    return tuple(out)


def extract_callback_blocks(text: str, *, start_line: int=1) -> tuple[CallbackBlock,...]:
    """Extract bounded anonymous timer/queue/listener callbacks from a source block.

    The parser recognizes the callback wrapper and balances the anonymous function body. It does
    not execute delay expressions or listener predicates.
    """
    raw=text.splitlines()
    structural=_structural_lua_lines(text)
    out=[]
    claimed_until=-1
    for i,line in enumerate(raw):
        if i<=claimed_until:
            continue
        code=structural[i] if i<len(structural) else ""
        callback_type=None
        for candidate in ("timer","queue","addListener"):
            if re.search(rf":{candidate}\s*\(",code):
                callback_type=candidate
                break
        if callback_type is None:
            continue

        function_line=None
        header_lines=[]
        for j in range(i,min(len(raw),i+5)):
            header_lines.append(raw[j])
            if re.search(r"\bfunction\s*\(",structural[j]):
                function_line=j
                break
        if function_line is None:
            continue
        header="\n".join(header_lines)

        receiver_match=re.search(
            rf"(.+?):{callback_type}\s*\(",
            header,
            flags=re.DOTALL,
        )
        receiver=receiver_match.group(1).strip() if receiver_match else None
        # Keep only the final source expression when indentation/previous text is captured.
        if receiver and "\n" in receiver:
            receiver=receiver.split("\n")[-1].strip()

        args_match=re.search(r"\bfunction\s*\(([^)]*)\)",header,flags=re.DOTALL)
        args=tuple(
            part.strip() for part in (args_match.group(1) if args_match else "").split(",")
            if part.strip()
        )

        prefix_match=re.search(
            rf":{callback_type}\s*\((.*?)\bfunction\s*\(",
            header,
            flags=re.DOTALL,
        )
        prefix=(prefix_match.group(1).strip() if prefix_match else "")
        delay_source=None
        event_name=None
        trigger=callback_type.upper()+"_CALLBACK"
        if callback_type in {"timer","queue"}:
            delay_source=prefix.strip().rstrip(",").strip() or None
            trigger=("TIMER_CALLBACK" if callback_type=="timer" else "QUEUE_CALLBACK")
        elif callback_type=="addListener":
            quoted=re.findall(r"['\"]([^'\"]+)['\"]",prefix)
            event_name=quoted[0] if quoted else None
            trigger=f"LISTENER:{event_name}" if event_name else "LISTENER_CALLBACK"

        depth=0
        started=False
        end_line=None
        for j in range(function_line,len(raw)):
            row=structural[j]
            opens=_open_count(row)
            closes=_close_count(row)
            if opens:
                started=True
            depth+=opens-closes
            if started and depth<=0:
                end_line=j
                break
        if end_line is None:
            continue
        claimed_until=end_line
        out.append(CallbackBlock(
            callback_type=callback_type,
            receiver=receiver,
            trigger=trigger,
            args=args,
            call_line=start_line+i,
            start_line=start_line+function_line,
            end_line=start_line+end_line,
            body="\n".join(raw[function_line:end_line+1]),
            delay_source=delay_source,
            event_name=event_name,
        ))
    return tuple(out)


def _callback_rules(
    *,
    text: str,
    start_line: int,
    subject: str,
    parent_hook: str,
    source_path: str,
    helper: str | None=None,
    call_chain: tuple[str,...] | None=None,
) -> tuple[BehaviorRule,...]:
    rules=[]
    for index,callback in enumerate(extract_callback_blocks(text,start_line=start_line),1):
        meta={
            "source_path":source_path,
            "source_lines":(callback.start_line,callback.end_line),
            "hook":parent_hook,
            "callback_type":callback.callback_type,
            "callback_receiver":callback.receiver,
            "callback_call_line":callback.call_line,
            "callback_event":callback.event_name,
            "callback_delay_source":callback.delay_source,
            "callback_args":callback.args,
        }
        if helper:
            meta["helper"]=helper
        if call_chain:
            meta["call_chain"]=call_chain

        conditions=[]
        if callback.delay_source is not None:
            conditions.append(BehaviorCondition(
                "callback","DELAY_SOURCE",callback.delay_source,
                {"source_line":callback.call_line},
            ))
        if callback.event_name is not None:
            conditions.append(BehaviorCondition(
                "callback","LISTENER_EVENT",callback.event_name,
                {"source_line":callback.call_line},
            ))
        callback_id=f"{parent_hook}:callback:{index}:{callback.callback_type}"
        rules.append(BehaviorRule(
            callback_id,
            "callback",
            subject,
            trigger=callback.trigger,
            conditions=tuple(conditions),
            effects=(BehaviorEffect(
                "EXECUTE_CALLBACK",
                callback.receiver or subject,
                callback.trigger,
                {
                    "callback_type":callback.callback_type,
                    "event":callback.event_name,
                    "delay_source":callback.delay_source,
                },
            ),),
            confidence="VERIFIED",
            implementation_status="PRESENT",
            metadata=meta,
        ))

        api_rule=_api_call_rule(
            rule_id=f"{callback_id}:api",
            subject=subject,
            trigger=callback.trigger,
            calls=_api_calls(callback.body,start_line=callback.start_line),
            meta=meta,
        )
        if api_rule is not None:
            rules.append(api_rule)
        state_rule=_state_flow_rule(
            rule_id=f"{callback_id}:state",
            subject=subject,
            trigger=callback.trigger,
            accesses=_named_state_accesses(callback.body,start_line=callback.start_line),
            meta=meta,
        )
        if state_rule is not None:
            rules.append(state_rule)
        context_rule=_context_condition_rule(
            rule_id=f"{callback_id}:context",
            subject=subject,
            trigger=callback.trigger,
            text=callback.body,
            start_line=callback.start_line,
            meta=meta,
        )
        if context_rule is not None:
            rules.append(context_rule)
        entity_ref_rule=_direct_entity_reference_rule(
            rule_id=f"{callback_id}:entity-refs",
            subject=subject,
            trigger=callback.trigger,
            text=callback.body,
            start_line=callback.start_line,
            meta=meta,
        )
        if entity_ref_rule is not None:
            rules.append(entity_ref_rule)
        transition_rules=_switch_state_transition_rules(
            text=callback.body,
            start_line=callback.start_line,
            subject=subject,
            trigger=callback.trigger,
            meta=meta,
        )
        if transition_rules:
            rules.extend(transition_rules)
    return tuple(rules)


def _reachable_helpers(hook: HookBlock, helpers: tuple[HelperBlock,...], *, max_depth: int=6):
    """Follow statically named local/entity helper calls from one hook, cycle-safe."""
    by_name={helper.name:helper for helper in helpers}
    reached=[]
    seen=set()
    queue=[(hook.body,0,())]
    while queue:
        text,depth,chain=queue.pop(0)
        if depth>=max_depth:
            continue
        for name,helper in by_name.items():
            if name in seen:
                continue
            if not re.search(rf"(?<![A-Za-z0-9_])(?:entity\.)?{re.escape(name)}\s*\(",text):
                continue
            seen.add(name)
            next_chain=chain+(name,)
            reached.append((helper,next_chain))
            queue.append((helper.body,depth+1,next_chain))
    return tuple(reached)


def _symbol(name: str) -> str:
    return f"entity-symbol:{name}"


def _source_meta(block: HookBlock, source_path: str) -> dict:
    return {
        "source_path":source_path,
        "source_lines":(block.start_line,block.end_line),
        "hook":block.hook,
        "hook_owner":block.owner,
    }


def _api_calls(text: str, *, start_line: int) -> tuple[dict,...]:
    """Preserve statically visible Lua-bound calls without requiring semantic knowledge.

    This is intentionally syntax-level evidence. Nested argument expressions are retained as the
    visible remainder of the source line rather than evaluated.
    """
    raw=text.splitlines()
    structural=_structural_lua_lines(text)
    calls=[]
    seen=set()
    for offset,code in enumerate(structural):
        line_no=start_line+offset
        raw_line=raw[offset] if offset < len(raw) else ""
        for match in _METHOD_API_CALL.finditer(code):
            receiver,method=match.groups()
            key=(line_no,"method",receiver,method,match.start())
            if key in seen:
                continue
            seen.add(key)
            calls.append({
                "style":"method",
                "receiver":receiver,
                "function":method,
                "qualified_name":f"{receiver}:{method}",
                "source_line":raw_line.strip(),
                "line":line_no,
            })
        for match in _DOTTED_API_CALL.finditer(code):
            qualified=match.group(1)
            # A dotted call that starts at a method receiver's method token is a duplicate.
            if any(
                row["line"]==line_no and row["qualified_name"].replace(":",".")==qualified
                for row in calls
            ):
                continue
            key=(line_no,"dotted",qualified,match.start())
            if key in seen:
                continue
            seen.add(key)
            parts=qualified.rsplit(".",1)
            calls.append({
                "style":"dotted",
                "receiver":parts[0] if len(parts)==2 else None,
                "function":parts[-1],
                "qualified_name":qualified,
                "source_line":raw_line.strip(),
                "line":line_no,
            })
        for match in _GLOBAL_API_CALL.finditer(code):
            name=match.group(1)
            key=(line_no,"global",name,match.start())
            if key in seen:
                continue
            seen.add(key)
            calls.append({
                "style":"global",
                "receiver":None,
                "function":name,
                "qualified_name":name,
                "source_line":raw_line.strip(),
                "line":line_no,
            })
    calls.sort(key=lambda row:(row["line"],row["qualified_name"],row["style"]))
    return tuple(calls)


def _strip_line_comment_preserve_strings(line: str) -> str:
    """Remove Lua -- comments while preserving quoted string contents."""
    out=[]
    quote=None
    i=0
    while i<len(line):
        ch=line[i]
        if quote is not None:
            out.append(ch)
            if ch=="\\" and i+1<len(line):
                out.append(line[i+1])
                i+=2
                continue
            if ch==quote:
                quote=None
            i+=1
            continue
        if ch in {"'","\""}:
            quote=ch
            out.append(ch)
            i+=1
            continue
        if line.startswith("--",i):
            break
        out.append(ch)
        i+=1
    return "".join(out)


def _state_scope(receiver: str | None, method: str) -> str:
    if method in {"getCharVar","setCharVar"}:
        return "PLAYER_CHAR"
    if receiver=="instance":
        return "INSTANCE_LOCAL"
    if receiver=="player":
        return "PLAYER_LOCAL"
    if receiver in {"zone","zoneObject"}:
        return "ZONE_LOCAL"
    if receiver:
        return "ENTITY_LOCAL"
    return "SERVER_GLOBAL"


def _state_id(scope: str, name: str, receiver: str | None=None) -> str:
    owner=(receiver or "server").replace(" ","_")
    return f"state:{scope}:{owner}:{name}"


def _named_state_accesses(text: str, *, start_line: int) -> tuple[dict,...]:
    """Extract named runtime/persistent state accesses line-by-line without evaluating values."""
    rows=[]
    seen=set()
    for offset,raw_line in enumerate(text.splitlines()):
        code=_strip_line_comment_preserve_strings(raw_line)
        line_no=start_line+offset
        for match in _NAMED_STATE_GET.finditer(code):
            receiver,method,name=match.groups()
            scope=_state_scope(receiver,method)
            key=("READ",scope,receiver,name,line_no)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "access":"READ","scope":scope,"receiver":receiver,"method":method,
                "name":name,"state_id":_state_id(scope,name,receiver),
                "value":None,"line":line_no,"source_line":raw_line.strip(),
            })
        match=_NAMED_STATE_SET.search(code)
        if match:
            receiver,method,name,value=match.groups()
            scope=_state_scope(receiver,method)
            key=("WRITE",scope,receiver,name,line_no,value.strip())
            if key not in seen:
                seen.add(key)
                rows.append({
                    "access":"WRITE","scope":scope,"receiver":receiver,"method":method,
                    "name":name,"state_id":_state_id(scope,name,receiver),
                    "value":value.strip(),"line":line_no,"source_line":raw_line.strip(),
                })
        for match in _SERVER_STATE_GET.finditer(code):
            name=match.group(1)
            scope="SERVER_GLOBAL"
            key=("READ",scope,None,name,line_no)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "access":"READ","scope":scope,"receiver":None,"method":"GetServerVariable",
                "name":name,"state_id":_state_id(scope,name),
                "value":None,"line":line_no,"source_line":raw_line.strip(),
            })
        match=_SERVER_STATE_SET.search(code)
        if match:
            name,value=match.groups()
            scope="SERVER_GLOBAL"
            key=("WRITE",scope,None,name,line_no,value.strip())
            if key not in seen:
                seen.add(key)
                rows.append({
                    "access":"WRITE","scope":scope,"receiver":None,"method":"SetServerVariable",
                    "name":name,"state_id":_state_id(scope,name),
                    "value":value.strip(),"line":line_no,"source_line":raw_line.strip(),
                })
        for match in _INSTANCE_LIFECYCLE_GET.finditer(code):
            receiver,method=match.groups()
            name="stage" if method=="getStage" else "progress"
            scope="INSTANCE_LIFECYCLE"
            key=("READ",scope,receiver,name,line_no)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "access":"READ","scope":scope,"receiver":receiver,"method":method,
                "name":name,"state_id":_state_id(scope,name,receiver),
                "value":None,"line":line_no,"source_line":raw_line.strip(),
            })
        match=_INSTANCE_LIFECYCLE_SET.search(code)
        if match:
            receiver,method,value=match.groups()
            name="stage" if method=="setStage" else "progress"
            scope="INSTANCE_LIFECYCLE"
            key=("WRITE",scope,receiver,name,line_no,value.strip())
            if key not in seen:
                seen.add(key)
                rows.append({
                    "access":"WRITE","scope":scope,"receiver":receiver,"method":method,
                    "name":name,"state_id":_state_id(scope,name,receiver),
                    "value":value.strip(),"line":line_no,"source_line":raw_line.strip(),
                })
    rows.sort(key=lambda row:(row["line"],row["state_id"],row["access"]))
    return tuple(rows)


def _state_aliases(text: str, *, start_line: int) -> dict[str,dict]:
    aliases={}
    for offset,raw_line in enumerate(text.splitlines()):
        code=_strip_line_comment_preserve_strings(raw_line)
        line_no=start_line+offset
        for match in _STATE_ALIAS_ASSIGN.finditer(code):
            alias,receiver,method,name=match.groups()
            scope=_state_scope(receiver,method)
            aliases[alias]={
                "alias":alias,
                "scope":scope,
                "receiver":receiver,
                "method":method,
                "name":name,
                "state_id":_state_id(scope,name,receiver),
                "source_line":line_no,
                "source_line_text":raw_line.strip(),
            }
        for match in _SERVER_ALIAS_ASSIGN.finditer(code):
            alias,name=match.groups()
            scope="SERVER_GLOBAL"
            aliases[alias]={
                "alias":alias,
                "scope":scope,
                "receiver":None,
                "method":"GetServerVariable",
                "name":name,
                "state_id":_state_id(scope,name),
                "source_line":line_no,
                "source_line_text":raw_line.strip(),
            }
        for match in _INSTANCE_LIFECYCLE_ALIAS_ASSIGN.finditer(code):
            alias,receiver,method=match.groups()
            name="stage" if method=="getStage" else "progress"
            scope="INSTANCE_LIFECYCLE"
            aliases[alias]={
                "alias":alias,
                "scope":scope,
                "receiver":receiver,
                "method":method,
                "name":name,
                "state_id":_state_id(scope,name,receiver),
                "source_line":line_no,
                "source_line_text":raw_line.strip(),
            }
    return aliases


def _switch_state_transition_rules(
    *,
    text: str,
    start_line: int,
    subject: str,
    trigger: str,
    meta: dict,
) -> tuple[BehaviorRule,...]:
    """Recognize literal switch/case transitions for a directly aliased named state.

    Only writes back to the selector's exact canonical state identity are promoted to transitions.
    """
    raw=text.splitlines()
    structural=_structural_lua_lines(text)
    aliases=_state_aliases(text,start_line=start_line)
    rules=[]
    transition_index=0
    context_parts=[trigger]
    if meta.get("helper"):
        context_parts.append(f"helper:{meta['helper']}")
    if meta.get("callback_type"):
        context_parts.append(
            f"callback:{meta.get('callback_call_line')}:{meta.get('callback_type')}"
        )
    rule_prefix=":".join(str(part) for part in context_parts)

    for i,code in enumerate(structural):
        selector_match=_SWITCH_SELECTOR.search(code)
        if not selector_match:
            continue
        alias=selector_match.group(1)
        state=aliases.get(alias)
        if state is None:
            continue

        brace_depth=code.count("{")-code.count("}")
        opened=brace_depth>0
        j=i+1
        while j<len(raw):
            row=structural[j]
            if not opened:
                brace_depth+=row.count("{")-row.count("}")
                if row.count("{"):
                    opened=True
                j+=1
                continue
            if brace_depth<=0:
                break

            case_match=_SWITCH_CASE.match(row)
            if case_match:
                case_value=case_match.group(1).strip()
                depth=0
                started=False
                case_end=None
                for k in range(j,len(raw)):
                    krow=structural[k]
                    opens=_open_count(krow)
                    closes=_close_count(krow)
                    if opens:
                        started=True
                    depth+=opens-closes
                    if started and depth<=0:
                        case_end=k
                        break
                if case_end is not None:
                    body="\n".join(raw[j:case_end+1])
                    accesses=_named_state_accesses(body,start_line=start_line+j)
                    writes=[
                        row for row in accesses
                        if row["access"]=="WRITE" and row["state_id"]==state["state_id"]
                    ]
                    for write in writes:
                        transition_index+=1
                        common={
                            "scope":state["scope"],
                            "name":state["name"],
                            "receiver":state["receiver"],
                            "selector_alias":alias,
                            "switch_case":case_value,
                            "source_line":write["line"],
                            "source_line_text":write["source_line"],
                        }
                        rules.append(BehaviorRule(
                            f"{rule_prefix}:state-transition:{transition_index}",
                            "state_transition",
                            subject,
                            trigger=trigger,
                            conditions=(BehaviorCondition(
                                state["state_id"],"STATE_EQUALS",case_value,
                                {
                                    **common,
                                    "selector_source_line":state["source_line"],
                                    "selector_source_line_text":state["source_line_text"],
                                },
                            ),),
                            effects=(BehaviorEffect(
                                "WRITE_STATE",state["state_id"],write["value"],common
                            ),),
                            confidence="VERIFIED",
                            implementation_status="PRESENT",
                            metadata={
                                **meta,
                                "source_lines":(start_line+j,start_line+case_end),
                                "state_id":state["state_id"],
                                "state_scope":state["scope"],
                                "state_name":state["name"],
                                "selector_alias":alias,
                                "switch_case":case_value,
                            },
                        ))
                    j=case_end

            brace_depth+=row.count("{")-row.count("}")
            j+=1

    rules.extend(_literal_if_transition_rules(
        text=text,
        start_line=start_line,
        subject=subject,
        trigger=trigger,
        meta=meta,
    ))
    return tuple(rules)


def _literal_if_transition_rules(
    *,
    text: str,
    start_line: int,
    subject: str,
    trigger: str,
    meta: dict,
) -> tuple[BehaviorRule,...]:
    """Recognize literal if-equality transitions for supported canonical lifecycle state."""
    raw=text.splitlines()
    structural=_structural_lua_lines(text)
    aliases=_state_aliases(text,start_line=start_line)
    rules=[]
    transition_index=0
    context_parts=[trigger]
    if meta.get("helper"):
        context_parts.append(f"helper:{meta['helper']}")
    if meta.get("callback_type"):
        context_parts.append(
            f"callback:{meta.get('callback_call_line')}:{meta.get('callback_type')}"
        )
    rule_prefix=":".join(str(part) for part in context_parts)

    for i,raw_line in enumerate(raw):
        code=_strip_line_comment_preserve_strings(raw_line)
        match=_ALIAS_IF_LITERAL_EQUALS.match(code)
        state=None
        selector_alias=None
        selector_expression=None
        case_value=None
        if match:
            selector_alias,case_value=match.groups()
            state=aliases.get(selector_alias)
            selector_expression=selector_alias
        else:
            server_match=_SERVER_DIRECT_IF_LITERAL_EQUALS.match(code)
            if server_match:
                name,case_value=server_match.groups()
                state={
                    "scope":"SERVER_GLOBAL",
                    "receiver":None,
                    "method":"GetServerVariable",
                    "name":name,
                    "state_id":_state_id("SERVER_GLOBAL",name),
                    "source_line":start_line+i,
                    "source_line_text":raw_line.strip(),
                }
                selector_expression=f"GetServerVariable({name!r})"
            else:
                instance_match=_INSTANCE_DIRECT_IF_LITERAL_EQUALS.match(code)
                if instance_match:
                    receiver,method,case_value=instance_match.groups()
                    name="stage" if method=="getStage" else "progress"
                    state={
                        "scope":"INSTANCE_LIFECYCLE",
                        "receiver":receiver,
                        "method":method,
                        "name":name,
                        "state_id":_state_id("INSTANCE_LIFECYCLE",name,receiver),
                        "source_line":start_line+i,
                        "source_line_text":raw_line.strip(),
                    }
                    selector_expression=f"{receiver}:{method}()"
        if state is None or state.get("scope") not in {"SERVER_GLOBAL","INSTANCE_LIFECYCLE"}:
            continue

        depth=0
        started=False
        block_end=None
        for j in range(i,len(raw)):
            row=structural[j]
            opens=_open_count(row)
            closes=_close_count(row)
            if opens:
                started=True
            depth+=opens-closes
            if started and depth<=0:
                block_end=j
                break
        if block_end is None:
            continue

        body="\n".join(raw[i:block_end+1])
        accesses=_named_state_accesses(body,start_line=start_line+i)
        writes=[
            row for row in accesses
            if row["access"]=="WRITE" and row["state_id"]==state["state_id"]
        ]
        for write in writes:
            transition_index+=1
            common={
                "scope":state["scope"],
                "name":state["name"],
                "receiver":state["receiver"],
                "selector_alias":selector_alias,
                "selector_expression":selector_expression,
                "if_literal":case_value,
                "source_line":write["line"],
                "source_line_text":write["source_line"],
            }
            rules.append(BehaviorRule(
                f"{rule_prefix}:literal-if-transition:{transition_index}",
                "state_transition",
                subject,
                trigger=trigger,
                conditions=(BehaviorCondition(
                    state["state_id"],"STATE_EQUALS",case_value,
                    {
                        **common,
                        "selector_source_line":state["source_line"],
                        "selector_source_line_text":state["source_line_text"],
                    },
                ),),
                effects=(BehaviorEffect(
                    "WRITE_STATE",state["state_id"],write["value"],common
                ),),
                confidence="VERIFIED",
                implementation_status="PRESENT",
                metadata={
                    **meta,
                    "source_lines":(start_line+i,start_line+block_end),
                    "state_id":state["state_id"],
                    "state_scope":state["scope"],
                    "state_name":state["name"],
                    "selector_alias":selector_alias,
                    "selector_expression":selector_expression,
                    "if_literal":case_value,
                    "transition_form":(
                        "SERVER_GLOBAL_LITERAL_IF"
                        if state["scope"]=="SERVER_GLOBAL"
                        else "INSTANCE_LIFECYCLE_LITERAL_IF"
                    ),
                },
            ))
    return tuple(rules)


def _context_condition_rule(
    *,
    rule_id: str,
    subject: str,
    trigger: str,
    text: str,
    start_line: int,
    meta: dict,
) -> BehaviorRule | None:
    """Promote only literal environmental/actor-context predicates we can prove statically."""
    aliases={}
    rows=[]
    for offset,raw_line in enumerate(text.splitlines()):
        code=_strip_line_comment_preserve_strings(raw_line)
        line_no=start_line+offset
        alias=_TIME_ALIAS_ASSIGN.search(code)
        if alias:
            aliases[alias.group(1)]=(alias.group(2),line_no,raw_line.strip())

        for match in _WEATHER_ELEMENT_COMPARE.finditer(code):
            source,operator,element=match.groups()
            rows.append(BehaviorCondition(
                "environment:weather",
                "WEATHER_ELEMENT_EQUALS" if operator=="==" else "WEATHER_ELEMENT_NOT_EQUALS",
                element,
                {
                    "weather_source":source.strip(),
                    "source_line":line_no,
                    "source_line_text":raw_line.strip(),
                },
            ))

        for match in _POSITION_COMPARE.finditer(code):
            receiver,axis,operator,value=match.groups()
            rows.append(BehaviorCondition(
                f"actor:{receiver}",
                "POSITION_COMPARE",
                {
                    "axis":axis,
                    "operator":operator,
                    "value":float(value) if "." in value else int(value),
                },
                {"source_line":line_no,"source_line_text":raw_line.strip()},
            ))

        for match in _DISTANCE_COMPARE.finditer(code):
            receiver,target,operator,value=match.groups()
            rows.append(BehaviorCondition(
                f"actor:{receiver}",
                "DISTANCE_COMPARE",
                {
                    "target":target.strip(),
                    "operator":operator,
                    "value":float(value) if "." in value else int(value),
                },
                {"source_line":line_no,"source_line_text":raw_line.strip()},
            ))

        for match in _GROUP_ACCESS.finditer(code):
            receiver,method=match.groups()
            group="ALLIANCE" if method=="getAlliance" else "PARTY"
            rows.append(BehaviorCondition(
                f"actor:{receiver}",
                f"ACCESSES_{group}",
                True,
                {"source_line":line_no,"source_line_text":raw_line.strip()},
            ))

        range_match=_TIME_RANGE.search(code)
        if range_match and range_match.group(1) in aliases:
            alias_name,start,end=range_match.groups()
            api,alias_line,alias_source=aliases[alias_name]
            rows.append(BehaviorCondition(
                "environment:vanadiel_time",
                f"{api.upper()}_RANGE",
                {"min":int(start),"max":int(end)},
                {
                    "alias":alias_name,
                    "alias_source_line":alias_line,
                    "alias_source_line_text":alias_source,
                    "source_line":line_no,
                    "source_line_text":raw_line.strip(),
                },
            ))

    if not rows:
        return None
    return BehaviorRule(
        rule_id,
        "context_conditions",
        subject,
        trigger=trigger,
        conditions=tuple(rows),
        effects=(),
        confidence="VERIFIED",
        implementation_status="PRESENT",
        metadata={**meta,"context_condition_count":len(rows)},
    )


def _literal_csid_branches(text: str, *, start_line: int) -> tuple[dict,...]:
    """Return bounded top-level literal CSID branches with branch-local state accesses."""
    raw=text.splitlines()
    structural=_structural_lua_lines(text)
    rows=[]
    depth=0
    active=None

    def finish(end_index: int):
        nonlocal active
        if active is None:
            return
        body_start=active["start_index"]
        body_end=max(body_start,end_index)
        body="\n".join(raw[body_start:body_end+1])
        rows.append({
            "csid":active["csid"],
            "start_line":start_line+body_start,
            "end_line":start_line+body_end,
            "source_line":active["source_line"],
            "body":body,
            "state_accesses":_named_state_accesses(body,start_line=start_line+body_start),
        })
        active=None

    for i,raw_line in enumerate(raw):
        code=_strip_line_comment_preserve_strings(raw_line)
        stripped=code.strip()
        if active is not None and depth==active["branch_depth"]:
            if re.match(r"^(?:elseif\b|else\b|end\b)",stripped):
                finish(i-1)

        branch_match=re.match(r"^\s*(?:if|elseif)\s+csid\s*==\s*(\d+)\s+then\b",code)
        if branch_match:
            active={
                "csid":int(branch_match.group(1)),
                "start_index":i,
                "source_line":raw_line.strip(),
                "branch_depth":depth + (1 if stripped.startswith("if ") else 0),
            }

        depth+=_open_count(structural[i])-_close_count(structural[i])

    if active is not None:
        finish(len(raw)-1)
    return tuple(rows)


def _event_branch_nonstate_effects(
    text: str,
    *,
    start_line: int,
    subject: str,
    trigger: str,
    meta: dict,
) -> tuple[BehaviorEffect,...]:
    """Extract conservative non-state effects from one literal CSID branch."""
    effects=[]
    effects.extend(
        BehaviorEffect("GRANT_KEY_ITEM","player",symbol)
        for symbol in dict.fromkeys(_KEYITEM_GIVE.findall(text))
    )
    effects.extend(
        BehaviorEffect("REMOVE_KEY_ITEM","player",symbol)
        for symbol in dict.fromkeys(_KEYITEM_DEL.findall(text))
    )
    effects.extend(
        BehaviorEffect("GRANT_ITEM","player",value.strip())
        for value in dict.fromkeys(_ITEM_GIVE.findall(text))
    )
    effects.extend(
        BehaviorEffect("ADD_GIL","player",value.strip())
        for value in dict.fromkeys(_ADD_GIL.findall(text))
    )
    effects.extend(
        BehaviorEffect("REMOVE_GIL","player",value.strip())
        for value in dict.fromkeys(_DEL_GIL.findall(text))
    )
    if _UPDATE_EVENT.search(text):
        effects.append(BehaviorEffect("UPDATE_EVENT","player"))
    for duration in _OPEN_DOOR.findall(text):
        effects.append(BehaviorEffect("OPEN_DOOR","world_entity",duration.strip() or None))
    for value in _SET_ANIMATION.findall(text):
        effects.append(BehaviorEffect("SET_ANIMATION","world_entity",value.strip()))
    for value in _SET_STATUS.findall(text):
        effects.append(BehaviorEffect("SET_STATUS","world_entity",value.strip()))
    for value in _SET_UNTARGETABLE.findall(text):
        effects.append(BehaviorEffect("SET_UNTARGETABLE","world_entity",value.strip()))
    if _SET_POS.search(text):
        effects.append(BehaviorEffect("SET_POSITION","world_entity"))

    entity_rule=_direct_entity_reference_rule(
        rule_id="event-branch-entity-refs",
        subject=subject,
        trigger=trigger,
        text=text,
        start_line=start_line,
        meta=meta,
    )
    if entity_rule is not None:
        effects.extend(entity_rule.effects)
    return tuple(effects)


def _literal_event_outcome_branches(text: str, *, start_line: int) -> tuple[dict,...]:
    """Return bounded nested literal option/result branches inside an event branch."""
    raw=text.splitlines()
    structural=_structural_lua_lines(text)
    rows=[]
    depth=0
    active=None

    def finish(end_index: int):
        nonlocal active
        if active is None:
            return
        body_start=active["start_index"]
        body_end=max(body_start,end_index)
        body="\n".join(raw[body_start:body_end+1])
        rows.append({
            "selector":active["selector"],
            "literal":active["literal"],
            "start_index":body_start,
            "end_index":body_end,
            "start_line":start_line+body_start,
            "end_line":start_line+body_end,
            "source_line":active["source_line"],
            "body":body,
            "state_accesses":_named_state_accesses(body,start_line=start_line+body_start),
        })
        active=None

    for i,raw_line in enumerate(raw):
        code=_strip_line_comment_preserve_strings(raw_line)
        stripped=code.strip()
        if active is not None and depth==active["branch_depth"]:
            if re.match(r"^(?:elseif\b|else\b|end\b)",stripped):
                finish(i-1)

        match=re.match(
            r"^\s*(?:if|elseif)\s+(option|result)\s*==\s*"
            r"(-?\d+|true|false|['\"][^'\"]+['\"])\s+then\b",
            code,
        )
        if match:
            selector,literal=match.groups()
            active={
                "selector":selector,
                "literal":literal,
                "start_index":i,
                "source_line":raw_line.strip(),
                "branch_depth":depth + (1 if stripped.startswith("if ") else 0),
            }

        depth+=_open_count(structural[i])-_close_count(structural[i])

    if active is not None:
        finish(len(raw)-1)
    return tuple(rows)


def _without_event_outcome_branches(text: str, branches: tuple[dict,...]) -> str:
    """Blank nested outcome branch spans so parent CSID effects are not double-attributed."""
    raw=text.splitlines()
    for branch in branches:
        for index in range(branch["start_index"],branch["end_index"]+1):
            if 0 <= index < len(raw):
                raw[index]=""
    return "\n".join(raw)


def _literal_csid_guards(text: str, *, start_line: int) -> tuple[dict,...]:
    rows=[]
    for offset,raw_line in enumerate(text.splitlines()):
        code=_strip_line_comment_preserve_strings(raw_line)
        for match in _CSID_LITERAL_COMPARE.finditer(code):
            rows.append({
                "csid":int(match.group(1)),
                "line":start_line+offset,
                "source_line":raw_line.strip(),
            })
    return tuple(rows)


def _entity_symbol_target(kind: str, symbol: str, sign: str | None, offset: str | None) -> str:
    base=f"entity-symbol:{kind}:{symbol}"
    if sign and offset:
        value=int(offset) * (1 if sign=="+" else -1)
        return f"{base}:offset:{value:+d}"
    return base


def _literal_entity_aliases(text: str) -> dict[str,dict]:
    aliases={}
    for raw_line in text.splitlines():
        code=_strip_line_comment_preserve_strings(raw_line)
        match=_ENTITY_ALIAS_ASSIGN.search(code)
        if not match:
            continue
        alias,kind,symbol,sign,offset=match.groups()
        base_offset=0
        if sign and offset:
            base_offset=int(offset) * (1 if sign=="+" else -1)
        aliases[alias]={
            "kind":kind,
            "symbol":symbol,
            "offset":base_offset,
            "source_line_text":raw_line.strip(),
        }
    return aliases


def _runtime_entity_id_aliases(text: str, *, start_line: int) -> dict[str,dict]:
    """Track direct local aliases of runtime entity IDs without inventing symbol identity."""
    aliases={}
    for offset_idx,raw_line in enumerate(text.splitlines()):
        code=_strip_line_comment_preserve_strings(raw_line)
        match=_RUNTIME_ENTITY_ID_ALIAS_ASSIGN.search(code)
        if not match:
            continue
        alias,receiver=match.groups()
        aliases[alias]={
            "receiver":receiver,
            "source_line":start_line+offset_idx,
            "source_line_text":raw_line.strip(),
        }
    return aliases


def _runtime_entity_target(receiver: str, offset: int) -> str:
    base=f"entity-runtime-id:{receiver}"
    return f"{base}:offset:{offset:+d}" if offset else base


def _symbolic_range_loop_entity_effects(
    text: str,
    *,
    start_line: int,
    max_expansion: int=64,
) -> tuple[BehaviorEffect,...]:
    """Expand loops whose bounds are the same direct entity symbol plus literal offsets."""
    raw=text.splitlines()
    structural=_structural_lua_lines(text)
    effects=[]
    for i,code in enumerate(structural):
        match=_SYMBOLIC_FOR.match(code)
        if not match:
            continue
        (
            var,kind1,symbol1,sign1,off1,
            kind2,symbol2,sign2,off2,step_raw
        )=match.groups()
        if kind1!=kind2 or symbol1!=symbol2:
            continue
        start_off=(int(off1)*(1 if sign1=="+" else -1)) if sign1 and off1 else 0
        end_off=(int(off2)*(1 if sign2=="+" else -1)) if sign2 and off2 else 0
        step=int(step_raw) if step_raw is not None else (1 if end_off>=start_off else -1)
        if step==0 or (end_off-start_off)*step < 0:
            continue
        offsets=list(range(start_off,end_off+(1 if step>0 else -1),step))
        if not offsets or len(offsets)>max_expansion:
            continue

        depth=0
        loop_end=None
        for j in range(i,len(raw)):
            depth+=_open_count(structural[j])-_close_count(structural[j])
            if j>i and depth<=0:
                loop_end=j
                break
        if loop_end is None:
            continue

        call_re=re.compile(
            rf"\b(GetNPCByID|GetMobByID|SpawnMob|DespawnMob)\(\s*{re.escape(var)}"
            rf"(?=\s*(?:,|\)))"
        )
        for body_index in range(i+1,loop_end):
            body_line=raw[body_index]
            body_code=_strip_line_comment_preserve_strings(body_line)
            source_line=start_line+body_index
            for call in call_re.findall(body_code):
                for offset in offsets:
                    target=_entity_symbol_target(
                        kind1,symbol1,
                        "+" if offset>0 else "-" if offset<0 else None,
                        str(abs(offset)) if offset else None,
                    )
                    effect_name={
                        "GetNPCByID":"REFERENCES_ENTITY",
                        "GetMobByID":"REFERENCES_ENTITY",
                        "SpawnMob":"SPAWN_ENTITY",
                        "DespawnMob":"DESPAWN_ENTITY",
                    }[call]
                    effects.append(BehaviorEffect(
                        effect_name,target,f"{var}[{offset:+d}]",
                        {
                            "call":call,"entity_kind":kind1,"symbol":symbol1,
                            "offset":offset,"resolution":"SYMBOLIC_RANGE_LOOP",
                            "loop_variable":var,"loop_start_offset":start_off,
                            "loop_end_offset":end_off,"loop_step":step,
                            "loop_source_line":start_line+i,
                            "source_line":source_line,"source_line_text":body_line.strip(),
                        },
                    ))
    return tuple(effects)


def _bounded_numeric_loop_entity_effects(
    text: str,
    *,
    start_line: int,
    aliases: dict[str,dict],
    max_expansion: int=64,
) -> tuple[BehaviorEffect,...]:
    """Expand literal numeric for-loops only when their full iteration set is small and provable."""
    raw=text.splitlines()
    structural=_structural_lua_lines(text)
    effects=[]
    for i,code in enumerate(structural):
        match=_NUMERIC_FOR.match(code)
        if not match:
            continue
        var,start_raw,end_raw,step_raw=match.groups()
        start=int(start_raw)
        end=int(end_raw)
        step=int(step_raw) if step_raw is not None else (1 if end>=start else -1)
        if step==0:
            continue
        if (end-start)*step < 0:
            continue
        values=list(range(start,end+(1 if step>0 else -1),step))
        if not values or len(values)>max_expansion:
            continue

        depth=0
        loop_end=None
        for j in range(i,len(raw)):
            depth+=_open_count(structural[j])-_close_count(structural[j])
            if j>i and depth<=0:
                loop_end=j
                break
        if loop_end is None:
            continue

        direct_re=re.compile(
            rf"\b(GetNPCByID|GetMobByID|SpawnMob|DespawnMob)\(\s*"
            rf"ID\.(npc|mob)\.([A-Z0-9_]+)\s*([+-])\s*{re.escape(var)}"
            rf"(?=\s*(?:,|\)))"
        )
        alias_re=re.compile(
            rf"\b(GetNPCByID|GetMobByID|SpawnMob|DespawnMob)\(\s*"
            rf"([A-Za-z_][A-Za-z0-9_]*)\s*([+-])\s*{re.escape(var)}"
            rf"(?=\s*(?:,|\)))"
        )
        for body_index in range(i+1,loop_end):
            body_line=raw[body_index]
            body_code=_strip_line_comment_preserve_strings(body_line)
            source_line=start_line+body_index
            for call,kind,symbol,sign in direct_re.findall(body_code):
                for value in values:
                    total=value if sign=="+" else -value
                    target=_entity_symbol_target(
                        kind,symbol,
                        "+" if total>0 else "-" if total<0 else None,
                        str(abs(total)) if total else None,
                    )
                    effect_name={
                        "GetNPCByID":"REFERENCES_ENTITY",
                        "GetMobByID":"REFERENCES_ENTITY",
                        "SpawnMob":"SPAWN_ENTITY",
                        "DespawnMob":"DESPAWN_ENTITY",
                    }[call]
                    effects.append(BehaviorEffect(
                        effect_name,target,f"ID.{kind}.{symbol}{total:+d}",
                        {
                            "call":call,"entity_kind":kind,"symbol":symbol,"offset":total,
                            "resolution":"BOUNDED_NUMERIC_LOOP",
                            "loop_variable":var,"loop_value":value,
                            "loop_start":start,"loop_end":end,"loop_step":step,
                            "loop_source_line":start_line+i,
                            "source_line":source_line,"source_line_text":body_line.strip(),
                        },
                    ))
            for call,alias,sign in alias_re.findall(body_code):
                if alias not in aliases:
                    continue
                base=aliases[alias]
                for value in values:
                    delta=value if sign=="+" else -value
                    total=base["offset"]+delta
                    target=_entity_symbol_target(
                        base["kind"],base["symbol"],
                        "+" if total>0 else "-" if total<0 else None,
                        str(abs(total)) if total else None,
                    )
                    effect_name={
                        "GetNPCByID":"REFERENCES_ENTITY",
                        "GetMobByID":"REFERENCES_ENTITY",
                        "SpawnMob":"SPAWN_ENTITY",
                        "DespawnMob":"DESPAWN_ENTITY",
                    }[call]
                    effects.append(BehaviorEffect(
                        effect_name,target,f"{alias}{delta:+d}",
                        {
                            "call":call,"entity_kind":base["kind"],"symbol":base["symbol"],
                            "offset":total,"resolution":"BOUNDED_NUMERIC_LOOP",
                            "alias":alias,"alias_base_offset":base["offset"],
                            "loop_variable":var,"loop_value":value,
                            "loop_start":start,"loop_end":end,"loop_step":step,
                            "loop_source_line":start_line+i,
                            "source_line":source_line,"source_line_text":body_line.strip(),
                        },
                    ))
    return tuple(effects)


def _direct_entity_reference_rule(
    *,
    rule_id: str,
    subject: str,
    trigger: str,
    text: str,
    start_line: int,
    meta: dict,
) -> BehaviorRule | None:
    """Resolve only direct ID.npc/ID.mob symbols with optional literal integer offsets."""
    effects=[]
    aliases=_literal_entity_aliases(text)
    runtime_aliases=_runtime_entity_id_aliases(text,start_line=start_line)
    effects.extend(_symbolic_range_loop_entity_effects(
        text,start_line=start_line
    ))
    effects.extend(_bounded_numeric_loop_entity_effects(
        text,start_line=start_line,aliases=aliases
    ))
    for offset_idx,raw_line in enumerate(text.splitlines()):
        code=_strip_line_comment_preserve_strings(raw_line)
        line_no=start_line+offset_idx
        for match in _DIRECT_ENTITY_EXPR.finditer(code):
            call,expression,kind,symbol,sign,offset=match.groups()
            target=_entity_symbol_target(kind,symbol,sign,offset)
            effect_name={
                "GetNPCByID":"REFERENCES_ENTITY",
                "GetMobByID":"REFERENCES_ENTITY",
                "SpawnMob":"SPAWN_ENTITY",
                "DespawnMob":"DESPAWN_ENTITY",
            }[call]
            effects.append(BehaviorEffect(
                effect_name,
                target,
                expression.replace(" ",""),
                {
                    "call":call,
                    "entity_kind":kind,
                    "symbol":symbol,
                    "offset":(
                        int(offset) * (1 if sign=="+" else -1)
                        if sign and offset else 0
                    ),
                    "resolution":"DIRECT_SYMBOL",
                    "source_line":line_no,
                    "source_line_text":raw_line.strip(),
                },
            ))
        for match in _ENTITY_ALIAS_CALL.finditer(code):
            call,alias,sign,offset=match.groups()
            call_offset=0
            if sign and offset:
                call_offset=int(offset) * (1 if sign=="+" else -1)
            effect_name={
                "GetNPCByID":"REFERENCES_ENTITY",
                "GetMobByID":"REFERENCES_ENTITY",
                "SpawnMob":"SPAWN_ENTITY",
                "DespawnMob":"DESPAWN_ENTITY",
            }[call]
            if alias in aliases:
                base=aliases[alias]
                total=base["offset"]+call_offset
                target=_entity_symbol_target(
                    base["kind"],
                    base["symbol"],
                    "+" if total>=0 and total!=0 else "-" if total<0 else None,
                    str(abs(total)) if total!=0 else None,
                )
                effects.append(BehaviorEffect(
                    effect_name,
                    target,
                    f"{alias}{'' if call_offset==0 else f'{call_offset:+d}'}",
                    {
                        "call":call,
                        "entity_kind":base["kind"],
                        "symbol":base["symbol"],
                        "offset":total,
                        "resolution":"LITERAL_ALIAS",
                        "alias":alias,
                        "alias_base_offset":base["offset"],
                        "call_offset":call_offset,
                        "alias_source_line_text":base["source_line_text"],
                        "source_line":line_no,
                        "source_line_text":raw_line.strip(),
                    },
                ))
                continue
            if alias not in runtime_aliases:
                continue
            base=runtime_aliases[alias]
            target=_runtime_entity_target(base["receiver"],call_offset)
            effects.append(BehaviorEffect(
                effect_name,
                target,
                f"{alias}{'' if call_offset==0 else f'{call_offset:+d}'}",
                {
                    "call":call,
                    "offset":call_offset,
                    "resolution":"RUNTIME_RELATIVE_ID",
                    "alias":alias,
                    "runtime_receiver":base["receiver"],
                    "alias_source_line":base["source_line"],
                    "alias_source_line_text":base["source_line_text"],
                    "source_line":line_no,
                    "source_line_text":raw_line.strip(),
                },
            ))
    if not effects:
        return None
    return BehaviorRule(
        rule_id,
        "entity_references",
        subject,
        trigger=trigger,
        effects=tuple(effects),
        confidence="VERIFIED",
        implementation_status="PRESENT",
        metadata={**meta,"entity_reference_count":len(effects)},
    )


def _state_flow_rule(
    *,
    rule_id: str,
    subject: str,
    trigger: str,
    accesses: tuple[dict,...],
    meta: dict,
) -> BehaviorRule | None:
    if not accesses:
        return None
    conditions=[]
    effects=[]
    for row in accesses:
        common={
            "scope":row["scope"],
            "name":row["name"],
            "receiver":row["receiver"],
            "method":row["method"],
            "source_line":row["line"],
            "source_line_text":row["source_line"],
        }
        if row["access"]=="READ":
            conditions.append(BehaviorCondition(
                row["state_id"],"READS_STATE",None,common
            ))
        else:
            effects.append(BehaviorEffect(
                "WRITE_STATE",row["state_id"],row["value"],common
            ))
    return BehaviorRule(
        rule_id,
        "state_flow",
        subject,
        trigger=trigger,
        conditions=tuple(conditions),
        effects=tuple(effects),
        confidence="VERIFIED",
        implementation_status="PRESENT",
        metadata={**meta,"state_access_count":len(accesses)},
    )


def _api_call_rule(
    *,
    rule_id: str,
    subject: str,
    trigger: str,
    calls: tuple[dict,...],
    meta: dict,
) -> BehaviorRule | None:
    if not calls:
        return None
    return BehaviorRule(
        rule_id,
        "api_calls",
        subject,
        trigger=trigger,
        effects=tuple(
            BehaviorEffect(
                "API_CALL",
                call.get("receiver") or "global",
                call["function"],
                {
                    "style":call["style"],
                    "qualified_name":call["qualified_name"],
                    "source_line_text":call["source_line"],
                    "source_line":call["line"],
                },
            )
            for call in calls
        ),
        confidence="VERIFIED",
        implementation_status="PRESENT",
        metadata={**meta,"api_call_count":len(calls)},
    )


def _dedupe_rules(rules: Iterable[BehaviorRule]) -> tuple[BehaviorRule,...]:
    out=[]
    seen=set()
    for rule in rules:
        key=(rule.kind,rule.subject,rule.target,rule.trigger,repr(rule.conditions),repr(rule.effects))
        if key in seen:
            continue
        seen.add(key)
        out.append(rule)
    return tuple(out)


def extract_lsb_scripted_behavior(
    lua: str,
    *,
    feature_id: str,
    subject: str,
    zone: str | None,
    source_path: str,
) -> ScriptedBehaviorMap:
    """Extract conservative scripted behavior from one LSB entity Lua script.

    The same representation is used for mobs, NPCs, doors/objects, escorts, and other scripted
    actors; domain-specific mission/quest interpretation remains a separate layer.
    """
    blocks=extract_hook_blocks(lua)
    helpers=extract_helper_blocks(lua)
    rules=[]
    modeled_hooks=set()
    reached_helpers=set()

    for block in blocks:
        text=block.body
        meta=_source_meta(block,source_path)
        hook=block.hook

        api_rule=_api_call_rule(
            rule_id=f"{hook}:api-calls",
            subject=subject,
            trigger=hook.upper(),
            calls=_api_calls(text,start_line=block.start_line),
            meta=meta,
        )
        if api_rule is not None:
            rules.append(api_rule)
            modeled_hooks.add(hook)
        state_rule=_state_flow_rule(
            rule_id=f"{hook}:state-flow",
            subject=subject,
            trigger=hook.upper(),
            accesses=_named_state_accesses(text,start_line=block.start_line),
            meta=meta,
        )
        if state_rule is not None:
            rules.append(state_rule)
            modeled_hooks.add(hook)
        context_rule=_context_condition_rule(
            rule_id=f"{hook}:context",
            subject=subject,
            trigger=hook.upper(),
            text=text,
            start_line=block.start_line,
            meta=meta,
        )
        if context_rule is not None:
            rules.append(context_rule)
            modeled_hooks.add(hook)
        entity_ref_rule=_direct_entity_reference_rule(
            rule_id=f"{hook}:entity-refs",
            subject=subject,
            trigger=hook.upper(),
            text=text,
            start_line=block.start_line,
            meta=meta,
        )
        if entity_ref_rule is not None:
            rules.append(entity_ref_rule)
            modeled_hooks.add(hook)
        transition_rules=_switch_state_transition_rules(
            text=text,
            start_line=block.start_line,
            subject=subject,
            trigger=hook.upper(),
            meta=meta,
        )
        if transition_rules:
            rules.extend(transition_rules)
            modeled_hooks.add(hook)

        callback_rules=_callback_rules(
            text=text,
            start_line=block.start_line,
            subject=subject,
            parent_hook=hook,
            source_path=source_path,
        )
        if callback_rules:
            rules.extend(callback_rules)
            modeled_hooks.add(hook)

        # Hook classes are useful behavior facts even when the internal dynamic logic is not yet
        # structurally decoded.
        if hook=="onPlayerAbilityUse":
            rules.append(BehaviorRule(
                f"{hook}:response","player_action_response",subject,
                trigger="PLAYER_ACTION",
                conditions=(BehaviorCondition("player","ACTION_OBSERVED",True),),
                effects=(BehaviorEffect("RESPOND_TO_ACTION",subject),),
                confidence="VERIFIED",implementation_status="PRESENT",metadata=meta,
            ))
            modeled_hooks.add(hook)
        elif hook=="onMagicHit":
            rules.append(BehaviorRule(
                f"{hook}:response","magic_response",subject,
                trigger="MAGIC_HIT",
                conditions=(BehaviorCondition("player","MAGIC_INPUT",True),),
                effects=(BehaviorEffect("ADJUST_COMBAT_STATE",subject),),
                confidence="VERIFIED",implementation_status="PRESENT",metadata=meta,
            ))
            modeled_hooks.add(hook)
        elif hook=="onSpellPrecast" and _SPELL_OVERRIDE.search(text):
            rules.append(BehaviorRule(
                f"{hook}:override","spell_override",subject,
                trigger="SPELL_PRECAST",
                effects=(BehaviorEffect("OVERRIDE_SPELL",subject),),
                confidence="VERIFIED",implementation_status="PRESENT",metadata=meta,
            ))
            modeled_hooks.add(hook)

        for index,match in enumerate(_HPP.finditer(text),1):
            operator,threshold=match.groups()
            rules.append(BehaviorRule(
                f"{hook}:hpp:{index}","hp_threshold",subject,
                trigger=hook.upper(),
                conditions=(BehaviorCondition(subject,{
                    "<=":"HPP_AT_OR_BELOW",
                    "<":"HPP_BELOW",
                    ">=":"HPP_AT_OR_ABOVE",
                    ">":"HPP_ABOVE",
                }[operator],int(threshold)),),
                effects=(BehaviorEffect("CONDITIONAL_BEHAVIOR_PHASE",subject),),
                confidence="VERIFIED",implementation_status="PRESENT",
                metadata={**meta,"source_expression":match.group(0)},
            ))
            modeled_hooks.add(hook)

        percent=_RANDOM_PERCENT.search(text)
        timer=_TIMER_MS.search(text)
        spawn_symbols=tuple(dict.fromkeys(_SPAWN_SYMBOL.findall(text)))
        if hook=="onMobDeath" and spawn_symbols:
            for index,symbol in enumerate(spawn_symbols,1):
                conditions=[]
                if percent:
                    conditions.append(BehaviorCondition(
                        subject,"PROBABILITY_PERCENT",int(percent.group(1))
                    ))
                delay_ms=int(timer.group(1)) if timer else None
                rules.append(BehaviorRule(
                    f"{hook}:spawn:{index}",
                    "spawn_from_death",
                    subject,
                    trigger="ENTITY_DEATH",
                    target=_symbol(symbol),
                    conditions=tuple(conditions),
                    effects=(BehaviorEffect(
                        "SPAWN_ENTITY",_symbol(symbol),
                        None if delay_ms is None else delay_ms/1000.0,
                        {"delay_ms":delay_ms},
                    ),),
                    confidence="VERIFIED",implementation_status="PRESENT",
                    metadata={**meta,"entity_symbol":symbol},
                ))
                modeled_hooks.add(hook)

            if _ENMITY_TRANSFER.search(text):
                for index,symbol in enumerate(spawn_symbols,1):
                    rules.append(BehaviorRule(
                        f"{hook}:runtime-target:{index}",
                        "inherit_runtime_target",
                        subject,
                        trigger="SPAWN",
                        target=_symbol(symbol),
                        effects=(BehaviorEffect(
                            "TRANSFER_RUNTIME_STATE",_symbol(symbol),"enmity_or_claim"
                        ),),
                        confidence="INFERRED",implementation_status="PRESENT",
                        metadata={
                            **meta,
                            "entity_symbol":symbol,
                            "inference_basis":"spawned entity receives updateEnmity/updateClaim in the same hook",
                        },
                    ))

        referenced=tuple(dict.fromkeys(_GETMOB_SYMBOL.findall(text)))
        local_reads=tuple(dict.fromkeys(_LOCAL_READ.findall(text)))
        if referenced and local_reads:
            for index,symbol in enumerate(referenced,1):
                rules.append(BehaviorRule(
                    f"{hook}:cross-state:{index}",
                    "cross_entity_state",
                    _symbol(symbol),
                    trigger=hook.upper(),
                    target=subject,
                    conditions=tuple(
                        BehaviorCondition(_symbol(symbol),"READS_LOCAL_STATE",name)
                        for name in local_reads
                    ),
                    effects=(BehaviorEffect("TRANSFER_RUNTIME_STATE",subject,list(local_reads)),),
                    confidence="VERIFIED",implementation_status="PRESENT",
                    metadata={**meta,"entity_symbol":symbol,"local_vars":list(local_reads)},
                ))
                modeled_hooks.add(hook)

        random_ranges=[
            (int(a),int(b)) for a,b in _RANDOM_RANGE.findall(text)
            if not (int(a)==1 and int(b)==100)
        ]
        if random_ranges and ("GetSystemTime" in text or "timer(" in text):
            # Preserve every distinct source range; consumers can decide whether it is an action
            # cadence, state timer, or another random interval.
            for index,bounds in enumerate(dict.fromkeys(random_ranges),1):
                rules.append(BehaviorRule(
                    f"{hook}:random-timer:{index}",
                    "timed_random_action",
                    subject,
                    trigger="TIMER",
                    conditions=(BehaviorCondition(
                        subject,"RANDOM_INTERVAL",bounds
                    ),),
                    effects=(BehaviorEffect("TIMED_BEHAVIOR",subject),),
                    confidence="INFERRED",implementation_status="PRESENT",
                    metadata={**meta,"range":bounds},
                ))
                modeled_hooks.add(hook)

        drop=_DROP_ID.search(text)
        if drop:
            rules.append(BehaviorRule(
                f"{hook}:loot","loot_override",subject,
                trigger=hook.upper(),
                effects=(BehaviorEffect("OVERRIDE_LOOT",subject,int(drop.group(1))),),
                confidence="VERIFIED",implementation_status="PRESENT",
                metadata={**meta,"drop_id":int(drop.group(1))},
            ))
            modeled_hooks.add(hook)

        modifiers=tuple(dict.fromkeys(_MOD_CALL.findall(text)))
        if modifiers:
            rules.append(BehaviorRule(
                f"{hook}:modifiers","combat_modifier",subject,
                trigger=hook.upper(),
                effects=tuple(
                    BehaviorEffect("MODIFY_COMBAT_STAT",subject,modifier)
                    for modifier in modifiers
                ),
                confidence="VERIFIED",implementation_status="PRESENT",
                metadata={**meta,"modifier_symbols":list(modifiers)},
            ))
            modeled_hooks.add(hook)

        if hook in {"onMobDeath","onMobDespawn"} and _DESPAWN.search(text):
            rules.append(BehaviorRule(
                f"{hook}:cleanup","cleanup",subject,
                trigger=hook.upper(),
                effects=(BehaviorEffect("CLEANUP_RELATED_ENTITIES",subject),),
                confidence="VERIFIED",implementation_status="PRESENT",metadata=meta,
            ))
            modeled_hooks.add(hook)

        # Generic NPC/object/player/world-state effects. These are intentionally semantic
        # primitives rather than quest/mission-specific conclusions.
        keyitems=tuple(dict.fromkeys(_KEYITEM_GIVE.findall(text)))
        if keyitems:
            rules.append(BehaviorRule(
                f"{hook}:grant-key-items","player_progression",subject,
                trigger=hook.upper(),
                effects=tuple(
                    BehaviorEffect("GRANT_KEY_ITEM","player",symbol)
                    for symbol in keyitems
                ),
                confidence="VERIFIED",implementation_status="PRESENT",metadata=meta,
            ))
            modeled_hooks.add(hook)

        removed_keyitems=tuple(dict.fromkeys(_KEYITEM_DEL.findall(text)))
        if removed_keyitems:
            rules.append(BehaviorRule(
                f"{hook}:remove-key-items","player_progression",subject,
                trigger=hook.upper(),
                effects=tuple(
                    BehaviorEffect("REMOVE_KEY_ITEM","player",symbol)
                    for symbol in removed_keyitems
                ),
                confidence="VERIFIED",implementation_status="PRESENT",metadata=meta,
            ))
            modeled_hooks.add(hook)

        char_reads=tuple(dict.fromkeys(_CHAR_READ.findall(text)))
        char_sets=tuple(dict.fromkeys(_CHAR_SET.findall(text)))
        if char_reads or char_sets:
            rules.append(BehaviorRule(
                f"{hook}:player-state","player_state",subject,
                trigger=hook.upper(),
                conditions=tuple(
                    BehaviorCondition("player","READS_CHAR_VAR",name)
                    for name in char_reads
                ),
                effects=tuple(
                    BehaviorEffect("SET_CHAR_VAR","player",{"name":name,"value":value.strip()})
                    for name,value in char_sets
                ),
                confidence="VERIFIED",implementation_status="PRESENT",metadata=meta,
            ))
            modeled_hooks.add(hook)

        event_ids=tuple(dict.fromkeys(int(x) for x in _START_EVENT.findall(text)))
        csid_guards=_literal_csid_guards(text,start_line=block.start_line)
        csid_branches=_literal_csid_branches(text,start_line=block.start_line)
        if event_ids or _UPDATE_EVENT.search(text) or csid_guards:
            effects=[
                BehaviorEffect("START_EVENT","player",event_id)
                for event_id in event_ids
            ]
            if _UPDATE_EVENT.search(text):
                effects.append(BehaviorEffect("UPDATE_EVENT","player"))
            conditions=tuple(
                BehaviorCondition(
                    "event:csid",
                    "EVENT_ID_EQUALS",
                    row["csid"],
                    {
                        "source_line":row["line"],
                        "source_line_text":row["source_line"],
                        "event_id":row["csid"],
                    },
                )
                for row in csid_guards
            )
            rules.append(BehaviorRule(
                f"{hook}:event-flow","event_flow",subject,
                trigger=hook.upper(),
                conditions=conditions,
                effects=tuple(effects),
                confidence="VERIFIED",implementation_status="PRESENT",metadata=meta,
            ))
            modeled_hooks.add(hook)

        for branch in csid_branches:
            outcome_branches=_literal_event_outcome_branches(
                branch["body"],
                start_line=branch["start_line"],
            )
            parent_body=_without_event_outcome_branches(branch["body"],outcome_branches)
            branch_writes=[
                row for row in _named_state_accesses(parent_body,start_line=branch["start_line"])
                if row["access"]=="WRITE"
            ]
            branch_effects=_event_branch_nonstate_effects(
                parent_body,
                start_line=branch["start_line"],
                subject=subject,
                trigger=hook.upper(),
                meta=meta,
            )
            if not branch_writes and not branch_effects:
                continue
            rules.append(BehaviorRule(
                f"{hook}:event-branch:{branch['csid']}",
                "event_branch_effects",
                subject,
                trigger=hook.upper(),
                conditions=(BehaviorCondition(
                    "event:csid","EVENT_ID_EQUALS",branch["csid"],
                    {
                        "event_id":branch["csid"],
                        "source_line":branch["start_line"],
                        "source_line_text":branch["source_line"],
                    },
                ),),
                effects=tuple(
                    BehaviorEffect(
                        "WRITE_STATE",row["state_id"],row["value"],
                        {
                            "scope":row["scope"],
                            "receiver":row["receiver"],
                            "name":row["name"],
                            "source_line":row["line"],
                            "source_line_text":row["source_line"],
                            "event_id":branch["csid"],
                        },
                    )
                    for row in branch_writes
                ) + tuple(
                    BehaviorEffect(
                        effect.effect,effect.target,effect.value,
                        {**dict(effect.metadata),"event_id":branch["csid"]},
                    )
                    for effect in branch_effects
                ),
                confidence="VERIFIED",
                implementation_status="PRESENT",
                metadata={
                    **meta,
                    "event_id":branch["csid"],
                    "source_lines":(branch["start_line"],branch["end_line"]),
                    "branch_form":"CSID_LITERAL_BRANCH",
                },
            ))
            modeled_hooks.add(hook)

            for outcome_index,outcome in enumerate(outcome_branches,1):
                outcome_writes=[
                    row for row in outcome["state_accesses"]
                    if row["access"]=="WRITE"
                ]
                outcome_effects=_event_branch_nonstate_effects(
                    outcome["body"],
                    start_line=outcome["start_line"],
                    subject=subject,
                    trigger=hook.upper(),
                    meta=meta,
                )
                if not outcome_writes and not outcome_effects:
                    continue
                outcome_conditions=(
                    BehaviorCondition(
                        "event:csid","EVENT_ID_EQUALS",branch["csid"],
                        {
                            "event_id":branch["csid"],
                            "source_line":branch["start_line"],
                            "source_line_text":branch["source_line"],
                        },
                    ),
                    BehaviorCondition(
                        f"event:{outcome['selector']}",
                        "EVENT_OUTCOME_EQUALS",
                        outcome["literal"],
                        {
                            "event_id":branch["csid"],
                            "selector":outcome["selector"],
                            "source_line":outcome["start_line"],
                            "source_line_text":outcome["source_line"],
                        },
                    ),
                )
                rules.append(BehaviorRule(
                    f"{hook}:event-outcome:{branch['csid']}:{outcome_index}",
                    "event_outcome_effects",
                    subject,
                    trigger=hook.upper(),
                    conditions=outcome_conditions,
                    effects=tuple(
                        BehaviorEffect(
                            "WRITE_STATE",row["state_id"],row["value"],
                            {
                                "scope":row["scope"],
                                "receiver":row["receiver"],
                                "name":row["name"],
                                "source_line":row["line"],
                                "source_line_text":row["source_line"],
                                "event_id":branch["csid"],
                                "outcome_selector":outcome["selector"],
                                "outcome_literal":outcome["literal"],
                            },
                        )
                        for row in outcome_writes
                    ) + tuple(
                        BehaviorEffect(
                            effect.effect,effect.target,effect.value,
                            {
                                **dict(effect.metadata),
                                "event_id":branch["csid"],
                                "outcome_selector":outcome["selector"],
                                "outcome_literal":outcome["literal"],
                            },
                        )
                        for effect in outcome_effects
                    ),
                    confidence="VERIFIED",
                    implementation_status="PRESENT",
                    metadata={
                        **meta,
                        "event_id":branch["csid"],
                        "outcome_selector":outcome["selector"],
                        "outcome_literal":outcome["literal"],
                        "source_lines":(outcome["start_line"],outcome["end_line"]),
                        "branch_form":"EVENT_OUTCOME_LITERAL_BRANCH",
                    },
                ))
                modeled_hooks.add(hook)

        if _TRADE_PREDICATE.search(text) or _CONFIRM_TRADE.search(text):
            rules.append(BehaviorRule(
                f"{hook}:trade","trade_flow",subject,
                trigger=hook.upper(),
                conditions=(BehaviorCondition("trade","TRADE_PREDICATE_PRESENT",True),)
                if _TRADE_PREDICATE.search(text) else (),
                effects=(BehaviorEffect("COMPLETE_TRADE","player"),)
                if _CONFIRM_TRADE.search(text) else (),
                confidence="VERIFIED",implementation_status="PRESENT",metadata=meta,
            ))
            modeled_hooks.add(hook)

        item_rewards=tuple(dict.fromkeys(x.strip() for x in _ITEM_GIVE.findall(text)))
        gil_add=tuple(dict.fromkeys(x.strip() for x in _ADD_GIL.findall(text)))
        gil_del=tuple(dict.fromkeys(x.strip() for x in _DEL_GIL.findall(text)))
        if item_rewards or gil_add or gil_del:
            effects=[]
            effects.extend(BehaviorEffect("GRANT_ITEM","player",value) for value in item_rewards)
            effects.extend(BehaviorEffect("ADD_GIL","player",value) for value in gil_add)
            effects.extend(BehaviorEffect("REMOVE_GIL","player",value) for value in gil_del)
            rules.append(BehaviorRule(
                f"{hook}:rewards","player_reward",subject,
                trigger=hook.upper(),
                effects=tuple(effects),
                confidence="VERIFIED",implementation_status="PRESENT",metadata=meta,
            ))
            modeled_hooks.add(hook)

        world_effects=[]
        for duration in _OPEN_DOOR.findall(text):
            world_effects.append(BehaviorEffect("OPEN_DOOR","world_entity",duration.strip() or None))
        for value in _SET_ANIMATION.findall(text):
            world_effects.append(BehaviorEffect("SET_ANIMATION","world_entity",value.strip()))
        for value in _SET_STATUS.findall(text):
            world_effects.append(BehaviorEffect("SET_STATUS","world_entity",value.strip()))
        for value in _SET_UNTARGETABLE.findall(text):
            world_effects.append(BehaviorEffect("SET_UNTARGETABLE","world_entity",value.strip()))
        if _SET_POS.search(text):
            world_effects.append(BehaviorEffect("SET_POSITION","world_entity"))
        if world_effects:
            rules.append(BehaviorRule(
                f"{hook}:world-state","world_state_change",subject,
                trigger=hook.upper(),
                effects=tuple(world_effects),
                confidence="VERIFIED",implementation_status="PRESENT",metadata=meta,
            ))
            modeled_hooks.add(hook)

        paths=tuple(dict.fromkeys(_PATH_CALL.findall(text)))
        if paths:
            rules.append(BehaviorRule(
                f"{hook}:pathing","path_control",subject,
                trigger=hook.upper(),
                effects=tuple(
                    BehaviorEffect("PATH_ACTOR",subject,method)
                    for method in paths
                ),
                confidence="VERIFIED",implementation_status="PRESENT",metadata=meta,
            ))
            modeled_hooks.add(hook)

        system_calls=tuple(dict.fromkeys(_SYSTEM_HELPER.findall(text)))
        if system_calls:
            rules.append(BehaviorRule(
                f"{hook}:system-calls","system_helper_call",subject,
                trigger=hook.upper(),
                effects=tuple(
                    BehaviorEffect(
                        "CALL_SYSTEM_HELPER",
                        f"system:xi.{module}",
                        function,
                        {"module":module,"function":function},
                    )
                    for module,function in system_calls
                ),
                confidence="VERIFIED",implementation_status="PRESENT",metadata=meta,
            ))
            modeled_hooks.add(hook)

        for helper,call_chain in _reachable_helpers(block,helpers):
            reached_helpers.add(helper.name)
            helper_meta={
                "source_path":source_path,
                "source_lines":(helper.start_line,helper.end_line),
                "hook":hook,
                "helper":helper.name,
                "helper_owner":helper.owner,
                "call_chain":call_chain,
            }
            helper_api_rule=_api_call_rule(
                rule_id=f"{hook}:helper-api:{helper.name}",
                subject=subject,
                trigger=hook.upper(),
                calls=_api_calls(helper.body,start_line=helper.start_line),
                meta=helper_meta,
            )
            if helper_api_rule is not None:
                rules.append(helper_api_rule)
            helper_state_rule=_state_flow_rule(
                rule_id=f"{hook}:helper-state:{helper.name}",
                subject=subject,
                trigger=hook.upper(),
                accesses=_named_state_accesses(helper.body,start_line=helper.start_line),
                meta=helper_meta,
            )
            if helper_state_rule is not None:
                rules.append(helper_state_rule)
            helper_context_rule=_context_condition_rule(
                rule_id=f"{hook}:helper-context:{helper.name}",
                subject=subject,
                trigger=hook.upper(),
                text=helper.body,
                start_line=helper.start_line,
                meta=helper_meta,
            )
            if helper_context_rule is not None:
                rules.append(helper_context_rule)
            helper_entity_ref_rule=_direct_entity_reference_rule(
                rule_id=f"{hook}:helper-entity-refs:{helper.name}",
                subject=subject,
                trigger=hook.upper(),
                text=helper.body,
                start_line=helper.start_line,
                meta=helper_meta,
            )
            if helper_entity_ref_rule is not None:
                rules.append(helper_entity_ref_rule)
            helper_transition_rules=_switch_state_transition_rules(
                text=helper.body,
                start_line=helper.start_line,
                subject=subject,
                trigger=hook.upper(),
                meta=helper_meta,
            )
            if helper_transition_rules:
                rules.extend(helper_transition_rules)
            helper_callback_rules=_callback_rules(
                text=helper.body,
                start_line=helper.start_line,
                subject=subject,
                parent_hook=hook,
                source_path=source_path,
                helper=helper.name,
                call_chain=call_chain,
            )
            if helper_callback_rules:
                rules.extend(helper_callback_rules)
            rules.append(BehaviorRule(
                f"{hook}:helper:{helper.name}",
                "helper_call",
                subject,
                trigger=hook.upper(),
                effects=(BehaviorEffect(
                    "CALL_LOCAL_HELPER",
                    f"helper:{helper.name}",
                    helper.name,
                    {"call_chain":call_chain},
                ),),
                confidence="VERIFIED",implementation_status="PRESENT",
                metadata=helper_meta,
            ))
            modeled_hooks.add(hook)

            helper_effects=[]
            for duration in _OPEN_DOOR.findall(helper.body):
                helper_effects.append(BehaviorEffect("OPEN_DOOR","world_entity",duration.strip() or None))
            for value in _SET_ANIMATION.findall(helper.body):
                helper_effects.append(BehaviorEffect("SET_ANIMATION","world_entity",value.strip()))
            for value in _SET_STATUS.findall(helper.body):
                helper_effects.append(BehaviorEffect("SET_STATUS","world_entity",value.strip()))
            for value in _SET_UNTARGETABLE.findall(helper.body):
                helper_effects.append(BehaviorEffect("SET_UNTARGETABLE","world_entity",value.strip()))
            if _SET_POS.search(helper.body):
                helper_effects.append(BehaviorEffect("SET_POSITION","world_entity"))
            for method in dict.fromkeys(_PATH_CALL.findall(helper.body)):
                helper_effects.append(BehaviorEffect("PATH_ACTOR",subject,method))
            for module,function in dict.fromkeys(_SYSTEM_HELPER.findall(helper.body)):
                helper_effects.append(BehaviorEffect(
                    "CALL_SYSTEM_HELPER",
                    f"system:xi.{module}",
                    function,
                    {"module":module,"function":function},
                ))
            for modifier in dict.fromkeys(_MOD_CALL.findall(helper.body)):
                helper_effects.append(BehaviorEffect("MODIFY_COMBAT_STAT",subject,modifier))
            if _DESPAWN.search(helper.body):
                helper_effects.append(BehaviorEffect("DESPAWN_ENTITY","world_entity"))
            helper_spawns=tuple(dict.fromkeys(_SPAWN_SYMBOL.findall(helper.body)))
            helper_effects.extend(
                BehaviorEffect("SPAWN_ENTITY",_symbol(symbol))
                for symbol in helper_spawns
            )
            helper_keyitems=tuple(dict.fromkeys(_KEYITEM_GIVE.findall(helper.body)))
            helper_effects.extend(
                BehaviorEffect("GRANT_KEY_ITEM","player",symbol)
                for symbol in helper_keyitems
            )
            if helper_effects:
                rules.append(BehaviorRule(
                    f"{hook}:helper-effects:{helper.name}",
                    "helper_effects",
                    subject,
                    trigger=hook.upper(),
                    effects=tuple(helper_effects),
                    confidence="VERIFIED",implementation_status="PRESENT",
                    metadata=helper_meta,
                ))

    hooks=tuple(block.hook for block in blocks)
    return ScriptedBehaviorMap(
        map_id=f"behavior-map:{feature_id}",
        feature_id=feature_id,
        subject=subject,
        zone=zone,
        hooks=hooks,
        rules=_dedupe_rules(rules),
        metadata={
            "extractor":"lsb_scripted_behavior_v1",
            "source_path":source_path,
            "source_hook_count":len(blocks),
            "hook_owners":sorted({block.owner for block in blocks}),
            "source_helper_count":len(helpers),
            "reachable_helper_count":len(reached_helpers),
            "reachable_helpers":sorted(reached_helpers),
            "callback_count":sum(1 for rule in rules if rule.kind=="callback"),
            "state_transition_count":sum(1 for rule in rules if rule.kind=="state_transition"),
            "modeled_hook_count":len(modeled_hooks),
            "unmodeled_hooks":sorted(set(hooks)-modeled_hooks),
        },
    )
