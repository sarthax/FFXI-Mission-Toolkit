"""Read-only client code evidence report (JSON); no DLL patches or execution."""
from __future__ import annotations
import argparse
import json
import hashlib
import re
from pathlib import Path
from workbench.client.pol1_unpack import inspect_pol1, search_unpacked
from workbench.client.binary.address_candidates import address_candidates
from workbench.client.binary.code_evidence import decode_window


def wardrobe_command_evidence(binary: str) -> dict:
    """Compare bounded exact ASCII slash-command tokens in on-disk client data."""
    path = Path(binary)
    if path.stat().st_size > 64 * 1024 * 1024:
        return {"status": "SKIPPED", "reason": "File exceeds 64 MiB safety bound"}
    data = path.read_bytes()
    rows = []
    for number in range(1, 9):
        command = "/wardrobe" + (str(number) if number > 1 else "")
        pattern = re.compile(rb"(?<![a-zA-Z0-9_/])" + re.escape(command.encode("ascii")) + rb"(?![a-zA-Z0-9_])")
        offsets = [m.start() for _, m in zip(range(100), pattern.finditer(data))]
        rows.append({"command": command, "status": "VERIFIED_BYTES" if offsets else "UNKNOWN",
                     "offsets": offsets, "truncated": len(offsets) == 100})
    return {"status": "SCANNED", "sha256": hashlib.sha256(data).hexdigest(),
            "commands": rows,
            "warning": "An on-disk string hit does not demonstrate command handling; misses do not prove absence."}


def generate_report(binary: str, *, pattern: str | None = None,
                    target_rva: int | None = None, decode_rva: int | None = None) -> dict:
    result = {"binary_name": Path(binary).name, "unpacked": inspect_pol1(binary)}
    result["wardrobe_commands"] = wardrobe_command_evidence(binary)
    if pattern is not None:
        result["byte_search"] = search_unpacked(binary, pattern)
    if target_rva is not None:
        result["address_candidates"] = address_candidates(binary, target_rva)
    if decode_rva is not None:
        result["decode"] = decode_window(binary, decode_rva)
    result["disclaimer"] = (
        "Read-only research observations. No result proves a function boundary, "
        "runtime reachability, or support for additional inventory containers."
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", help="Local FFXiMain.dll path")
    parser.add_argument("--pattern", help="Exact space-delimited hex bytes")
    parser.add_argument("--target-rva", type=lambda x: int(x, 0))
    parser.add_argument("--decode-rva", type=lambda x: int(x, 0))
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    report = generate_report(args.binary, pattern=args.pattern,
                             target_rva=args.target_rva, decode_rva=args.decode_rva)
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"Research report written: {args.output}")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
