#!/usr/bin/env python3
"""Compare two precomputed client binary indexes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from workbench.client.binary_diff import diff_binary_indexes


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("left",type=Path)
    ap.add_argument("right",type=Path)
    ap.add_argument("--max-items",type=int,default=500)
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()

    left=json.loads(args.left.read_text(encoding="utf-8"))
    right=json.loads(args.right.read_text(encoding="utf-8"))
    result=diff_binary_indexes(left,right,max_items=args.max_items)
    text=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text,encoding="utf-8")
    print(text,end="")


if __name__=="__main__":
    main()
