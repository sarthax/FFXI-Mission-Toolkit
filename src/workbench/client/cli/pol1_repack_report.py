"""Read-only, exact-hash-gated POL1 repack capacity report.

This command NEVER writes an EXE/DLL or a POL1 packed stream. Local copies of
licensed binaries are allowed as input, but no retail bytes are committed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from workbench.client.pol1_repack_experiment import assess_pol1_repack_fit
from workbench.client.pol1_unpack import Pol1Error


MAX_INPUT_FILE = 16 * 1024 * 1024


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path, help="Local, isolated research copy of FFXiMain.dll")
    parser.add_argument("--expected-sha256", required=True, help="Required full original SHA-256")
    args = parser.parse_args()
    expected = args.expected_sha256.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        parser.error("--expected-sha256 must contain exactly 64 hexadecimal characters")
    try:
        if args.binary.stat().st_size > MAX_INPUT_FILE:
            parser.error("binary exceeds 16 MiB read-only experiment limit")
        image = args.binary.read_bytes()
    except OSError as exc:
        parser.error(f"unable to read binary: {exc}")
    actual = hashlib.sha256(image).hexdigest()
    if actual != expected:
        parser.error(f"exact-build fingerprint mismatch: observed {actual}")
    try:
        report = assess_pol1_repack_fit(image)
    except (ValueError, Pol1Error) as exc:
        parser.error(f"unable to assess POL1 repack feasibility: {exc}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
