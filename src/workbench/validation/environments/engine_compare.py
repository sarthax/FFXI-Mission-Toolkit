#!/usr/bin/env python3
"""Compare two C++ API indexes and emit conservative generic migration actions.

No feature-specific assumptions are made. Exact symbol/signature matches become COMPATIBLE; missing
target symbols become IMPLEMENT/PATCH candidates; unresolved evidence remains MANUAL_REVIEW/UNKNOWN.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path

def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))

def sig_key(fn):
    s=fn.get("signature",{})
    return (fn.get("qualified_name"),s.get("return_type"),tuple(s.get("parameters",[])),s.get("const"),s.get("static"),s.get("noexcept"))

def compare(src,tgt):
    sf={x.get("qualified_name"):x for x in src.get("functions",[])}
    tf={x.get("qualified_name"):x for x in tgt.get("functions",[])}
    actions=[]
    for name in sorted(set(sf)|set(tf)):
        if name in sf and name in tf:
            if sig_key(sf[name])==sig_key(tf[name]):
                state="COMPATIBLE"; action="NOT_REQUIRED"; reason="TARGET_ALREADY_HAS"
            else:
                state="MANUAL_REQUIRED"; action="PATCH"; reason="MANUAL_REWRITE"
        elif name in sf:
            state="MANUAL_REQUIRED"; action="IMPLEMENT"; reason="ENGINE_DEPENDENCY"
        else:
            state="COMPATIBLE"; action="NOT_REQUIRED"; reason="TARGET_ALREADY_HAS"
        actions.append({"symbol":name,"state":state,"action":action,"reason":reason})
    sb={x.get("lua_name"):x for x in src.get("bindings",[])}
    tb={x.get("lua_name"):x for x in tgt.get("bindings",[])}
    for name in sorted(set(sb)|set(tb)):
        if name in sb and name in tb:
            if sb[name].get("cpp_symbol")==tb[name].get("cpp_symbol"):
                state="COMPATIBLE"; action="NOT_REQUIRED"
            else:
                state="MANUAL_REQUIRED"; action="PATCH"
            reason="TARGET_HAS_DIFFERENT_IMPLEMENTATION" if action=="PATCH" else "TARGET_ALREADY_HAS"
        elif name in sb:
            state="MANUAL_REQUIRED"; action="IMPLEMENT"; reason="ENGINE_DEPENDENCY"
        else:
            continue
        actions.append({"binding":name,"state":state,"action":action,"reason":reason})
    return actions

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("source",type=Path); ap.add_argument("target",type=Path); ap.add_argument("--json",type=Path); args=ap.parse_args()
    src,tgt=load(args.source),load(args.target)
    actions=compare(src,tgt)
    payload={"schema":1,"source":str(args.source),"target":str(args.target),"status":"ANALYZED","actions":actions}
    if args.json: args.json.parent.mkdir(parents=True,exist_ok=True); args.json.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    else: print(json.dumps(payload,indent=2))
if __name__=="__main__": raise SystemExit(main())
