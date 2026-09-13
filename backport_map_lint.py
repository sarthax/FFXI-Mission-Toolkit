#!/usr/bin/env python3
"""
backport_map_lint.py -- enforces that every entry in data/dsp_namespace_map.json says which real
DSP codebase it was actually checked against, so the mistake that cost an entire session's worth
of rework (auditing against D:\\Claude\\landsandboat-reference while the real production target is
D:\\Claude\\old-dsp-reference, silently, for weeks of accumulated map entries) can't quietly recur.

The map grew a `checked_against`-by-convention pattern this session (the `old_dsp_reference_
verified_2026-09-13`/`namespace_family_index_2026-09-13`/`per_zone_flat_id_shape_findings_
2026-09-13` sections all declare it in their own `_readme`), but nothing enforces a NEW entry
actually follows it. This does:

1. Every dated top-level section (matched by a `_20\\d\\d-\\d\\d-\\d\\d` suffix in its key name --
   the convention every real correction/audit section this session used) must have its own
   `_readme` explaining what it covers and what it was checked against.
2. Every entry under `method_renames`/`simple_families`/`reshaped_families` (the older, pre-
   correction sections -- landsandboat-era by default, per the map's own top-level
   `_CORRECTION_NOTICE`) must still carry a `source`/`evidence` field (the pre-existing discipline)
   -- a regression check, not a new rule.
3. Flags (does not fail on) any such entry whose own `source` string mentions a LandSandBoat-shaped
   file path (`lua_base_entity.cpp`, with the underscore) with no corresponding override for that
   same name in `old_dsp_reference_verified_2026-09-13` -- these are real, valid research, just not
   yet re-checked against the actual production target, worth a visible reminder every run rather
   than silently trusting a name that might not carry over.

Usage:
    py -3 backport_map_lint.py
"""
from __future__ import annotations

import re
import sys

import backport_lua_convert as blc

DATED_SECTION_RE = re.compile(r"_\d{4}-\d{2}-\d{2}$")
LSB_FILE_MARKER = "lua_base_entity.cpp"  # landsandboat's real filename (has the underscore)
LEGACY_SECTIONS = ("method_renames", "simple_families", "reshaped_families")


def lint() -> int:
    m = blc.load_map()
    errors: list[str] = []
    warnings: list[str] = []

    for key, value in m.items():
        if key.startswith("_") or not isinstance(value, dict):
            continue
        if DATED_SECTION_RE.search(key):
            if "_readme" not in value:
                errors.append(f"section '{key}' has a dated name but no '_readme' explaining "
                               f"what it covers / what it was checked against")

    verified_old_dsp = set(m.get("old_dsp_reference_verified_2026-09-13", {}).keys()) - {"_readme"}

    for section in LEGACY_SECTIONS:
        entries = m.get(section, {})
        for name, spec in entries.items():
            if name.startswith("_") or not isinstance(spec, dict):
                continue
            # `note` is accepted too -- a documented alias of another already-evidenced family
            # (e.g. simple_families.keyItem: "tpz.keyItem is a Topaz-side alias of tpz.ki, same
            # DSP mapping applies") doesn't need its own duplicate evidence citation.
            if not spec.get("source") and not spec.get("evidence") and not spec.get("note"):
                errors.append(f"{section}.{name} has no 'source'/'evidence'/'note' field -- every "
                               f"entry must cite real DSP source (or explain why it doesn't need "
                               f"its own), per this map's own long-standing rule")
                continue
            source_text = str(spec.get("source", "")) + str(spec.get("evidence", ""))
            if LSB_FILE_MARKER in source_text and name not in verified_old_dsp:
                warnings.append(f"{section}.{name} was checked against a LandSandBoat-shaped path "
                                 f"({LSB_FILE_MARKER}) and has no override in "
                                 f"old_dsp_reference_verified_2026-09-13 -- not yet confirmed for "
                                 f"the real production target, use with caution")

    for w in warnings:
        print(f"WARN   {w}")
    for e in errors:
        print(f"ERROR  {e}")

    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(lint())
