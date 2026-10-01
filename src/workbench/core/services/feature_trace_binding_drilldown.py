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


def _build_binding_index(server: str, root: Path) -> tuple[dict[str, list[dict]], str | None]:
    """Build the provider binding index while preserving index-build failure as evidence."""
    root=Path(root)
    try:
        if server=="dsp":
            return backport_binding_index.build_dsp_index(root),None
        return backport_binding_index.build_topaz_index(root),None
    except Exception as exc:
        return {},f"{type(exc).__name__}: {exc}"


def binding_index_for_server(server: str, root: Path) -> dict[str, list[dict]]:
    """Compatibility helper returning only the index."""
    index,_error=_build_binding_index(server,root)
    return index


def _implementation_candidates(lines: list[str], cls: str, method: str) -> list[dict]:
    if not cls or not method:
        return []
    pattern=re.compile(rf"\b{re.escape(cls)}::{re.escape(method)}\s*\(")
    rows=[]
    for idx,line in enumerate(lines):
        if not pattern.search(line):
            continue
        a=max(0,idx-2); b=min(len(lines),idx+12)
        rows.append({
            "line":idx+1,
            "excerpt":{
                "start_line":a+1,
                "end_line":b,
                "text":"\n".join(lines[a:b]),
                "truncated_before":a>0,
                "truncated_after":b<len(lines),
            },
        })
        if len(rows)>=8:
            break
    return rows


def binding_location(root: Path, method: str, location: dict) -> dict:
    row=dict(location)
    rel=str(row.get("file") or "")
    path=(Path(root)/rel).resolve()
    root_resolved=Path(root).resolve()
    row["registration_excerpt"]=None
    row["implementation_line"]=None
    row["implementation_excerpt"]=None
    row["implementation_candidates"]=[]
    row["implementation_candidate_count"]=0
    row["source_read_status"]="UNREAD"
    if not path.is_file() or not (path==root_resolved or root_resolved in path.parents):
        row["source_read_status"]="MISSING_OR_OUTSIDE_ROOT"
        return row
    try:
        lines=path.read_text(encoding="utf-8",errors="replace").splitlines()
    except OSError as exc:
        row["source_read_status"]="READ_ERROR"
        row["source_read_error"]=f"{type(exc).__name__}: {exc}"
        return row
    row["source_read_status"]="READ"
    reg_line=int(row.get("line") or 0)
    if reg_line>0:
        a=max(0,reg_line-3); b=min(len(lines),reg_line+2)
        row["registration_excerpt"]={
            "start_line":a+1,
            "end_line":b,
            "text":"\n".join(lines[a:b]),
            "truncated_before":a>0,
            "truncated_after":b<len(lines),
        }
    cls=str(row.get("class") or "")
    candidates=_implementation_candidates(lines,cls,method)
    row["implementation_candidates"]=candidates
    row["implementation_candidate_count"]=len(candidates)
    if candidates:
        first=candidates[0]
        row["implementation_line"]=first["line"]
        row["implementation_excerpt"]=first["excerpt"]
    return row


def _binding_summary(locations: list[dict]) -> dict:
    classes=sorted({str(row.get("class") or "") for row in locations if row.get("class")})
    files=sorted({str(row.get("file") or "") for row in locations if row.get("file")})
    return {
        "location_count":len(locations),
        "multiple_locations":len(locations)>1,
        "classes":classes,
        "class_count":len(classes),
        "files":files,
        "file_count":len(files),
    }


def binding_lookup(
    server: str,
    root: Path,
    method: str,
    *,
    index: dict[str,list[dict]] | None=None,
    index_error: str | None=None,
) -> dict:
    if index is None:
        index,index_error=_build_binding_index(server,root)
    if not method:
        return {
            "status":"NO_METHOD",
            "query":method,
            "resolved_name":method,
            "candidate_names":[],
            "locations":[],
            **_binding_summary([]),
        }
    if index_error:
        return {
            "status":"INDEX_UNAVAILABLE",
            "query":method,
            "resolved_name":method,
            "candidate_names":[],
            "locations":[],
            "index_error":index_error,
            "binding_href":f"/backport/bindings?q={quote(method,safe='')}",
            "basis":"Binding registration index could not be built from the configured provider tree.",
            **_binding_summary([]),
        }

    exact_locations=index.get(method) or []
    candidate_names=[]
    resolved_name=method
    status="NOT_INDEXED"
    locations=[]

    if exact_locations:
        status="EXACT"
        locations=list(exact_locations)
        candidate_names=[method]
    else:
        folded=method.casefold()
        candidate_names=sorted(name for name in index if name.casefold()==folded)
        if len(candidate_names)==1:
            status="CASE_ONLY"
            resolved_name=candidate_names[0]
            locations=list(index.get(resolved_name) or [])
        elif len(candidate_names)>1:
            status="CASE_AMBIGUOUS"
            for name in candidate_names:
                for row in index.get(name) or []:
                    locations.append({**row,"registered_name":name})

    locations=sorted(
        locations,
        key=lambda row:(
            str(row.get("file") or ""),
            int(row.get("line") or 0),
            str(row.get("class") or ""),
        ),
    )[:8]
    enriched=[
        binding_location(root,str(row.get("registered_name") or resolved_name),row)
        for row in locations
    ]
    return {
        "status":status,
        "query":method,
        "resolved_name":resolved_name,
        "candidate_names":candidate_names,
        "locations":enriched,
        "locations_truncated":sum(len(index.get(name) or []) for name in candidate_names)>len(enriched),
        "binding_href":f"/backport/bindings?q={quote(method,safe='')}",
        "basis":"Binding registration index generated from configured server C++ binding sources.",
        **_binding_summary(enriched),
    }


