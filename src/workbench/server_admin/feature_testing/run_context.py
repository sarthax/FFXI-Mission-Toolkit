"""#1408: derive ``environment_fingerprint`` and ``fixture_context`` from facts a runner already recorded.

Offline and read-only: it reads a report file and writes a NEW report file. It runs nothing, contacts nothing and
never touches a result database; import the new file with ``importer`` (into a scratch database when re-importing
old receipts). Nothing is guessed: a field is added only when every input it needs is present in the report's own
``evidence.observations``; otherwise it is left out and Compare runs reports it as missing.

Definitions (OWNER DECISION PENDING, smallest reversible version; see docs/workbench/RUN_CONTEXT_1408.md):
- ``environment_fingerprint`` = ``headless_dll_sha256=<64 hex>;headless_tree=<clean|dirty:12 hex of the sha256 of the
  sorted dirty-file lines>``. Source: ``observations.provenance`` written by the observation runner. DSP, headless
  and toolkit commits are separate columns already, and the DSP working tree/database state is NOT recorded.
- ``fixture_context`` = ``character_id=<id>;zone_id=<id>;stored_furnishing_item_ids=<sorted comma list>``. Source:
  ``observations.snapshot`` and ``observations.stored_furnishing_item_ids``. Only meaningful for the MOG-09 receipt
  shape; other report shapes get no fixture_context.
Equality is the only compatibility rule, so two runs on different characters or different headless builds are
NOT_COMPARABLE by design until the owner says which of those differences may be ignored.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re

_SHA256 = re.compile(r"[0-9a-f]{64}")
_MAX = 256


def environment_fingerprint(observations: object) -> str | None:
    prov = observations.get("provenance") if isinstance(observations, dict) else None
    if not isinstance(prov, dict):
        return None
    digest, dirty = prov.get("headless_dll_sha256"), prov.get("headless_dirty_files")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        return None
    if not isinstance(dirty, list) or not all(isinstance(x, str) for x in dirty):
        return None
    tree = "clean" if not dirty else "dirty:" + hashlib.sha256(
        "\n".join(sorted(x.strip() for x in dirty)).encode("utf-8")).hexdigest()[:12]
    return f"headless_dll_sha256={digest};headless_tree={tree}"


def fixture_context(observations: object) -> str | None:
    if not isinstance(observations, dict):
        return None
    snap, items = observations.get("snapshot"), observations.get("stored_furnishing_item_ids")
    if not isinstance(snap, dict) or not isinstance(items, list):
        return None
    cid, zone = snap.get("id"), snap.get("zone")
    if type(cid) is not int or type(zone) is not int or not all(type(i) is int for i in items):
        return None
    text = f"character_id={cid};zone_id={zone};stored_furnishing_item_ids={','.join(str(i) for i in sorted(items))}"
    return text if len(text) <= _MAX else None


def add_run_context(report: dict) -> tuple[dict, list[str]]:
    """A copy of ``report`` with derivable context fields added; existing values are never overwritten.

    Returns ``(new_report, notes)``; ``notes`` lists each row/field left out and why.
    """
    out, notes = copy.deepcopy(report), []
    for row in out.get("results", []):
        evidence = row.get("evidence")
        if not isinstance(evidence, dict):
            continue
        name = f"{row.get('run_id')}/{row.get('case_id')}"
        for key, fn in (("environment_fingerprint", environment_fingerprint), ("fixture_context", fixture_context)):
            if key in evidence:
                notes.append(f"{name}: {key} already present, kept")
                continue
            value = fn(evidence.get("observations"))
            if value is None:
                notes.append(f"{name}: {key} not derivable from recorded observations, left out")
            else:
                evidence[key] = value
    return out, notes


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a copy of a report with run context fields derived")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.resolve() == args.report.resolve():
        raise SystemExit("--out must differ from --report")
    new, notes = add_run_context(json.loads(args.report.read_text(encoding="utf-8")))
    args.out.write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")
    print("\n".join(notes) or "all fields derived")


if __name__ == "__main__":
    main()
