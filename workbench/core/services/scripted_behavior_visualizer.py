"""Behavior inspector projection for LSB Lua source.

Builds a bounded visualization model from one primary script plus same-zone context. Context files
are explicitly labelled CONTEXT unless source evidence proves a stronger link elsewhere; merely
sharing a zone is never promoted to a dependency.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Any

from workbench.plugins.domain.scripted_behavior_lsb_extract import (
    _api_calls,
    _close_count,
    _context_condition_rule,
    _direct_entity_reference_rule,
    _named_state_accesses,
    _open_count,
    _structural_lua_lines,
    extract_lsb_scripted_behavior,
)


def _safe_path(root: Path, relative: str) -> Path:
    root=Path(root).resolve()
    candidate=(root/relative.replace("\\","/")).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Source path must stay inside the configured LSB root.") from exc
    if not candidate.is_file():
        raise FileNotFoundError(relative)
    return candidate


def _zone_parts(relative: str) -> tuple[str | None,str | None]:
    parts=relative.replace("\\","/").split("/")
    if len(parts)>=3 and parts[:2]==["scripts","zones"]:
        return parts[2],"/".join(parts[3:])
    return None,None


def find_lsb_behavior_sources(root: Path, query: str, *, limit: int=100) -> list[dict]:
    """Find candidate zone Lua files by filename/path substring."""
    root=Path(root)
    zones=root/"scripts"/"zones"
    if not query.strip() or not zones.is_dir():
        return []
    needle=query.strip().lower().replace(" ","_")
    rows=[]
    for path in zones.rglob("*.lua"):
        rel=path.relative_to(root).as_posix()
        hay=(path.stem+" "+rel).lower()
        if needle not in hay:
            continue
        zone,_=_zone_parts(rel)
        role=(
            "mob" if "/mobs/" in rel else
            "npc" if "/npcs/" in rel else
            "instance" if "/instances/" in rel else
            "zone" if path.name=="Zone.lua" else
            "zone-global" if path.name=="globals.lua" else
            "script"
        )
        rows.append({"path":rel,"zone":zone,"role":role,"name":path.stem})
        if len(rows)>=max(1,min(limit,250)):
            break
    return sorted(rows,key=lambda row:(row["zone"] or "",row["role"],row["path"]))


def _subject_for(path: Path, relative: str) -> str:
    zone,tail=_zone_parts(relative)
    if path.name=="Zone.lua":
        return f"{zone or 'Zone'} controller"
    if path.name=="globals.lua":
        return f"{zone or 'Zone'} globals"
    return path.stem.replace("_"," ")


def _effect_category(effect: str) -> str:
    if effect=="API_CALL":
        return "api"
    if effect=="WRITE_STATE":
        return "state"
    if "KEY_ITEM" in effect or effect in {"GRANT_ITEM","ADD_GIL","REMOVE_GIL","SET_CHAR_VAR","COMPLETE_TRADE"}:
        return "progression"
    if effect in {"OPEN_DOOR","SET_ANIMATION","SET_STATUS","SET_UNTARGETABLE","SET_POSITION"}:
        return "world"
    if effect in {"SPAWN_ENTITY","DESPAWN_ENTITY","CLEANUP_RELATED_ENTITIES","TRANSFER_RUNTIME_STATE"}:
        return "lifecycle"
    if effect in {"PATH_ACTOR"}:
        return "movement"
    if "SPELL" in effect or "COMBAT" in effect or effect in {"RESPOND_TO_ACTION","ADJUST_COMBAT_STATE","SELECT_ACTION","TIMED_BEHAVIOR"}:
        return "combat"
    if effect in {"CALL_SYSTEM_HELPER","CALL_LOCAL_HELPER"}:
        return "helper"
    if effect in {"START_EVENT","UPDATE_EVENT"}:
        return "event"
    return "other"


def _balanced_function_span(text: str, start_offset: int, *, preview_lines: int=40) -> dict:
    """Return a balanced Lua function span starting at a matched function definition."""
    raw=text.splitlines()
    start_line=text.count("\n",0,start_offset)+1
    structural=_structural_lua_lines(text)
    start_index=max(0,start_line-1)
    depth=0
    started=False
    end_index=start_index
    for j in range(start_index,len(raw)):
        opens=_open_count(structural[j])
        closes=_close_count(structural[j])
        if opens:
            started=True
        depth+=opens-closes
        end_index=j
        if started and depth<=0:
            break
    end_line=end_index+1
    body_lines=raw[start_index:end_index+1]
    preview=body_lines[:preview_lines]
    return {
        "line":start_line,
        "end_line":end_line,
        "line_count":max(0,end_line-start_line+1),
        "source_preview":"\n".join(preview),
        "source_text":"\n".join(body_lines),
        "preview_truncated":len(body_lines)>preview_lines,
    }


def _analyze_shared_helper_body(
    text: str,
    *,
    source_path: str,
    start_line: int,
    qualified_name: str,
) -> dict:
    """One-level conservative analysis of a uniquely resolved shared helper body."""
    meta={
        "source_path":source_path,
        "source_lines":(start_line,start_line+max(0,len(text.splitlines())-1)),
        "hook":f"shared-helper:{qualified_name}",
    }
    api_calls=[dict(row) for row in _api_calls(text,start_line=start_line)]
    state_accesses=[dict(row) for row in _named_state_accesses(text,start_line=start_line)]

    context_rule=_context_condition_rule(
        rule_id=f"shared-helper:{qualified_name}:context",
        subject=qualified_name,
        trigger="SHARED_HELPER_CALL",
        text=text,
        start_line=start_line,
        meta=meta,
    )
    context_conditions=[]
    if context_rule is not None:
        context_conditions=[
            {
                "subject":condition.subject,
                "operator":condition.operator,
                "value":condition.value,
                "metadata":dict(condition.metadata),
            }
            for condition in context_rule.conditions
        ]

    entity_rule=_direct_entity_reference_rule(
        rule_id=f"shared-helper:{qualified_name}:entity-refs",
        subject=qualified_name,
        trigger="SHARED_HELPER_CALL",
        text=text,
        start_line=start_line,
        meta=meta,
    )
    entity_effects=[]
    if entity_rule is not None:
        entity_effects=[
            {
                "effect":effect.effect,
                "target":effect.target,
                "value":effect.value,
                "metadata":dict(effect.metadata),
            }
            for effect in entity_rule.effects
        ]

    state_reads=[row for row in state_accesses if row.get("access")=="READ"]
    state_writes=[row for row in state_accesses if row.get("access")=="WRITE"]
    shared_helper_callees=[
        {
            "qualified_name":row.get("qualified_name"),
            "line":row.get("line"),
            "source_line":row.get("source_line"),
        }
        for row in api_calls
        if isinstance(row.get("qualified_name"),str)
        and re.fullmatch(
            r"xi\.[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*",
            row["qualified_name"],
        )
        and row["qualified_name"]!=qualified_name
    ]
    impact={
        "upstream":[
            {
                "kind":"STATE_READ",
                "label":row.get("state_id"),
                "value":row.get("value"),
                "source_line":row.get("line"),
                "source_line_text":row.get("source_line"),
            }
            for row in state_reads
        ] + [
            {
                "kind":"CONTEXT",
                "label":f"{row.get('subject')} {row.get('operator')}",
                "value":row.get("value"),
                "source_line":row.get("metadata",{}).get("source_line"),
                "source_line_text":row.get("metadata",{}).get("source_line_text"),
            }
            for row in context_conditions
        ],
        "downstream":[
            {
                "kind":"STATE_WRITE",
                "label":row.get("state_id"),
                "value":row.get("value"),
                "source_line":row.get("line"),
                "source_line_text":row.get("source_line"),
            }
            for row in state_writes
        ] + [
            {
                "kind":row.get("effect"),
                "label":row.get("target"),
                "value":row.get("value"),
                "source_line":row.get("metadata",{}).get("source_line"),
                "source_line_text":row.get("metadata",{}).get("source_line_text"),
            }
            for row in entity_effects
        ],
        "calls":[
            {
                "qualified_name":row.get("qualified_name"),
                "receiver":row.get("receiver"),
                "function":row.get("function"),
                "line":row.get("line"),
                "source_line":row.get("source_line"),
            }
            for row in api_calls
        ],
    }
    return {
        "api_calls":api_calls,
        "state_accesses":state_accesses,
        "context_conditions":context_conditions,
        "entity_effects":entity_effects,
        "shared_helper_callees":shared_helper_callees,
        "impact":impact,
        "summary":{
            "api_calls":len(api_calls),
            "state_accesses":len(state_accesses),
            "context_conditions":len(context_conditions),
            "entity_effects":len(entity_effects),
            "shared_helper_callees":len(shared_helper_callees),
            "upstream_impacts":len(impact["upstream"]),
            "downstream_impacts":len(impact["downstream"]),
        },
    }


def _resolve_shared_helpers(root: Path, behavior) -> list[dict]:
    """Resolve top-level and direct nested xi.<module>.<function> definition candidates."""
    globals_root=Path(root)/"scripts"/"globals"

    def definition_candidates(module: str, function: str) -> list[dict]:
        candidates=[]
        module_file=globals_root/f"{module}.lua"
        module_dir=globals_root/module
        files=[]
        if module_file.is_file():
            files.append(module_file)
        if module_dir.is_dir():
            files.extend(sorted(module_dir.rglob("*.lua")))
        qualified_name=f"xi.{module}.{function}"
        pattern=re.compile(
            rf"(?:function\s+{re.escape(qualified_name)}\s*\(|"
            rf"{re.escape(qualified_name)}\s*=\s*function\s*\()"
        )
        for path in files:
            text=path.read_text(encoding="utf-8",errors="ignore")
            for match in pattern.finditer(text):
                span=_balanced_function_span(text,match.start())
                candidates.append({
                    "path":path.relative_to(root).as_posix(),
                    "line":span["line"],
                    "end_line":span["end_line"],
                    "line_count":span["line_count"],
                    "source_preview":span["source_preview"],
                    "preview_truncated":span["preview_truncated"],
                    "qualified_name":qualified_name,
                    "_source_text":span["source_text"],
                })
        return candidates

    def resolution_status(candidates: list[dict]) -> str:
        return (
            "RESOLVED" if len(candidates)==1
            else "AMBIGUOUS" if len(candidates)>1
            else "UNRESOLVED"
        )

    requested=sorted({
        (
            effect.metadata.get("module"),
            effect.metadata.get("function"),
        )
        for rule in behavior.rules
        for effect in rule.effects
        if effect.effect=="CALL_SYSTEM_HELPER"
        and effect.metadata.get("module")
        and effect.metadata.get("function")
    })
    rows=[]
    for module,function in requested:
        candidates=definition_candidates(module,function)
        status=resolution_status(candidates)
        qualified_name=f"xi.{module}.{function}"
        analysis=None
        if status=="RESOLVED":
            candidate=candidates[0]
            analysis=_analyze_shared_helper_body(
                candidate["_source_text"],
                source_path=candidate["path"],
                start_line=candidate["line"],
                qualified_name=qualified_name,
            )
            for callee in analysis.get("shared_helper_callees",[]):
                callee_name=callee.get("qualified_name")
                match=re.fullmatch(
                    r"xi\.([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)",
                    str(callee_name or ""),
                )
                if not match:
                    continue
                callee_module,callee_function=match.groups()
                callee_candidates=definition_candidates(callee_module,callee_function)
                callee["status"]=resolution_status(callee_candidates)
                callee["candidates"]=[
                    {key:value for key,value in row.items() if key!="_source_text"}
                    for row in callee_candidates
                ]
        for candidate in candidates:
            candidate.pop("_source_text",None)
        rows.append({
            "module":module,
            "function":function,
            "qualified_name":qualified_name,
            "status":status,
            "candidates":candidates,
            "analysis":analysis,
        })
    return rows


def _graph_for_behavior(behavior, *, helper_resolutions: list[dict] | None=None) -> dict:
    nodes={}
    edges=[]
    helper_resolution_map={
        row["qualified_name"]:row for row in (helper_resolutions or [])
    }
    expanded_shared_helpers=set()

    def node(node_id: str, kind: str, label: str, **meta):
        nodes.setdefault(node_id,{"id":node_id,"kind":kind,"label":label,"meta":meta})
        return node_id

    root=node(
        f"behavior:{behavior.feature_id}",
        "subject",
        behavior.subject,
        zone=behavior.zone,
        source_path=behavior.metadata.get("source_path"),
    )
    hook_nodes={}
    for hook in behavior.hooks:
        hid=f"hook:{hook}"
        hook_nodes[hook]=node(hid,"hook",hook)
        edges.append({"source":root,"target":hid,"kind":"HAS_HOOK"})

    callback_nodes={}
    for rule in behavior.rules:
        rid=f"rule:{rule.rule_id}"
        node(
            rid,"rule",rule.kind,
            trigger=rule.trigger,
            confidence=rule.confidence,
            implementation_status=rule.implementation_status,
            source_path=rule.metadata.get("source_path"),
            source_lines=rule.metadata.get("source_lines"),
            helper=rule.metadata.get("helper"),
            call_chain=rule.metadata.get("call_chain"),
            callback_type=rule.metadata.get("callback_type"),
            callback_event=rule.metadata.get("callback_event"),
            callback_delay_source=rule.metadata.get("callback_delay_source"),
            callback_call_line=rule.metadata.get("callback_call_line"),
        )
        hook=rule.metadata.get("hook")
        parent=hook_nodes.get(hook,root)
        callback_type=rule.metadata.get("callback_type")
        callback_call_line=rule.metadata.get("callback_call_line")
        if callback_type:
            cbkey=(hook,callback_call_line,callback_type)
            cbid=callback_nodes.get(cbkey)
            if cbid is None:
                cbid=f"callback:{hook}:{callback_call_line}:{callback_type}"
                callback_nodes[cbkey]=cbid
                cb_label=rule.metadata.get("callback_event") or callback_type
                delay=rule.metadata.get("callback_delay_source")
                if delay not in (None,""):
                    cb_label=f"{callback_type} · {delay}"
                node(
                    cbid,"callback",cb_label,
                    callback_type=callback_type,
                    callback_event=rule.metadata.get("callback_event"),
                    callback_delay_source=delay,
                    callback_receiver=rule.metadata.get("callback_receiver"),
                    callback_args=rule.metadata.get("callback_args"),
                    source_path=rule.metadata.get("source_path"),
                    source_lines=rule.metadata.get("source_lines"),
                    hook=hook,
                )
                edges.append({"source":parent,"target":cbid,"kind":"SCHEDULES_CALLBACK"})
            parent=cbid
        edges.append({"source":parent,"target":rid,"kind":"HAS_RULE"})

        for index,condition in enumerate(rule.conditions):
            cid=f"{rid}:condition:{index}"
            label=f"{condition.subject} {condition.operator}"
            node(
                cid,"condition",label,
                value=condition.value,
                metadata=dict(condition.metadata),
                source_path=rule.metadata.get("source_path"),
                source_lines=rule.metadata.get("source_lines"),
                hook=rule.metadata.get("hook"),
            )
            edges.append({"source":cid,"target":rid,"kind":"GUARDS"})
            if condition.operator in {"READS_STATE","STATE_EQUALS"} and isinstance(condition.subject,str) and condition.subject.startswith("state:"):
                smeta=dict(condition.metadata)
                sid=f"state-node:{condition.subject}"
                node(
                    sid,"state",smeta.get("name") or condition.subject,
                    state_id=condition.subject,
                    scope=smeta.get("scope"),
                    receiver=smeta.get("receiver"),
                    name=smeta.get("name"),
                )
                edges.append({
                    "source":sid,
                    "target":cid,
                    "kind":"STATE_GUARD" if condition.operator=="STATE_EQUALS" else "STATE_READ",
                })

        for index,effect in enumerate(rule.effects):
            eid=f"{rid}:effect:{index}"
            category=_effect_category(effect.effect)
            label=effect.effect
            if effect.value not in (None,""):
                label+=f" · {effect.value}"
            node(
                eid,"effect",label,
                effect=effect.effect,
                target=effect.target,
                value=effect.value,
                category=category,
                metadata=dict(effect.metadata),
                source_path=rule.metadata.get("source_path"),
                source_lines=rule.metadata.get("source_lines"),
                hook=rule.metadata.get("hook"),
                helper=rule.metadata.get("helper"),
                call_chain=rule.metadata.get("call_chain"),
                callback_type=rule.metadata.get("callback_type"),
                callback_event=rule.metadata.get("callback_event"),
                callback_delay_source=rule.metadata.get("callback_delay_source"),
            )
            edges.append({"source":rid,"target":eid,"kind":"EMITS"})
            target=effect.target
            if effect.effect=="WRITE_STATE" and isinstance(target,str) and target.startswith("state:"):
                smeta=dict(effect.metadata)
                sid=f"state-node:{target}"
                node(
                    sid,"state",smeta.get("name") or target,
                    state_id=target,
                    scope=smeta.get("scope"),
                    receiver=smeta.get("receiver"),
                    name=smeta.get("name"),
                )
                edges.append({"source":eid,"target":sid,"kind":"STATE_WRITE"})
            elif effect.effect=="CALL_SYSTEM_HELPER":
                module=effect.metadata.get("module")
                function=effect.metadata.get("function")
                qualified=(
                    f"xi.{module}.{function}"
                    if module and function else str(effect.value or target)
                )
                resolution=helper_resolution_map.get(qualified)
                hid=f"shared-helper:{qualified}"
                node(
                    hid,"shared_helper",qualified,
                    resolution_status=(resolution or {}).get("status","UNRESOLVED"),
                    candidates=(resolution or {}).get("candidates",[]),
                    analysis=(resolution or {}).get("analysis"),
                    module=module,
                    function=function,
                )
                edges.append({"source":eid,"target":hid,"kind":"CALLS_SHARED_HELPER"})
                analysis=(resolution or {}).get("analysis")
                if analysis and qualified not in expanded_shared_helpers:
                    expanded_shared_helpers.add(qualified)
                    for impact_index,impact in enumerate(analysis.get("impact",{}).get("upstream",[])):
                        iid=f"shared-helper-input:{qualified}:{impact_index}"
                        impact_meta=dict(impact)
                        impact_meta["impact_kind"]=impact_meta.pop("kind",None)
                        impact_meta["impact_label"]=impact_meta.pop("label",None)
                        node(
                            iid,"helper_input",
                            f"{impact.get('kind')} · {impact.get('label')}",
                            **impact_meta,
                            helper=qualified,
                        )
                        edges.append({"source":iid,"target":hid,"kind":"HELPER_UPSTREAM_INPUT"})
                    for impact_index,impact in enumerate(analysis.get("impact",{}).get("downstream",[])):
                        oid=f"shared-helper-effect:{qualified}:{impact_index}"
                        impact_meta=dict(impact)
                        impact_meta["impact_kind"]=impact_meta.pop("kind",None)
                        impact_meta["impact_label"]=impact_meta.pop("label",None)
                        node(
                            oid,"helper_effect",
                            f"{impact.get('kind')} · {impact.get('label')}",
                            **impact_meta,
                            helper=qualified,
                        )
                        edges.append({"source":hid,"target":oid,"kind":"HELPER_DOWNSTREAM_EFFECT"})
                    for call_index,call in enumerate(analysis.get("impact",{}).get("calls",[])):
                        cid=f"shared-helper-call:{qualified}:{call_index}"
                        node(
                            cid,"helper_call",
                            str(call.get("qualified_name") or call.get("function") or "API_CALL"),
                            **dict(call),
                            helper=qualified,
                        )
                        edges.append({"source":hid,"target":cid,"kind":"HELPER_DIRECT_CALL"})
                    for callee_index,callee in enumerate(analysis.get("shared_helper_callees",[])):
                        nid=f"shared-helper-callee:{qualified}:{callee_index}"
                        node(
                            nid,"shared_helper_callee",
                            str(callee.get("qualified_name") or "SHARED_HELPER"),
                            **dict(callee),
                            helper=qualified,
                        )
                        edges.append({
                            "source":hid,
                            "target":nid,
                            "kind":"CALLS_NESTED_SHARED_HELPER",
                        })
                if isinstance(target,str):
                    tid=f"target:{target}"
                    node(tid,"target",target)
                    edges.append({"source":hid,"target":tid,"kind":"DEFINED_IN_SYSTEM"})
            elif isinstance(target,str) and target not in {"player","world_entity","global"}:
                tid=f"target:{target}"
                node(tid,"target",target)
                edges.append({"source":eid,"target":tid,"kind":"AFFECTS"})

    state_rows={}
    for rule in behavior.rules:
        hook=rule.metadata.get("hook")
        for condition in rule.conditions:
            if condition.operator not in {"READS_STATE","STATE_EQUALS"} or not isinstance(condition.subject,str):
                continue
            meta=dict(condition.metadata)
            row=state_rows.setdefault(condition.subject,{
                "state_id":condition.subject,
                "scope":meta.get("scope"),
                "receiver":meta.get("receiver"),
                "name":meta.get("name") or condition.subject,
                "reads":[],
                "writes":[],
            })
            row["reads"].append({
                "hook":hook,
                "line":meta.get("source_line"),
                "source":meta.get("source_line_text"),
            })
        for effect in rule.effects:
            if effect.effect!="WRITE_STATE" or not isinstance(effect.target,str):
                continue
            meta=dict(effect.metadata)
            row=state_rows.setdefault(effect.target,{
                "state_id":effect.target,
                "scope":meta.get("scope"),
                "receiver":meta.get("receiver"),
                "name":meta.get("name") or effect.target,
                "reads":[],
                "writes":[],
            })
            row["writes"].append({
                "hook":hook,
                "line":meta.get("source_line"),
                "source":meta.get("source_line_text"),
                "value":effect.value,
            })

    state_links=[]
    for state_id,row in state_rows.items():
        read_hooks=sorted({
            entry.get("hook") for entry in row["reads"]
            if entry.get("hook")
        })
        write_hooks=sorted({
            entry.get("hook") for entry in row["writes"]
            if entry.get("hook")
        })
        cross_pairs=[
            {"writer_hook":writer,"reader_hook":reader}
            for writer in write_hooks
            for reader in read_hooks
            if writer!=reader
        ]
        if not cross_pairs:
            continue
        state_links.append({
            "state_id":state_id,
            "scope":row.get("scope"),
            "name":row.get("name"),
            "writer_hooks":write_hooks,
            "reader_hooks":read_hooks,
            "cross_hook_pairs":cross_pairs,
            "relationship":"SHARED_STATE_ACROSS_HOOKS",
            "ordering":"UNPROVEN",
            "evidence_basis":"same canonical state identity is written in one hook and read in another",
        })

    transition_rows=[]
    for rule in behavior.rules:
        if rule.kind!="state_transition":
            continue
        guards=[
            condition for condition in rule.conditions
            if condition.operator=="STATE_EQUALS" and isinstance(condition.subject,str)
        ]
        writes=[
            effect for effect in rule.effects
            if effect.effect=="WRITE_STATE" and isinstance(effect.target,str)
        ]
        for condition in guards:
            for effect in writes:
                if condition.subject!=effect.target:
                    continue
                transition_rows.append({
                    "state_id":condition.subject,
                    "scope":condition.metadata.get("scope"),
                    "name":condition.metadata.get("name") or rule.metadata.get("state_name") or condition.subject,
                    "from":condition.value,
                    "to":effect.value,
                    "hook":rule.metadata.get("hook"),
                    "source_path":rule.metadata.get("source_path"),
                    "source_lines":rule.metadata.get("source_lines"),
                    "selector_alias":rule.metadata.get("selector_alias"),
                    "confidence":rule.confidence,
                })

    categories=Counter(
        n["meta"].get("category")
        for n in nodes.values()
        if n["kind"]=="effect" and n["meta"].get("category")
    )
    return {
        "root":root,
        "nodes":list(nodes.values()),
        "edges":edges,
        "states":sorted(state_rows.values(),key=lambda row:(row["scope"] or "",row["name"])),
        "state_links":sorted(state_links,key=lambda row:(row["scope"] or "",row["name"] or "",row["state_id"])),
        "transitions":transition_rows,
        "summary":{
            "hooks":len(behavior.hooks),
            "rules":len(behavior.rules),
            "effects":sum(1 for n in nodes.values() if n["kind"]=="effect"),
            "conditions":sum(1 for n in nodes.values() if n["kind"]=="condition"),
            "targets":sum(1 for n in nodes.values() if n["kind"]=="target"),
            "states":len(state_rows),
            "cross_hook_state_links":len(state_links),
            "callbacks":len(callback_nodes),
            "transitions":len(transition_rows),
            "shared_helpers":len(helper_resolutions or []),
            "shared_helper_impact_nodes":sum(
                1 for row in nodes.values()
                if row["kind"] in {"helper_input","helper_effect","helper_call"}
            ),
            "shared_helper_callee_nodes":sum(
                1 for row in nodes.values()
                if row["kind"]=="shared_helper_callee"
            ),
            "effect_categories":dict(sorted(categories.items())),
            "unmodeled_hooks":list(behavior.metadata.get("unmodeled_hooks") or ()),
            "reachable_helpers":list(behavior.metadata.get("reachable_helpers") or ()),
            "hook_owners":list(behavior.metadata.get("hook_owners") or ()),
        },
    }


def _context_candidates(root: Path, primary: Path, *, max_instances: int=24) -> list[dict]:
    rel=primary.relative_to(root).as_posix()
    zone,_=_zone_parts(rel)
    if not zone:
        return []
    zone_root=root/"scripts"/"zones"/zone
    candidates=[]
    for role,name in (("zone","Zone.lua"),("zone-global","globals.lua")):
        path=zone_root/name
        if path.is_file() and path.resolve()!=primary.resolve():
            candidates.append((role,path))
    instance_dir=zone_root/"instances"
    if instance_dir.is_dir():
        for path in sorted(instance_dir.glob("*.lua"))[:max_instances]:
            if path.resolve()!=primary.resolve():
                candidates.append(("instance-context",path))
    return [{"role":role,"path":path} for role,path in candidates]


def inspect_lsb_behavior(root: Path, relative: str) -> dict:
    root=Path(root).resolve()
    primary=_safe_path(root,relative)
    rel=primary.relative_to(root).as_posix()
    zone,_=_zone_parts(rel)
    text=primary.read_text(encoding="utf-8",errors="ignore")
    behavior=extract_lsb_scripted_behavior(
        text,
        feature_id=f"behavior-source:{rel}",
        subject=_subject_for(primary,rel),
        zone=zone,
        source_path=rel,
    )
    helper_resolutions=_resolve_shared_helpers(root,behavior)
    graph=_graph_for_behavior(
        behavior,
        helper_resolutions=helper_resolutions,
    )

    contexts=[]
    for row in _context_candidates(root,primary):
        path=row["path"]
        context_rel=path.relative_to(root).as_posix()
        context_text=path.read_text(encoding="utf-8",errors="ignore")
        context_behavior=extract_lsb_scripted_behavior(
            context_text,
            feature_id=f"behavior-context:{context_rel}",
            subject=_subject_for(path,context_rel),
            zone=zone,
            source_path=context_rel,
        )
        api_calls=sum(
            1 for rule in context_behavior.rules for effect in rule.effects
            if effect.effect=="API_CALL"
        )
        contexts.append({
            "role":row["role"],
            "path":context_rel,
            "subject":context_behavior.subject,
            "hooks":list(context_behavior.hooks),
            "rule_count":len(context_behavior.rules),
            "api_call_count":api_calls,
            "shared_systems":sorted({
                effect.target for rule in context_behavior.rules for effect in rule.effects
                if effect.effect=="CALL_SYSTEM_HELPER" and isinstance(effect.target,str)
            }),
            "scope_basis":"same-zone context; not a proven dependency",
        })

    return {
        "source":{"path":rel,"zone":zone,"subject":behavior.subject},
        "behavior":behavior,
        "graph":graph,
        "shared_helpers":helper_resolutions,
        "contexts":contexts,
        "notes":[
            "Primary graph edges come from the selected Lua source and bounded helper traversal.",
            "Zone/global/instance files are contextual controllers unless another analyzer proves a direct dependency.",
            "API_CALL observations preserve unfamiliar Lua-bound behavior even when no semantic effect classifier exists yet.",
            "Cross-hook state links mean the same canonical state is written in one hook and read in another; execution ordering and causal sequencing remain unproven.",
        ],
    }