def behavior_engine_drilldown(inspected: dict, *, server: str, source_root: Path) -> dict:
    behavior=inspected.get("behavior")
    binding_index,index_error=_build_binding_index(server,source_root)
    direct_calls=[]
    raw_direct_call_count=0
    if behavior is not None:
        for rule in behavior.rules:
            for effect in rule.effects:
                if effect.effect!="API_CALL":
                    continue
                raw_direct_call_count+=1
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
                        server,source_root,str(effect.value or ""),
                        index=binding_index,index_error=index_error,
                    ),
                })
    seen=set(); deduped=[]
    for row in sorted(direct_calls,key=lambda x:(x.get("line") or 0,str(x.get("qualified_name") or ""))):
        key=(row.get("line"),row.get("qualified_name"),row.get("hook"))
        if key in seen:
            continue
        seen.add(key); deduped.append(row)

    helpers=[]
    helper_binding_counts=Counter()
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
            lookup=binding_lookup(
                server,source_root,str(call.get("function") or ""),
                index=binding_index,index_error=index_error,
            )
            helper_binding_counts[lookup["status"]]+=1
            helper["api_calls"].append({**call,"binding":lookup})
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
    callbacks=sorted(callbacks,key=lambda row:(str(row.get("callback_type") or ""),str(row.get("id") or "")))

    binding_counts=Counter(row["binding"]["status"] for row in deduped)
    unindexed=[row for row in deduped if row["binding"]["status"]=="NOT_INDEXED"]
    unavailable=[row for row in deduped if row["binding"]["status"]=="INDEX_UNAVAILABLE"]
    case_only=[row for row in deduped if row["binding"]["status"]=="CASE_ONLY"]
    case_ambiguous=[row for row in deduped if row["binding"]["status"]=="CASE_AMBIGUOUS"]
    multi_location=[row for row in deduped if row["binding"].get("multiple_locations")]
    return {
        "direct_calls":deduped,
        "raw_direct_call_count":raw_direct_call_count,
        "duplicate_direct_call_count":max(0,raw_direct_call_count-len(deduped)),
        "direct_call_count":len(deduped),
        "binding_counts":dict(sorted(binding_counts.items())),
        "binding_index_size":len(binding_index),
        "binding_index_status":"UNAVAILABLE" if index_error else "READY",
        "binding_index_error":index_error,
        "unindexed_calls":unindexed,
        "unindexed_call_count":len(unindexed),
        "unavailable_calls":unavailable,
        "unavailable_call_count":len(unavailable),
        "case_only_calls":case_only,
        "case_only_call_count":len(case_only),
        "case_ambiguous_calls":case_ambiguous,
        "case_ambiguous_call_count":len(case_ambiguous),
        "multi_location_calls":multi_location,
        "multi_location_call_count":len(multi_location),
        "shared_helpers":helpers,
        "helper_binding_counts":dict(sorted(helper_binding_counts.items())),
        "callbacks":callbacks,
        "callback_count":len(callbacks),
        "notes":[
            "Lua API calls are syntax-level observations from the selected source/helper bodies.",
            "Binding matches come from registered C++ Lua binding names in the configured server tree.",
            "A binding registration proves a Lua-to-C++ handoff name/location, not the semantics of the C++ body.",
            "INDEX_UNAVAILABLE means the provider binding index could not be built; NOT_INDEXED is only used when a successfully built index lacks the method.",
            "CASE_AMBIGUOUS preserves multiple registered names that differ only by case instead of choosing one.",
            "Multiple binding locations and implementation candidates are preserved as review evidence rather than collapsed.",
            "Shared-helper and callback ownership come from the existing bounded Behavior Inspector analysis.",
        ],
    }
