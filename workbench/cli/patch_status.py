"""Read-only CLI for Workbench patch-package lifecycle status."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from workbench.migrations.patch_lifecycle import assess_patch_lifecycle


def patch_status(
    package_root: Path,
    target_root: Path,
    *,
    apply_journal: Path | None = None,
) -> dict:
    result=assess_patch_lifecycle(
        package_root,
        target_root,
        apply_journal_path=apply_journal,
    )
    return asdict(result)


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("package_root",type=Path)
    ap.add_argument("target_root",type=Path)
    ap.add_argument("--apply-journal",type=Path,default=None)
    args=ap.parse_args()
    result=patch_status(
        args.package_root,
        args.target_root,
        apply_journal=args.apply_journal,
    )
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result["status"] not in {"PACKAGE_FAILED","DRIFTED"} else 2


if __name__=="__main__":
    raise SystemExit(main())
