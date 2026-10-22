"""Print metadata-only 2019 client wardrobe compatibility evidence as JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from workbench.client.pol1_unpack import Pol1Error
from workbench.client.wardrobe_2019_audit import MAX_INPUT_BYTES, audit_2019_wardrobe


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path, help="Exact archived original FFXiMain.dll; read-only")
    args = parser.parse_args()
    try:
        if args.binary.stat().st_size > MAX_INPUT_BYTES:
            parser.error("input file exceeds 16 MiB bound")
        report = audit_2019_wardrobe(args.binary.read_bytes())
    except (OSError, Pol1Error, ValueError) as exc:
        parser.error(f"2019 static audit failed: {exc}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
