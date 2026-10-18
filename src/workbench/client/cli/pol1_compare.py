"""Compare two read-only POL1 report JSON documents by verified evidence."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

COMMANDS = ["/wardrobe"] + [f"/wardrobe{i}" for i in range(2, 9)]


def compare_reports(old: dict, new: dict) -> dict:
    def commands(report: dict) -> dict:
        rows = report.get("wardrobe_commands", {}).get("commands", [])
        return {row["command"]: row for row in rows if row.get("command") in COMMANDS}
    left, right = commands(old), commands(new)
    comparisons = []
    for command in COMMANDS:
        a, b = left.get(command), right.get(command)
        if not a or not b:
            status = "NOT_MEASURED"
        elif a.get("status") == b.get("status"):
            status = "UNCHANGED"
        else:
            status = "DIFFERENT_EVIDENCE"
        comparisons.append({"command": command, "old": a.get("status") if a else None,
                            "new": b.get("status") if b else None, "result": status})
    old_img, new_img = old.get("unpacked", {}), new.get("unpacked", {})
    return {"old_sha256": old.get("wardrobe_commands", {}).get("sha256"),
            "new_sha256": new.get("wardrobe_commands", {}).get("sha256"),
            "old_unpacked_sha256": old_img.get("sha256"),
            "new_unpacked_sha256": new_img.get("sha256"),
            "identical_decoded_code": bool(old_img.get("sha256") and old_img.get("sha256") == new_img.get("sha256")),
            "command_comparison": comparisons,
            "warning": "Different strings or code hashes are build differences, not evidence that wardrobe 5-8 can be backported."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("older", type=Path)
    parser.add_argument("newer", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare_reports(json.loads(args.older.read_text(encoding="utf-8")),
                             json.loads(args.newer.read_text(encoding="utf-8")))
    output = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
