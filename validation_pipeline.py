#!/usr/bin/env python3
"""Normalize existing validator outputs into the generic Workbench ValidationResult shape."""
from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path

def run(script,args):
    p=subprocess.run([sys.executable,script,*args],capture_output=True,text=True)
    status="VERIFIED" if p.returncode==0 else "FAILED"
    return {"validation_id":f"{Path(script).stem}:{' '.join(args)}",
            "validation_type":Path(script).stem.upper(),
            "subject_id":" ".join(args) or script,"status":status,
            "notes":p.stdout.splitlines()[-10:]+p.stderr.splitlines()[-5:]}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("script"); ap.add_argument("args",nargs="*"); a=ap.parse_args()
    r=run(a.script,a.args); print(json.dumps({"schema":1,"validation":r},indent=2))
    if r["status"]=="FAILED": raise SystemExit(1)
if __name__=="__main__": raise SystemExit(main())
