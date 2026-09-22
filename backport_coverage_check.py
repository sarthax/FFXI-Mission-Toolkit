"""
backport_coverage_check.py -- regression test for backport_lua_convert.py / data/dsp_namespace_map.json.

Runs the converter against EVERY .lua file under the real Topaz checkout's scripts/zones tree (not
just the zones a particular mission package happens to touch) and reports any line that still
mentions `tpz.` in the converted output without being covered by a flag -- see
ConversionResult.unflagged_leftovers() in backport_lua_convert.py for exactly what counts as a gap.

A non-empty "unflagged" list means the namespace map or converter has a real coverage hole: either
a tpz.* family that needs a new entry (checked against real DSP source, same discipline as every
existing entry), or a converter rule that isn't matching text it should. This mirrors the manual
stress test run once against 6 zones outside the Nyzul package (see STRESS_TEST_FINDINGS.md) --
run this any time data/dsp_namespace_map.json or backport_lua_convert.py changes, and any time a
new zone's files are about to be converted for a package, to catch gaps before they ship silently.

Usage:
    py -3 backport_coverage_check.py                  # full zones/ tree, summary only
    py -3 backport_coverage_check.py --zone Bhaflau_Remnants Ilrusi_Atoll
    py -3 backport_coverage_check.py --report out.md   # also write a full Markdown report
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sys

import backport_lua_convert as blc
import settings


def iter_lua_files(topaz_root: pathlib.Path, zones: list[str] | None):
    zones_dir = topaz_root / "scripts" / "zones"
    if zones:
        roots = [zones_dir / z for z in zones]
    else:
        roots = [zones_dir]
    for root in roots:
        if not root.exists():
            print(f"WARNING: {root} does not exist, skipping", file=sys.stderr)
            continue
        yield from sorted(root.rglob("*.lua"))


def run(topaz_root: pathlib.Path, zones: list[str] | None):
    ns_map = blc.load_map()
    files_processed = 0
    files_with_flags = 0
    files_with_unflagged = 0
    flag_reason_counts: collections.Counter = collections.Counter()
    unflagged_token_counts: collections.Counter = collections.Counter()
    unflagged_detail: list[tuple[str, int, str]] = []
    errors: list[tuple[str, str]] = []

    for f in iter_lua_files(topaz_root, zones):
        rel = f.relative_to(topaz_root)
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            errors.append((str(rel), str(e)))
            continue

        res = blc.convert(text, zone_table=None, id_shape=None, id_file_hint=None, ns_map=ns_map)
        files_processed += 1
        if res.flagged:
            files_with_flags += 1
            for fl in res.flagged:
                for reason in fl["reasons"]:
                    flag_reason_counts[reason] += 1

        leftovers = res.unflagged_leftovers()
        if leftovers:
            files_with_unflagged += 1
            for lo in leftovers:
                unflagged_detail.append((str(rel), lo["line"], lo["text"]))
                for tok in re.findall(r"tpz\.[A-Za-z_][A-Za-z0-9_.]*", lo["text"]):
                    unflagged_token_counts[tok.split("(")[0]] += 1

    return {
        "files_processed": files_processed,
        "files_with_flags": files_with_flags,
        "files_with_unflagged": files_with_unflagged,
        "flag_reason_counts": flag_reason_counts,
        "unflagged_token_counts": unflagged_token_counts,
        "unflagged_detail": unflagged_detail,
        "errors": errors,
    }


def print_summary(result: dict):
    print(f"Files processed:        {result['files_processed']}")
    print(f"Files with known flags: {result['files_with_flags']}")
    print(f"Files with GAPS:        {result['files_with_unflagged']}")
    if result["errors"]:
        print(f"Read errors:            {len(result['errors'])}")

    print()
    print("=== Top known-flag reasons (expected, working as intended) ===")
    for reason, cnt in result["flag_reason_counts"].most_common(15):
        print(f"{cnt:5d}  {reason}")

    if result["unflagged_token_counts"]:
        print()
        print("=== GAP tokens (unflagged tpz.* leftovers -- namespace map needs these) ===")
        for tok, cnt in result["unflagged_token_counts"].most_common(50):
            print(f"{cnt:5d}  {tok}")
        print()
        print("=== Sample gap lines (first 30) ===")
        for rel, line, text in result["unflagged_detail"][:30]:
            print(f"{rel}:{line}: {text}")
    else:
        print()
        print("No gaps found -- every tpz.* reference in the converted output is flagged for review.")


def write_report(result: dict, out_path: pathlib.Path):
    lines = [
        "# Backport Coverage Report",
        "",
        f"Files processed: {result['files_processed']}",
        f"Files with known flags: {result['files_with_flags']}",
        f"Files with unflagged gaps: {result['files_with_unflagged']}",
        "",
        "## Known-flag reasons",
        "",
    ]
    for reason, cnt in result["flag_reason_counts"].most_common():
        lines.append(f"- `{cnt}` &nbsp; {reason}")
    lines.append("")
    lines.append("## Gap tokens (namespace map needs these)")
    lines.append("")
    if not result["unflagged_token_counts"]:
        lines.append("None -- full coverage as of this run.")
    else:
        for tok, cnt in result["unflagged_token_counts"].most_common():
            lines.append(f"- `{cnt}` &nbsp; `{tok}`")
        lines.append("")
        lines.append("## Gap lines")
        lines.append("")
        for rel, line, text in result["unflagged_detail"]:
            lines.append(f"- `{rel}:{line}`: `{text}`")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote report to {out_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zone", nargs="*", default=None, help="Limit to these zone folder names (default: all zones)")
    ap.add_argument("--report", type=str, default=None, help="Write a full Markdown report to this path")
    args = ap.parse_args()

    topaz_root = settings.get_topaz_root()
    result = run(topaz_root, args.zone)
    print_summary(result)
    if args.report:
        write_report(result, pathlib.Path(args.report))


if __name__ == "__main__":
    main()
