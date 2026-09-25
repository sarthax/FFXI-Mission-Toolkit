#!/usr/bin/env python3
"""Index packet definitions into generic Workbench relationships.

This is evidence mapping, not semantic handler inference. It records opcode definitions as packet
artifacts and can optionally inspect a server source tree for explicit opcode/handler references.
"""
from __future__ import annotations
import argparse,json,re
from pathlib import Path

# Only explicit dispatch/registration patterns become HANDLED_BY. Generic opcode references remain REFERENCES.
SWITCH_CASE_RE=re.compile(r'\\bcase\\s+(0x[0-9A-Fa-f]+|\\d+)\\s*:',re.I)
DISPATCH_RE=re.compile(r'\\b(?:register|add|set)[A-Za-z_]*(?:Handler|PacketHandler|CommandHandler)\\s*\\(\\s*(0x[0-9A-Fa-f]+|\\d+)\\s*,\\s*&?([A-Za-z_][A-Za-z0-9_:]*)',re.I)

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
    known={str(op.get("opcode","")) for op in opcodes if op.get("opcode")}
    normalized={}
    for token in known:
        try: normalized[token.lower()]=int(token,0)
        except ValueError:
            try: normalized[token.lower()]=int(token,16)
            except ValueError: pass
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in {".cpp",".h",".hpp",".cc",".cxx"}: continue
        t=p.read_text(encoding="utf-8",errors="replace")
        for n,line in enumerate(t.splitlines(),1):
            m=SWITCH_CASE_RE.search(line)
            if m:
                try: value=int(m.group(1),0)
                except ValueError: continue
                for tok,val in normalized.items():
                    if val==value:
                        edges.append({"source_node":f"packet:{tok}","target_node":f"cpp:{p.relative_to(root).as_posix()}:{n}",
                                      "relationship":"HANDLED_BY","confidence":"VERIFIED","status":"DISCOVERED",
                                      "source_location":f"{p}:{n}","notes":["Explicit switch/case opcode dispatch; downstream handler resolution is not inferred."]})
            m=DISPATCH_RE.search(line)
            if m:
                try: value=int(m.group(1),0)
                except ValueError: continue
                for tok,val in normalized.items():
                    if val==value:
                        edges.append({"source_node":f"packet:{tok}","target_node":f"cpp-symbol:{m.group(2)}",
                                      "relationship":"HANDLED_BY","confidence":"VERIFIED","status":"DISCOVERED",
                                      "source_location":f"{p}:{n}","notes":["Explicit packet-handler registration pattern matched."]})
            for tok,val in normalized.items():
                if re.search(rf'(?<![A-Za-z0-9_])(?:0x)?{re.escape(tok)}(?![A-Za-z0-9_])',line,re.I):
                    if not any(e["source_node"]==f"packet:{tok}" and e["source_location"]==f"{p}:{n}" for e in edges):
                        edges.append({"source_node":f"packet:{tok}","target_node":f"cpp:{p.relative_to(root).as_posix()}:{n}",
                                      "relationship":"REFERENCES","confidence":"INFERRED","status":"DISCOVERED",
                                      "source_location":f"{p}:{n}","notes":["Opcode token occurrence only; not proof this code is the runtime handler."]})
    return edges

def self_test():
    """Exercise only deterministic dispatch patterns with a tiny synthetic source fixture."""
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as td:
        root=Path(td)
        packet_db=root/"packets.xml"
        server=root/"server.cpp"
        packet_db.write_text('<packet opcode="0x02A" />', encoding="utf-8")
        server.write_text('switch (opcode) {\\n  case 0x02A: handle_dialog(); break;\\n}\\n', encoding="utf-8")
        ops=index_packet_db(packet_db)
        edges=index_server(root,[ops[0]])
        assert any(e["relationship"]=="HANDLED_BY" and e["confidence"]=="VERIFIED" for e in edges)
        assert any(e["relationship"]=="REFERENCES" for e in edges) is False


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--self-test",action="store_true"); ap.add_argument("packet_db",type=Path,nargs="?"); ap.add_argument("--server-root",type=Path); ap.add_argument("--json",type=Path); a=ap.parse_args()
    if a.self_test:\n        self_test(); print("packet_opcode_index self-test: PASS"); return\n    if not a.packet_db: ap.error("packet_db is required unless --self-test")\n    ops=index_packet_db(a.packet_db)
    edges=index_server(a.server_root,ops) if a.server_root else []
    out={"schema":2,"analysis":{"analysis_id":"packet-opcode-index","analysis_type":"PACKET_OPCODE_SURFACE","source":str(a.packet_db),"status":"ANALYZED"},
         "opcodes":ops,"edges":edges}
    s=json.dumps(out,indent=2)+"\n"
    if a.json: a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(s,encoding="utf-8")
    else: print(s)
if __name__=="__main__": raise SystemExit(main())
