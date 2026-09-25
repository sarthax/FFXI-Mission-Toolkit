#!/usr/bin/env python3
"""Index Lua event handlers and API calls for capture/server backtracing."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from workbench.core.provenance import snapshot_id
EVENT_RE=re.compile(r'(?P<expr>startEvent|csid\\s*==|event\\s*==)\\s*\\(?\\s*(?P<id>\\d+)')
FUNC_RE=re.compile(r'(?m)^\s*function\s+([\w.:]+)\s*\(')
CALL_RE=re.compile(r'(?<![\w])([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(')
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
            calls=[{"object":cm.group(1),"method":cm.group(2),"line":text.count("\n",0,cm.start())+1} for cm in CALL_RE.finditer(text,start,end)]
            rows.append({"zone":f.parent.parent.name,"script":f.stem,"path":f.relative_to(root).as_posix(),"event_id":int(m.group("id")),"event_expression":m.group("expr"),"line":line,"function":containing.group(1) if containing else None,"function_line":text.count("\n",0,containing.start())+1 if containing else None,"calls":calls})
    return rows
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("root",type=Path); ap.add_argument("--json",type=Path)
    a=ap.parse_args(); sid=snapshot_id(a.root); rows=index(a.root)
    out={"schema":1,"source":str(a.root),"source_snapshot_id":sid,"analysis":{"analysis_id":"lua-event-index","analysis_type":"LUA_EVENT_SURFACE","source":str(a.root),"status":"ANALYZED","source_snapshot_id":sid},"events":rows}
    data=json.dumps(out,indent=2,sort_keys=True)
    if a.json: a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(data+"\n",encoding="utf-8")
    else: print(data)
if __name__=="__main__": main()
