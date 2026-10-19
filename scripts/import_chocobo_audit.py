#!/usr/bin/env python3
"""Import reviewed DSP audit evidence into the versioned Chocobo Raising domain.

Usage:
  python scripts/import_chocobo_audit.py reports/chocobo_dsp_audit.json --check
  python scripts/import_chocobo_audit.py reports/chocobo_dsp_audit.json --apply

Input is a JSON object with target_commit and findings. Each finding must have
name, dsp, evidence (non-empty list of references), and note. This importer
does NOT run probes, modify DSP, or infer pass/fail status from file existence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DOMAIN = Path(__file__).resolve().parents[1] / "src/workbench/domains/definitions.d/chocobo_raising.json"
ALLOWED = {"unknown", "present", "partial", "missing", "validated"}


def merge(domain: dict, report: dict) -> tuple[dict, list[str]]:
    if not isinstance(report, dict) or not isinstance(report.get("findings"), list):
        raise ValueError("report must contain a findings array")
    commit = report.get("target_commit")
    if not isinstance(commit, str) or len(commit.strip()) < 7:
        raise ValueError("target_commit (authoritative DSP commit SHA) is required")
    base = domain["domains"]["chocobo_raising"]
    mapping = {f["name"]: f for f in base["findings"]}
    seen = set()
    updates = []
    for item in report["findings"]:
        if not isinstance(item, dict):
            raise ValueError("finding must be an object")
        name = item.get("name")
        if name not in mapping or name in seen:
            raise ValueError(f"unknown or duplicate subsystem: {name!r}")
        seen.add(name)
        status = item.get("dsp")
        if status not in ALLOWED:
            raise ValueError(f"invalid DSP status for {name}: {status!r}")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(isinstance(x, str) and x.strip() for x in evidence):
            raise ValueError(f"non-empty evidence list required for {name}")
        note = item.get("note")
        if not isinstance(note, str) or not note.strip():
            raise ValueError(f"non-empty note required for {name}")
        if status == "validated" and not any(x.startswith(("test:", "capture:", "runtime:")) for x in evidence):
            raise ValueError(f"validated status needs test:, capture: or runtime: evidence for {name}")
        previous = mapping[name].get("dsp", "unknown")
        if previous != "unknown" and status == "unknown":
            raise ValueError(f"refusing to replace reviewed DSP status with unknown for {name}")
        if previous == "validated" and status != "validated":
            raise ValueError(f"refusing to downgrade validated status for {name}; use a reviewed manual correction")
        if previous == "validated" and mapping[name].get("dsp_target_commit") != commit.strip():
            raise ValueError(f"target commit changed for previously validated {name}; require manual revalidation")
        mapping[name]["dsp"] = status
        mapping[name]["dsp_evidence"] = evidence
        mapping[name]["dsp_note"] = note.strip()
        mapping[name]["dsp_target_commit"] = commit.strip()
        updates.append(name)
    return domain, updates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="validate and preview without writing")
    mode.add_argument("--apply", action="store_true", help="update the versioned domain JSON after review")
    args = parser.parse_args()
    data = json.loads(DOMAIN.read_text(encoding="utf-8"))
    report = json.loads(args.report.read_text(encoding="utf-8"))
    updated, names = merge(data, report)
    if args.apply:
        DOMAIN.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{'Updated' if args.apply else 'Checked'} {len(names)} findings: " + ", ".join(names))


if __name__ == "__main__":
    main()
