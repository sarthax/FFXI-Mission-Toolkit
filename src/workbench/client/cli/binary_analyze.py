#!/usr/bin/env python3
"""CLI for bounded read-only client binary byte/xref/function-candidate analysis."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from workbench.client.binary_deep import byte_search, function_candidates, import_thunk_refs, xrefs


def _int(value: str) -> int:
    return int(value,0)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("binary",type=Path)
    sub=ap.add_subparsers(dest="command",required=True)

    p=sub.add_parser("pattern")
    p.add_argument("pattern")
    p.add_argument("--section")
    p.add_argument("--executable-only",action="store_true")
    p.add_argument("--max-matches",type=int,default=500)
    p.add_argument("--context-bytes",type=int,default=8)

    x=sub.add_parser("xrefs")
    target=x.add_mutually_exclusive_group(required=True)
    target.add_argument("--rva",type=_int)
    target.add_argument("--va",type=_int)
    target.add_argument("--offset",type=_int)
    x.add_argument("--all-sections",action="store_true")
    x.add_argument("--no-pointers",action="store_true")
    x.add_argument("--max-results",type=int,default=2000)

    f=sub.add_parser("functions")
    f.add_argument("--max-candidates",type=int,default=5000)

    imp=sub.add_parser("import-refs")
    imp.add_argument("--max-results",type=int,default=2000)

    args=ap.parse_args()
    if args.command=="pattern":
        result=byte_search(args.binary,args.pattern,section=args.section,
            executable_only=args.executable_only,max_matches=args.max_matches,
            context_bytes=args.context_bytes)
    elif args.command=="xrefs":
        result=xrefs(args.binary,rva=args.rva,va=args.va,offset=args.offset,
            executable_only=not args.all_sections,include_pointers=not args.no_pointers,
            max_results=args.max_results)
    elif args.command=="import-refs":
        result=import_thunk_refs(args.binary,max_results=args.max_results)
    else:
        result=function_candidates(args.binary,max_candidates=args.max_candidates)
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
