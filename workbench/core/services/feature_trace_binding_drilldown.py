"""Read-only Lua -> C++ binding/engine drill-down for Feature Trace.

This service joins syntax-level Behavior Inspector API observations with registration evidence
from configured server C++ binding sources. It does not create canonical graph relationships or
infer C++ semantics from a binding name.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from urllib.parse import quote

import backport_binding_index


def binding_index_for_server(server: str, root: Path) -> dict[str, list[dict]]:
    root=Path(root)
    try:
        if server=="dsp":
            return backport_binding_index.build_dsp_index(root)
        return backport_binding_index.build_topaz_index(root)
    except Exception:
        return {}


def binding_location(root: Path, method: str, location: dict) -> dict:
    row=dict(location)
    rel=str(row.get("file") or "")
    path=(Path(root)/rel).resolve()
    root_resolved=Path(root).resolve()
    row["registration_excerpt"]=None
    row["implementation_line"]=None
    row["implementation_excerpt"]=None
    if not path.is_file() or not (path==root_resolved or root_resolved in path.parents):
        return row
    try:
        lines=path.read_text(encoding="utf-8",errors="replace").splitlines()
    except OSError:
        return row
    reg_line=int(row.get("line") or 0)
    if reg_line>0:
        a=max(0,reg_line-3); b=min(len(lines),reg_line+2)
        row["registration_excerpt"]={
            "start_line":a+1,"end_line":b,"text":"\n".join(lines[a:b]),
        }
    cls=str(row.get("class") or "")
    if cls and method:
        pattern=re.compile(rf"\b{re.escape(cls)}::{re.escape(method)}\s*\(")
        for idx,line in enumerate(lines):
            if not pattern.search(line):
                continue
            a=max(0,idx-2); b=min(len(lines),idx+12)
            row["implementation_line"]=idx+1
            row["implementation_excerpt"]={
                "start_line":a+1,
                "end_line":b,
                "text":"\n".join(lines[a:b]),
                "truncated":b<len(lines),
            }
            break
    return row


def binding_lookup(
    server: str,
    root: Path,
    method: str,
    *,
    index: dict[str,list[dict]] | None=None,
) -> dict:
    index=index if index is not None else binding_index_for_server(server,root)
    if not method:
        return {"status":"NO_METHOD","locations":[]}
    locations=index.get(method) or []
    exact_name=method if locations else None
    case_name=None
    if not locations:
        lowered={name.casefold():name for name in index}
        case_name=lowered.get(method.casefold())
        if case_name:
            locations=index.get(case_name) or []
    status="EXACT" if exact_name else "CASE_ONLY" if case_name else "NOT_INDEXED"
    resolved_name=exact_name or case_name or method
    return {
        "status":status,
        "query":method,
        "resolved_name":resolved_name,
        "locations":[binding_location(root,resolved_name,row) for row in locations[:8]],
        "binding_href":f"/backport/bindings?q={quote(method,safe='')}",
        "basis":"Binding registration index generated from configured server C++ binding sources.",
    }


def behavior_engine_drilldown(inspected: dict, *, server: str, source_root: Path) -> dict:
    behavior=inspected.get("behavior")
    binding_index=binding_index_for_server(server,source_root)
    direct_calls=[]
    if behavior is not None:
        for rule in behavior.rules:
            for effect in rule.effects:
                if effect.effect!="API_CALL":
                    continue
                meta=dict(effect.metadata or {})
                direct_calls.append({
                    "receiver":effect.target,
                    "function":effect.value,
                    "qualified_name":meta.get("qualified_name"),
                    "line":meta.get("source_line"),
                    "source_line":meta.get("source_line_text"),
                    "hook":rule.metadata.get("hook"),
                    "hook_owner":rule.metadata.get("hook_owner"),
                    "trigger":rule.trigger,
                    "binding":binding_lookup(
                        server,source_root,str(effect.value or ""),index=binding_index
                    ),
                })
    seen=set(); deduped=[]
    for row in sorted(direct_calls,key=lambda x:(x.get("line") or 0,str(x.get("qualified_name") or ""))):
        key=(row.get("line"),row.get("qualified_name"),row.get("hook"))
        if key in seen:
            continue
        seen.add(key); deduped.append(row)

    helpers=[]
    for row in inspected.get("shared_helpers") or []:
        helper={
            "qualified_name":row.get("qualified_name"),
            "status":row.get("status"),
            "candidates":row.get("candidates") or [],
            "api_calls":[],
            "callees":[],
        }
        analysis=row.get("analysis") or {}
        for call in analysis.get("api_calls") or []:
            helper["api_calls"].append({
                **call,
                "binding":binding_lookup(
                    server,source_root,str(call.get("function") or ""),index=binding_index
                ),
            })
        helper["callees"]=analysis.get("shared_helper_callees") or []
        helpers.append(helper)

    callbacks=[]
    graph_data=inspected.get("graph") or {}
    for node in graph_data.get("nodes") or []:
        if node.get("kind")!="callback":
            continue
        meta=node.get("meta") or {}
        callbacks.append({
            "id":node.get("id"),
            "label":node.get("label"),
            "callback_type":meta.get("callback_type"),
            "event":meta.get("callback_event"),
            "delay":meta.get("callback_delay_source"),
        })

    binding_counts=Counter(row["binding"]["status"] for row in deduped)
    unindexed=[row for row in deduped if row["binding"]["status"]=="NOT_INDEXED"]
    case_only=[row for row in deduped if row["binding"]["status"]=="CASE_ONLY"]
    return {
        "direct_calls":deduped,
        "direct_call_count":len(deduped),
        "binding_counts":dict(sorted(binding_counts.items())),
        "binding_index_size":len(binding_index),
        "unindexed_calls":unindexed,
        "unindexed_call_count":len(unindexed),
        "case_only_calls":case_only,
        "case_only_call_count":len(case_only),
        "shared_helpers":helpers,
        "callbacks":callbacks,
        "callback_count":len(callbacks),
        "notes":[
            "Lua API calls are syntax-level observations from the selected source/helper bodies.",
            "Binding matches come from registered C++ Lua binding names in the configured server tree.",
            "A binding registration proves a Lua-to-C++ handoff name/location, not the semantics of the C++ body.",
            "Shared-helper and callback ownership come from the existing bounded Behavior Inspector analysis.",
        ],
    }
