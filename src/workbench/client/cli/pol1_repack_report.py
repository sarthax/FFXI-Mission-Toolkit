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

from workbench.client.pol1_repack_experiment import SEARCH_DEPTHS, assess_pol1_repack_fit
from workbench.client.pol1_unpack import Pol1Error


MAX_INPUT_FILE = 16 * 1024 * 1024


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path, help="Local, isolated research copy of FFXiMain.dll")
    parser.add_argument("--expected-sha256", required=True, help="Required full original SHA-256")
    depth_group = parser.add_mutually_exclusive_group()
    depth_group.add_argument("--search-depth", type=int, choices=SEARCH_DEPTHS, default=64,
                             help="Bounded encoder match candidates per position (default 64)")
    depth_group.add_argument("--compare-depths", action="store_true",
                             help="Evaluate 16, 64 and 128 in one read-only JSON summary")
    depth_group.add_argument("--compare-improved", action="store_true",
                             help="Read-only comparison: deep greedy 256/512/1024, lazy 128/256")
    parser.add_argument("--lazy-match", action="store_true",
                        help="Use bounded one-byte lookahead in a single-depth experiment")
    args = parser.parse_args()
    if args.compare_improved and args.lazy_match:
        parser.error("--compare-improved selects its own explicit lazy and non-lazy modes")
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
        if args.compare_depths or args.compare_improved:
            configs = (
                [(256, False), (512, False), (1024, False), (128, True), (256, True)]
                if args.compare_improved else
                [(16, args.lazy_match), (64, args.lazy_match), (128, args.lazy_match)]
            )
            evaluations = [
                assess_pol1_repack_fit(
                    image, search_depth=depth, lazy_match=lazy
                )
                for depth, lazy in configs
            ]
            reports = [{
                "depth": entry["encoder_search_depth"],
                "lazy_match": entry["encoder_lazy_match"],
                "candidate_encoded_size": entry["candidate_encoded_size"],
                "headroom_bytes": entry["headroom_bytes"],
                "status": entry["status"],
                "in_memory_decoded_roundtrip": entry["in_memory_decoded_roundtrip"],
                "protected_suffix_unchanged": entry["protected_suffix_unchanged"],
                "candidate_sha256": entry["candidate_sha256"],
                "candidate_matches_original_stream": entry["candidate_matches_original_stream"],
                "candidate_common_prefix_bytes": entry["candidate_common_prefix_bytes"],
                "candidate_decoder_termination": entry["candidate_decoder_termination"],
            } for entry in evaluations]
            base = evaluations[0]
            report = {
                "source_sha256": base["source_sha256"],
                "decoded_sha256": base["decoded_sha256"],
                "decoded_size": base["decoded_size"],
                "pol1_raw_section_size": base["pol1_raw_section_size"],
                "pol1_raw_section_isolated": base["pol1_raw_section_isolated"],
                "original_stream_consumed_bytes": base["original_stream_consumed_bytes"],
                "original_decoder_termination": base["original_decoder_termination"],
                "bytes_between_stream_end_and_entrypoint": base["bytes_between_stream_end_and_entrypoint"],
                "original_stream_sha256": base["original_stream_sha256"],
                "protected_suffix_bytes": base["protected_suffix_bytes"],
                "entrypoint_section_offset": base["entrypoint_section_offset"],
                "entrypoint_in_pol1": base["entrypoint_in_pol1"],
                "entrypoint_boundary_safe": base["entrypoint_boundary_safe"],
                "safe_stream_budget_bytes": base["safe_stream_budget_bytes"],
                "method": "read-only experimental original-stream-boundary comparison",
                "comparison_mode": "improved" if args.compare_improved else "baseline",
                "results": reports,
                "best_fit_depth": min(
                    (x for x in reports if x["status"] == "FITS_ORIGINAL_STREAM_BUDGET"),
                    key=lambda x: (x["candidate_encoded_size"], x["depth"], x["lazy_match"]),
                    default=None,
                ),
                "caution": "Best fit is compressed-prefix arithmetic, not PE loader or launcher acceptance.",
            }
        else:
            report = assess_pol1_repack_fit(
                image, search_depth=args.search_depth, lazy_match=args.lazy_match
            )
    except (ValueError, Pol1Error) as exc:
        parser.error(f"unable to assess POL1 repack feasibility: {exc}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
