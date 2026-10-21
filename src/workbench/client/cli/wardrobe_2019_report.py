"""Read-only JSON report for exactly the archived 2019 FFXiMain.dll build."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from workbench.client.pol1_unpack import Pol1Error
from workbench.client.wardrobe_2019_audit import inspect_2019_wardrobe


def main() -> int:
    parser = argparse.ArgumentParser(
        description="2019 FFXiMain exact-hash wardrobe capacity and store collision audit (read-only)"
    )
    parser.add_argument("binary", type=Path, help="Untouched 2019 archival FFXiMain.dll")
    args = parser.parse_args()
    try:
        report = inspect_2019_wardrobe(args.binary)
    except (OSError, Pol1Error, UnicodeError, ValueError) as exc:
        parser.error(f"cannot establish exact-build evidence: {exc}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
