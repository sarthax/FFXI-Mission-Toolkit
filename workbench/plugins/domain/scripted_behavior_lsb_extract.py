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
    r"^\s*entity\.(on[A-Za-z0-9_]+)\s*=\s*function\s*\(([^)]*)\)"
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


@dataclass(frozen=True)
class HookBlock:
    hook: str
    args: tuple[str,...]
    start_line: int
    end_line: int
    body: str


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
    """Return balanced top-level entity.on* hook functions with exact source line ranges."""
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
                    part.strip() for part in match.group(2).split(",") if part.strip()
                )
                out.append(HookBlock(
                    match.group(1),args,i+1,j+1,"\n".join(raw[i:j+1])
                ))
                break
    return tuple(out)


def _symbol(name: str) -> str:
    return f"entity-symbol:{name}"


def _source_meta(block: HookBlock, source_path: str) -> dict:
    return {
        "source_path":source_path,
        "source_lines":(block.start_line,block.end_line),
        "hook":block.hook,
    }


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
    """Extract conservative scripted behavior from one LSB-style mob Lua script."""
    blocks=extract_hook_blocks(lua)
    rules=[]
    modeled_hooks=set()

    for block in blocks:
        text=block.body
        meta=_source_meta(block,source_path)
        hook=block.hook

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
            "modeled_hook_count":len(modeled_hooks),
            "unmodeled_hooks":sorted(set(hooks)-modeled_hooks),
        },
    )
