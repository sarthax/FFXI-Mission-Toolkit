#!/usr/bin/env python3
"""Index packet definitions into generic Workbench relationships.

This is evidence mapping, not semantic handler inference. It records opcode definitions as packet
artifacts and can optionally inspect a server source tree for explicit opcode/handler references.
"""
from __future__ import annotations
import argparse,json,re
from pathlib import Path

OP_RE=re.compile(r'\b(?:0x)?([0-9A-Fa-f]{2,4})\b')
HANDLER_RE=re.compile(r'\b(?:opcode|packet|command|type)\s*\(?\s*([0-9A-Fa-fx]+)',re.I)

def index_packet_db(path:Path):
    text=path.read_text(encoding="utf-8",errors="replace")
    rows=[]
    for m in re.finditer(r'<packet[^>]*?(?:opcode|id)=["\']([^"\']+)["\'][^>]*>',text,re.I):
        rows.append({"opcode":m.group(1),"location":f"{path}:{text.count(chr(10),0,m.start())+1}"})
    if not rows:
        for m in re.finditer(r'GP_(?:CLI|SERV)_COMMAND_[A-Z0-9_]+',text):
            rows.append({"symbol":m.group(),"location":f"{path}:{text.count(chr(10),0,m.start())+1}"})
    return rows

def index_server(root:Path,opcodes):
    edges=[]
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in {".cpp",".h",".hpp",".cc",".cxx"}: continue
        t=p.read_text(encoding="utf-8",errors="replace")
        for op in opcodes:
            token=str(op.get("opcode",""))
            if token and token in t:
                line=t[:t.find(token)].count("\n")+1
                edges.append({"source_node":f"packet:{token}","target_node":f"cpp:{p.relative_to(root).as_posix()}:{line}",
                              "relationship":"REFERENCES","confidence":"INFERRED",
                              "source_location":f"{p}:{line}",
                              "notes":["Opcode token occurrence only; not proof this code is the runtime handler."]})
    return edges

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("packet_db",type=Path); ap.add_argument("--server-root",type=Path); ap.add_argument("--json",type=Path); a=ap.parse_args()
    ops=index_packet_db(a.packet_db)
    edges=index_server(a.server_root,ops) if a.server_root else []
    out={"schema":1,"analysis":{"analysis_id":"packet-opcode-index","analysis_type":"PACKET_OPCODE_SURFACE","source":str(a.packet_db),"status":"ANALYZED"},
         "opcodes":ops,"edges":edges}
    s=json.dumps(out,indent=2)+"\n"
    if a.json: a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(s,encoding="utf-8")
    else: print(s)
if __name__=="__main__": raise SystemExit(main())
