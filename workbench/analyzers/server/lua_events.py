#!/usr/bin/env python3
"""Index Lua event handlers and API calls for capture/server backtracing."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from workbench.core.provenance import snapshot_id

EVENT_RE=re.compile(r'(?P<expr>startEvent|csid\s*==|event\s*==)\s*\(?\s*(?P<id>\d+)')
FUNC_RE=re.compile(r'(?m)^\s*function\s+([\w.:]+)\s*\(([^)]*)\)')
CALL_RE=re.compile(r'(?<![\w])([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(')
ALIAS_RE=re.compile(r'(?m)^\s*local\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:--.*)?
# These are hints, not semantic proof. They are limited to conventional FFXI server callback
# parameter names whose runtime wrapper type is stable enough to reduce binding candidates.
KNOWN_PARAM_TYPES={
    "player":"CLuaBaseEntity","npc":"CLuaBaseEntity","mob":"CLuaBaseEntity","target":"CLuaBaseEntity",
    "entity":"CLuaBaseEntity","caster":"CLuaBaseEntity","attacker":"CLuaBaseEntity","victim":"CLuaBaseEntity",
    "instance":"CLuaInstance",
}

def param_type_hints(fn):
    if fn is None: return {}
    params=[p.strip() for p in fn.group(2).split(",") if p.strip()]
    return {p:KNOWN_PARAM_TYPES[p.lower()] for p in params if p.lower() in KNOWN_PARAM_TYPES}

def typed_calls(text, start, end, fn, return_type_hints=None):
    """Collect method calls with conservative local type propagation.

    Parameter-name hints seed the environment. Direct local aliases inherit that type.
    Returned-object types are used only when explicitly supplied by the caller as
    {(receiver_class, method_name): returned_class}. No method-name guessing occurs.
    """
    return_type_hints=return_type_hints or {}
    types={name:(klass,"FUNCTION_PARAMETER_NAME") for name,klass in param_type_hints(fn).items()}
    events=[]
    for m in ALIAS_RE.finditer(text,start,end):
        events.append((m.start(),"alias",m))
    for m in RETURN_ASSIGN_RE.finditer(text,start,end):
        events.append((m.start(),"return",m))
    for m in CALL_RE.finditer(text,start,end):
        events.append((m.start(),"call",m))
    events.sort(key=lambda item:(item[0],{"alias":0,"return":0,"call":1}[item[1]]))

    calls=[]
    for _pos,kind,m in events:
        if kind=="alias":
            lhs,rhs=m.group(1),m.group(2)
            if rhs in types:
                types[lhs]=(types[rhs][0],"LOCAL_ALIAS")
            continue
        if kind=="return":
            lhs,obj,method=m.group(1),m.group(2),m.group(3)
            receiver=types.get(obj)
            if receiver:
                returned=return_type_hints.get((receiver[0],method))
                if returned:
                    types[lhs]=(returned,"CONFIGURED_RETURN_TYPE")
            continue

        obj,method=m.group(1),m.group(2)
        hint=types.get(obj)
        calls.append({
            "object":obj,
            "method":method,
            "line":text.count("\n",0,m.start())+1,
            "class_hint":hint[0] if hint else None,
            "class_hint_source":hint[1] if hint else None,
        })
    return calls

def index(root: Path, return_type_hints=None):
    rows=[]; scripts=root/"scripts/zones"
    if not scripts.is_dir(): return rows
    for f in sorted(scripts.rglob("npcs/*.lua")):
        text=f.read_text(encoding="utf-8",errors="replace"); funcs=list(FUNC_RE.finditer(text))
        for m in EVENT_RE.finditer(text):
            line=text.count("\n",0,m.start())+1; containing=None; idx=-1
            for i,fn in enumerate(funcs):
                if fn.start()<=m.start(): containing=fn; idx=i
                else: break
            start=containing.start() if containing else max(0,m.start()-1000)
            end=funcs[idx+1].start() if containing and idx+1<len(funcs) else min(len(text),m.end()+2000)
            calls=typed_calls(text,start,end,containing,return_type_hints)
            rows.append({"zone":f.parent.parent.name,"script":f.stem,"path":f.relative_to(root).as_posix(),
                         "event_id":int(m.group("id")),"event_expression":m.group("expr"),"line":line,
                         "function":containing.group(1) if containing else None,
                         "function_line":text.count("\n",0,containing.start())+1 if containing else None,
                         "calls":calls})
    return rows

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("root",type=Path); ap.add_argument("--json",type=Path)
    a=ap.parse_args(); sid=snapshot_id(a.root); rows=index(a.root)
    out={"schema":1,"source":str(a.root),"source_snapshot_id":sid,
         "analysis":{"analysis_id":"lua-event-index","analysis_type":"LUA_EVENT_SURFACE","source":str(a.root),
                     "status":"ANALYZED","source_snapshot_id":sid},
         "events":rows}
    data=json.dumps(out,indent=2,sort_keys=True)
    if a.json: a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(data+"\n",encoding="utf-8")
    else: print(data)
if __name__=="__main__": main()
)
RETURN_ASSIGN_RE=re.compile(r'(?m)^\s*local\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(')

# These are hints, not semantic proof. They are limited to conventional FFXI server callback
# parameter names whose runtime wrapper type is stable enough to reduce binding candidates.
KNOWN_PARAM_TYPES={
    "player":"CLuaBaseEntity","npc":"CLuaBaseEntity","mob":"CLuaBaseEntity","target":"CLuaBaseEntity",
    "entity":"CLuaBaseEntity","caster":"CLuaBaseEntity","attacker":"CLuaBaseEntity","victim":"CLuaBaseEntity",
    "instance":"CLuaInstance",
}

def param_type_hints(fn):
    if fn is None: return {}
    params=[p.strip() for p in fn.group(2).split(",") if p.strip()]
    return {p:KNOWN_PARAM_TYPES[p.lower()] for p in params if p.lower() in KNOWN_PARAM_TYPES}

def index(root: Path):
    rows=[]; scripts=root/"scripts/zones"
    if not scripts.is_dir(): return rows
    for f in sorted(scripts.rglob("npcs/*.lua")):
        text=f.read_text(encoding="utf-8",errors="replace"); funcs=list(FUNC_RE.finditer(text))
        for m in EVENT_RE.finditer(text):
            line=text.count("\n",0,m.start())+1; containing=None; idx=-1
            for i,fn in enumerate(funcs):
                if fn.start()<=m.start(): containing=fn; idx=i
                else: break
            start=containing.start() if containing else max(0,m.start()-1000)
            end=funcs[idx+1].start() if containing and idx+1<len(funcs) else min(len(text),m.end()+2000)
            hints=param_type_hints(containing)
            calls=[]
            for cm in CALL_RE.finditer(text,start,end):
                obj=cm.group(1); hint=hints.get(obj)
                calls.append({"object":obj,"method":cm.group(2),"line":text.count("\n",0,cm.start())+1,
                              "class_hint":hint,
                              "class_hint_source":"FUNCTION_PARAMETER_NAME" if hint else None})
            rows.append({"zone":f.parent.parent.name,"script":f.stem,"path":f.relative_to(root).as_posix(),
                         "event_id":int(m.group("id")),"event_expression":m.group("expr"),"line":line,
                         "function":containing.group(1) if containing else None,
                         "function_line":text.count("\n",0,containing.start())+1 if containing else None,
                         "calls":calls})
    return rows

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("root",type=Path); ap.add_argument("--json",type=Path)
    a=ap.parse_args(); sid=snapshot_id(a.root); rows=index(a.root)
    out={"schema":1,"source":str(a.root),"source_snapshot_id":sid,
         "analysis":{"analysis_id":"lua-event-index","analysis_type":"LUA_EVENT_SURFACE","source":str(a.root),
                     "status":"ANALYZED","source_snapshot_id":sid},
         "events":rows}
    data=json.dumps(out,indent=2,sort_keys=True)
    if a.json: a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(data+"\n",encoding="utf-8")
    else: print(data)
if __name__=="__main__": main()
