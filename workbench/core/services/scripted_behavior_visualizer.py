"""Behavior inspector projection for LSB Lua source.

Builds a bounded visualization model from one primary script plus same-zone context. Context files
are explicitly labelled CONTEXT unless source evidence proves a stronger link elsewhere; merely
sharing a zone is never promoted to a dependency.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from workbench.plugins.domain.scripted_behavior_lsb_extract import (
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


def _graph_for_behavior(behavior) -> dict:
    nodes={}
    edges=[]

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
            if condition.operator=="READS_STATE" and isinstance(condition.subject,str) and condition.subject.startswith("state:"):
                smeta=dict(condition.metadata)
                sid=f"state-node:{condition.subject}"
                node(
                    sid,"state",smeta.get("name") or condition.subject,
                    state_id=condition.subject,
                    scope=smeta.get("scope"),
                    receiver=smeta.get("receiver"),
                    name=smeta.get("name"),
                )
                edges.append({"source":sid,"target":cid,"kind":"STATE_READ"})

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
            elif isinstance(target,str) and target not in {"player","world_entity","global"}:
                tid=f"target:{target}"
                node(tid,"target",target)
                edges.append({"source":eid,"target":tid,"kind":"AFFECTS"})

    state_rows={}
    for rule in behavior.rules:
        hook=rule.metadata.get("hook")
        for condition in rule.conditions:
            if condition.operator!="READS_STATE" or not isinstance(condition.subject,str):
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
        "summary":{
            "hooks":len(behavior.hooks),
            "rules":len(behavior.rules),
            "effects":sum(1 for n in nodes.values() if n["kind"]=="effect"),
            "conditions":sum(1 for n in nodes.values() if n["kind"]=="condition"),
            "targets":sum(1 for n in nodes.values() if n["kind"]=="target"),
            "states":len(state_rows),
            "callbacks":len(callback_nodes),
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
    graph=_graph_for_behavior(behavior)

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
        "contexts":contexts,
        "notes":[
            "Primary graph edges come from the selected Lua source and bounded helper traversal.",
            "Zone/global/instance files are contextual controllers unless another analyzer proves a direct dependency.",
            "API_CALL observations preserve unfamiliar Lua-bound behavior even when no semantic effect classifier exists yet.",
        ],
    }
