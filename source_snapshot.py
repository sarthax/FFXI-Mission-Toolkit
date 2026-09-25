#!/usr/bin/env python3
"""Create reproducible source snapshot metadata for external server/client/tool roots."""
from __future__ import annotations
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path

IGNORE={".git",".venv","__pycache__","node_modules"}

def snapshot(root:Path):
    """Return a deterministic content snapshot; recorded_at is metadata, not part of the hash."""

    root=root.resolve()
    if not root.is_dir(): raise ValueError(f"Snapshot root is not a directory: {root}")
    h=hashlib.sha256(); count=0; total=0
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(part in IGNORE for part in p.parts): continue
        rel=p.relative_to(root).as_posix()
        data=p.read_bytes()
        h.update(rel.encode()); h.update(b"\0"); h.update(hashlib.sha256(data).digest())
        count+=1; total+=len(data)
    return {"schema":2,"snapshot_id":f"sha256:{h.hexdigest()}","root":str(root.resolve()),
            "fingerprint":h.hexdigest(),"file_count":count,"byte_count":total,
            "recorded_at":datetime.now(timezone.utc).isoformat()}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("root",type=Path); ap.add_argument("--json",type=Path); a=ap.parse_args()
    out=snapshot(a.root)
    if a.json: a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    else: print(json.dumps(out,indent=2))
if __name__=="__main__": raise SystemExit(main())
