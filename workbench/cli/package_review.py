"""Read-only CLI for consolidated Workbench package review status."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from workbench.migrations.package_review import package_review_summary_dict


def package_review(
    package_root: Path,
    target_root: Path,
) -> dict:
    return package_review_summary_dict(package_root,target_root)


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("package_root",type=Path)
    ap.add_argument("target_root",type=Path)
    args=ap.parse_args()

    result=package_review(args.package_root,args.target_root)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 2 if result["status"] in {"PACKAGE_FAILED","DRIFTED"} else 0


if __name__=="__main__":
    raise SystemExit(main())
