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
    depth_group = parser.add_mutually_exclusive_group()
    depth_group.add_argument("--search-depth", type=int, choices=(16, 64, 128), default=64,
                             help="Bounded encoder match candidates per position (default 64)")
    depth_group.add_argument("--compare-depths", action="store_true",
                             help="Evaluate 16, 64 and 128 in one read-only JSON summary")
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
        if args.compare_depths:
            evaluations = [assess_pol1_repack_fit(image, search_depth=depth) for depth in (16, 64, 128)]
            reports = [{
                "depth": entry["encoder_search_depth"],
                "candidate_encoded_size": entry["candidate_encoded_size"],
                "headroom_bytes": entry["headroom_bytes"],
                "status": entry["status"],
                "in_memory_decoded_roundtrip": entry["in_memory_decoded_roundtrip"],
                "protected_suffix_unchanged": entry["protected_suffix_unchanged"],
            } for entry in evaluations]
            base = evaluations[0]
            report = {
                "source_sha256": base["source_sha256"],
                "decoded_sha256": base["decoded_sha256"],
                "decoded_size": base["decoded_size"],
                "pol1_raw_section_size": base["pol1_raw_section_size"],
                "original_stream_consumed_bytes": base["original_stream_consumed_bytes"],
                "protected_suffix_bytes": base["protected_suffix_bytes"],
                "entrypoint_section_offset": base["entrypoint_section_offset"],
                "safe_stream_budget_bytes": base["safe_stream_budget_bytes"],
                "method": "read-only experimental original-stream-boundary comparison",
                "results": reports,
                "best_fit_depth": min(
                    (x for x in reports if x["status"] == "FITS_ORIGINAL_STREAM_BUDGET"),
                    key=lambda x: (x["candidate_encoded_size"], x["depth"]),
                    default=None,
                ),
                "caution": "Best fit is compressed-prefix arithmetic, not PE loader or launcher acceptance.",
            }
        else:
            report = assess_pol1_repack_fit(image, search_depth=args.search_depth)
    except (ValueError, Pol1Error) as exc:
        parser.error(f"unable to assess POL1 repack feasibility: {exc}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
